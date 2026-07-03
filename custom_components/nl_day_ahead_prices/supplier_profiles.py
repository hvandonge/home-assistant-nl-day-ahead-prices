"""Supplier profile loading for NL Day Ahead Prices."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .price_resolution import (
    PRICE_RESOLUTION_HOURLY,
    normalize_profile_price_resolution,
)

_LOGGER = logging.getLogger(__name__)

PROFILE_FILE = Path(__file__).with_name("supplier_profiles.json")
PURCHASE_FEE_UNIT_EUR_PER_KWH = "EUR_PER_KWH"


@dataclass(frozen=True)
class SupplierProfile:
    """Normalized supplier profile."""

    key: str
    name: str
    monthly_fee_electricity: float
    purchase_fee_electricity: float
    purchase_fee_unit: str
    purchase_fee_includes_vat: bool
    sell_fee_electricity: float
    sell_fee_includes_vat: bool
    last_verified: str | None
    source_url: str | None
    price_resolution: str = PRICE_RESOLUTION_HOURLY
    price_resolution_changes: list[dict[str, str]] | None = None
    default_price_resolution_before_change: str | None = None


_PROFILE_CACHE: dict[str, SupplierProfile] | None = None


def load_supplier_profiles() -> dict[str, SupplierProfile]:
    """Load valid supplier profiles from JSON."""
    global _PROFILE_CACHE
    if _PROFILE_CACHE is not None:
        return _PROFILE_CACHE

    try:
        raw_profiles = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        _LOGGER.warning("Could not load supplier profiles: %s", err)
        _PROFILE_CACHE = {}
        return _PROFILE_CACHE

    profiles: dict[str, SupplierProfile] = {}
    if not isinstance(raw_profiles, dict):
        _LOGGER.warning("Supplier profiles JSON root must be an object")
        _PROFILE_CACHE = profiles
        return profiles

    for key, raw_profile in raw_profiles.items():
        try:
            profiles[str(key)] = normalize_supplier_profile(raw_profile, str(key))
        except (TypeError, ValueError) as err:
            _LOGGER.warning("Skipping invalid supplier profile %s: %s", key, err)

    _PROFILE_CACHE = profiles
    return profiles


def normalize_supplier_profile(profile: dict[str, Any], key: str = "custom") -> SupplierProfile:
    """Validate and normalize a supplier profile dict."""
    if not isinstance(profile, dict):
        raise TypeError("profile must be an object")

    name = str(profile["name"])
    monthly_fee = float(profile["monthly_fee_electricity"])
    purchase_fee = float(profile["purchase_fee_electricity"])
    purchase_fee_unit = str(profile.get("purchase_fee_unit", PURCHASE_FEE_UNIT_EUR_PER_KWH))
    purchase_fee_includes_vat = bool(profile.get("purchase_fee_includes_vat", True))
    sell_fee = float(profile.get("sell_fee_electricity", 0.0))
    sell_fee_includes_vat = bool(profile.get("sell_fee_includes_vat", True))
    price_resolution = normalize_profile_price_resolution(profile.get("price_resolution", PRICE_RESOLUTION_HOURLY))
    price_resolution_changes = _normalize_price_resolution_changes(profile.get("price_resolution_changes", []))
    default_before_change = profile.get("default_price_resolution_before_change")
    if default_before_change is not None:
        default_before_change = normalize_profile_price_resolution(default_before_change)
    last_verified = profile.get("last_verified")
    source_url = profile.get("source_url")

    if monthly_fee < 0:
        raise ValueError("monthly_fee_electricity must be >= 0")
    if purchase_fee < 0:
        raise ValueError("purchase_fee_electricity must be >= 0")
    if purchase_fee_unit != PURCHASE_FEE_UNIT_EUR_PER_KWH:
        raise ValueError(f"unsupported purchase_fee_unit: {purchase_fee_unit}")
    if last_verified is not None and not isinstance(last_verified, str):
        raise ValueError("last_verified must be a string or null")
    if source_url is not None and not isinstance(source_url, str):
        raise ValueError("source_url must be a string or null")

    return SupplierProfile(
        key=key,
        name=name,
        monthly_fee_electricity=monthly_fee,
        purchase_fee_electricity=purchase_fee,
        purchase_fee_unit=purchase_fee_unit,
        purchase_fee_includes_vat=purchase_fee_includes_vat,
        sell_fee_electricity=sell_fee,
        sell_fee_includes_vat=sell_fee_includes_vat,
        price_resolution=price_resolution,
        price_resolution_changes=price_resolution_changes,
        default_price_resolution_before_change=default_before_change,
        last_verified=last_verified,
        source_url=source_url,
    )


def supplier_profile_to_dict(profile: SupplierProfile) -> dict[str, Any]:
    """Return a serializable supplier profile."""
    return {
        "key": profile.key,
        "name": profile.name,
        "monthly_fee_electricity": profile.monthly_fee_electricity,
        "purchase_fee_electricity": profile.purchase_fee_electricity,
        "purchase_fee_unit": profile.purchase_fee_unit,
        "purchase_fee_includes_vat": profile.purchase_fee_includes_vat,
        "sell_fee_electricity": profile.sell_fee_electricity,
        "sell_fee_includes_vat": profile.sell_fee_includes_vat,
        "price_resolution": profile.price_resolution,
        "price_resolution_changes": profile.price_resolution_changes or [],
        "default_price_resolution_before_change": profile.default_price_resolution_before_change,
        "last_verified": profile.last_verified,
        "source_url": profile.source_url,
    }


def _normalize_price_resolution_changes(value: Any) -> list[dict[str, str]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("price_resolution_changes must be a list")
    changes: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("price_resolution_changes entries must be objects")
        from_date = str(item["from"])
        resolution = normalize_profile_price_resolution(item["resolution"])
        changes.append({"from": from_date, "resolution": resolution})
    return changes
