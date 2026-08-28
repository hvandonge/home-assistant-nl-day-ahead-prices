"""Pure cache validation helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def cache_is_valid(cached: dict[str, Any] | None, now: datetime) -> bool:
    """Accept only same-local-day caches that contain today's prices."""
    if not cached or cached.get("local_date") != now.date().isoformat():
        return False
    prices_today = cached.get("prices_today")
    return isinstance(prices_today, list) and bool(prices_today)


def cache_needs_roll(cached: dict[str, Any] | None, now: datetime) -> bool:
    """Detect a cache written yesterday whose 'tomorrow' prices are today's.

    Bridges the midnight gap: `cache_is_valid` rejects any cache not written
    today, even though a cache from just before midnight still holds today's
    prices in its `prices_tomorrow` field. Without this, an outage spanning
    the date boundary blanks every sensor until the next successful fetch,
    even though yesterday's cache already has what "today" needs.
    """
    if not cached:
        return False
    local_date = cached.get("local_date")
    if not local_date:
        return False
    yesterday = (now.date() - timedelta(days=1)).isoformat()
    if local_date != yesterday:
        return False
    prices_tomorrow = cached.get("prices_tomorrow")
    return isinstance(prices_tomorrow, list) and bool(prices_tomorrow)
