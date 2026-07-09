"""Solar export planner."""

from __future__ import annotations

from typing import Any

from ..models import PriceEntry
from ..optimizer import add_minutes, optimize_intervals


def plan_export(
    prices: list[PriceEntry],
    *,
    expected_export_kwh: float | None = None,
    duration_minutes: int = 60,
) -> dict[str, Any]:
    """Find the highest-paying export period."""
    inverted = [PriceEntry(item.time, -item.price) for item in prices]
    plan = optimize_intervals(inverted, duration_minutes)
    if plan is None:
        raise ValueError("No export window is available")
    selected_times = {item["time"] for item in plan["selected_intervals"]}
    selected = [item for item in prices if item.time.isoformat() in selected_times]
    average = sum(item.price for item in selected) / len(selected)
    start = selected[0].time
    end = add_minutes(selected[-1].time, plan["duration_minutes"] // len(selected))
    value = average * expected_export_kwh if expected_export_kwh is not None else None
    return {
        "best_export_start": start,
        "best_export_end": end,
        "average_sell_price": round(average, 6),
        "estimated_revenue": round(value, 4) if value is not None else None,
        "recommendation": "Export during this window when generation or stored energy is available.",
    }
