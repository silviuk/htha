"""Sensor platform for the Ht HA integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
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
from homeassistant.helpers.event import async_track_time_interval

from htheatpump import HtParams
from htheatpump.htparams import HtDataTypes

from .const import PARAM_SENSOR_METADATA, PARAM_TRANSLATION_KEYS
from .coordinator import HtHACoordinator
from .entity import HtHAEntity, HtHASensorEntity
from . import HtHAConfigEntry

if TYPE_CHECKING:
    from datetime import datetime

_LOGGER = logging.getLogger(__name__)

# Update interval for the date/time sensor (separate from coordinator)
DATETIME_UPDATE_INTERVAL = timedelta(minutes=5)

# Entity description for heat pump date/time
HT_DATETIME_DESCRIPTION = SensorEntityDescription(
    key="ht_datetime",
    translation_key="ht_datetime",
    device_class=SensorDeviceClass.TIMESTAMP,
    icon="mdi:clock-outline",
)


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

    # Add the heat pump date/time sensor
    entities.append(
        HtHADateTimeSensor(
            coordinator=coordinator,
            config_entry=config_entry,
            description=HT_DATETIME_DESCRIPTION,
        )
    )

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


class HtHADateTimeSensor(HtHAEntity, SensorEntity):
    """Sensor entity for heat pump date/time.

    This sensor updates independently from the coordinator's polling cycle
    to avoid connection conflicts. The heat pump has limited connection
    slots, so we use a separate update interval.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HtHACoordinator,
        config_entry: HtHAConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the date/time sensor.

        Args:
            coordinator: Data coordinator
            config_entry: Config entry
            description: Entity description
        """
        super().__init__(coordinator, config_entry, description)
        self._attr_native_value: datetime | None = None
        self._unsub_interval: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Set up periodic updates when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        # Fetch initial value
        await self._async_update_datetime()

        # Schedule periodic updates
        self._unsub_interval = async_track_time_interval(
            self.hass,
            self._async_update_datetime,
            DATETIME_UPDATE_INTERVAL,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed from Home Assistant."""
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None
        await super().async_will_remove_from_hass()

    async def _async_update_datetime(
        self, now: datetime | None = None
    ) -> None:
        """Fetch the heat pump date/time.

        Args:
            now: Current time (provided by async_track_time_interval).
        """
        self._attr_native_value = await self.coordinator.async_get_datetime()
        self.async_write_ha_state()
