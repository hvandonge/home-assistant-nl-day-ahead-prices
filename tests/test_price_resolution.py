from datetime import datetime, timezone

import pytest

from custom_components.nl_day_ahead_prices.models import PriceEntry, ProviderResult, average_price
from custom_components.nl_day_ahead_prices.price_resolution import (
    aggregate_quarter_hour_to_hourly,
    convert_prices_to_resolution,
    expand_hourly_to_quarter_hour,
    find_cheapest_consecutive_block,
    get_supplier_price_resolution,
)
from custom_components.nl_day_ahead_prices.supplier_profiles import SupplierProfile


def test_expand_hourly_to_quarter_hour() -> None:
    prices = [PriceEntry(datetime(2026, 7, 3, 13, tzinfo=timezone.utc), 0.12)]

    expanded = expand_hourly_to_quarter_hour(prices)

    assert [entry.time.minute for entry in expanded] == [0, 15, 30, 45]
    assert [entry.price for entry in expanded] == [0.12, 0.12, 0.12, 0.12]


def test_aggregate_quarter_hour_to_hourly() -> None:
    prices = [
        PriceEntry(datetime(2026, 7, 3, 13, 0, tzinfo=timezone.utc), 0.10),
        PriceEntry(datetime(2026, 7, 3, 13, 15, tzinfo=timezone.utc), 0.20),
        PriceEntry(datetime(2026, 7, 3, 13, 30, tzinfo=timezone.utc), 0.30),
        PriceEntry(datetime(2026, 7, 3, 13, 45, tzinfo=timezone.utc), 0.40),
    ]

    aggregated = aggregate_quarter_hour_to_hourly(prices)

    assert aggregated == [PriceEntry(datetime(2026, 7, 3, 13, tzinfo=timezone.utc), 0.25)]


def test_zonneplan_resolution_before_august_2026() -> None:
    profile = _zonneplan_profile()

    assert get_supplier_price_resolution(profile, datetime(2026, 7, 31, 23, tzinfo=timezone.utc)) == "hourly"


def test_zonneplan_resolution_from_august_2026() -> None:
    profile = _zonneplan_profile()

    assert get_supplier_price_resolution(profile, datetime(2026, 8, 1, tzinfo=timezone.utc)) == "quarter_hour"


def test_average_today_with_96_quarter_hour_prices() -> None:
    prices = [
        PriceEntry(datetime(2026, 7, 3, hour, minute, tzinfo=timezone.utc), 0.10)
        for hour in range(24)
        for minute in (0, 15, 30, 45)
    ]

    assert len(prices) == 96
    assert average_price(prices) == pytest.approx(0.10)


def test_convert_prices_to_resolution_keeps_raw_count_separate() -> None:
    raw_prices = [PriceEntry(datetime(2026, 7, 3, 13, tzinfo=timezone.utc), 0.12)]

    converted = convert_prices_to_resolution(raw_prices, "quarter_hour", "hourly")

    assert len(raw_prices) == 1
    assert len(converted) == 4


def test_provider_result_preserves_raw_price_resolution_attributes() -> None:
    raw_prices = [PriceEntry(datetime(2026, 7, 3, 13, tzinfo=timezone.utc), 0.12)]
    converted = convert_prices_to_resolution(raw_prices, "quarter_hour", "hourly")

    result = ProviderResult(
        provider="test",
        prices_today=converted,
        prices_tomorrow=[],
        raw_prices_today=raw_prices,
        raw_prices_tomorrow=[],
        raw_price_resolution="hourly",
        requested_price_resolution="quarter_hour",
        effective_price_resolution="quarter_hour",
        resolution_converted=True,
    )

    assert result.raw_price_resolution == "hourly"
    assert result.source_prices_today == raw_prices
    assert len(result.prices_today) == 4
    assert result.resolution_converted is True


def test_find_cheapest_consecutive_block_quarter_hour() -> None:
    prices = [
        PriceEntry(datetime(2026, 7, 3, 13, 0, tzinfo=timezone.utc), 0.30),
        PriceEntry(datetime(2026, 7, 3, 13, 15, tzinfo=timezone.utc), 0.10),
        PriceEntry(datetime(2026, 7, 3, 13, 30, tzinfo=timezone.utc), 0.20),
        PriceEntry(datetime(2026, 7, 3, 13, 45, tzinfo=timezone.utc), 0.50),
    ]

    block = find_cheapest_consecutive_block(prices, 30)

    assert block is not None
    assert block["start"] == "2026-07-03T13:15:00+00:00"
    assert block["end"] == "2026-07-03T13:45:00+00:00"
    assert block["average_price"] == 0.15


def _zonneplan_profile() -> SupplierProfile:
    return SupplierProfile(
        key="zonneplan",
        name="Zonneplan",
        monthly_fee_electricity=6.25,
        purchase_fee_electricity=0.02,
        purchase_fee_unit="EUR_PER_KWH",
        purchase_fee_includes_vat=True,
        sell_fee_electricity=0.02,
        sell_fee_includes_vat=True,
        last_verified="2026-07-03",
        source_url="https://www.zonneplan.nl/blog/kwartierprijzen-bij-zonneplan",
        price_resolution="date_based",
        price_resolution_changes=[{"from": "2026-08-01", "resolution": "quarter_hour"}],
        default_price_resolution_before_change="hourly",
    )
