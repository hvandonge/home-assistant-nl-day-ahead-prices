"""Boiler and heat-pump boiler planning."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models import PriceEntry
from ..optimizer import add_minutes, available_between, interval_minutes, optimize_intervals


def plan_heating(
    prices: list[PriceEntry],
    *,
    duration_minutes: int,
    earliest_start: datetime,
    deadline: datetime,
    prefer_before_peak: bool = True,
    minimum_gap_minutes: int = 0,
) -> dict[str, Any]:
    """Find the cheapest consecutive heating period."""
    available = available_between(prices, earliest_start, deadline)
    if prefer_before_peak and available:
        peak = max(available, key=lambda item: item.price)
        minutes = interval_minutes(available)
        cutoff = add_minutes(peak.time, -max(0, minimum_gap_minutes))
        before_peak = [
            item
            for item in available
            if add_minutes(item.time, minutes).astimezone(timezone.utc) <= cutoff.astimezone(timezone.utc)
        ]
        if before_peak:
            available = before_peak
    plan = optimize_intervals(available, duration_minutes)
    if plan is None:
        raise ValueError("No heating window fits the requested range")
    return {
        "recommended_start": plan["recommended_start"],
        "recommended_end": plan["recommended_end"],
        "average_price": plan["average_price"],
        "estimated_cost_per_kwh": plan["average_price"],
        "reason": "Cheapest consecutive window before the next peak." if prefer_before_peak else "Cheapest consecutive window.",
        "minimum_gap_minutes": minimum_gap_minutes,
    }
