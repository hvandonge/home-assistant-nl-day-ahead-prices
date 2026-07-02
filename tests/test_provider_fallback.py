from datetime import date, datetime

import pytest

from custom_components.nl_day_ahead_prices.models import PriceEntry, ProviderResult
from custom_components.nl_day_ahead_prices.providers import BasePriceProvider, ProviderError, async_fetch_with_fallback


class FailingProvider(BasePriceProvider):
    key = "failing"

    async def async_fetch(self, today: date, tomorrow: date) -> ProviderResult:
        raise ProviderError("boom")


class WorkingProvider(BasePriceProvider):
    key = "working"

    async def async_fetch(self, today: date, tomorrow: date) -> ProviderResult:
        return ProviderResult(
            provider=self.key,
            prices_today=[PriceEntry(datetime(2026, 7, 2), 0.1)],
            prices_tomorrow=[PriceEntry(datetime(2026, 7, 3), 0.2)],
        )


@pytest.mark.asyncio
async def test_provider_fallback_uses_second_provider() -> None:
    result, fallback_used, errors = await async_fetch_with_fallback(
        [FailingProvider(None), WorkingProvider(None)],
        date(2026, 7, 2),
        date(2026, 7, 3),
    )

    assert result.provider == "working"
    assert fallback_used is True
    assert errors == {"failing": "boom"}


@pytest.mark.asyncio
async def test_provider_fallback_raises_when_every_provider_fails() -> None:
    with pytest.raises(ProviderError):
        await async_fetch_with_fallback([FailingProvider(None)], date(2026, 7, 2), date(2026, 7, 3))

