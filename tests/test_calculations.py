from custom_components.nl_day_ahead_prices.models import calculate_all_in_price, convert_to_eur_kwh


def test_convert_eur_mwh_to_eur_kwh() -> None:
    assert convert_to_eur_kwh(123.45, "EUR/MWh") == 0.12345


def test_convert_eur_kwh_is_unchanged() -> None:
    assert convert_to_eur_kwh(0.234, "EUR/kWh") == 0.234


def test_all_in_formula() -> None:
    assert calculate_all_in_price(0.1, 0.1108, 0.01653, 0.21) == 0.2308013

