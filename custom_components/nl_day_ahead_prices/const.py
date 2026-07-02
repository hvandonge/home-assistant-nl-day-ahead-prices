"""Constants for NL Day Ahead Prices."""

from datetime import timedelta

DOMAIN = "nl_day_ahead_prices"
NAME = "NL Day Ahead Prices"

CONF_COUNTRY = "country"
CONF_CURRENCY = "currency"
CONF_PRIMARY_PROVIDER = "primary_provider"
CONF_ENABLE_ENTSOE = "enable_entsoe"
CONF_ENTSOE_API_TOKEN = "entsoe_api_token"
CONF_ENERGY_TAX_INCL_VAT = "energy_tax_incl_vat"
CONF_SUPPLIER_MARKUP_EXCL_VAT = "supplier_markup_excl_vat"
CONF_VAT = "vat"

DEFAULT_COUNTRY = "NL"
DEFAULT_CURRENCY = "EUR"
DEFAULT_PRIMARY_PROVIDER = "nord_pool"
DEFAULT_ENERGY_TAX_INCL_VAT = 0.1108
DEFAULT_SUPPLIER_MARKUP_EXCL_VAT = 0.01653
DEFAULT_VAT = 0.21

PROVIDER_NORD_POOL = "nord_pool"
PROVIDER_ENERGY_CHARTS = "energy_charts"
PROVIDER_ENTSOE = "entsoe"
PROVIDER_CACHE = "last_known_valid_cache"

PROVIDER_NAMES = {
    PROVIDER_NORD_POOL: "Nord Pool",
    PROVIDER_ENERGY_CHARTS: "Energy-Charts",
    PROVIDER_ENTSOE: "ENTSO-E",
    PROVIDER_CACHE: "Last known valid prices cache",
}

UPDATE_INTERVAL = timedelta(hours=1)
REQUEST_TIMEOUT = 20
REQUEST_RETRIES = 2
CACHE_VERSION = 1
