"""Switch platform for the Ht HA integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_WRITE_ENABLED, DOMAIN
from .coordinator import HtHACoordinator
from . import HtHAConfigEntry

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HtHAConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ht HA switch entities from a config entry.

    Args:
        hass: Home Assistant instance
        config_entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up Ht HA switch entities")

    coordinator = config_entry.runtime_data

    # Create write protection switch
    description = SwitchEntityDescription(
        key="write_protection",
        name="Write Protection",
        icon="mdi:lock",
    )

    async_add_entities([
        HtHAWriteProtectionSwitch(
            coordinator=coordinator,
            config_entry=config_entry,
            description=description,
        )
    ])


class HtHAWriteProtectionSwitch(SwitchEntity):
    """Switch entity for write protection control."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HtHACoordinator,
        config_entry: HtHAConfigEntry,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch.

        Args:
            coordinator: Data coordinator
            config_entry: Config entry
            description: Entity description
        """
        self.coordinator = coordinator
        self.entity_description = description
        self._config_entry = config_entry

        # Set unique ID
        self._attr_unique_id = f"{config_entry.entry_id}_write_protection"

        # Set device info
        from homeassistant.helpers.entity import DeviceInfo
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(config_entry.entry_id))},
            name="Heliotherm Heat Pump",
            manufacturer="Heliotherm",
            model="Heat Pump",
            configuration_url=f"http://{coordinator.host}:{coordinator.port}",
        )

        # Initialize state from config
        self._attr_is_on = config_entry.data.get(CONF_WRITE_ENABLED, False)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on (enable writes).

        This requires user confirmation in a real implementation.
        For now, we just enable it directly.
        """
        _LOGGER.warning("Enabling writes to heat pump - use with caution!")
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off (disable writes)."""
        _LOGGER.info("Disabling writes to heat pump")
        self._attr_is_on = False
        self.async_write_ha_state()
