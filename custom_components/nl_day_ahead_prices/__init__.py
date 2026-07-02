"""NL Day Ahead Prices integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NL Day Ahead Prices from a config entry."""
    from .coordinator import NLDayAheadPricesCoordinator

    _LOGGER.info("Setting up NL Day Ahead Prices config entry %s", entry.entry_id)
    coordinator = NLDayAheadPricesCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _platforms())
    hass.async_create_task(coordinator.async_refresh())
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _LOGGER.info("NL Day Ahead Prices setup finished for config entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading NL Day Ahead Prices config entry %s", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _platforms())
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after options changes."""
    await hass.config_entries.async_reload(entry.entry_id)


def _platforms() -> list:
    """Return Home Assistant platforms without importing HA during pure module tests."""
    from homeassistant.const import Platform

    return [Platform.SENSOR, Platform.BINARY_SENSOR]
