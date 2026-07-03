"""Sensors for NL Day Ahead Prices."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .calculations import (
    build_all_in_price_attributes,
    calculate_all_in_price,
    calculate_monthly_fee,
    calculate_supplier_fee,
)
from .const import (
    CONF_CUSTOM_MONTHLY_FEE_ELECTRICITY,
    CONF_CUSTOM_PURCHASE_FEE_ELECTRICITY,
    CONF_CUSTOM_PURCHASE_FEE_INCLUDES_VAT,
    CONF_CUSTOM_SELL_FEE_ELECTRICITY,
    CONF_CUSTOM_SELL_FEE_INCLUDES_VAT,
    CONF_CUSTOM_SUPPLIER_NAME,
    CONF_ENERGY_TAX,
    CONF_ENERGY_TAX_INCL_VAT,
    CONF_SELECTED_SUPPLIER,
    CONF_SUPPLIER_MARKUP_EXCL_VAT,
    CONF_VAT,
    DEFAULT_CUSTOM_MONTHLY_FEE_ELECTRICITY,
    DEFAULT_CUSTOM_PURCHASE_FEE_INCLUDES_VAT,
    DEFAULT_CUSTOM_SELL_FEE_ELECTRICITY,
    DEFAULT_CUSTOM_SELL_FEE_INCLUDES_VAT,
    DEFAULT_CUSTOM_SUPPLIER_NAME,
    DEFAULT_ENERGY_TAX,
    DEFAULT_SELECTED_SUPPLIER,
    DEFAULT_SUPPLIER_MARKUP_EXCL_VAT,
    DEFAULT_VAT,
    DOMAIN,
    PROVIDER_NAMES,
)
from .coordinator import NLDayAheadPricesCoordinator
from .models import (
    PriceData,
    average_price,
    current_price,
    highest_price,
    lowest_price,
    next_hour_price,
)
from .price_resolution import (
    PRICE_RESOLUTION_HOURLY,
    PRICE_RESOLUTION_QUARTER_HOUR,
    find_cheapest_consecutive_block,
)
from .supplier_profiles import SupplierProfile, load_supplier_profiles, supplier_profile_to_dict

EUR_PER_KWH = f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}"
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NLPriceSensorDescription(SensorEntityDescription):
    """Price sensor description."""

    value_fn: Callable[[PriceData, datetime, ConfigEntry], Any]


def _current_market(data: PriceData, now: datetime, entry: ConfigEntry) -> float | None:
    return current_price(data.result.prices, now)


def _next_hour(data: PriceData, now: datetime, entry: ConfigEntry) -> float | None:
    return next_hour_price(data.result.prices, now)


def _average_today(data: PriceData, now: datetime, entry: ConfigEntry) -> float | None:
    market = average_price(data.result.prices_today)
    return _calculate_all_in(market, entry) if market is not None else None


def _average_tomorrow(data: PriceData, now: datetime, entry: ConfigEntry) -> float | None:
    market = average_price(data.result.prices_tomorrow)
    return _calculate_all_in(market, entry) if market is not None else None


def _lowest_today(data: PriceData, now: datetime, entry: ConfigEntry) -> float | None:
    entry_data = lowest_price(data.result.prices_today)
    return _calculate_all_in(entry_data.price, entry) if entry_data else None


def _highest_today(data: PriceData, now: datetime, entry: ConfigEntry) -> float | None:
    entry_data = highest_price(data.result.prices_today)
    return _calculate_all_in(entry_data.price, entry) if entry_data else None


def _lowest_time_today(data: PriceData, now: datetime, entry: ConfigEntry) -> datetime | None:
    entry_data = lowest_price(data.result.prices_today)
    return entry_data.time if entry_data else None


def _highest_time_today(data: PriceData, now: datetime, entry: ConfigEntry) -> datetime | None:
    entry_data = highest_price(data.result.prices_today)
    return entry_data.time if entry_data else None


def _current_all_in(data: PriceData, now: datetime, entry: ConfigEntry) -> float | None:
    market = current_price(data.result.prices, now)
    if market is None:
        return None
    return _calculate_all_in(market, entry)


def _next_hour_all_in(data: PriceData, now: datetime, entry: ConfigEntry) -> float | None:
    market = next_hour_price(data.result.prices, now)
    if market is None:
        return None
    return _calculate_all_in(market, entry)


def _average_all_in_today(data: PriceData, now: datetime, entry: ConfigEntry) -> float | None:
    return _average_today(data, now, entry)


def _lowest_all_in_today(data: PriceData, now: datetime, entry: ConfigEntry) -> float | None:
    return _lowest_today(data, now, entry)


def _highest_all_in_today(data: PriceData, now: datetime, entry: ConfigEntry) -> float | None:
    return _highest_today(data, now, entry)


def _supplier_purchase_fee(data: PriceData, now: datetime, entry: ConfigEntry) -> float:
    return calculate_supplier_fee(_selected_supplier_profile(entry), _vat(entry))


def _supplier_monthly_fee(data: PriceData, now: datetime, entry: ConfigEntry) -> float:
    return calculate_monthly_fee(_selected_supplier_profile(entry))


def _selected_supplier(data: PriceData, now: datetime, entry: ConfigEntry) -> str:
    return _selected_supplier_profile(entry).name


def _effective_price_resolution(data: PriceData, now: datetime, entry: ConfigEntry) -> str:
    return data.result.effective_price_resolution


def _calculate_all_in(market: float, entry: ConfigEntry) -> float:
    return calculate_all_in_price(
        market,
        _energy_tax(entry),
        _selected_supplier_profile(entry),
        _vat(entry),
    )


def _entry_options(entry: ConfigEntry) -> dict[str, Any]:
    return {**entry.data, **entry.options}


def _energy_tax(entry: ConfigEntry) -> float:
    options = _entry_options(entry)
    return float(options.get(CONF_ENERGY_TAX, options.get(CONF_ENERGY_TAX_INCL_VAT, DEFAULT_ENERGY_TAX)))


def _vat(entry: ConfigEntry) -> float:
    return float(_entry_options(entry).get(CONF_VAT, DEFAULT_VAT))


def _selected_supplier_key(entry: ConfigEntry) -> str:
    return str(_entry_options(entry).get(CONF_SELECTED_SUPPLIER, DEFAULT_SELECTED_SUPPLIER))


def _selected_supplier_profile(entry: ConfigEntry) -> SupplierProfile:
    key = _selected_supplier_key(entry)
    if key == "custom":
        return _custom_supplier_profile(entry)

    profiles = load_supplier_profiles()
    if key in profiles:
        return profiles[key]

    _LOGGER.warning("Configured supplier profile %s is unavailable; falling back to custom supplier", key)
    return _custom_supplier_profile(entry)


def _custom_supplier_profile(entry: ConfigEntry) -> SupplierProfile:
    options = _entry_options(entry)
    vat = _vat(entry)
    legacy_markup_incl_vat = float(
        options.get(CONF_SUPPLIER_MARKUP_EXCL_VAT, DEFAULT_SUPPLIER_MARKUP_EXCL_VAT)
    ) * (1 + vat)
    purchase_fee = float(options.get(CONF_CUSTOM_PURCHASE_FEE_ELECTRICITY, legacy_markup_incl_vat))
    return SupplierProfile(
        key="custom",
        name=str(options.get(CONF_CUSTOM_SUPPLIER_NAME, DEFAULT_CUSTOM_SUPPLIER_NAME)),
        monthly_fee_electricity=float(
            options.get(CONF_CUSTOM_MONTHLY_FEE_ELECTRICITY, DEFAULT_CUSTOM_MONTHLY_FEE_ELECTRICITY)
        ),
        purchase_fee_electricity=purchase_fee,
        purchase_fee_unit="EUR_PER_KWH",
        purchase_fee_includes_vat=bool(
            options.get(CONF_CUSTOM_PURCHASE_FEE_INCLUDES_VAT, DEFAULT_CUSTOM_PURCHASE_FEE_INCLUDES_VAT)
        ),
        sell_fee_electricity=float(
            options.get(CONF_CUSTOM_SELL_FEE_ELECTRICITY, DEFAULT_CUSTOM_SELL_FEE_ELECTRICITY)
        ),
        sell_fee_includes_vat=bool(options.get(CONF_CUSTOM_SELL_FEE_INCLUDES_VAT, DEFAULT_CUSTOM_SELL_FEE_INCLUDES_VAT)),
        last_verified=None,
        source_url=None,
        price_resolution=PRICE_RESOLUTION_HOURLY,
        price_resolution_changes=[],
        default_price_resolution_before_change=None,
    )


def _provider(data: PriceData, now: datetime, entry: ConfigEntry) -> str:
    return PROVIDER_NAMES.get(data.result.provider, data.result.provider)


def _last_successful(data: PriceData, now: datetime, entry: ConfigEntry) -> datetime | None:
    return data.last_successful_update


SENSORS: tuple[NLPriceSensorDescription, ...] = (
    NLPriceSensorDescription(
        key="current_market_price",
        translation_key="current_market_price",
        native_unit_of_measurement=EUR_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_current_market,
    ),
    NLPriceSensorDescription(
        key="next_hour_market_price",
        translation_key="next_hour_market_price",
        native_unit_of_measurement=EUR_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_next_hour,
    ),
    NLPriceSensorDescription(
        key="average_price_today",
        translation_key="average_price_today",
        native_unit_of_measurement=EUR_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_average_today,
    ),
    NLPriceSensorDescription(
        key="average_price_tomorrow",
        translation_key="average_price_tomorrow",
        native_unit_of_measurement=EUR_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_average_tomorrow,
    ),
    NLPriceSensorDescription(
        key="lowest_price_today",
        translation_key="lowest_price_today",
        native_unit_of_measurement=EUR_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_lowest_today,
    ),
    NLPriceSensorDescription(
        key="lowest_energy_price",
        translation_key="lowest_energy_price",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_lowest_time_today,
    ),
    NLPriceSensorDescription(
        key="highest_price_today",
        translation_key="highest_price_today",
        native_unit_of_measurement=EUR_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_highest_today,
    ),
    NLPriceSensorDescription(
        key="highest_energy_price",
        translation_key="highest_energy_price",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_highest_time_today,
    ),
    NLPriceSensorDescription(
        key="time_of_lowest_price_today",
        translation_key="time_of_lowest_price_today",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_lowest_time_today,
    ),
    NLPriceSensorDescription(
        key="time_of_highest_price_today",
        translation_key="time_of_highest_price_today",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_highest_time_today,
    ),
    NLPriceSensorDescription(
        key="current_all_in_price",
        translation_key="current_all_in_price",
        native_unit_of_measurement=EUR_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_current_all_in,
    ),
    NLPriceSensorDescription(
        key="next_hour_all_in_price",
        translation_key="next_hour_all_in_price",
        native_unit_of_measurement=EUR_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_next_hour_all_in,
    ),
    NLPriceSensorDescription(
        key="average_all_in_price_today",
        translation_key="average_all_in_price_today",
        native_unit_of_measurement=EUR_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_average_all_in_today,
    ),
    NLPriceSensorDescription(
        key="lowest_all_in_price_today",
        translation_key="lowest_all_in_price_today",
        native_unit_of_measurement=EUR_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_lowest_all_in_today,
    ),
    NLPriceSensorDescription(
        key="highest_all_in_price_today",
        translation_key="highest_all_in_price_today",
        native_unit_of_measurement=EUR_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_highest_all_in_today,
    ),
    NLPriceSensorDescription(
        key="supplier_purchase_fee",
        translation_key="supplier_purchase_fee",
        native_unit_of_measurement=EUR_PER_KWH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_supplier_purchase_fee,
    ),
    NLPriceSensorDescription(
        key="supplier_monthly_fee",
        translation_key="supplier_monthly_fee",
        native_unit_of_measurement="EUR",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_supplier_monthly_fee,
    ),
    NLPriceSensorDescription(
        key="selected_supplier",
        translation_key="selected_supplier",
        value_fn=_selected_supplier,
    ),
    NLPriceSensorDescription(
        key="effective_price_resolution",
        translation_key="effective_price_resolution",
        value_fn=_effective_price_resolution,
    ),
    NLPriceSensorDescription(key="current_provider", translation_key="current_provider", value_fn=_provider),
    NLPriceSensorDescription(
        key="last_successful_update",
        translation_key="last_successful_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_last_successful,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: NLDayAheadPricesCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [NLDayAheadPriceSensor(coordinator, entry, description) for description in SENSORS]
    _LOGGER.info("Adding %s NL Day Ahead Prices sensor entities", len(entities))
    async_add_entities(entities)


class NLDayAheadPriceSensor(CoordinatorEntity[NLDayAheadPricesCoordinator], SensorEntity):
    """NL Day Ahead Prices sensor."""

    entity_description: NLPriceSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NLDayAheadPricesCoordinator,
        entry: ConfigEntry,
        description: NLPriceSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "NL Day Ahead Prices",
            "manufacturer": "NL Day Ahead Prices",
        }

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        if self.coordinator.data is None:
            return None
        value = self.entity_description.value_fn(self.coordinator.data, dt_util.now(), self.entry)
        return round(value, 6) if isinstance(value, float) else value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return ApexCharts-friendly price attributes."""
        data = self.coordinator.data
        if data is None:
            return {}
        supplier_profile = _selected_supplier_profile(self.entry)
        cheapest_blocks = _cheapest_block_attributes(data)
        return {
            "prices": [entry.as_attribute() for entry in data.result.prices],
            "prices_today": [entry.as_attribute() for entry in data.result.prices_today],
            "prices_tomorrow": [entry.as_attribute() for entry in data.result.prices_tomorrow],
            "raw_prices": [entry.as_attribute() for entry in data.result.raw_prices],
            "raw_prices_today": [entry.as_attribute() for entry in data.result.source_prices_today],
            "raw_prices_tomorrow": [entry.as_attribute() for entry in data.result.source_prices_tomorrow],
            "all_in_prices_today": build_all_in_price_attributes(
                data.result.prices_today, _energy_tax(self.entry), supplier_profile, _vat(self.entry)
            ),
            "all_in_prices_tomorrow": build_all_in_price_attributes(
                data.result.prices_tomorrow, _energy_tax(self.entry), supplier_profile, _vat(self.entry)
            ),
            "raw_today": data.result.raw_today,
            "raw_tomorrow": data.result.raw_tomorrow,
            "price_resolution": data.result.effective_price_resolution,
            "requested_price_resolution": data.result.requested_price_resolution,
            "effective_price_resolution": data.result.effective_price_resolution,
            "raw_price_resolution": data.result.raw_price_resolution,
            "resolution_converted": data.result.resolution_converted,
            "provider": data.result.provider,
            "provider_name": PROVIDER_NAMES.get(data.result.provider, data.result.provider),
            "fallback_used": data.fallback_used,
            "last_successful_update": data.last_successful_update.isoformat()
            if data.last_successful_update
            else None,
            "selected_supplier": supplier_profile.key,
            "selected_supplier_name": supplier_profile.name,
            "supplier_purchase_fee": round(calculate_supplier_fee(supplier_profile, _vat(self.entry)), 6),
            "supplier_monthly_fee": round(calculate_monthly_fee(supplier_profile), 2),
            "energy_tax": _energy_tax(self.entry),
            "vat": _vat(self.entry),
            "supplier_profile_last_verified": supplier_profile.last_verified,
            "supplier_profile_source_url": supplier_profile.source_url,
            "supplier_profile": supplier_profile_to_dict(supplier_profile),
            **cheapest_blocks,
        }


def _cheapest_block_attributes(data: PriceData) -> dict[str, Any]:
    prices = data.result.prices_today
    if data.result.effective_price_resolution == PRICE_RESOLUTION_QUARTER_HOUR:
        durations = {
            "cheapest_15_minutes": 15,
            "cheapest_30_minutes": 30,
            "cheapest_45_minutes": 45,
            "cheapest_1_hour": 60,
            "cheapest_2_hours": 120,
            "cheapest_3_hours": 180,
            "cheapest_4_hours": 240,
        }
    else:
        durations = {
            "cheapest_1_hour": 60,
            "cheapest_2_hours": 120,
            "cheapest_3_hours": 180,
            "cheapest_4_hours": 240,
        }
    return {key: find_cheapest_consecutive_block(prices, minutes) for key, minutes in durations.items()}
