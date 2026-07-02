"""Coordinator for NL Day Ahead Prices."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CACHE_VERSION,
    CONF_COUNTRY,
    CONF_CURRENCY,
    CONF_ENABLE_ENTSOE,
    CONF_ENTSOE_API_TOKEN,
    CONF_PRIMARY_PROVIDER,
    DEFAULT_COUNTRY,
    DEFAULT_CURRENCY,
    DEFAULT_PRIMARY_PROVIDER,
    DOMAIN,
    PROVIDER_CACHE,
    PROVIDER_ENERGY_CHARTS,
    PROVIDER_ENTSOE,
    PROVIDER_NORD_POOL,
    UPDATE_INTERVAL,
)
from .models import PriceData, PriceEntry, ProviderResult
from .providers import (
    BasePriceProvider,
    EnergyChartsProvider,
    EntsoeProvider,
    NordPoolProvider,
    ProviderError,
    async_fetch_with_fallback,
)

_LOGGER = logging.getLogger(__name__)


class NLDayAheadPricesCoordinator(DataUpdateCoordinator[PriceData]):
    """Fetch prices and manage provider fallback."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self.store: Store[dict[str, Any]] = Store(hass, CACHE_VERSION, f"{DOMAIN}_{entry.entry_id}")

    async def _async_update_data(self) -> PriceData:
        now = dt_util.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)
        providers = self._providers()
        try:
            result, fallback_used, errors = await async_fetch_with_fallback(providers, today, tomorrow)
        except ProviderError as err:
            cached = await self._async_load_cached()
            if cached is not None:
                cached.errors["cache_reason"] = str(err)
                return cached
            raise UpdateFailed(str(err)) from err

        data = PriceData(result=result, fallback_used=fallback_used, last_successful_update=now)
        await self._async_store_cached(data)
        data.errors = errors
        return data

    def _providers(self) -> list[BasePriceProvider]:
        session = async_get_clientsession(self.hass)
        options = self.entry.options
        data = self.entry.data
        country = options.get(CONF_COUNTRY, data.get(CONF_COUNTRY, DEFAULT_COUNTRY))
        currency = options.get(CONF_CURRENCY, data.get(CONF_CURRENCY, DEFAULT_CURRENCY))
        primary = options.get(CONF_PRIMARY_PROVIDER, data.get(CONF_PRIMARY_PROVIDER, DEFAULT_PRIMARY_PROVIDER))

        by_key: dict[str, BasePriceProvider] = {
            PROVIDER_NORD_POOL: NordPoolProvider(session, country, currency),
            PROVIDER_ENERGY_CHARTS: EnergyChartsProvider(session, country, currency),
        }
        token = options.get(CONF_ENTSOE_API_TOKEN, data.get(CONF_ENTSOE_API_TOKEN))
        if options.get(CONF_ENABLE_ENTSOE, data.get(CONF_ENABLE_ENTSOE, False)) and token:
            by_key[PROVIDER_ENTSOE] = EntsoeProvider(session, token, country, currency)

        order = [primary, PROVIDER_NORD_POOL, PROVIDER_ENERGY_CHARTS, PROVIDER_ENTSOE]
        providers: list[BasePriceProvider] = []
        seen: set[str] = set()
        for key in order:
            if key in by_key and key not in seen:
                providers.append(by_key[key])
                seen.add(key)
        return providers

    async def _async_store_cached(self, data: PriceData) -> None:
        await self.store.async_save(
            {
                "provider": data.result.provider,
                "prices_today": [entry.as_attribute() for entry in data.result.prices_today],
                "prices_tomorrow": [entry.as_attribute() for entry in data.result.prices_tomorrow],
                "raw_today": data.result.raw_today,
                "raw_tomorrow": data.result.raw_tomorrow,
                "last_successful_update": data.last_successful_update.isoformat()
                if data.last_successful_update
                else None,
            }
        )

    async def _async_load_cached(self) -> PriceData | None:
        cached = await self.store.async_load()
        if not cached:
            return None
        result = ProviderResult(
            provider=PROVIDER_CACHE,
            prices_today=_deserialize_prices(cached.get("prices_today", [])),
            prices_tomorrow=_deserialize_prices(cached.get("prices_tomorrow", [])),
            raw_today=cached.get("raw_today"),
            raw_tomorrow=cached.get("raw_tomorrow"),
        )
        last_update = cached.get("last_successful_update")
        return PriceData(
            result=result,
            fallback_used=True,
            last_successful_update=datetime.fromisoformat(last_update) if last_update else None,
            from_cache=True,
        )


def _deserialize_prices(entries: list[dict[str, Any]]) -> list[PriceEntry]:
    return [PriceEntry(datetime.fromisoformat(entry["time"]), float(entry["price"])) for entry in entries]
