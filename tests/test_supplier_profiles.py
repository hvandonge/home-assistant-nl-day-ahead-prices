import json
from datetime import datetime

import pytest

from custom_components.nl_day_ahead_prices.calculations import (
    build_all_in_price_attributes,
    calculate_all_in_price,
    calculate_monthly_fee,
    calculate_supplier_fee,
)
from custom_components.nl_day_ahead_prices.models import PriceEntry
from custom_components.nl_day_ahead_prices.supplier_profiles import (
    SupplierProfile,
    load_supplier_profiles,
    normalize_supplier_profile,
)


def test_all_in_price_with_supplier_fee_including_vat() -> None:
    profile = SupplierProfile(
        key="test",
        name="Test",
        monthly_fee_electricity=5.0,
        purchase_fee_electricity=0.02,
        purchase_fee_unit="EUR_PER_KWH",
        purchase_fee_includes_vat=True,
        sell_fee_electricity=0.02,
        sell_fee_includes_vat=True,
        last_verified="2026-07-02",
        source_url="https://example.com",
    )

    assert calculate_supplier_fee(profile, 0.21) == 0.02
    assert calculate_all_in_price(0.1, 0.1108, profile, 0.21) == pytest.approx(0.2518)


def test_all_in_price_with_supplier_fee_excluding_vat() -> None:
    profile = SupplierProfile(
        key="test",
        name="Test",
        monthly_fee_electricity=5.0,
        purchase_fee_electricity=0.02,
        purchase_fee_unit="EUR_PER_KWH",
        purchase_fee_includes_vat=False,
        sell_fee_electricity=0.02,
        sell_fee_includes_vat=False,
        last_verified=None,
        source_url=None,
    )

    assert calculate_supplier_fee(profile, 0.21) == 0.0242
    assert calculate_all_in_price(0.1, 0.1108, profile, 0.21) == 0.256


def test_custom_supplier_profile() -> None:
    profile = normalize_supplier_profile(
        {
            "name": "Mijn leverancier",
            "monthly_fee_electricity": 7.5,
            "purchase_fee_electricity": 0.018,
            "purchase_fee_unit": "EUR_PER_KWH",
            "purchase_fee_includes_vat": True,
            "sell_fee_electricity": -0.001,
            "sell_fee_includes_vat": True,
            "last_verified": None,
            "source_url": None,
        },
        "custom",
    )

    assert profile.name == "Mijn leverancier"
    assert calculate_monthly_fee(profile) == 7.5
    assert calculate_all_in_price(0.1, 0.1108, profile, 0.21) == pytest.approx(0.2498)


def test_missing_supplier_profile_uses_zero_fee() -> None:
    assert calculate_supplier_fee(None, 0.21) == 0.0
    assert calculate_monthly_fee(None) == 0.0
    assert calculate_all_in_price(0.1, 0.1108, None, 0.21) == 0.2318


def test_supplier_profile_json_validation_skips_invalid_profile(tmp_path, monkeypatch) -> None:
    profile_file = tmp_path / "supplier_profiles.json"
    profile_file.write_text(
        json.dumps(
            {
                "valid": {
                    "name": "Valid",
                    "monthly_fee_electricity": 5,
                    "purchase_fee_electricity": 0.02,
                    "purchase_fee_unit": "EUR_PER_KWH",
                    "purchase_fee_includes_vat": True,
                    "sell_fee_electricity": 0.02,
                    "sell_fee_includes_vat": True,
                    "last_verified": "2026-07-02",
                    "source_url": "https://example.com",
                },
                "invalid": {
                    "name": "Invalid",
                    "monthly_fee_electricity": -1,
                    "purchase_fee_electricity": 0.02,
                    "purchase_fee_unit": "EUR_PER_KWH",
                    "purchase_fee_includes_vat": True,
                    "sell_fee_electricity": 0.02,
                    "sell_fee_includes_vat": True,
                    "last_verified": "2026-07-02",
                    "source_url": "https://example.com",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("custom_components.nl_day_ahead_prices.supplier_profiles.PROFILE_FILE", profile_file)
    monkeypatch.setattr("custom_components.nl_day_ahead_prices.supplier_profiles._PROFILE_CACHE", None)

    profiles = load_supplier_profiles()

    assert list(profiles) == ["valid"]


def test_all_in_price_attributes_for_today() -> None:
    profile = SupplierProfile(
        key="test",
        name="Test",
        monthly_fee_electricity=5.0,
        purchase_fee_electricity=0.02,
        purchase_fee_unit="EUR_PER_KWH",
        purchase_fee_includes_vat=True,
        sell_fee_electricity=0.02,
        sell_fee_includes_vat=True,
        last_verified="2026-07-02",
        source_url="https://example.com",
    )
    prices = [PriceEntry(datetime(2026, 7, 2, 14), 0.1)]

    assert build_all_in_price_attributes(prices, 0.1108, profile, 0.21) == [
        {"time": "2026-07-02T14:00:00", "price": 0.2518}
    ]
