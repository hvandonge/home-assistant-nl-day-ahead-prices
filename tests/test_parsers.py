from datetime import date, datetime, timezone

from custom_components.nl_day_ahead_prices.providers import parse_energy_charts, parse_nord_pool


def test_parse_nord_pool_converts_to_eur_kwh() -> None:
    payload = {
        "multiAreaEntries": [
            {
                "deliveryStart": "2026-07-02T00:00:00+02:00",
                "entryPerArea": {"NL": 101.5},
            }
        ]
    }

    prices = parse_nord_pool(payload, "NL")

    assert prices[0].price == 0.1015


def test_parse_energy_charts_filters_day_and_converts_to_eur_kwh() -> None:
    july_2 = int(datetime(2026, 7, 2, tzinfo=timezone.utc).timestamp())
    july_3 = int(datetime(2026, 7, 3, tzinfo=timezone.utc).timestamp())
    payload = {
        "unix_seconds": [july_2, july_3],
        "price": [50, 75],
    }

    prices = parse_energy_charts(payload, date(2026, 7, 2))

    assert len(prices) == 1
    assert prices[0].price == 0.05
