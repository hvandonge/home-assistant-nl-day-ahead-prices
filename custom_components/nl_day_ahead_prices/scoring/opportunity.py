"""Energy opportunity detection."""

from __future__ import annotations

from typing import Any

from ..analysis.periods import find_price_periods
from ..models import PriceEntry


def calculate_opportunity(prices: list[PriceEntry], language: str = "en") -> dict[str, Any]:
    """Find notable savings opportunities in available prices."""
    if not prices:
        return {
            "state": "none",
            "opportunity_type": "none",
            "expected_savings": 0.0,
            "best_window_start": None,
            "best_window_end": None,
            "explanation": "Geen prijzen beschikbaar." if language.startswith("nl") else "No prices available.",
            "suggested_actions": [],
        }
    values = [item.price for item in prices]
    spread = max(values) - min(values)
    average = sum(values) / len(values)
    negative = min(values) < 0
    relative_spread = spread / max(abs(average), 0.000001)
    if negative:
        state, kind = "exceptional", "negative_prices"
    elif relative_spread >= 1.0:
        state, kind = "high", "price_arbitrage"
    elif relative_spread >= 0.5:
        state, kind = "medium", "shift_consumption"
    elif relative_spread >= 0.25:
        state, kind = "small", "minor_savings"
    else:
        state, kind = "none", "none"
    best = find_price_periods(prices, 60)
    period = best[0] if best else None
    return {
        "state": state,
        "opportunity_type": kind,
        "expected_savings": round(max(0.0, spread), 6),
        "best_window_start": period.start if period else None,
        "best_window_end": period.end if period else None,
        "explanation": (
            f"Het beschikbare prijsverschil is {spread:.4f} EUR/kWh."
            if language.startswith("nl")
            else f"Available price spread is {spread:.4f} EUR/kWh."
        ),
        "suggested_actions": _actions(state, language),
    }


def _actions(state: str, language: str) -> list[str]:
    is_dutch = language.startswith("nl")
    if state in {"high", "exceptional"}:
        return (
            ["EV laden", "Boiler verwarmen", "Thuisbatterij laden", "Apparaten gebruiken"]
            if is_dutch
            else ["Charge EV", "Heat boiler", "Charge home battery", "Run appliances"]
        )
    if state == "medium":
        return ["Verschuif flexibel verbruik"] if is_dutch else ["Shift flexible consumption"]
    if state == "small":
        return ["Overweeg optioneel verbruik uit te stellen"] if is_dutch else ["Consider delaying optional loads"]
    return []
