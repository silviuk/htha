"""Datetime platform for the Ht HA integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.datetime import (
    DateTimeEntity,
    DateTimeEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import HtHACoordinator
from . import HtHAConfigEntry

if TYPE_CHECKING:
    from datetime import datetime

_LOGGER = logging.getLogger(__name__)

# Entity description for heat pump date/time
HT_DATETIME_DESCRIPTION = DateTimeEntityDescription(
    key="ht_datetime",
    translation_key="ht_datetime",
    icon="mdi:clock-outline",
    name="Heat Pump Date/Time",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HtHAConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ht HA datetime entities from a config entry.

    Args:
        hass: Home Assistant instance
        config_entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up Ht HA datetime entities")

    coordinator = config_entry.runtime_data

    # Add the heat pump date/time entity
    async_add_entities(
        [
            HtHADateTimeEntity(
                coordinator=coordinator,
                config_entry=config_entry,
                description=HT_DATETIME_DESCRIPTION,
            )
        ]
    )


class HtHADateTimeEntity(DateTimeEntity):
    """Datetime entity for heat pump date/time.

    This entity displays the heat pump's date and time.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HtHACoordinator,
        config_entry: HtHAConfigEntry,
        description: DateTimeEntityDescription,
    ) -> None:
        """Initialize the date/time entity.

        Args:
            coordinator: Data coordinator
            config_entry: Config entry
            description: Entity description
        """
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_datetime"
        self._attr_native_value: datetime | None = None

        # Set device info
        from homeassistant.helpers.entity import DeviceInfo
        from .const import DOMAIN
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(config_entry.entry_id))},
            name="Heliotherm Heat Pump",
            manufacturer="Heliotherm",
            model="Heat Pump",
            configuration_url=f"http://{coordinator.host}:{coordinator.port}",
        )

    @property
    def icon(self) -> str | None:
        """Return icon."""
        return "mdi:clock-outline"

    async def async_update(self) -> None:
        """Update the entity value."""
        _LOGGER.debug("Updating datetime entity")

        # Fetch datetime from heat pump
        result: datetime | None = await self.coordinator.async_get_datetime()

        if result:
            self._attr_native_value = result
            _LOGGER.info("Heat pump date/time: %s", result)
        else:
            _LOGGER.warning("Failed to get heat pump date/time - result was None")
