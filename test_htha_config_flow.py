"""Tests for the Ht HA integration config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.htha.const import DOMAIN, CONF_HOST, CONF_PORT, CONF_TIMEOUT, CONF_SCAN_INTERVAL


@pytest.fixture
def mock_heatpump_connection():
    """Mock heat pump connection for testing."""
    with patch("custom_components.htha.config_flow.AioHtHeatpump") as mock_hp:
        instance = MagicMock()
        instance.open_connection = MagicMock()
        instance.connect_async = AsyncMock()
        instance.login_async = AsyncMock()
        instance.logout_async = AsyncMock()
        instance.get_serial_number_async = AsyncMock(return_value=123456)
        instance.get_version_async = AsyncMock(return_value=("3.0.20", 2321))
        instance.is_open = False
        mock_hp.return_value = instance
        yield instance


class TestConfigFlow:
    """Test cases for config flow."""

    @pytest.mark.asyncio
    async def test_user_form(self, hass: HomeAssistant):
        """Test the user form is displayed."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert "host" in result["data_schema"].schema
        assert "port" in result["data_schema"].schema

    @pytest.mark.asyncio
    async def test_user_step_connection_success(
        self, hass: HomeAssistant, mock_heatpump_connection
    ):
        """Test successful connection in user step."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 9999,
                CONF_TIMEOUT: 10,
                CONF_SCAN_INTERVAL: 30,
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "write_protection"

    @pytest.mark.asyncio
    async def test_user_step_connection_failure(self, hass: HomeAssistant):
        """Test connection failure in user step."""
        with patch("custom_components.htha.config_flow.AioHtHeatpump") as mock_hp:
            instance = MagicMock()
            instance.open_connection = MagicMock()
            instance.connect_async = AsyncMock(side_effect=Exception("Connection failed"))
            mock_hp.return_value = instance

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "192.168.1.100",
                    CONF_PORT: 9999,
                    CONF_TIMEOUT: 10,
                    CONF_SCAN_INTERVAL: 30,
                },
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_write_protection_step(
        self, hass: HomeAssistant, mock_heatpump_connection
    ):
        """Test write protection step."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 9999,
                CONF_TIMEOUT: 10,
                CONF_SCAN_INTERVAL: 30,
            },
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"write_enabled": True},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Heat Pump 123456"
        assert result["data"]["host"] == "192.168.1.100"
        assert result["data"]["port"] == 9999
        assert result["data"]["write_enabled"] is True

    @pytest.mark.asyncio
    async def test_already_configured(
        self, hass: HomeAssistant, mock_heatpump_connection
    ):
        """Test that duplicate entries are rejected."""
        # First entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 9999,
                CONF_TIMEOUT: 10,
                CONF_SCAN_INTERVAL: 30,
            },
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"write_enabled": False},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY

        # Try to add duplicate
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 9999,
                CONF_TIMEOUT: 10,
                CONF_SCAN_INTERVAL: 30,
            },
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


class TestOptionsFlow:
    """Test cases for options flow."""

    @pytest.mark.asyncio
    async def test_options_flow(self, hass: HomeAssistant, mock_heatpump_connection):
        """Test options flow."""
        # Create config entry first
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 9999,
                CONF_TIMEOUT: 10,
                CONF_SCAN_INTERVAL: 30,
            },
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"write_enabled": False},
        )

        entry = result["result"]

        # Test options flow
        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"selected_params": ["Temp. Aussen", "Temp. Brauchwasser"]},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert "Temp. Aussen" in result["data"]["selected_params"]
