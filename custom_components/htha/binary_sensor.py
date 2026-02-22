"""Binary sensor platform for the Ht HA integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from htheatpump import HtParams
from htheatpump.htparams import HtDataTypes

from .const import PARAM_BINARY_SENSOR_METADATA, PARAM_TRANSLATION_KEYS
from .coordinator import HtHACoordinator
from .entity import HtHABinarySensorEntity
from . import HtHAConfigEntry

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


def _get_device_class(device_class_str: str | None) -> BinarySensorDeviceClass | None:
    """Get device class from string."""
    if device_class_str == "problem":
        return BinarySensorDeviceClass.PROBLEM
    if device_class_str == "running":
        return BinarySensorDeviceClass.RUNNING
    if device_class_str == "power":
        return BinarySensorDeviceClass.POWER
    if device_class_str == "connectivity":
        return BinarySensorDeviceClass.CONNECTIVITY
    if device_class_str == "heat":
        return BinarySensorDeviceClass.HEAT
    if device_class_str == "cold":
        return BinarySensorDeviceClass.COLD
    if device_class_str == "motion":
        return BinarySensorDeviceClass.MOTION
    if device_class_str == "door":
        return BinarySensorDeviceClass.DOOR
    if device_class_str == "plug":
        return BinarySensorDeviceClass.PLUG
    if device_class_str == "window":
        return BinarySensorDeviceClass.WINDOW
    if device_class_str == "lock":
        return BinarySensorDeviceClass.LOCK
    if device_class_str == "opening":
        return BinarySensorDeviceClass.OPENING
    if device_class_str == "smoke":
        return BinarySensorDeviceClass.SMOKE
    if device_class_str == "sound":
        return BinarySensorDeviceClass.SOUND
    if device_class_str == "vibration":
        return BinarySensorDeviceClass.VIBRATION
    if device_class_str == "battery":
        return BinarySensorDeviceClass.BATTERY
    if device_class_str == "battery_charging":
        return BinarySensorDeviceClass.BATTERY_CHARGING
    if device_class_str == "gas":
        return BinarySensorDeviceClass.GAS
    if device_class_str == "light":
        return BinarySensorDeviceClass.LIGHT
    if device_class_str == "moisture":
        return BinarySensorDeviceClass.MOISTURE
    if device_class_str == "moving":
        return BinarySensorDeviceClass.MOVING
    if device_class_str == "occupancy":
        return BinarySensorDeviceClass.OCCUPANCY
    if device_class_str == "presence":
        return BinarySensorDeviceClass.PRESENCE
    if device_class_str == "safety":
        return BinarySensorDeviceClass.SAFETY
    if device_class_str == "safety":
        return BinarySensorDeviceClass.SAFETY
    if device_class_str == "tamper":
        return BinarySensorDeviceClass.TAMPER
    if device_class_str == "update":
        return BinarySensorDeviceClass.UPDATE
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HtHAConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ht HA binary sensor entities from a config entry.

    Args:
        hass: Home Assistant instance
        config_entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up Ht HA binary sensor entities")

    coordinator = config_entry.runtime_data

    # Get selected parameters from options
    selected_params = config_entry.options.get("selected_params", [])

    entities: list[HtHABinarySensor] = []

    for param_name in selected_params:
        # Skip if not in HtParams
        if param_name not in HtParams:
            _LOGGER.warning("Parameter %s not found in HtParams", param_name)
            continue

        param = HtParams[param_name]

        # Only include boolean parameters
        if param.data_type != HtDataTypes.BOOL:
            continue

        # Get metadata for this parameter
        metadata = PARAM_BINARY_SENSOR_METADATA.get(param_name, {})

        # Get translation key for this parameter
        translation_key = PARAM_TRANSLATION_KEYS.get(param_name)

        # Create entity description
        description = BinarySensorEntityDescription(
            key=param_name,
            translation_key=translation_key,
            device_class=_get_device_class(metadata.get("device_class")),
            icon=metadata.get("icon_off", "mdi:toggle-switch-off"),
        )

        entities.append(
            HtHABinarySensor(
                coordinator=coordinator,
                config_entry=config_entry,
                description=description,
                param_name=param_name,
            )
        )

    _LOGGER.debug("Adding %d binary sensor entities", len(entities))
    async_add_entities(entities)


class HtHABinarySensor(HtHABinarySensorEntity, BinarySensorEntity):
    """Binary sensor entity for Ht HA integration."""

    def __init__(
        self,
        coordinator: HtHACoordinator,
        config_entry: HtHAConfigEntry,
        description: BinarySensorEntityDescription,
        param_name: str,
    ) -> None:
        """Initialize the binary sensor.

        Args:
            coordinator: Data coordinator
            config_entry: Config entry
            description: Entity description
            param_name: Parameter name
        """
        super().__init__(coordinator, config_entry, description, param_name)

        # Store icons for on/off states
        metadata = PARAM_BINARY_SENSOR_METADATA.get(param_name, {})
        self._icon_on = metadata.get("icon_on", "mdi:toggle-switch")
        self._icon_off = metadata.get("icon_off", "mdi:toggle-switch-off")

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend."""
        if self.is_on:
            return self._icon_on
        return self._icon_off
