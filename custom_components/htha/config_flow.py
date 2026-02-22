"""Config flow for the Ht HA integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from htheatpump import AioHtHeatpump

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SELECTED_PARAMS,
    CONF_TIMEOUT,
    CONF_WRITE_ENABLED,
    DEFAULT_PARAMS,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PARAM_CATEGORIES,
)

_LOGGER = logging.getLogger(__name__)


async def validate_connection(
    hass: HomeAssistant, host: str, port: int, timeout: int
) -> dict[str, Any]:
    """Validate connection to the heat pump.

    Args:
        hass: Home Assistant instance
        host: TCP host address
        port: TCP port number
        timeout: Connection timeout in seconds

    Returns:
        Dictionary with connection info

    Raises:
        Exception: If connection fails
    """
    heatpump = AioHtHeatpump(url=f"tcp://{host}:{port}", timeout=timeout)
    try:
        heatpump.open_connection()
        await heatpump.connect_async()
        await heatpump.login_async()

        # Get serial number and version for device info
        serial_number = await heatpump.get_serial_number_async()
        version, _ = await heatpump.get_version_async()

        await heatpump.logout_async()

        return {
            "serial_number": serial_number,
            "version": version,
        }
    except Exception as ex:
        _LOGGER.error("Connection validation failed: %s", ex)
        raise
    finally:
        if heatpump.is_open:
            await heatpump.logout_async()


class HtHAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ht HA integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._timeout: int = DEFAULT_TIMEOUT
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._write_enabled: bool = False
        self._device_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            self._timeout = user_input[CONF_TIMEOUT]
            self._scan_interval = user_input[CONF_SCAN_INTERVAL]

            try:
                self._device_info = await validate_connection(
                    self.hass, self._host, self._port, self._timeout
                )
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                # Check if already configured
                await self.async_set_unique_id(str(self._device_info.get("serial_number", "")))
                self._abort_if_unique_id_configured()

                return await self.async_step_write_protection()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): int,
                    vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                }
            ),
            errors=errors,
        )

    async def async_step_write_protection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the write protection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._write_enabled = user_input.get(CONF_WRITE_ENABLED, False)

            # Create the config entry
            return self.async_create_entry(
                title=f"Heat Pump {self._device_info.get('serial_number', self._host)}",
                data={
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_TIMEOUT: self._timeout,
                    CONF_SCAN_INTERVAL: self._scan_interval,
                    CONF_WRITE_ENABLED: self._write_enabled,
                },
                options={
                    CONF_SELECTED_PARAMS: DEFAULT_PARAMS,
                },
            )

        return self.async_show_form(
            step_id="write_protection",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_WRITE_ENABLED, default=False): bool,
                }
            ),
            description_placeholders={
                "warning": "Enabling writes allows changing heat pump settings. Use with caution!",
            },
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HtHAOptionsFlow:
        """Get the options flow for this handler."""
        return HtHAOptionsFlow(config_entry)


class HtHAOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Ht HA integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_SELECTED_PARAMS: user_input.get(CONF_SELECTED_PARAMS, DEFAULT_PARAMS),
                },
            )

        # Get current selected params
        current_params = self._config_entry.options.get(CONF_SELECTED_PARAMS, DEFAULT_PARAMS)

        # Build list of all available parameters
        all_params: list[str] = []
        for category_params in PARAM_CATEGORIES.values():
            all_params.extend(category_params)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SELECTED_PARAMS,
                        default=current_params,
                    ): cv.multi_select(all_params),
                }
            ),
        )
