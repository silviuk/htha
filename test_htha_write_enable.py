"""Tests for the Ht HA write enablement logic."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.switch import SwitchEntityDescription

from custom_components.htha.const import CONF_WRITE_ENABLED, DOMAIN
from custom_components.htha.switch import HtHAWriteProtectionSwitch
from custom_components.htha.number import HtHANumber
from custom_components.htha.select import HtHASelect


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
        CONF_WRITE_ENABLED: False,
    }
    entry.options = {}
    return entry


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.host = "192.168.1.100"
    coordinator.port = 9999
    coordinator.async_set_param = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_write_protection_switch_flow(hass: HomeAssistant, mock_config_entry, mock_coordinator):
    """Test HtHAWriteProtectionSwitch confirmation flow and toggling."""
    description = SwitchEntityDescription(
        key="write_protection",
        translation_key="write_protection",
    )

    # Initialize switch
    switch = HtHAWriteProtectionSwitch(
        coordinator=mock_coordinator,
        config_entry=mock_config_entry,
        description=description,
    )
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()

    assert not switch.is_on
    assert not switch._confirm_pending

    # Call turn_on for the first time (sets confirm pending)
    with patch("homeassistant.core.ServiceRegistry.async_call", AsyncMock()) as mock_call:
        await switch.async_turn_on()
        assert not switch.is_on
        assert switch._confirm_pending
        mock_call.assert_called_once_with(
            "persistent_notification",
            "create",
            {
                "title": "Enable Settings Modification",
                "message": "WARNING: Enabling write access to your heat pump allows changing settings. "
                "Incorrect settings may cause equipment damage or system malfunction. "
                "Click the switch again within 10 seconds to confirm.",
                "notification_id": "htha_write_confirm",
            },
        )

    # Call turn_on again to confirm the action
    with patch("homeassistant.core.ServiceRegistry.async_call", AsyncMock()) as mock_call:
        # Simulate updating the config entry data in hass
        def side_effect(entry, data):
            mock_config_entry.data = data

        with patch.object(hass.config_entries, "async_update_entry", side_effect):
            await switch.async_turn_on()
            assert switch.is_on
            assert not switch._confirm_pending
            assert mock_config_entry.data[CONF_WRITE_ENABLED] is True
            mock_call.assert_called_once_with(
                "persistent_notification",
                "dismiss",
                {"notification_id": "htha_write_confirm"},
            )

    # Turn the switch off
    with patch.object(hass.config_entries, "async_update_entry", side_effect):
        await switch.async_turn_off()
        assert not switch.is_on
        assert mock_config_entry.data[CONF_WRITE_ENABLED] is False


@pytest.mark.asyncio
async def test_number_write_validation(mock_config_entry, mock_coordinator):
    """Test that number entity validates write enablement dynamically."""
    description = NumberEntityDescription(
        key="hkr_soll_raum",
    )

    number = HtHANumber(
        coordinator=mock_coordinator,
        config_entry=mock_config_entry,
        description=description,
        param_name="HKR Soll_Raum",
        native_min_value=15.0,
        native_max_value=25.0,
        native_step=0.5,
    )

    # Writes disabled -> expect ValueError
    mock_config_entry.data[CONF_WRITE_ENABLED] = False
    with pytest.raises(ValueError, match="Writes are not enabled"):
        await number.async_set_native_value(21.5)
    mock_coordinator.async_set_param.assert_not_called()

    # Writes enabled -> expect success
    mock_config_entry.data[CONF_WRITE_ENABLED] = True
    await number.async_set_native_value(21.5)
    mock_coordinator.async_set_param.assert_called_once_with("HKR Soll_Raum", 21.5)


@pytest.mark.asyncio
async def test_select_write_validation(mock_config_entry, mock_coordinator):
    """Test that select entity validates write enablement dynamically."""
    description = SelectEntityDescription(
        key="betriebsart",
        options=["off", "heating", "auto"],
    )

    select = HtHASelect(
        coordinator=mock_coordinator,
        config_entry=mock_config_entry,
        description=description,
        param_name="Betriebsart",
    )

    # Writes disabled -> expect ValueError
    mock_config_entry.data[CONF_WRITE_ENABLED] = False
    with pytest.raises(ValueError, match="Writes are not enabled"):
        await select.async_select_option("heating")
    mock_coordinator.async_set_param.assert_not_called()

    # Writes enabled -> expect success
    mock_config_entry.data[CONF_WRITE_ENABLED] = True
    await select.async_select_option("heating")
    # Heating maps to 1 in OPERATING_MODES
    mock_coordinator.async_set_param.assert_called_once_with("Betriebsart", 1)
