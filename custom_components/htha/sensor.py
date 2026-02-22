"""Sensor platform for the Ht HA integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from htheatpump import HtParams
from htheatpump.htparams import HtDataTypes

from .const import PARAM_SENSOR_METADATA, PARAM_TRANSLATION_KEYS
from .coordinator import HtHACoordinator
from .entity import HtHASensorEntity
from . import HtHAConfigEntry

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


def _get_device_class(unit: str | None) -> SensorDeviceClass | None:
    """Get device class from unit string."""
    if unit in (UnitOfTemperature.CELSIUS, "°C", "K"):
        return SensorDeviceClass.TEMPERATURE
    if unit in (UnitOfPressure.BAR, "bar"):
        return SensorDeviceClass.PRESSURE
    return None


def _get_state_class(state_class_str: str | None) -> SensorStateClass | None:
    """Get state class from string."""
    if state_class_str == "measurement":
        return SensorStateClass.MEASUREMENT
    if state_class_str == "total_increasing":
        return SensorStateClass.TOTAL_INCREASING
    if state_class_str == "total":
        return SensorStateClass.TOTAL
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HtHAConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ht HA sensor entities from a config entry.

    Args:
        hass: Home Assistant instance
        config_entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up Ht HA sensor entities")

    coordinator = config_entry.runtime_data

    # Get selected parameters from options
    selected_params = config_entry.options.get("selected_params", [])

    entities: list[HtHASensor] = []

    for param_name in selected_params:
        # Skip if not in HtParams
        if param_name not in HtParams:
            _LOGGER.warning("Parameter %s not found in HtParams", param_name)
            continue

        param = HtParams[param_name]

        # Skip boolean parameters (they go to binary_sensor)
        if param.data_type == HtDataTypes.BOOL:
            continue

        # Get metadata for this parameter
        metadata = PARAM_SENSOR_METADATA.get(param_name, {})

        # Get translation key for this parameter
        translation_key = PARAM_TRANSLATION_KEYS.get(param_name)

        # Create entity description
        description = SensorEntityDescription(
            key=param_name,
            translation_key=translation_key,
            device_class=_get_device_class(metadata.get("unit")),
            native_unit_of_measurement=metadata.get("unit"),
            state_class=_get_state_class(metadata.get("state_class")),
            icon=metadata.get("icon", "mdi:gauge"),
        )

        entities.append(
            HtHASensor(
                coordinator=coordinator,
                config_entry=config_entry,
                description=description,
                param_name=param_name,
            )
        )

    _LOGGER.debug("Adding %d sensor entities", len(entities))
    async_add_entities(entities)


class HtHASensor(HtHASensorEntity, SensorEntity):
    """Sensor entity for Ht HA integration."""

    def __init__(
        self,
        coordinator: HtHACoordinator,
        config_entry: HtHAConfigEntry,
        description: SensorEntityDescription,
        param_name: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data coordinator
            config_entry: Config entry
            description: Entity description
            param_name: Parameter name
        """
        super().__init__(coordinator, config_entry, description, param_name)
