"""Number platform for the Ht HA integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from htheatpump import HtParams
from htheatpump.htparams import HtDataTypes

from .const import CONF_WRITE_ENABLED, PARAM_NUMBER_METADATA, PARAM_TRANSLATION_KEYS
from .coordinator import HtHACoordinator
from .entity import HtHANumberEntity
from . import HtHAConfigEntry

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


def _get_device_class(unit: str | None) -> NumberDeviceClass | None:
    """Get device class from unit string."""
    if unit in (UnitOfTemperature.CELSIUS, "°C", "K"):
        return NumberDeviceClass.TEMPERATURE
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HtHAConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ht HA number entities from a config entry.

    Args:
        hass: Home Assistant instance
        config_entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up Ht HA number entities")

    coordinator = config_entry.runtime_data

    # Check if writes are enabled
    write_enabled = config_entry.data.get(CONF_WRITE_ENABLED, False)

    # Get selected parameters from options
    selected_params = config_entry.options.get("selected_params", [])

    entities: list[HtHANumber] = []

    for param_name in selected_params:
        # Skip if not in HtParams
        if param_name not in HtParams:
            _LOGGER.warning("Parameter %s not found in HtParams", param_name)
            continue

        param = HtParams[param_name]

        # Only include numeric parameters
        if param.data_type == HtDataTypes.BOOL:
            continue

        # Skip if not in PARAM_NUMBER_METADATA
        if param_name not in PARAM_NUMBER_METADATA:
            continue

        # Note: We create the entity regardless of ACL.
        # The write_enabled flag controls whether changes are actually sent.
        # This allows displaying the current value even if the heat pump
        # reports the parameter as read-only.

        # Get metadata for this parameter
        metadata = PARAM_NUMBER_METADATA.get(param_name, {})

        # Get min/max from HtParams
        min_val = param.min_val if param.min_val is not None else 0
        max_val = param.max_val if param.max_val is not None else 100

        # Determine step based on data type
        step = metadata.get("step", 1 if param.data_type == HtDataTypes.INT else 0.5)

        # Get translation key for this parameter
        translation_key = PARAM_TRANSLATION_KEYS.get(param_name)

        # Create entity description
        description = NumberEntityDescription(
            key=param_name,
            translation_key=translation_key,
            device_class=_get_device_class(metadata.get("unit")),
            native_unit_of_measurement=metadata.get("unit"),
            icon=metadata.get("icon", "mdi:thermometer"),
            mode=NumberMode.BOX if metadata.get("mode") == "box" else NumberMode.AUTO,
        )

        entities.append(
            HtHANumber(
                coordinator=coordinator,
                config_entry=config_entry,
                description=description,
                param_name=param_name,
                native_min_value=float(min_val),
                native_max_value=float(max_val),
                native_step=float(step),
                write_enabled=write_enabled,
            )
        )

    _LOGGER.debug("Adding %d number entities", len(entities))
    async_add_entities(entities)


class HtHANumber(HtHANumberEntity, NumberEntity):
    """Number entity for Ht HA integration."""

    def __init__(
        self,
        coordinator: HtHACoordinator,
        config_entry: HtHAConfigEntry,
        description: NumberEntityDescription,
        param_name: str,
        native_min_value: float,
        native_max_value: float,
        native_step: float,
        write_enabled: bool,
    ) -> None:
        """Initialize the number entity.

        Args:
            coordinator: Data coordinator
            config_entry: Config entry
            description: Entity description
            param_name: Parameter name
            native_min_value: Minimum value
            native_max_value: Maximum value
            native_step: Step value
            write_enabled: Whether writes are enabled
        """
        super().__init__(coordinator, config_entry, description, param_name)

        self._attr_native_min_value = native_min_value
        self._attr_native_max_value = native_max_value
        self._attr_native_step = native_step
        self._write_enabled = write_enabled

    async def async_set_native_value(self, value: float) -> None:
        """Set new value.

        Args:
            value: The value to set

        Raises:
            ValueError: If writes are not enabled
        """
        if not self._write_enabled:
            raise ValueError(
                "Writes are not enabled. Enable writes in the integration configuration."
            )

        await self.coordinator.async_set_param(self._param_name, value)
