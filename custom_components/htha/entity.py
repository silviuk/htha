"""Base entity classes for the Ht HA integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HtHACoordinator

if TYPE_CHECKING:
    from . import HtHAConfigEntry


class HtHAEntity(CoordinatorEntity[HtHACoordinator]):
    """Base entity for Ht HA integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HtHACoordinator,
        config_entry: HtHAConfigEntry,
        description: EntityDescription,
        param_name: str | None = None,
    ) -> None:
        """Initialize the entity.

        Args:
            coordinator: Data coordinator
            config_entry: Config entry
            description: Entity description
            param_name: Parameter name from heat pump (optional for special entities)
        """
        super().__init__(coordinator)
        self.entity_description = description
        self._param_name = param_name

        # Set unique ID based on parameter name or description key
        unique_key = param_name if param_name else description.key
        self._attr_unique_id = f"{config_entry.entry_id}_{unique_key}"

        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(config_entry.entry_id))},
            name="Heliotherm Heat Pump",
            manufacturer="Heliotherm",
            model="Heat Pump",
            configuration_url=f"http://{coordinator.host}:{coordinator.port}",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Special entities without param_name are always available
        if self._param_name is None:
            return super().available
        return (
            super().available
            and self.coordinator.data is not None
            and self._param_name in self.coordinator.data
        )

    @property
    def native_value(self):
        """Return the state of the entity."""
        if self._param_name is None:
            return None
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._param_name)


class HtHASensorEntity(HtHAEntity):
    """Base sensor entity for Ht HA integration."""

    pass


class HtHABinarySensorEntity(HtHAEntity):
    """Base binary sensor entity for Ht HA integration."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self._param_name)
        return bool(value) if value is not None else None


class HtHANumberEntity(HtHAEntity):
    """Base number entity for Ht HA integration."""

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self._param_name)
        if value is None:
            return None
        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.coordinator.async_set_param(self._param_name, value)


class HtHASelectEntity(HtHAEntity):
    """Base select entity for Ht HA integration."""

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self._param_name)
        if value is None:
            return None
        # Convert integer value to string option
        from .const import OPERATING_MODES
        return OPERATING_MODES.get(int(value))

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        from .const import OPERATING_MODES
        # Find the integer value for the option
        for int_value, str_value in OPERATING_MODES.items():
            if str_value == option:
                await self.coordinator.async_set_param(self._param_name, int_value)
                return
