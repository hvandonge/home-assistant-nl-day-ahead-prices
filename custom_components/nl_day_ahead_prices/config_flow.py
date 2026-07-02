"""Config and options flow for NL Day Ahead Prices."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_COUNTRY,
    CONF_CURRENCY,
    CONF_ENABLE_ENTSOE,
    CONF_ENERGY_TAX_INCL_VAT,
    CONF_ENTSOE_API_TOKEN,
    CONF_PRIMARY_PROVIDER,
    CONF_SUPPLIER_MARKUP_EXCL_VAT,
    CONF_VAT,
    DEFAULT_COUNTRY,
    DEFAULT_CURRENCY,
    DEFAULT_ENERGY_TAX_INCL_VAT,
    DEFAULT_PRIMARY_PROVIDER,
    DEFAULT_SUPPLIER_MARKUP_EXCL_VAT,
    DEFAULT_VAT,
    DOMAIN,
    NAME,
    PROVIDER_ENERGY_CHARTS,
    PROVIDER_NORD_POOL,
)


class NLDayAheadPricesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Create a config entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=NAME): str,
                vol.Optional(CONF_COUNTRY, default=DEFAULT_COUNTRY): str,
                vol.Optional(CONF_CURRENCY, default=DEFAULT_CURRENCY): str,
                vol.Optional(CONF_PRIMARY_PROVIDER, default=DEFAULT_PRIMARY_PROVIDER): vol.In(
                    [PROVIDER_NORD_POOL, PROVIDER_ENERGY_CHARTS]
                ),
                vol.Optional(CONF_ENABLE_ENTSOE, default=False): bool,
                vol.Optional(CONF_ENTSOE_API_TOKEN, default=""): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> NLDayAheadPricesOptionsFlow:
        """Return options flow handler."""
        return NLDayAheadPricesOptionsFlow()


class NLDayAheadPricesOptionsFlow(config_entries.OptionsFlow):
    """Options flow for taxes, VAT, providers and fallback."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Optional(CONF_COUNTRY, default=data.get(CONF_COUNTRY, DEFAULT_COUNTRY)): str,
                vol.Optional(CONF_CURRENCY, default=data.get(CONF_CURRENCY, DEFAULT_CURRENCY)): str,
                vol.Optional(CONF_PRIMARY_PROVIDER, default=data.get(CONF_PRIMARY_PROVIDER, DEFAULT_PRIMARY_PROVIDER)): vol.In(
                    [PROVIDER_NORD_POOL, PROVIDER_ENERGY_CHARTS]
                ),
                vol.Optional(CONF_ENABLE_ENTSOE, default=data.get(CONF_ENABLE_ENTSOE, False)): bool,
                vol.Optional(CONF_ENTSOE_API_TOKEN, default=data.get(CONF_ENTSOE_API_TOKEN, "")): str,
                vol.Optional(
                    CONF_ENERGY_TAX_INCL_VAT,
                    default=data.get(CONF_ENERGY_TAX_INCL_VAT, DEFAULT_ENERGY_TAX_INCL_VAT),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_SUPPLIER_MARKUP_EXCL_VAT,
                    default=data.get(CONF_SUPPLIER_MARKUP_EXCL_VAT, DEFAULT_SUPPLIER_MARKUP_EXCL_VAT),
                ): vol.Coerce(float),
                vol.Optional(CONF_VAT, default=data.get(CONF_VAT, DEFAULT_VAT)): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
