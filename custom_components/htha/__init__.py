"""The Ht HA integration."""

from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
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
    FRONTEND_SCRIPT,
    FRONTEND_URL_BASE,
    SCHEDULE_FRONTEND_SCRIPT,
)
from .coordinator import HtHACoordinator
from .lovelace_resource import async_ensure_resource, async_remove_resource, resource_url

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)

FRONTEND_SCRIPTS = (FRONTEND_SCRIPT, SCHEDULE_FRONTEND_SCRIPT)

DATA_FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"

# Config schema for config entry only integration
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Platforms supported by this integration
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.DATETIME,
    Platform.BUTTON,
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
    from .schedule_services import register_services

    register_services(hass)
    await async_register_frontend(hass)
    return True


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the bundled strategy and schedule editor and load both modules.

    The modules register the dashboard, view and section strategies and the
    schedule editor card. Failures here must never break the integration.
    """
    if hass.data.get(DATA_FRONTEND_REGISTERED):
        return
    if getattr(hass, "http", None) is None or "frontend" not in hass.config.components:
        _LOGGER.debug("Frontend not loaded, not registering the dashboard strategy")
        return
    try:
        # Imported lazily so the integration still works without the frontend.
        from homeassistant.components.frontend import add_extra_js_url
        from homeassistant.components.http import StaticPathConfig
        from homeassistant.loader import async_get_integration

        integration = await async_get_integration(hass, DOMAIN)
        frontend_dir = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL_BASE, str(frontend_dir), False)]
        )
        for script in FRONTEND_SCRIPTS:
            add_extra_js_url(hass, resource_url(str(integration.version), script))
    except Exception:  # noqa: BLE001 - dashboard support is optional
        _LOGGER.exception("Could not register the Ht HA dashboard strategy")
        return
    hass.data[DATA_FRONTEND_REGISTERED] = True
    for script in FRONTEND_SCRIPTS:
        try:
            await async_ensure_resource(hass, str(integration.version), script)
        except Exception:  # noqa: BLE001 - dashboard support is optional
            _LOGGER.exception("Could not add the Ht HA frontend resource %s", script)


async def async_setup_entry(hass: HomeAssistant, entry: HtHAConfigEntry) -> bool:
    """Set up Ht HA from a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        True if setup was successful
    """
    _LOGGER.info("Setting up %s config entry: %s", DOMAIN, entry.entry_id)

    # Get configuration from entry (data for initial config, options for user changes)
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    timeout = entry.data[CONF_TIMEOUT]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, entry.data[CONF_SCAN_INTERVAL])
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

    # Writes are read live from entry.data; only other config requires reload.
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "reload_config": _reload_config(entry),
    }

    from .schedule_services import setup_scratchpad

    await setup_scratchpad(hass, entry, coordinator)

    # Surface interrupted-write recovery even if the controller is unavailable.
    await coordinator.async_config_entry_first_refresh()

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


async def async_remove_entry(hass: HomeAssistant, entry: HtHAConfigEntry) -> None:
    """Clean up when a config entry is deleted.

    Frontend resources are removed together with the last entry, and only
    if Ht HA added them.
    """
    # Reload keeps the manager/library; permanent removal deletes only the
    # profile Store. Recovery evidence is retained for manual inspection.
    from homeassistant.helpers.storage import Store
    manager = hass.data.get(DOMAIN, {}).get("scratchpads", {}).get(entry.entry_id)
    if manager:
        async with manager.lock:
            await Store(hass, 1, f"{DOMAIN}_schedule_profiles_{entry.entry_id}").async_remove()
            hass.data[DOMAIN]["scratchpads"].pop(entry.entry_id, None)
    else:
        await Store(hass, 1, f"{DOMAIN}_schedule_profiles_{entry.entry_id}").async_remove()
    remaining = [e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id]
    if remaining:
        return
    for script in FRONTEND_SCRIPTS:
        try:
            await async_remove_resource(hass, script)
        except Exception:  # noqa: BLE001 - best effort cleanup
            _LOGGER.exception("Could not remove the Ht HA frontend resource %s", script)


def _reload_config(entry: HtHAConfigEntry) -> tuple[dict, dict]:
    """Snapshot all config except the live write permission (including nested values)."""
    return deepcopy((
        {key: value for key, value in entry.data.items() if key != CONF_WRITE_ENABLED},
        dict(entry.options),
    ))


async def async_update_options(hass: HomeAssistant, entry: HtHAConfigEntry) -> None:
    """Update options for a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry
    """
    state = hass.data[DOMAIN][entry.entry_id]
    config = _reload_config(entry)
    if state["reload_config"] != config:
        _LOGGER.info("Reloading changed configuration for %s", entry.entry_id)
        if await hass.config_entries.async_reload(entry.entry_id):
            state["reload_config"] = config
        return
    # Publish live permission changes to the scratchpad sensor/editor immediately.
    entry.runtime_data.async_update_listeners()


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
