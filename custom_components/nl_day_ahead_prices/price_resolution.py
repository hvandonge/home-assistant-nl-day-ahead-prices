"""Price resolution helpers for NL Day Ahead Prices."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from .models import PriceEntry

if TYPE_CHECKING:
    from .supplier_profiles import SupplierProfile

PRICE_RESOLUTION_AUTO = "auto"
PRICE_RESOLUTION_HOURLY = "hourly"
PRICE_RESOLUTION_QUARTER_HOUR = "quarter_hour"
PRICE_RESOLUTION_DATE_BASED = "date_based"

VALID_PRICE_RESOLUTIONS = {
    PRICE_RESOLUTION_AUTO,
    PRICE_RESOLUTION_HOURLY,
    PRICE_RESOLUTION_QUARTER_HOUR,
}

VALID_PROFILE_PRICE_RESOLUTIONS = {
    PRICE_RESOLUTION_HOURLY,
    PRICE_RESOLUTION_QUARTER_HOUR,
    PRICE_RESOLUTION_DATE_BASED,
}


def normalize_price_resolution(value: str | None) -> str:
    """Normalize a configured price resolution value."""
    normalized = str(value or PRICE_RESOLUTION_AUTO).lower().replace("-", "_").replace(" ", "_")
    if normalized in {"quarter", "quarterhour", "quarter_hourly", "15_min", "15_minutes"}:
        normalized = PRICE_RESOLUTION_QUARTER_HOUR
    if normalized in {"hour", "hourly_prices"}:
        normalized = PRICE_RESOLUTION_HOURLY
    if normalized not in VALID_PRICE_RESOLUTIONS:
        raise ValueError(f"Unsupported price resolution: {value}")
    return normalized


def normalize_profile_price_resolution(value: str | None) -> str:
    """Normalize a supplier profile price resolution value."""
    normalized = str(value or PRICE_RESOLUTION_HOURLY).lower().replace("-", "_").replace(" ", "_")
    if normalized in {"quarter", "quarterhour", "quarter_hourly", "15_min", "15_minutes"}:
        normalized = PRICE_RESOLUTION_QUARTER_HOUR
    if normalized in {"hour", "hourly_prices"}:
        normalized = PRICE_RESOLUTION_HOURLY
    if normalized not in VALID_PROFILE_PRICE_RESOLUTIONS:
        raise ValueError(f"Unsupported supplier profile price resolution: {value}")
    return normalized


def get_supplier_price_resolution(profile: SupplierProfile, now: datetime) -> str:
    """Return the active price resolution for a supplier profile."""
    resolution = profile.price_resolution
    if resolution != PRICE_RESOLUTION_DATE_BASED:
        return resolution

    active_resolution = profile.default_price_resolution_before_change or PRICE_RESOLUTION_HOURLY
    today = now.date()
    for change in sorted(profile.price_resolution_changes or [], key=lambda item: item["from"]):
        change_date = _parse_date(change["from"])
        if today >= change_date:
            active_resolution = normalize_profile_price_resolution(change["resolution"])
    return active_resolution


def infer_price_resolution(prices: list[PriceEntry]) -> str:
    """Infer price resolution from timestamp deltas."""
    deltas = _positive_deltas(prices)
    if not deltas:
        return PRICE_RESOLUTION_HOURLY
    minimum_minutes = min(delta.total_seconds() / 60 for delta in deltas)
    return PRICE_RESOLUTION_QUARTER_HOUR if minimum_minutes <= 15 else PRICE_RESOLUTION_HOURLY


def interval_minutes_for_resolution(resolution: str) -> int:
    """Return interval length in minutes."""
    normalized = normalize_profile_price_resolution(resolution)
    return 15 if normalized == PRICE_RESOLUTION_QUARTER_HOUR else 60


def expand_hourly_to_quarter_hour(prices: list[PriceEntry]) -> list[PriceEntry]:
    """Expand hourly prices into four quarter-hour entries."""
    expanded: list[PriceEntry] = []
    for entry in sorted(prices, key=lambda item: item.time):
        expanded.extend(
            PriceEntry(entry.time + timedelta(minutes=offset), entry.price)
            for offset in (0, 15, 30, 45)
        )
    return expanded


def aggregate_quarter_hour_to_hourly(
    prices: list[PriceEntry],
    method: str = "average",
) -> list[PriceEntry]:
    """Aggregate quarter-hour prices to hourly prices."""
    if method != "average":
        raise ValueError(f"Unsupported aggregation method: {method}")
    grouped: dict[datetime, list[float]] = {}
    for entry in sorted(prices, key=lambda item: item.time):
        hour = entry.time.replace(minute=0, second=0, microsecond=0)
        grouped.setdefault(hour, []).append(entry.price)
    return [
        PriceEntry(hour, sum(values) / len(values))
        for hour, values in sorted(grouped.items(), key=lambda item: item[0])
        if values
    ]


def convert_prices_to_resolution(
    prices: list[PriceEntry],
    target_resolution: str,
    source_resolution: str | None = None,
) -> list[PriceEntry]:
    """Convert prices to the requested resolution."""
    target = normalize_profile_price_resolution(target_resolution)
    source = normalize_profile_price_resolution(source_resolution or infer_price_resolution(prices))
    if source == target:
        return sorted(prices, key=lambda item: item.time)
    if source == PRICE_RESOLUTION_HOURLY and target == PRICE_RESOLUTION_QUARTER_HOUR:
        return expand_hourly_to_quarter_hour(prices)
    if source == PRICE_RESOLUTION_QUARTER_HOUR and target == PRICE_RESOLUTION_HOURLY:
        return aggregate_quarter_hour_to_hourly(prices)
    raise ValueError(f"Cannot convert prices from {source} to {target}")


def find_cheapest_consecutive_block(
    prices: list[PriceEntry],
    duration_minutes: int,
) -> dict[str, Any] | None:
    """Find the cheapest consecutive block for a target duration."""
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be > 0")
    sorted_prices = sorted(prices, key=lambda item: item.time)
    if not sorted_prices:
        return None
    default_interval = timedelta(minutes=interval_minutes_for_resolution(infer_price_resolution(sorted_prices)))
    best_entries: list[PriceEntry] | None = None
    best_average: float | None = None

    for start_index in range(len(sorted_prices)):
        block: list[PriceEntry] = []
        total_duration = timedelta()
        for index in range(start_index, len(sorted_prices)):
            current = sorted_prices[index]
            if block:
                previous = block[-1]
                previous_duration = _entry_duration(sorted_prices, index - 1, default_interval)
                if current.time != previous.time + previous_duration:
                    break
            duration = _entry_duration(sorted_prices, index, default_interval)
            if total_duration + duration > timedelta(minutes=duration_minutes):
                break
            block.append(current)
            total_duration += duration
            if total_duration == timedelta(minutes=duration_minutes):
                average = sum(entry.price for entry in block) / len(block)
                if best_average is None or average < best_average:
                    best_entries = list(block)
                    best_average = average
                break

    if best_entries is None or best_average is None:
        return None

    end = best_entries[-1].time + _entry_duration(
        sorted_prices,
        sorted_prices.index(best_entries[-1]),
        default_interval,
    )
    return {
        "start": best_entries[0].time.isoformat(),
        "end": end.isoformat(),
        "price": round(best_average, 6),
        "average_price": round(best_average, 6),
        "duration_minutes": duration_minutes,
        "prices": [entry.as_attribute() for entry in best_entries],
    }


def _positive_deltas(prices: list[PriceEntry]) -> list[timedelta]:
    sorted_prices = sorted(prices, key=lambda item: item.time)
    return [
        later.time - earlier.time
        for earlier, later in zip(sorted_prices, sorted_prices[1:])  # noqa: B905 - Python 3.9 compatibility.
        if later.time > earlier.time
    ]


def _entry_duration(prices: list[PriceEntry], index: int, default_interval: timedelta) -> timedelta:
    if index + 1 < len(prices):
        duration = prices[index + 1].time - prices[index].time
        if duration > timedelta():
            return duration
    return default_interval


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)
