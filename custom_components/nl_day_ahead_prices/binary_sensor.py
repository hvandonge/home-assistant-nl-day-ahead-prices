"""Binary sensors for NL Day Ahead Prices."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NLDayAheadPricesCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator: NLDayAheadPricesCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TomorrowPricesAvailableBinarySensor(coordinator, entry)])


class TomorrowPricesAvailableBinarySensor(CoordinatorEntity[NLDayAheadPricesCoordinator], BinarySensorEntity):
    """Whether tomorrow's prices are available."""

    _attr_has_entity_name = True
    _attr_translation_key = "tomorrow_prices_available"

    def __init__(self, coordinator: NLDayAheadPricesCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_tomorrow_prices_available"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "NL Day Ahead Prices",
            "manufacturer": "NL Day Ahead Prices",
        }

    @property
    def is_on(self) -> bool | None:
        """Return true when tomorrow prices are available."""
        if self.coordinator.data is None:
            return None
        return bool(self.coordinator.data.result.prices_tomorrow)

