"""Register bundled frontend modules as Lovelace resources.

Each module is also loaded through ``add_extra_js_url``. Registering
it as a (storage mode) Lovelace resource as well means dashboards load it
through the same path as any other custom card, after the frontend has
finished booting. The resource is only created if no resource for the
module exists yet, its version query is kept up to date, and it is only
removed again (when the last Ht HA entry is deleted) if Ht HA created it.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, FRONTEND_SCRIPT, FRONTEND_URL_BASE

_LOGGER = logging.getLogger(__name__)

RESOURCE_PATH = f"{FRONTEND_URL_BASE}/{FRONTEND_SCRIPT}"
STORE_KEY = f"{DOMAIN}.lovelace_resource"
STORE_VERSION = 1


def resource_url(version: str, script: str = FRONTEND_SCRIPT) -> str:
    """Return the versioned (cache busting) URL of a bundled module."""
    return f"{FRONTEND_URL_BASE}/{script}?v={version}"


def _store(hass: HomeAssistant, script: str = FRONTEND_SCRIPT) -> Store[dict[str, Any]]:
    # Preserve ownership recorded by versions that only loaded the strategy.
    key = STORE_KEY if script == FRONTEND_SCRIPT else f"{STORE_KEY}.{script}"
    return Store(hass, STORE_VERSION, key)


def _resources(hass: HomeAssistant) -> Any | None:
    """Return the storage mode resource collection, or None."""
    data = hass.data.get("lovelace")
    if data is None:
        return None
    resources = getattr(data, "resources", None)
    if resources is None and isinstance(data, dict):
        resources = data.get("resources")
    if resources is None or not hasattr(resources, "async_create_item"):
        # YAML mode resources (read only) or an unknown layout.
        return None
    return resources


async def _loaded(resources: Any) -> Any:
    if not getattr(resources, "loaded", True):
        await resources.async_load()
        resources.loaded = True
    return resources


def _ours(item: dict[str, Any], script: str = FRONTEND_SCRIPT) -> bool:
    return str(item.get("url", "")).split("?", 1)[0] == f"{FRONTEND_URL_BASE}/{script}"


async def async_ensure_resource(
    hass: HomeAssistant, version: str, script: str = FRONTEND_SCRIPT,
) -> None:
    """Create or update the Lovelace resource for a bundled module."""
    if "lovelace" not in hass.config.components:
        if hass.is_running:
            _LOGGER.debug("Lovelace not loaded, not adding a dashboard resource")
            return

        async def _later(_event: Event) -> None:
            await async_ensure_resource(hass, version, script)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _later)
        return

    resources = _resources(hass)
    if resources is None:
        _LOGGER.info(
            "Lovelace resources are managed in YAML; add %s (type: module) "
            "manually if required for the Ht HA frontend",
            resource_url(version, script),
        )
        return
    await _loaded(resources)
    url = resource_url(version, script)
    existing = [item for item in resources.async_items() if _ours(item, script)]
    for item in existing:
        if item.get("url") != url or item.get("type") != "module":
            await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
            _LOGGER.info("Updated dashboard resource %s", url)
    if existing:
        return
    item = await resources.async_create_item({"res_type": "module", "url": url})
    await _store(hass, script).async_save({"resource_id": item["id"]})
    _LOGGER.info("Added dashboard resource %s", url)


async def async_remove_resource(hass: HomeAssistant, script: str = FRONTEND_SCRIPT) -> None:
    """Remove the Lovelace resource, but only if Ht HA created it."""
    store = _store(hass, script)
    data = await store.async_load() or {}
    resource_id = data.get("resource_id")
    if not resource_id:
        return
    resources = _resources(hass)
    if resources is not None:
        await _loaded(resources)
        if any(
            item.get("id") == resource_id and _ours(item, script)
            for item in resources.async_items()
        ):
            await resources.async_delete_item(resource_id)
            _LOGGER.info("Removed dashboard resource %s", f"{FRONTEND_URL_BASE}/{script}")
    await store.async_remove()
