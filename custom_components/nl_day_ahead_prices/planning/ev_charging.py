"""EV charging planner."""

from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from typing import Any

from ..models import PriceEntry
from ..optimizer import (
    add_minutes,
    available_between,
    interval_minutes,
    optimize_intervals,
    window_payload,
)


def plan_ev_charging(
    prices: list[PriceEntry],
    *,
    target_energy_kwh: float,
    max_power_kw: float,
    earliest_start: datetime,
    deadline: datetime,
    require_consecutive: bool = True,
    minimum_session_minutes: int = 60,
    allow_split_sessions: bool = False,
    round_to_resolution: bool = True,
) -> dict[str, Any]:
    """Find a low-cost EV charging plan."""
    if target_energy_kwh <= 0 or max_power_kw <= 0:
        raise ValueError("target_energy_kwh and max_power_kw must be positive")
    available = available_between(prices, earliest_start, deadline)
    required = target_energy_kwh / max_power_kw * 60
    if round_to_resolution and available:
        interval = interval_minutes(available)
        required = ((int(required) + interval - 1) // interval) * interval
    required = max(required, minimum_session_minutes)
    plan = (
        _split_plan(available, int(required), minimum_session_minutes)
        if allow_split_sessions
        else optimize_intervals(available, int(required), require_consecutive=require_consecutive)
    )
    if plan is None:
        raise ValueError("No charging window fits the requested range")
    actual_energy = min(target_energy_kwh, max_power_kw * plan["duration_minutes"] / 60)
    plan.update(
        {
            "expected_energy_kwh": round(actual_energy, 3),
            "estimated_cost": round(actual_energy * plan["average_price"], 4),
        }
    )
    return plan


def _split_plan(
    prices: list[PriceEntry],
    required_minutes: int,
    minimum_session_minutes: int,
) -> dict[str, Any] | None:
    """Choose low-cost non-overlapping sessions with a minimum session length."""
    if not prices:
        return None
    minutes = interval_minutes(prices)
    session_count = max(1, ceil(minimum_session_minutes / minutes))
    required_count = ceil(required_minutes / minutes)
    candidates = []
    for index in range(len(prices) - session_count + 1):
        entries = prices[index : index + session_count]
        if all(
            later.time.astimezone(timezone.utc) == add_minutes(earlier.time, minutes).astimezone(timezone.utc)
            for earlier, later in zip(entries, entries[1:])  # noqa: B905 - Python 3.9 compatibility.
        ):
            candidates.append(entries)
    candidates.sort(key=lambda entries: sum(item.price for item in entries) / len(entries))
    selected: list[PriceEntry] = []
    selected_times = set()
    for candidate in candidates:
        if any(item.time in selected_times for item in candidate):
            continue
        selected.extend(candidate)
        selected_times.update(item.time for item in candidate)
        if len(selected) >= required_count:
            break
    if len(selected) < required_count:
        return None
    selected.sort(key=lambda item: item.time.astimezone(timezone.utc))
    return {**window_payload(selected, minutes), "alternatives": []}
