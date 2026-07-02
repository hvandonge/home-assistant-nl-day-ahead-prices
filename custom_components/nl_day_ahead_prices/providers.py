"""Async price providers for NL Day Ahead Prices."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from xml.etree import ElementTree

from aiohttp import ClientError, ClientSession

from .const import (
    DEFAULT_COUNTRY,
    DEFAULT_CURRENCY,
    PROVIDER_ENERGY_CHARTS,
    PROVIDER_ENTSOE,
    PROVIDER_NORD_POOL,
    REQUEST_RETRIES,
    REQUEST_TIMEOUT,
)
from .models import PriceEntry, ProviderResult, convert_to_eur_kwh

_LOGGER = logging.getLogger(__name__)

ENTSOE_NL_DOMAIN = "10YNL----------L"


class ProviderError(Exception):
    """Raised when a provider cannot return usable prices."""


class BasePriceProvider(ABC):
    """Base class for asynchronous day-ahead price providers."""

    key: str

    def __init__(
        self,
        session: ClientSession,
        country: str = DEFAULT_COUNTRY,
        currency: str = DEFAULT_CURRENCY,
    ) -> None:
        self.session = session
        self.country = country
        self.currency = currency

    @abstractmethod
    async def async_fetch(self, today: date, tomorrow: date) -> ProviderResult:
        """Fetch normalized today and tomorrow prices."""

    async def _request_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """Fetch JSON with timeout and retry."""
        last_error: Exception | None = None
        for attempt in range(REQUEST_RETRIES):
            try:
                async with asyncio.timeout(REQUEST_TIMEOUT):
                    async with self.session.get(url, params=params) as response:
                        response.raise_for_status()
                        return await response.json(content_type=None)
            except (TimeoutError, ClientError) as err:
                last_error = err
                if attempt + 1 < REQUEST_RETRIES:
                    await asyncio.sleep(1)
        raise ProviderError(str(last_error) if last_error else "request failed")

    async def _request_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        """Fetch text with timeout and retry."""
        last_error: Exception | None = None
        for attempt in range(REQUEST_RETRIES):
            try:
                async with asyncio.timeout(REQUEST_TIMEOUT):
                    async with self.session.get(url, params=params) as response:
                        response.raise_for_status()
                        return await response.text()
            except (TimeoutError, ClientError) as err:
                last_error = err
                if attempt + 1 < REQUEST_RETRIES:
                    await asyncio.sleep(1)
        raise ProviderError(str(last_error) if last_error else "request failed")


class NordPoolProvider(BasePriceProvider):
    """Nord Pool day-ahead provider."""

    key = PROVIDER_NORD_POOL

    async def async_fetch(self, today: date, tomorrow: date) -> ProviderResult:
        today_raw = await self._fetch_day(today)
        tomorrow_raw = await self._fetch_day(tomorrow)
        return ProviderResult(
            provider=self.key,
            prices_today=parse_nord_pool(today_raw, self.country),
            prices_tomorrow=parse_nord_pool(tomorrow_raw, self.country),
            raw_today=today_raw,
            raw_tomorrow=tomorrow_raw,
        )

    async def _fetch_day(self, day: date) -> Any:
        return await self._request_json(
            "https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices",
            {
                "date": day.isoformat(),
                "market": "DayAhead",
                "deliveryArea": self.country,
                "currency": self.currency,
            },
        )


class EnergyChartsProvider(BasePriceProvider):
    """Energy-Charts day-ahead provider."""

    key = PROVIDER_ENERGY_CHARTS

    async def async_fetch(self, today: date, tomorrow: date) -> ProviderResult:
        start = datetime.combine(today, time.min).isoformat()
        end = datetime.combine(tomorrow + timedelta(days=1), time.min).isoformat()
        raw = await self._request_json(
            "https://api.energy-charts.info/price",
            {"bzn": self.country, "start": start, "end": end},
        )
        today_prices = parse_energy_charts(raw, today)
        tomorrow_prices = parse_energy_charts(raw, tomorrow)
        return ProviderResult(
            provider=self.key,
            prices_today=today_prices,
            prices_tomorrow=tomorrow_prices,
            raw_today=raw,
            raw_tomorrow=raw,
        )


class EntsoeProvider(BasePriceProvider):
    """Optional ENTSO-E fallback provider."""

    key = PROVIDER_ENTSOE

    def __init__(
        self,
        session: ClientSession,
        api_token: str,
        country: str = DEFAULT_COUNTRY,
        currency: str = DEFAULT_CURRENCY,
    ) -> None:
        super().__init__(session, country, currency)
        self.api_token = api_token

    async def async_fetch(self, today: date, tomorrow: date) -> ProviderResult:
        today_raw = await self._fetch_day(today)
        tomorrow_raw = await self._fetch_day(tomorrow)
        return ProviderResult(
            provider=self.key,
            prices_today=parse_entsoe_xml(today_raw),
            prices_tomorrow=parse_entsoe_xml(tomorrow_raw),
            raw_today=today_raw,
            raw_tomorrow=tomorrow_raw,
        )

    async def _fetch_day(self, day: date) -> str:
        start = datetime.combine(day, time.min).strftime("%Y%m%d%H%M")
        end = datetime.combine(day + timedelta(days=1), time.min).strftime("%Y%m%d%H%M")
        return await self._request_text(
            "https://web-api.tp.entsoe.eu/api",
            {
                "securityToken": self.api_token,
                "documentType": "A44",
                "in_Domain": ENTSOE_NL_DOMAIN,
                "out_Domain": ENTSOE_NL_DOMAIN,
                "periodStart": start,
                "periodEnd": end,
            },
        )


async def async_fetch_with_fallback(
    providers: list[BasePriceProvider],
    today: date,
    tomorrow: date,
) -> tuple[ProviderResult, bool, dict[str, str]]:
    """Fetch prices from providers, falling back automatically."""
    errors: dict[str, str] = {}
    for index, provider in enumerate(providers):
        try:
            result = await provider.async_fetch(today, tomorrow)
            if not result.prices_today:
                raise ProviderError("provider returned no prices for today")
            return result, index > 0, errors
        except Exception as err:  # noqa: BLE001 - provider isolation is intentional.
            _LOGGER.warning("Provider %s failed: %s", provider.key, err)
            errors[provider.key] = str(err)
    raise ProviderError("all providers failed")


def parse_nord_pool(payload: Any, area: str) -> list[PriceEntry]:
    """Parse Nord Pool's public day-ahead payload.

    Nord Pool can return 15-minute MTU rows for NL. Home Assistant sensors in
    this integration expose hourly prices, so multiple rows in the same hour
    are aggregated with a duration-weighted average.
    """
    entries = payload.get("multiAreaEntries") or payload.get("MultiAreaEntries") or []
    hourly_totals: dict[datetime, tuple[float, float]] = {}
    for row in entries:
        price_value = row.get("entryPerArea", {}).get(area)
        if price_value is None:
            price_value = row.get("EntryPerArea", {}).get(area)
        if price_value is None:
            continue
        start = row.get("deliveryStart") or row.get("DeliveryStart") or row.get("time")
        if not start:
            continue
        start_dt = _parse_datetime(start)
        end = row.get("deliveryEnd") or row.get("DeliveryEnd")
        end_dt = _parse_datetime(end) if end else start_dt + timedelta(hours=1)
        hour_start = start_dt.replace(minute=0, second=0, microsecond=0)
        duration = max((end_dt - start_dt).total_seconds(), 0)
        if duration == 0:
            duration = 3600
        price = convert_to_eur_kwh(float(price_value), "EUR/MWh")
        weighted_total, duration_total = hourly_totals.get(hour_start, (0.0, 0.0))
        hourly_totals[hour_start] = (weighted_total + price * duration, duration_total + duration)

    return [
        PriceEntry(hour, weighted_total / duration_total)
        for hour, (weighted_total, duration_total) in sorted(hourly_totals.items(), key=lambda item: item[0])
        if duration_total
    ]


def parse_energy_charts(payload: Any, target_day: date) -> list[PriceEntry]:
    """Parse Energy-Charts price payload."""
    timestamps = payload.get("unix_seconds") or payload.get("time") or []
    values = payload.get("price") or payload.get("prices") or []
    prices: list[PriceEntry] = []
    for index, timestamp in enumerate(timestamps):
        if index >= len(values):
            break
        value = values[index]
        if value is None:
            continue
        dt = (
            datetime.fromtimestamp(timestamp, tz=timezone.utc)
            if isinstance(timestamp, (int, float))
            else datetime.fromisoformat(timestamp)
        )
        if dt.date() == target_day:
            prices.append(PriceEntry(dt, convert_to_eur_kwh(float(value), "EUR/MWh")))
    return sorted(prices, key=lambda entry: entry.time)


def _parse_datetime(value: str) -> datetime:
    """Parse provider datetimes across supported Python versions."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_entsoe_xml(payload: str) -> list[PriceEntry]:
    """Parse ENTSO-E XML into EUR/kWh prices."""
    root = ElementTree.fromstring(payload)
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}")[0] + "}"
    prices: list[PriceEntry] = []
    for period in root.iter(f"{namespace}Period"):
        start_node = period.find(f"{namespace}timeInterval/{namespace}start")
        if start_node is None or not start_node.text:
            continue
        start = datetime.fromisoformat(start_node.text.replace("Z", "+00:00"))
        resolution = period.findtext(f"{namespace}resolution", default="PT60M")
        if resolution != "PT60M":
            _LOGGER.debug("Unsupported ENTSO-E resolution %s, assuming hourly positions", resolution)
        for point in period.findall(f"{namespace}Point"):
            position = point.findtext(f"{namespace}position")
            price = point.findtext(f"{namespace}price.amount")
            if position is None or price is None:
                continue
            prices.append(
                PriceEntry(
                    start + timedelta(hours=int(position) - 1),
                    convert_to_eur_kwh(float(price), "EUR/MWh"),
                )
            )
    return sorted(prices, key=lambda entry: entry.time)
