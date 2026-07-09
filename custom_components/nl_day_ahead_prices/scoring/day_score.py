"""Whole-day price assessment."""

from __future__ import annotations

from typing import Any

from ..analysis.periods import find_price_periods
from ..analysis.volatility import volatility
from ..models import PriceEntry


def calculate_day_score(
    prices: list[PriceEntry],
    reference: list[PriceEntry] | None = None,
    language: str = "en",
) -> dict[str, Any]:
    """Describe one price day relative to all available prices."""
    if not prices:
        return {
            "state": None,
            "average_price": None,
            "min_price": None,
            "max_price": None,
            "volatility": None,
            "cheapest_block_1h": None,
            "cheapest_block_2h": None,
            "cheapest_block_4h": None,
            "expensive_block_1h": None,
            "negative_price_minutes": 0,
            "cheap_minutes": 0,
            "expensive_minutes": 0,
            "summary": "Geen prijzen beschikbaar" if language.startswith("nl") else "No prices available",
        }
    values = [item.price for item in prices]
    ref_values = sorted(item.price for item in (reference or prices))
    average = sum(values) / len(values)
    ref_average = sum(ref_values) / len(ref_values)
    stats = volatility(prices)
    interval_minutes = _interval_minutes(prices)
    cheap_limit = _percentile(ref_values, 0.25)
    expensive_limit = _percentile(ref_values, 0.75)
    negative_minutes = sum(interval_minutes for value in values if value < 0)
    cheap_minutes = sum(interval_minutes for value in values if value <= cheap_limit)
    expensive_minutes = sum(interval_minutes for value in values if value >= expensive_limit)
    relative = average / max(abs(ref_average), 0.000001)
    if negative_minutes:
        state = "excellent"
    elif stats["level"] == "very_high":
        state = "volatile"
    elif relative <= 0.75:
        state = "excellent"
    elif relative <= 0.95:
        state = "good"
    elif relative >= 1.2:
        state = "expensive"
    else:
        state = "normal"
    return {
        "state": state,
        "average_price": round(average, 6),
        "min_price": round(min(values), 6),
        "max_price": round(max(values), 6),
        "volatility": stats["level"],
        "cheapest_block_1h": _first_period(prices, 60),
        "cheapest_block_2h": _first_period(prices, 120),
        "cheapest_block_4h": _first_period(prices, 240),
        "expensive_block_1h": _first_period(prices, 60, peak=True),
        "negative_price_minutes": negative_minutes,
        "cheap_minutes": cheap_minutes,
        "expensive_minutes": expensive_minutes,
        "summary": _summary(state, average, language),
    }


def _first_period(prices: list[PriceEntry], minutes: int, *, peak: bool = False) -> dict | None:
    periods = find_price_periods(prices, minutes, peak=peak)
    return periods[0].as_dict() if periods else None


def _interval_minutes(prices: list[PriceEntry]) -> int:
    deltas = [
        int((later.time - earlier.time).total_seconds() / 60)
        for earlier, later in zip(prices, prices[1:])  # noqa: B905 - Python 3.9 compatibility.
        if later.time > earlier.time
    ]
    return min(deltas, default=60)


def _percentile(values: list[float], fraction: float) -> float:
    return values[min(len(values) - 1, int((len(values) - 1) * fraction))]


def _summary(state: str, average: float, language: str) -> str:
    if language.startswith("nl"):
        labels = {
            "excellent": "Uitzonderlijk voordelige energiedag",
            "good": "Gunstige energiedag",
            "normal": "Normale energiedag",
            "expensive": "Relatief dure energiedag",
            "volatile": "Sterk wisselende energieprijzen",
        }
        return f"{labels[state]}; gemiddeld {average:.4f} EUR/kWh."
    labels = {
        "excellent": "Exceptionally affordable energy day",
        "good": "Favorable energy day",
        "normal": "Typical energy price day",
        "expensive": "Relatively expensive energy day",
        "volatile": "Highly volatile energy price day",
    }
    return f"{labels[state]}; average {average:.4f} EUR/kWh."
