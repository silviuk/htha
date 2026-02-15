"""The Ht HA integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SELECTED_PARAMS,
    CONF_TIMEOUT,
    CONF_WRITE_ENABLED,
    DEFAULT_PARAMS,
    DOMAIN,
)
from .coordinator import HtHACoordinator

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)

# Platforms supported by this integration
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]

# Type alias for config entry
type HtHAConfigEntry = ConfigEntry[HtHACoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ht HA integration from YAML configuration.

    Args:
        hass: Home Assistant instance
        config: YAML configuration

    Returns:
        True if setup was successful
    """
    _LOGGER.info("Setting up %s integration", DOMAIN)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HtHAConfigEntry) -> bool:
    """Set up Ht HA from a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        True if setup was successful
    """
    _LOGGER.info("Setting up %s config entry: %s", DOMAIN, entry.entry_id)

    # Get configuration from entry
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    timeout = entry.data[CONF_TIMEOUT]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]
    write_enabled = entry.data.get(CONF_WRITE_ENABLED, False)
    selected_params = entry.options.get(CONF_SELECTED_PARAMS, DEFAULT_PARAMS)

    # Create coordinator
    coordinator = HtHACoordinator(
        hass,
        entry,
        host=host,
        port=port,
        timeout=timeout,
        scan_interval=scan_interval,
        selected_params=selected_params,
    )

    # Store coordinator in entry runtime data
    entry.runtime_data = coordinator

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store write_enabled flag for platforms to access
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "write_enabled": write_enabled,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HtHAConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        True if unload was successful
    """
    _LOGGER.info("Unloading %s config entry: %s", DOMAIN, entry.entry_id)

    # Shutdown coordinator
    coordinator = entry.runtime_data
    await coordinator.async_shutdown()

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: HtHAConfigEntry) -> None:
    """Update options for a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry
    """
    _LOGGER.info("Updating options for %s config entry: %s", DOMAIN, entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: HtHAConfigEntry) -> bool:
    """Migrate old entry data to new version.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        True if migration was successful
    """
    _LOGGER.info(
        "Migrating %s config entry from version %s", DOMAIN, entry.version
    )

    if entry.version == 1:
        # Current version, no migration needed
        return True

    _LOGGER.error("Unknown version %s for %s config entry", entry.version, DOMAIN)
    return False
