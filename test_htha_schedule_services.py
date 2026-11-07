"""HA service wiring with mocked native transport; no hardware/network access."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized

from custom_components.htha.const import CONF_WRITE_ENABLED, DOMAIN
from custom_components.htha.schedule_services import setup_scratchpad, register_services


@pytest.fixture
async def scratchpad(hass):
    program = dict(index=2, name='Heating', ead=7, nos=3, ste=15, nod=7,
                   entries=[[dict(start='00:00', end='24:00', state=1), *[dict(start='24:00', end='24:00', state=0) for _ in range(6)]] for _ in range(7)])
    pump = SimpleNamespace(get_time_prog_async=AsyncMock(return_value=SimpleNamespace(as_json=lambda:deepcopy(program))),
                           set_time_prog_async=AsyncMock())
    coordinator = SimpleNamespace(_connection_lock=asyncio.Lock(), _connect=AsyncMock(),
                                  _disconnect=AsyncMock(), heatpump=pump, time_programs=[program],
                                  async_update_listeners=MagicMock(), async_request_refresh=AsyncMock(), async_shutdown=AsyncMock())
    entry = MockConfigEntry(domain=DOMAIN, title='Mock pump', data={CONF_WRITE_ENABLED:False})
    entry.add_to_hass(hass)
    entry.runtime_data = coordinator
    entry._async_set_state(hass, ConfigEntryState.LOADED, None)
    hass.data[DOMAIN] = {entry.entry_id:{}}
    register_services(hass)
    await setup_scratchpad(hass, entry, coordinator)
    return coordinator, entry


@pytest.mark.asyncio
async def test_admin_service_responses_and_allow_writes_gate(hass, hass_admin_user, scratchpad):
    coordinator, entry = scratchpad
    context=Context(user_id=hass_admin_user.id)
    async def call(service, **data):
        return await hass.services.async_call(DOMAIN,service,{'config_entry_id':entry.entry_id,**data},
                                              blocking=True,return_response=True,context=context)
    loaded = await call('load_time_program_draft',program_index=2)
    assert loaded['status']=='unvalidated'
    report = await call('validate_time_program',draft=loaded['draft'],policy=dict(kind='heating',normal_state=1,mapping_confirmed=True,floor_heating=True))
    assert report['critical_count']==0
    ack = await call('acknowledge_time_program_warnings',draft_hash=report['draft_hash'],warning_ids=report['warning_ids'])
    assert ack['warnings_acknowledged']
    assert not ack['can_apply']
    with pytest.raises(HomeAssistantError):
        await call('apply_time_program',draft=loaded['draft'],draft_hash=report['draft_hash'],confirm=True)
    coordinator.heatpump.set_time_prog_async.assert_not_awaited()
    # Enable only the mocked entry; successful apply exercises real TimeProgram conversion.
    hass.config_entries.async_update_entry(entry, data={CONF_WRITE_ENABLED:True})
    applied = await call('apply_time_program',draft=loaded['draft'],draft_hash=report['draft_hash'],confirm=True)
    assert applied['status']=='applied'
    assert not applied['can_apply']
    program=coordinator.heatpump.set_time_prog_async.await_args.args[0].as_json()
    assert all(len(day)==7 for day in program['entries'])


@pytest.mark.asyncio
async def test_service_isolation_and_admin_only(hass, hass_read_only_user, scratchpad):
    coordinator, entry=scratchpad
    with pytest.raises(Unauthorized):
        await hass.services.async_call(DOMAIN,'load_time_program_draft',{'config_entry_id':entry.entry_id,'program_index':2},
                                      blocking=True,context=Context(user_id=hass_read_only_user.id))
    coordinator.heatpump.get_time_prog_async.assert_not_awaited()
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN,'load_time_program_draft',{'config_entry_id':'not-loaded','program_index':2},blocking=True)
    assert err.value.translation_key == 'entry_not_loaded'


async def test_reload_mid_review_keeps_draft_and_approval(hass, scratchpad):
    coordinator, entry = scratchpad
    manager = coordinator.schedule_scratchpad
    await manager.load(2)
    draft = deepcopy(manager.draft)
    draft['entries'][0][0]['state'] = 2
    report = await manager.check(draft, dict(kind='heating', normal_state=1, mapping_confirmed=True))
    await manager.acknowledge(report['draft_hash'], report['warning_ids'])
    # Mimic unload/setup replacing the runtime coordinator and per-entry data.
    hass.data[DOMAIN].pop(entry.entry_id)
    hass.data[DOMAIN][entry.entry_id] = {}
    replacement = SimpleNamespace(**vars(coordinator))
    entry.runtime_data = replacement
    hass.config_entries.async_update_entry(entry, data={CONF_WRITE_ENABLED: True})
    await setup_scratchpad(hass, entry, replacement)
    assert replacement.schedule_scratchpad is manager
    assert manager.coordinator is replacement
    assert manager.draft == draft
    assert manager.report['draft_hash'] == report['draft_hash']
    assert manager.can_apply


async def test_two_loaded_entries_use_their_own_runtime(hass, scratchpad):
    coordinator, entry = scratchpad
    other = MockConfigEntry(domain=DOMAIN, title='Second mock pump', data={CONF_WRITE_ENABLED: False})
    other.add_to_hass(hass)
    other._async_set_state(hass, ConfigEntryState.LOADED, None)
    second = SimpleNamespace(**vars(coordinator))
    second.heatpump = SimpleNamespace(get_time_prog_async=AsyncMock(return_value=coordinator.heatpump.get_time_prog_async.return_value),
                                     set_time_prog_async=AsyncMock())
    other.runtime_data = second
    hass.data[DOMAIN][other.entry_id] = {}
    await setup_scratchpad(hass, other, second)
    response = await hass.services.async_call(DOMAIN, 'load_time_program_draft',
        {'config_entry_id': other.entry_id, 'program_index': '2'}, blocking=True, return_response=True)
    assert response['draft']
    assert coordinator.schedule_scratchpad.draft is None
    coordinator.heatpump.get_time_prog_async.assert_not_awaited()
    assert second.schedule_scratchpad is not coordinator.schedule_scratchpad
    other._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, 'load_time_program_draft',
            {'config_entry_id': other.entry_id, 'program_index': 2}, blocking=True)


async def test_interrupted_record_creates_startup_repair_without_transport(hass, scratchpad):
    from homeassistant.helpers import issue_registry as ir
    coordinator, entry = scratchpad
    previous = coordinator.heatpump.get_time_prog_async.return_value.as_json()
    hass.data[DOMAIN]['scratchpads'].pop(entry.entry_id)
    record = dict(in_progress=True, previous_program=previous, actual_program=None)
    with patch('custom_components.htha.schedule_services.Store') as store:
        store.return_value.async_load = AsyncMock(return_value=record)
        store.return_value.async_save = AsyncMock()
        await setup_scratchpad(hass, entry, coordinator)
    manager = coordinator.schedule_scratchpad
    assert manager.previous_program == previous
    assert manager.report['status'] == 'failed'
    assert not manager.can_apply
    assert ir.async_get(hass).async_get_issue(DOMAIN, f'schedule_recovery_{entry.entry_id}')
    coordinator.heatpump.get_time_prog_async.assert_not_awaited()
    coordinator.heatpump.set_time_prog_async.assert_not_awaited()
