"""Data models and price helpers for NL Day Ahead Prices."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class PriceEntry:
    """One hourly market price entry in EUR/kWh."""

    time: datetime
    price: float

    def as_attribute(self) -> dict[str, Any]:
        """Return an ApexCharts-friendly attribute payload."""
        return {"time": self.time.isoformat(), "price": round(self.price, 6)}


@dataclass
class ProviderResult:
    """Normalized provider payload."""

    provider: str
    prices_today: list[PriceEntry]
    prices_tomorrow: list[PriceEntry]
    raw_today: Any = None
    raw_tomorrow: Any = None

    @property
    def prices(self) -> list[PriceEntry]:
        """Return today and tomorrow prices."""
        return sorted([*self.prices_today, *self.prices_tomorrow], key=lambda item: item.time)


@dataclass
class PriceData:
    """Coordinator data exposed to entities."""

    result: ProviderResult
    fallback_used: bool
    last_successful_update: datetime | None
    from_cache: bool = False
    errors: dict[str, str] = field(default_factory=dict)


def convert_to_eur_kwh(value: float, unit: str) -> float:
    """Convert an energy price to EUR/kWh."""
    normalized_unit = unit.lower().replace(" ", "")
    if normalized_unit in {"eur/kwh", "€/kwh"}:
        return float(value)
    if normalized_unit in {"eur/mwh", "€/mwh"}:
        return float(value) / 1000
    raise ValueError(f"Unsupported price unit: {unit}")


def calculate_all_in_price(
    market_price: float,
    energy_tax_incl_vat: float,
    supplier_markup_excl_vat: float,
    vat: float,
) -> float:
    """Calculate the all-in price in EUR/kWh."""
    return market_price + energy_tax_incl_vat + supplier_markup_excl_vat * (1 + vat)


def current_price(prices: list[PriceEntry], now: datetime) -> float | None:
    """Return the price for the hour containing now."""
    for entry in sorted(prices, key=lambda item: item.time):
        start = _align_timezone(entry.time, now)
        end = start + timedelta(hours=1)
        if start <= now < end:
            return entry.price
    return None


def next_hour_price(prices: list[PriceEntry], now: datetime) -> float | None:
    """Return the price for the next full hour."""
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    for entry in prices:
        if _align_timezone(entry.time, next_hour) == next_hour:
            return entry.price
    return None


def average_price(prices: list[PriceEntry]) -> float | None:
    """Return the average price."""
    if not prices:
        return None
    return sum(entry.price for entry in prices) / len(prices)


def lowest_price(prices: list[PriceEntry]) -> PriceEntry | None:
    """Return the lowest price entry."""
    return min(prices, key=lambda entry: entry.price, default=None)


def highest_price(prices: list[PriceEntry]) -> PriceEntry | None:
    """Return the highest price entry."""
    return max(prices, key=lambda entry: entry.price, default=None)


def _align_timezone(value: datetime, reference: datetime) -> datetime:
    """Attach the reference timezone when a provider returns a naive timestamp."""
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    return value
