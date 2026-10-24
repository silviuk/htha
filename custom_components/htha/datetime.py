"""Datetime platform for the Ht HA integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.datetime import (
    DateTimeEntity,
    DateTimeEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import HtHACoordinator
from . import HtHAConfigEntry

if TYPE_CHECKING:
    from datetime import datetime

_LOGGER = logging.getLogger(__name__)

HT_DATETIME_DESCRIPTION = DateTimeEntityDescription(
    key="ht_datetime",
    translation_key="ht_datetime",
    entity_category=EntityCategory.CONFIG,
    name="Heat Pump Date/Time",
)

_cached_datetime: datetime | None = None


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

    async_add_entities(
        [
            HtHADateTimeEntity(
                coordinator=coordinator,
                config_entry=config_entry,
                description=HT_DATETIME_DESCRIPTION,
            )
        ]
    )


def set_cached_datetime(value: datetime) -> None:
    """Update cached datetime (called by button)."""
    global _cached_datetime
    if value is not None and value.tzinfo is None:
        from homeassistant.util import dt as dt_util
        value = dt_util.as_local(value)
    _cached_datetime = value
    _LOGGER.debug("Cached datetime updated: %s", value)


class HtHADateTimeEntity(DateTimeEntity):
    """Datetime entity for heat pump date/time.

    This entity displays the heat pump's date and time.
    Updated manually via the sync button.
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
    def native_value(self) -> datetime | None:
        """Return the cached datetime value."""
        return _cached_datetime
