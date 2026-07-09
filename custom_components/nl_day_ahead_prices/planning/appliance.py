"""Generic appliance planner."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import PriceEntry
from ..optimizer import available_between, optimize_intervals


def plan_appliance(
    prices: list[PriceEntry],
    *,
    appliance_name: str,
    duration_minutes: int,
    earliest_start: datetime,
    deadline: datetime,
    energy_kwh: float | None = None,
    require_consecutive: bool = True,
    avoid_peak_periods: bool = True,
) -> dict[str, Any]:
    """Plan a flexible household appliance."""
    available = available_between(prices, earliest_start, deadline)
    if avoid_peak_periods and len(available) > 2:
        values = sorted(item.price for item in available)
        peak_limit = values[int((len(values) - 1) * 0.8)]
        filtered = [item for item in available if item.price < peak_limit]
        if filtered:
            available = filtered
    plan = optimize_intervals(available, duration_minutes, require_consecutive=require_consecutive)
    if plan is None:
        raise ValueError("No appliance window fits the requested range")
    cost = energy_kwh * plan["average_price"] if energy_kwh is not None else None
    return {
        "recommended_start": plan["recommended_start"],
        "recommended_end": plan["recommended_end"],
        "average_price": plan["average_price"],
        "estimated_cost": round(cost, 4) if cost is not None else None,
        "reason": f"Lowest suitable price window for {appliance_name}.",
        "automation_example": _automation(appliance_name, plan["recommended_start"]),
    }


def _automation(name: str, start: datetime) -> str:
    slug = name.lower().replace(" ", "_")
    return f"""alias: Start {name} at recommended time
triggers:
  - trigger: time
    at: "{start.isoformat()}"
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.{slug}
"""
