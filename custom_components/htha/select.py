"""Select platform for the Ht HA integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from htheatpump import HtParams

from .const import (
    CONF_WRITE_ENABLED,
    OPERATING_MODES,
    PARAM_SELECT_METADATA,
    PARAM_TRANSLATION_KEYS,
)
from .coordinator import HtHACoordinator
from .entity import HtHASelectEntity
from . import HtHAConfigEntry

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HtHAConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ht HA select entities from a config entry.

    Args:
        hass: Home Assistant instance
        config_entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up Ht HA select entities")

    coordinator = config_entry.runtime_data

    # Check if writes are enabled
    write_enabled = config_entry.data.get(CONF_WRITE_ENABLED, False)

    # Get selected parameters from options
    selected_params = config_entry.options.get("selected_params", [])

    entities: list[HtHASelect] = []

    for param_name in selected_params:
        # Skip if not in HtParams
        if param_name not in HtParams:
            _LOGGER.warning("Parameter %s not found in HtParams", param_name)
            continue

        # Only include parameters that are in PARAM_SELECT_METADATA
        if param_name not in PARAM_SELECT_METADATA:
            continue

        # Note: We create the entity regardless of ACL.
        # The write_enabled flag controls whether changes are actually sent.
        # This allows displaying the current value even if the heat pump
        # reports the parameter as read-only.

        # Get metadata for this parameter
        metadata = PARAM_SELECT_METADATA.get(param_name, {})

        # Get translation key for this parameter
        translation_key = PARAM_TRANSLATION_KEYS.get(param_name)

        # Create entity description
        description = SelectEntityDescription(
            key=param_name,
            translation_key=translation_key,
            icon=metadata.get("icon", "mdi:home-automation"),
            options=metadata.get("options", list(OPERATING_MODES.values())),
        )

        entities.append(
            HtHASelect(
                coordinator=coordinator,
                config_entry=config_entry,
                description=description,
                param_name=param_name,
                write_enabled=write_enabled,
            )
        )

    _LOGGER.debug("Adding %d select entities", len(entities))
    async_add_entities(entities)


class HtHASelect(HtHASelectEntity, SelectEntity):
    """Select entity for Ht HA integration."""

    def __init__(
        self,
        coordinator: HtHACoordinator,
        config_entry: HtHAConfigEntry,
        description: SelectEntityDescription,
        param_name: str,
        write_enabled: bool,
    ) -> None:
        """Initialize the select entity.

        Args:
            coordinator: Data coordinator
            config_entry: Config entry
            description: Entity description
            param_name: Parameter name
            write_enabled: Whether writes are enabled
        """
        super().__init__(coordinator, config_entry, description, param_name)
        self._write_enabled = write_enabled

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self._param_name)
        if value is None:
            return None
        # Convert integer value to string option
        return OPERATING_MODES.get(int(value))

    async def async_select_option(self, option: str) -> None:
        """Select an option.

        Args:
            option: The option to select

        Raises:
            ValueError: If writes are not enabled
        """
        if not self._write_enabled:
            raise ValueError(
                "Writes are not enabled. Enable writes in the integration configuration."
            )

        # Find the integer value for the option
        for int_value, str_value in OPERATING_MODES.items():
            if str_value == option:
                await self.coordinator.async_set_param(self._param_name, int_value)
                return

        raise ValueError(f"Unknown option: {option}")
