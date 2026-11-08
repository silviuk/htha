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
from custom_components.htha import async_setup_entry, async_update_options
from custom_components.htha.coordinator import HtHACoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed


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
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    with (
        patch("custom_components.htha.HtHACoordinator", return_value=mock_coordinator),
        patch("custom_components.htha.schedule_services.setup_scratchpad", AsyncMock()),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        await async_setup_entry(hass, mock_config_entry)
    reload = AsyncMock(return_value=True)

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
            mock_coordinator.async_update_listeners.assert_called_once()
            with patch.object(hass.config_entries, "async_reload", reload):
                await async_update_options(hass, mock_config_entry)
            reload.assert_not_called()
            mock_call.assert_called_once_with(
                "persistent_notification",
                "dismiss",
                {"notification_id": "htha_write_confirm"},
            )

    # Turn the switch off
    mock_coordinator.async_update_listeners.reset_mock()
    with patch.object(hass.config_entries, "async_update_entry", side_effect):
        await switch.async_turn_off()
        assert not switch.is_on
        assert mock_config_entry.data[CONF_WRITE_ENABLED] is False
        mock_coordinator.async_update_listeners.assert_called_once()
        with patch.object(hass.config_entries, "async_reload", reload):
            await async_update_options(hass, mock_config_entry)
        reload.assert_not_called()
        assert "write_enabled" not in hass.data[DOMAIN][mock_config_entry.entry_id]


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


@pytest.mark.parametrize(("section", "key", "value"), [
    ("data", "host", "localhost"),
    ("data", "port", 10000),
    ("data", "timeout", 20),
    ("data", "scan_interval", 60),
    ("data", "selected_params", ["Betriebsart"]),
    ("options", "scan_interval", 60),
    ("options", "selected_params", ["Betriebsart"]),
    ("options", "model", "Other model"),
    ("options", CONF_WRITE_ENABLED, True),
])
async def test_configuration_changes_still_reload(
    hass, mock_config_entry, mock_coordinator, section, key, value
):
    """Setup snapshots all data except write permission, and every option."""
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    with (
        patch("custom_components.htha.HtHACoordinator", return_value=mock_coordinator),
        patch("custom_components.htha.schedule_services.setup_scratchpad", AsyncMock()),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        await async_setup_entry(hass, mock_config_entry)
    with patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)) as reload:
        await async_update_options(hass, mock_config_entry)
        reload.assert_not_called()
        getattr(mock_config_entry, section)[key] = value
        # A simultaneous write toggle must not hide configuration changes.
        mock_config_entry.data[CONF_WRITE_ENABLED] = True
        await async_update_options(hass, mock_config_entry)
        reload.assert_awaited_once_with(mock_config_entry.entry_id)
        await async_update_options(hass, mock_config_entry)
        reload.assert_awaited_once()


async def test_reload_snapshot_copies_nested_options(hass, mock_config_entry, mock_coordinator):
    """Nested option mutations do not mutate the setup snapshot."""
    mock_config_entry.options = {"selected_params": ["Betriebsart"]}
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    with (
        patch("custom_components.htha.HtHACoordinator", return_value=mock_coordinator),
        patch("custom_components.htha.schedule_services.setup_scratchpad", AsyncMock()),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        await async_setup_entry(hass, mock_config_entry)
    mock_config_entry.options["selected_params"].append("Temp. Aussen")
    with patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)) as reload:
        await async_update_options(hass, mock_config_entry)
        reload.assert_awaited_once_with(mock_config_entry.entry_id)


@pytest.mark.parametrize("entity_kind", ["number", "select"])
@pytest.mark.parametrize("revoke_at", ["before_call", "lock", "connect"])
async def test_revoked_writes_never_reach_pump(hass, mock_config_entry, entity_kind, revoke_at):
    """Live permission gates both queued and connecting entity writes."""
    mock_config_entry.data[CONF_WRITE_ENABLED] = True
    coordinator = HtHACoordinator(
        hass, mock_config_entry, host="fake", port=9999, timeout=10,
        scan_interval=30, selected_params=[],
    )
    coordinator._heatpump = MagicMock(set_param_async=AsyncMock())
    coordinator._connect = AsyncMock()
    coordinator._disconnect = AsyncMock()
    if entity_kind == "number":
        entity = HtHANumber(coordinator, mock_config_entry, NumberEntityDescription(key="test"),
                            "HKR Soll_Raum", 15, 25, 0.5)
        write = lambda: entity.async_set_native_value(21.5)
    else:
        entity = HtHASelect(coordinator, mock_config_entry, SelectEntityDescription(key="test"),
                            "Betriebsart")
        write = lambda: entity.async_select_option("heating")
    if revoke_at == "lock":
        await coordinator._connection_lock.acquire()
        task = asyncio.create_task(write())
        await asyncio.sleep(0)
        assert not task.done()
        mock_config_entry.data[CONF_WRITE_ENABLED] = False
        coordinator._connection_lock.release()
        with pytest.raises(ValueError, match="Writes are not enabled"):
            await task
    elif revoke_at == "connect":
        async def revoke():
            mock_config_entry.data[CONF_WRITE_ENABLED] = False
        coordinator._connect.side_effect = revoke
        with pytest.raises(UpdateFailed, match="Writes are not enabled"):
            await write()
    else:
        mock_config_entry.data[CONF_WRITE_ENABLED] = False
        with pytest.raises(ValueError, match="Writes are not enabled"):
            await write()
    coordinator.heatpump.set_param_async.assert_not_called()


@pytest.mark.asyncio
async def test_time_programs_sensor(mock_config_entry, mock_coordinator):
    """Test HtHATimeProgramsSensor state and attributes."""
    from custom_components.htha.sensor import HtHATimeProgramsSensor
    from homeassistant.components.sensor import SensorEntityDescription

    description = SensorEntityDescription(
        key="time_programs",
    )

    sensor = HtHATimeProgramsSensor(
        coordinator=mock_coordinator,
        config_entry=mock_config_entry,
        description=description,
    )

    # Initial state when coordinator has no data
    mock_coordinator.time_programs = None
    assert sensor.native_value is None
    assert sensor.extra_state_attributes is None

    # State with time programs loaded
    mock_coordinator.time_programs = [
        {
            "index": 0,
            "name": "Heizkreis",
            "entries": [[{"state": 1, "start": "06:00", "end": "22:00"}]]
        },
        {
            "index": 1,
            "name": "Warmwasser",
            "entries": [[{"state": 1, "start": "14:00", "end": "18:00"}]]
        }
    ]

    assert sensor.native_value == "2"
    assert sensor.extra_state_attributes == {
        "time_programs": mock_coordinator.time_programs
    }
