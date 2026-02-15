"""Tests for the Ht HA integration coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.htha.coordinator import HtHACoordinator
from custom_components.htha.const import DEFAULT_PARAMS


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "host": "192.168.1.100",
        "port": 9999,
        "timeout": 10,
        "scan_interval": 30,
    }
    entry.options = {
        "selected_params": DEFAULT_PARAMS,
    }
    return entry


@pytest.fixture
def mock_heatpump():
    """Create a mock heat pump instance."""
    heatpump = MagicMock()
    heatpump.is_open = False
    heatpump.open_connection = MagicMock()
    heatpump.connect_async = AsyncMock()
    heatpump.login_async = AsyncMock()
    heatpump.logout_async = AsyncMock()
    heatpump.fast_query_async = AsyncMock()
    heatpump.query_async = AsyncMock()
    heatpump.set_param_async = AsyncMock()
    return heatpump


class TestHtHACoordinator:
    """Test cases for HtHACoordinator."""

    @pytest.mark.asyncio
    async def test_coordinator_init(self, hass: HomeAssistant, mock_config_entry):
        """Test coordinator initialization."""
        coordinator = HtHACoordinator(
            hass,
            mock_config_entry,
            host="192.168.1.100",
            port=9999,
            timeout=10,
            scan_interval=30,
            selected_params=DEFAULT_PARAMS,
        )

        assert coordinator.host == "192.168.1.100"
        assert coordinator.port == 9999
        assert coordinator.timeout == 10
        assert coordinator.scan_interval == 30
        assert coordinator.selected_params == DEFAULT_PARAMS
        assert coordinator._heatpump is None
        assert not coordinator._connected

    @pytest.mark.asyncio
    async def test_categorize_params(self, hass: HomeAssistant, mock_config_entry):
        """Test parameter categorization."""
        coordinator = HtHACoordinator(
            hass,
            mock_config_entry,
            host="192.168.1.100",
            port=9999,
            timeout=10,
            scan_interval=30,
            selected_params=["Temp. Aussen", "Betriebsart"],
        )

        # Temp. Aussen is MP type, Betriebsart is SP type
        assert "Temp. Aussen" in coordinator._mp_params
        assert "Betriebsart" in coordinator._sp_params

    @pytest.mark.asyncio
    async def test_async_update_data_success(
        self, hass: HomeAssistant, mock_config_entry, mock_heatpump
    ):
        """Test successful data update."""
        coordinator = HtHACoordinator(
            hass,
            mock_config_entry,
            host="192.168.1.100",
            port=9999,
            timeout=10,
            scan_interval=30,
            selected_params=["Temp. Aussen"],
        )

        # Mock the heat pump
        with patch(
            "custom_components.htha.coordinator.AioHtHeatpump",
            return_value=mock_heatpump,
        ):
            mock_heatpump.fast_query_async.return_value = {"Temp. Aussen": 15.5}

            data = await coordinator._async_update_data()

            assert data == {"Temp. Aussen": 15.5}
            mock_heatpump.open_connection.assert_called_once()
            mock_heatpump.connect_async.assert_called_once()
            mock_heatpump.login_async.assert_called_once()
            mock_heatpump.fast_query_async.assert_called_once()
            mock_heatpump.logout_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_data_connection_failure(
        self, hass: HomeAssistant, mock_config_entry, mock_heatpump
    ):
        """Test data update with connection failure."""
        coordinator = HtHACoordinator(
            hass,
            mock_config_entry,
            host="192.168.1.100",
            port=9999,
            timeout=10,
            scan_interval=30,
            selected_params=["Temp. Aussen"],
        )

        with patch(
            "custom_components.htha.coordinator.AioHtHeatpump",
            return_value=mock_heatpump,
        ):
            mock_heatpump.connect_async.side_effect = Exception("Connection failed")

            with pytest.raises(UpdateFailed):
                await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_async_set_param(
        self, hass: HomeAssistant, mock_config_entry, mock_heatpump
    ):
        """Test setting a parameter value."""
        coordinator = HtHACoordinator(
            hass,
            mock_config_entry,
            host="192.168.1.100",
            port=9999,
            timeout=10,
            scan_interval=30,
            selected_params=["HKR Soll_Raum"],
        )

        with patch(
            "custom_components.htha.coordinator.AioHtHeatpump",
            return_value=mock_heatpump,
        ):
            mock_heatpump.set_param_async.return_value = 21.5

            result = await coordinator.async_set_param("HKR Soll_Raum", 21.5)

            assert result == 21.5
            mock_heatpump.set_param_async.assert_called_once_with("HKR Soll_Raum", 21.5)

    @pytest.mark.asyncio
    async def test_async_shutdown(self, hass: HomeAssistant, mock_config_entry, mock_heatpump):
        """Test coordinator shutdown."""
        coordinator = HtHACoordinator(
            hass,
            mock_config_entry,
            host="192.168.1.100",
            port=9999,
            timeout=10,
            scan_interval=30,
            selected_params=DEFAULT_PARAMS,
        )

        with patch(
            "custom_components.htha.coordinator.AioHtHeatpump",
            return_value=mock_heatpump,
        ):
            # Simulate a connected state
            coordinator._heatpump = mock_heatpump
            coordinator._connected = True

            await coordinator.async_shutdown()

            mock_heatpump.logout_async.assert_called_once()
            assert coordinator._heatpump is None
            assert not coordinator._connected
