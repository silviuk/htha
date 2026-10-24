"""Sensor platform for the Ht HA integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from htheatpump import HtParams
from htheatpump.htparams import HtDataTypes

from .const import (
    DERIVED_HEATING_SPREAD,
    DERIVED_OPERATING_STATE,
    DERIVED_SOURCE_SPREAD,
    DIAGNOSTIC_SENSOR_PARAMS,
    OPERATING_STATES,
    PARAM_NUMBER_METADATA,
    PARAM_SELECT_METADATA,
    PARAM_SENSOR_METADATA,
    PARAM_TRANSLATION_KEYS,
    SENSOR_MIRROR_UNITS,
)
from .coordinator import HtHACoordinator
from .entity import HtHAEntity, HtHASensorEntity
from . import HtHAConfigEntry

_LOGGER = logging.getLogger(__name__)


def _get_device_class(unit: str | None) -> SensorDeviceClass | None:
    """Get device class from unit string."""
    if unit in (UnitOfTemperature.CELSIUS, "°C"):
        return SensorDeviceClass.TEMPERATURE
    if unit in (UnitOfTemperature.KELVIN, "K"):
        # Values in K are temperature differences (offsets, hystereses).
        return SensorDeviceClass.TEMPERATURE_DELTA
    if unit in (UnitOfPressure.BAR, "bar"):
        return SensorDeviceClass.PRESSURE
    if unit in (UnitOfTime.HOURS, "h"):
        return SensorDeviceClass.DURATION
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


def _get_precision(unit: str | None) -> int | None:
    """Get a sensible display precision for a unit."""
    if unit in ("°C", "K", "bar"):
        return 1
    if unit in ("h", "min", "s", "%"):
        return 0
    return None


def is_mirror_param(param_name: str) -> bool:
    """Return True if a sensor for this parameter mirrors a number/select."""
    return param_name in PARAM_NUMBER_METADATA or param_name in PARAM_SELECT_METADATA


def build_param_sensor_description(param_name: str) -> SensorEntityDescription:
    """Build the entity description for a non-boolean heat pump parameter."""
    metadata = PARAM_SENSOR_METADATA.get(param_name, {})
    unit = metadata.get("unit", SENSOR_MIRROR_UNITS.get(param_name))
    state_class = metadata.get("state_class")
    if state_class is None and unit in ("°C", "K"):
        state_class = "measurement"
    translation_key = PARAM_TRANSLATION_KEYS.get(param_name)
    mirror = is_mirror_param(param_name)

    entity_category = None
    if mirror or param_name in DIAGNOSTIC_SENSOR_PARAMS:
        entity_category = EntityCategory.DIAGNOSTIC

    return SensorEntityDescription(
        key=param_name,
        translation_key=translation_key,
        device_class=_get_device_class(unit),
        native_unit_of_measurement=unit,
        state_class=_get_state_class(state_class),
        suggested_display_precision=_get_precision(unit),
        # Icons come from icons.json; only fall back for unknown parameters.
        icon=None if translation_key else metadata.get("icon", "mdi:gauge"),
        entity_category=entity_category,
        # Read-only mirrors of controllable settings are redundant with the
        # number/select entity; only create them disabled for new installs.
        entity_registry_enabled_default=not mirror,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HtHAConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ht HA sensor entities from a config entry."""
    _LOGGER.debug("Setting up Ht HA sensor entities")

    coordinator = config_entry.runtime_data

    # Get selected parameters from options
    selected_params = config_entry.options.get("selected_params", [])

    entities: list[SensorEntity] = []

    for param_name in selected_params:
        # Skip if not in HtParams
        if param_name not in HtParams:
            _LOGGER.warning("Parameter %s not found in HtParams", param_name)
            continue

        param = HtParams[param_name]

        # Skip boolean parameters (they go to binary_sensor)
        if param.data_type == HtDataTypes.BOOL:
            continue

        entities.append(
            HtHASensor(
                coordinator=coordinator,
                config_entry=config_entry,
                description=build_param_sensor_description(param_name),
                param_name=param_name,
            )
        )

    # Create the special Time Programs sensor
    time_prog_description = SensorEntityDescription(
        key="time_programs",
        translation_key="time_programs",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    entities.append(
        HtHATimeProgramsSensor(
            coordinator=coordinator,
            config_entry=config_entry,
            description=time_prog_description,
        )
    )

    # Derived sensors, computed from parameters that are already polled.
    if "Verdichter" in selected_params:
        entities.append(
            HtHAOperatingStateSensor(
                coordinator=coordinator,
                config_entry=config_entry,
                description=SensorEntityDescription(
                    key=DERIVED_OPERATING_STATE,
                    translation_key=DERIVED_OPERATING_STATE,
                    device_class=SensorDeviceClass.ENUM,
                    options=OPERATING_STATES,
                ),
            )
        )
    for key, minuend, subtrahend in (
        (DERIVED_HEATING_SPREAD, "Temp. Vorlauf", "Temp. Ruecklauf"),
        (DERIVED_SOURCE_SPREAD, "Temp. EQ_Eintritt", "Temp. EQ_Austritt"),
    ):
        if minuend in selected_params and subtrahend in selected_params:
            entities.append(
                HtHATemperatureSpreadSensor(
                    coordinator=coordinator,
                    config_entry=config_entry,
                    description=SensorEntityDescription(
                        key=key,
                        translation_key=key,
                        device_class=SensorDeviceClass.TEMPERATURE_DELTA,
                        native_unit_of_measurement=UnitOfTemperature.KELVIN,
                        state_class=SensorStateClass.MEASUREMENT,
                        suggested_display_precision=1,
                    ),
                    minuend=minuend,
                    subtrahend=subtrahend,
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
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, description, param_name)


class HtHATimeProgramsSensor(HtHAEntity, SensorEntity):
    """Sensor entity to display time programs."""

    def __init__(
        self,
        coordinator: HtHACoordinator,
        config_entry: HtHAConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, description)

    @property
    def native_value(self) -> str | None:
        """Return the number of time programs as state."""
        if self.coordinator.time_programs is None:
            return None
        return str(len(self.coordinator.time_programs))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return time programs in extra attributes."""
        if self.coordinator.time_programs is None:
            return None
        # Format time programs in attributes
        return {
            "time_programs": self.coordinator.time_programs
        }


def compute_operating_state(data: dict[str, Any] | None) -> str | None:
    """Derive a human readable operating state from polled parameters."""
    if not data or data.get("Verdichter") is None:
        return None
    if data.get("Stoerung"):
        return "fault"
    if data.get("Hauptschalter") is not None and not data.get("Hauptschalter"):
        return "off"
    mode = data.get("Betriebsart")
    if mode is not None and int(mode) == 0:
        return "off"
    if data.get("Verdichter"):
        if data.get("Warmwasservorrang"):
            return "hot_water"
        if mode is not None and int(mode) == 2:
            return "cooling"
        return "heating"
    return "standby"


class HtHAOperatingStateSensor(HtHAEntity, SensorEntity):
    """What the heat pump is doing right now (derived)."""

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "Verdichter" in self.coordinator.data
        )

    @property
    def native_value(self) -> str | None:
        """Return the derived operating state."""
        return compute_operating_state(self.coordinator.data)


class HtHATemperatureSpreadSensor(HtHAEntity, SensorEntity):
    """Difference between two polled temperatures (derived)."""

    def __init__(
        self,
        coordinator: HtHACoordinator,
        config_entry: HtHAConfigEntry,
        description: SensorEntityDescription,
        minuend: str,
        subtrahend: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, description)
        self._minuend = minuend
        self._subtrahend = subtrahend

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        data = self.coordinator.data
        return (
            self.coordinator.last_update_success
            and data is not None
            and data.get(self._minuend) is not None
            and data.get(self._subtrahend) is not None
        )

    @property
    def native_value(self) -> float | None:
        """Return the temperature difference."""
        data = self.coordinator.data
        if not data:
            return None
        first = data.get(self._minuend)
        second = data.get(self._subtrahend)
        if first is None or second is None:
            return None
        return round(float(first) - float(second), 2)
