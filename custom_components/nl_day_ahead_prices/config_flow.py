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
    CONF_CUSTOM_MONTHLY_FEE_ELECTRICITY,
    CONF_CUSTOM_PURCHASE_FEE_ELECTRICITY,
    CONF_CUSTOM_PURCHASE_FEE_INCLUDES_VAT,
    CONF_CUSTOM_SELL_FEE_ELECTRICITY,
    CONF_CUSTOM_SELL_FEE_INCLUDES_VAT,
    CONF_CUSTOM_SUPPLIER_NAME,
    CONF_ENABLE_ENTSOE,
    CONF_ENERGY_TAX,
    CONF_ENERGY_TAX_INCL_VAT,
    CONF_ENTSOE_API_TOKEN,
    CONF_PRIMARY_PROVIDER,
    CONF_SELECTED_SUPPLIER,
    CONF_VAT,
    DEFAULT_COUNTRY,
    DEFAULT_CURRENCY,
    DEFAULT_CUSTOM_MONTHLY_FEE_ELECTRICITY,
    DEFAULT_CUSTOM_PURCHASE_FEE_ELECTRICITY,
    DEFAULT_CUSTOM_PURCHASE_FEE_INCLUDES_VAT,
    DEFAULT_CUSTOM_SELL_FEE_ELECTRICITY,
    DEFAULT_CUSTOM_SELL_FEE_INCLUDES_VAT,
    DEFAULT_CUSTOM_SUPPLIER_NAME,
    DEFAULT_ENERGY_TAX,
    DEFAULT_PRIMARY_PROVIDER,
    DEFAULT_SELECTED_SUPPLIER,
    DEFAULT_VAT,
    DOMAIN,
    NAME,
    PROVIDER_ENERGY_CHARTS,
    PROVIDER_NORD_POOL,
)
from .supplier_profiles import load_supplier_profiles


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
            errors = _validate_options(user_input)
            if errors:
                return self.async_show_form(
                    step_id="init",
                    data_schema=await self._async_options_schema(user_input),
                    errors=errors,
                )
            return self.async_create_entry(title="", data=user_input)

        data = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=await self._async_options_schema(data))

    async def _async_options_schema(self, data: dict[str, Any]) -> vol.Schema:
        profiles = await self.hass.async_add_executor_job(load_supplier_profiles)
        supplier_choices = {key: profile.name for key, profile in profiles.items()}
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
                    CONF_SELECTED_SUPPLIER,
                    default=data.get(CONF_SELECTED_SUPPLIER, DEFAULT_SELECTED_SUPPLIER),
                ): vol.In(supplier_choices),
                vol.Optional(
                    CONF_ENERGY_TAX,
                    default=data.get(CONF_ENERGY_TAX, data.get(CONF_ENERGY_TAX_INCL_VAT, DEFAULT_ENERGY_TAX)),
                ): vol.All(vol.Coerce(float), vol.Range(min=0)),
                vol.Optional(CONF_VAT, default=data.get(CONF_VAT, DEFAULT_VAT)): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=1)
                ),
                vol.Optional(
                    CONF_CUSTOM_SUPPLIER_NAME,
                    default=data.get(CONF_CUSTOM_SUPPLIER_NAME, DEFAULT_CUSTOM_SUPPLIER_NAME),
                ): str,
                vol.Optional(
                    CONF_CUSTOM_MONTHLY_FEE_ELECTRICITY,
                    default=data.get(CONF_CUSTOM_MONTHLY_FEE_ELECTRICITY, DEFAULT_CUSTOM_MONTHLY_FEE_ELECTRICITY),
                ): vol.All(vol.Coerce(float), vol.Range(min=0)),
                vol.Optional(
                    CONF_CUSTOM_PURCHASE_FEE_ELECTRICITY,
                    default=data.get(CONF_CUSTOM_PURCHASE_FEE_ELECTRICITY, DEFAULT_CUSTOM_PURCHASE_FEE_ELECTRICITY),
                ): vol.All(vol.Coerce(float), vol.Range(min=0)),
                vol.Optional(
                    CONF_CUSTOM_PURCHASE_FEE_INCLUDES_VAT,
                    default=data.get(
                        CONF_CUSTOM_PURCHASE_FEE_INCLUDES_VAT, DEFAULT_CUSTOM_PURCHASE_FEE_INCLUDES_VAT
                    ),
                ): bool,
                vol.Optional(
                    CONF_CUSTOM_SELL_FEE_ELECTRICITY,
                    default=data.get(CONF_CUSTOM_SELL_FEE_ELECTRICITY, DEFAULT_CUSTOM_SELL_FEE_ELECTRICITY),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_CUSTOM_SELL_FEE_INCLUDES_VAT,
                    default=data.get(CONF_CUSTOM_SELL_FEE_INCLUDES_VAT, DEFAULT_CUSTOM_SELL_FEE_INCLUDES_VAT),
                ): bool,
            }
        )
        return schema


def _validate_options(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate numeric option ranges."""
    errors: dict[str, str] = {}
    vat = _float_option(user_input, CONF_VAT, DEFAULT_VAT)
    energy_tax = _float_option(user_input, CONF_ENERGY_TAX, DEFAULT_ENERGY_TAX)
    monthly_fee = _float_option(user_input, CONF_CUSTOM_MONTHLY_FEE_ELECTRICITY, 0)
    purchase_fee = _float_option(user_input, CONF_CUSTOM_PURCHASE_FEE_ELECTRICITY, 0)
    if vat is None or vat < 0 or vat > 1:
        errors[CONF_VAT] = "invalid_vat"
    if energy_tax is None or energy_tax < 0:
        errors[CONF_ENERGY_TAX] = "negative_value"
    if monthly_fee is None or monthly_fee < 0:
        errors[CONF_CUSTOM_MONTHLY_FEE_ELECTRICITY] = "negative_value"
    if purchase_fee is None or purchase_fee < 0:
        errors[CONF_CUSTOM_PURCHASE_FEE_ELECTRICITY] = "negative_value"
    return errors


def _float_option(user_input: dict[str, Any], key: str, default: float) -> float | None:
    """Read an option as float without raising from the options flow."""
    try:
        return float(user_input.get(key, default))
    except (TypeError, ValueError):
        return None
