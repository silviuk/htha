"""Button platform for the Ht HA integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import HtHACoordinator
from . import HtHAConfigEntry

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)

HT_DATETIME_SYNC_DESCRIPTION = ButtonEntityDescription(
    key="ht_datetime_sync",
    translation_key="ht_datetime_sync",
    icon="mdi:clock-sync",
    name="Sync Heat Pump Date/Time",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HtHAConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ht HA button entities from a config entry.

    Args:
        hass: Home Assistant instance
        config_entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up Ht HA button entities")

    coordinator = config_entry.runtime_data

    async_add_entities(
        [
            HtHADateTimeSyncButton(
                coordinator=coordinator,
                config_entry=config_entry,
                description=HT_DATETIME_SYNC_DESCRIPTION,
            )
        ]
    )


class HtHADateTimeSyncButton(ButtonEntity):
    """Button entity to sync heat pump date/time.

    This button triggers a manual sync of the heat pump's date/time
    when pressed.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HtHACoordinator,
        config_entry: HtHAConfigEntry,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button.

        Args:
            coordinator: Data coordinator
            config_entry: Config entry
            description: Entity description
        """
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_datetime_sync"

        from homeassistant.helpers.entity import DeviceInfo
        from .const import DOMAIN
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(config_entry.entry_id))},
            name="Heliotherm Heat Pump",
            manufacturer="Heliotherm",
            model="Heat Pump",
            configuration_url=f"http://{coordinator.host}:{coordinator.port}",
        )

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info("Sync heat pump date/time button pressed")

        result = await self.coordinator.async_set_datetime()

        if result:
            _LOGGER.info("Heat pump date/time synced to: %s", result)
            from .datetime import set_cached_datetime
            set_cached_datetime(result)
        else:
            _LOGGER.warning("Failed to sync heat pump date/time")