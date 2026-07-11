"""Data update coordinator for the Ht HA integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from htheatpump import AioHtHeatpump, HtParams
from htheatpump.htparams import HtParamValueType

from .const import DOMAIN

if TYPE_CHECKING:
    from . import HtHAConfigEntry

_LOGGER = logging.getLogger(__name__)


class HtHACoordinator(DataUpdateCoordinator[dict[str, HtParamValueType]]):
    """Coordinator for Ht HA integration.

    Manages the connection to the heat pump and polls for parameter values.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HtHAConfigEntry,
        host: str,
        port: int,
        timeout: int,
        scan_interval: int,
        selected_params: list[str],
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            config_entry: Config entry instance
            host: TCP host address
            port: TCP port number
            timeout: Connection timeout in seconds
            scan_interval: Polling interval in seconds
            selected_params: List of parameter names to poll
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=scan_interval),
        )

        self.host = host
        self.port = port
        self.timeout = timeout
        self.scan_interval = scan_interval
        self.selected_params = selected_params
        self._heatpump: AioHtHeatpump | None = None
        self._connected = False
        self._connection_lock = asyncio.Lock()

        # Track parameters that consistently fail
        self._failed_params: set[str] = set()

        # Cache for time programs
        self.time_programs: list[dict] | None = None
        self._last_time_programs_update: float = 0

        # Separate parameters by type for efficient querying
        self._mp_params: list[str] = []
        self._sp_params: list[str] = []
        self._categorize_params()

    def _categorize_params(self) -> None:
        """Categorize parameters into MP (fast query) and SP types."""
        for param_name in self.selected_params:
            if param_name in HtParams:
                param = HtParams[param_name]  # type: ignore
                if param.dp_type == "MP":
                    self._mp_params.append(param_name)
                else:
                    self._sp_params.append(param_name)
            else:
                _LOGGER.warning("Unknown parameter: %s", param_name)

        _LOGGER.debug(
            "Categorized params - MP: %s, SP: %s",
            self._mp_params,
            self._sp_params,
        )

    @property
    def heatpump(self) -> AioHtHeatpump | None:
        """Return the heat pump instance."""
        return self._heatpump

    @property
    def is_connected(self) -> bool:
        """Return whether we have an active connection."""
        return self._connected

    async def _connect(self) -> None:
        """Establish connection to the heat pump.
        
        Must be called under self._connection_lock.
        """
        if self._heatpump is None:
            if self.host.startswith("/") or self.host.upper().startswith("COM") or "/" in self.host or "\\" in self.host:
                # Serial connection: host is device path, port is baudrate
                _LOGGER.debug("Initializing serial AioHtHeatpump on %s at %d baud", self.host, self.port)
                self._heatpump = AioHtHeatpump(
                    device=self.host,
                    baudrate=self.port,
                    timeout=self.timeout,
                )
            else:
                # TCP connection
                _LOGGER.debug("Initializing TCP AioHtHeatpump on tcp://%s:%d", self.host, self.port)
                self._heatpump = AioHtHeatpump(
                    url=f"tcp://{self.host}:{self.port}",
                    timeout=self.timeout,
                )

        if not self._connected or not self._heatpump.is_open:
            try:
                self._heatpump.open_connection()
                await self._heatpump.connect_async()
                await self._heatpump.login_async()
                self._connected = True
                _LOGGER.info(
                    "Connected to heat pump at %s (port/baud: %s)", self.host, self.port
                )
            except Exception as ex:
                self._connected = False
                _LOGGER.error("Failed to connect to heat pump: %s", ex)
                raise

    async def _disconnect(self) -> None:
        """Disconnect from the heat pump.
        
        Must be called under self._connection_lock.
        """
        if self._heatpump is not None and (self._connected or self._heatpump.is_open):
            try:
                await self._heatpump.logout_async()
                _LOGGER.info("Disconnected from heat pump")
            except Exception as ex:
                _LOGGER.warning("Error during disconnect: %s", ex)
            finally:
                self._connected = False

    async def _async_update_data(self) -> dict[str, HtParamValueType]:
        """Fetch data from the heat pump.

        Returns:
            Dictionary mapping parameter names to their values.
        """
        data: dict[str, HtParamValueType] = {}
        mp_fallback_used = False  # Track if we used the fallback method

        async with self._connection_lock:
            try:
                # Ensure we're connected
                await self._connect()

                if self._heatpump is None:
                    raise UpdateFailed("Heat pump instance not initialized")

                # Query MP parameters using fast_query_async for efficiency
                if self._mp_params:
                    try:
                        _LOGGER.debug(
                            "Querying MP parameters: %s", self._mp_params
                        )
                        mp_values = await self._heatpump.fast_query_async(
                            *self._mp_params
                        )
                        data.update(mp_values)
                    except ValueError as ex:
                        if "bytes must be in range" in str(ex):
                            _LOGGER.debug(
                                "fast_query_async failed with protocol error '%s', "
                                "falling back to query_async for MP parameters",
                                ex,
                            )
                            # Close the broken connection and reconnect
                            await self._disconnect()
                            await self._connect()
                            
                            # Fall back to querying MP parameters using query_async
                            for param in self._mp_params:
                                try:
                                    value = await self._heatpump.query_async(param)
                                    data.update(value)
                                except Exception as inner_ex:
                                    _LOGGER.warning(
                                        "Failed to query MP parameter '%s': %s",
                                        param,
                                        inner_ex,
                                    )
                            mp_fallback_used = True
                        else:
                            raise
                    except Exception as ex:
                        _LOGGER.error(
                            "Failed to query MP parameters: %s. Params: %s",
                            ex,
                            self._mp_params,
                        )
                        # Try querying individually to identify problematic parameter
                        for param in self._mp_params:
                            try:
                                value = await self._heatpump.fast_query_async(param)
                                data.update(value)
                            except Exception as inner_ex:
                                _LOGGER.warning(
                                    "Failed to query MP parameter '%s': %s",
                                    param,
                                    inner_ex,
                                )
                        # Don't raise here, try to get SP params too

                # Query SP parameters using regular query_async
                # Only if we haven't already queried MP params via fallback
                if self._sp_params and not mp_fallback_used:
                    try:
                        _LOGGER.debug(
                            "Querying SP parameters: %s", self._sp_params
                        )
                        sp_values = await self._heatpump.query_async(*self._sp_params)
                        data.update(sp_values)
                    except Exception as ex:
                        _LOGGER.error(
                            "Failed to query SP parameters: %s. Params: %s",
                            ex,
                            self._sp_params,
                        )
                        # Try querying individually
                        for param in self._sp_params:
                            try:
                                value = await self._heatpump.query_async(param)
                                data.update(value)
                            except Exception as inner_ex:
                                _LOGGER.warning(
                                    "Failed to query SP parameter '%s': %s",
                                    param,
                                    inner_ex,
                                )
                elif self._sp_params and mp_fallback_used:
                    # Already have a connection, query SP params too
                    try:
                        _LOGGER.debug(
                            "Querying SP parameters (after MP fallback): %s",
                            self._sp_params,
                        )
                        sp_values = await self._heatpump.query_async(*self._sp_params)
                        data.update(sp_values)
                    except Exception as ex:
                        _LOGGER.error(
                            "Failed to query SP parameters: %s. Params: %s",
                            ex,
                            self._sp_params,
                        )
                        # Try querying individually
                        for param in self._sp_params:
                            try:
                                value = await self._heatpump.query_async(param)
                                data.update(value)
                            except Exception as inner_ex:
                                _LOGGER.warning(
                                    "Failed to query SP parameter '%s': %s",
                                    param,
                                    inner_ex,
                                )

                # Periodically update time program schedule cache (once per hour)
                now_ts = asyncio.get_running_loop().time()
                if self.time_programs is None or (now_ts - self._last_time_programs_update) > 3600:
                    try:
                        _LOGGER.debug("Fetching detailed time programs from heat pump")
                        progs = await self._heatpump.get_time_progs_async()
                        detailed_progs = []
                        for prog in progs:
                            detailed = await self._heatpump.get_time_prog_async(prog.index, with_entries=True)
                            detailed_progs.append(detailed.as_json())
                        self.time_programs = detailed_progs
                        self._last_time_programs_update = now_ts
                    except Exception as prog_ex:
                        _LOGGER.warning("Failed to fetch time programs: %s", prog_ex)

                if not data:
                    raise UpdateFailed("No data received from heat pump")

                _LOGGER.debug("Retrieved %d parameter values", len(data))
                return data

            except UpdateFailed:
                raise
            except Exception as ex:
                self._connected = False
                raise UpdateFailed(f"Error communicating with heat pump: {ex}") from ex
            finally:
                # Always close the connection after each poll/attempt
                await self._disconnect()

    async def async_set_param(self, name: str, value: HtParamValueType) -> HtParamValueType:
        """Set a parameter value on the heat pump.

        Args:
            name: Parameter name
            value: Value to set

        Returns:
            The actual value set (may differ from requested value)

        Raises:
            UpdateFailed: If communication fails
        """
        async with self._connection_lock:
            try:
                # Ensure we're connected
                await self._connect()

                if self._heatpump is None:
                    raise UpdateFailed("Heat pump instance not initialized")

                result = await self._heatpump.set_param_async(name, value)
                _LOGGER.info("Set parameter %s to %s (result: %s)", name, value, result)

                # Update local data
                if self.data is None:
                    self.data = {}
                self.data[name] = result
                self.async_update_listeners()

                return result

            except Exception as ex:
                self._connected = False
                raise UpdateFailed(f"Failed to set parameter {name}: {ex}") from ex
            finally:
                # Always disconnect after write
                await self._disconnect()

    async def async_get_datetime(self) -> datetime | None:
        """Fetch the heat pump's date/time.

        Returns:
            The heat pump's date/time, or None if unavailable.
        """
        _LOGGER.debug("Starting async_get_datetime")
        async with self._connection_lock:
            try:
                await self._connect()

                if self._heatpump is None:
                    _LOGGER.error("Heat pump instance not initialized")
                    return None

                _LOGGER.debug("Calling get_date_time_async on heat pump")
                # get_date_time_async returns tuple (datetime, weekday)
                ht_datetime, _ = await self._heatpump.get_date_time_async()
                _LOGGER.debug("Heat pump date/time: %s", ht_datetime)

                return ht_datetime

            except Exception as ex:
                self._connected = False
                _LOGGER.error("Failed to get heat pump date/time: %s", ex, exc_info=True)
                return None
            finally:
                # Always disconnect after query
                await self._disconnect()

    async def async_set_datetime(
        self, dt: datetime | None = None
    ) -> datetime | None:
        """Set the heat pump's date/time.

        Args:
            dt: The datetime to set. If None, uses current system time.

        Returns:
            The heat pump's date/time after setting, or None on failure.
        """
        async with self._connection_lock:
            try:
                await self._connect()

                if self._heatpump is None:
                    _LOGGER.error("Heat pump instance not initialized")
                    return None

                if dt is None:
                    dt = dt_util.now()

                # set_date_time_async returns tuple (datetime, weekday)
                ht_datetime, _ = await self._heatpump.set_date_time_async(dt)
                _LOGGER.info("Set heat pump date/time to: %s", ht_datetime)

                return ht_datetime

            except Exception as ex:
                self._connected = False
                _LOGGER.error("Failed to set heat pump date/time: %s", ex)
                return None
            finally:
                # Always disconnect after write
                await self._disconnect()

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        async with self._connection_lock:
            await self._disconnect()
            self._heatpump = None
        await super().async_shutdown()
