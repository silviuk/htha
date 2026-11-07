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


@pytest.mark.parametrize('index,category,key,mapping,state', [
    (2, 'heating', 'factory_default_heating', {'0':'normal','1':'boost','2':'setback'}, 0),
    (0, 'hot_water', 'factory_default_hot_water', {'0':'charging','1':'minimum'}, 0),
])
async def test_factory_service_load_save_as_and_read_only_gates(hass, hass_read_only_user, scratchpad, index, category, key, mapping, state):
    coordinator, entry = scratchpad
    manager = coordinator.schedule_scratchpad
    program = deepcopy(coordinator.time_programs[0])
    program.update(index=index, name='Heating' if index == 2 else 'Hot water', nos=3 if index == 2 else 2)
    coordinator.heatpump.get_time_prog_async.return_value = SimpleNamespace(as_json=lambda:deepcopy(program))
    await manager.load(index)

    async def call(service, **data):
        return await hass.services.async_call(DOMAIN, service, {'config_entry_id':entry.entry_id, **data}, blocking=True, return_response=True)

    async def load():
        return await call('load_time_program_profile', profile_id=key, expected_draft_revision=manager.revision,
                          session_id=manager.session_id, read_only=True)

    listing = await call('list_time_program_profiles', category=category)
    assert listing['profiles'] == [] and listing['builtin_profiles'][0]['id'] == key
    with pytest.raises(Unauthorized):
        await hass.services.async_call(DOMAIN, 'load_time_program_profile',
            {'config_entry_id':entry.entry_id, 'profile_id':key, 'expected_draft_revision':manager.revision,
             'session_id':manager.session_id, 'read_only':True}, blocking=True,
            context=Context(user_id=hass_read_only_user.id))
    before = coordinator.heatpump.get_time_prog_async.await_count
    unresolved = await load()
    assert unresolved['profile_context']['read_only'] and unresolved['draft']['entries'][0][0]['state'] is None
    policy = dict(kind=category, normal_state=state, mapping_confirmed=True)
    report = await call('validate_time_program', draft=unresolved['draft'], policy=policy)
    assert report['critical_count'] and 'factory_mapping' in report['missing_gates'] and not report['can_apply']
    await manager.set_mapping(mapping, 0, True)
    loaded = await load()
    assert loaded['draft']['entries'][0][0]['state'] == state
    assert coordinator.heatpump.get_time_prog_async.await_count == before  # no reads on preset loads
    report = await call('validate_time_program', draft=loaded['draft'], policy=policy, fresh_read=True)
    assert report['critical_count'] == 0 and not report['can_apply']  # writes OFF
    await call('acknowledge_time_program_warnings', draft_hash=report['draft_hash'], warning_ids=report['warning_ids'])
    for service, extra in [('rename_time_program_profile', {'name':'Renamed'}),
                           ('delete_time_program_profile', {'confirm':True}),
                           ('save_time_program_profile', {'category':category, 'name':'Overwrite', 'draft':loaded['draft']})]:
        with pytest.raises(ServiceValidationError) as err:
            await call(service, profile_id=key, expected_profile_revision=1, **extra)
        assert err.value.translation_key == 'profile_read_only'
    copied = await call('save_time_program_profile', category=category, name='My copy', draft=loaded['draft'])
    p = copied['saved_profile']
    assert p['id'] != key and not p.get('read_only') and p['draft'] == loaded['draft']
    assert manager.profile_context['id'] == p['id']
    assert copied['warnings_acknowledged']  # saving identical numeric contents preserves existing behavior
    await call('rename_time_program_profile', profile_id=p['id'], name='Editable', expected_profile_revision=1)
    await call('delete_time_program_profile', profile_id=p['id'], expected_profile_revision=2, confirm=True)
    assert manager.library.listing(category)['profiles'] == []
    assert manager.library.listing(category)['builtin_profiles'][0]['id'] == key
    coordinator.heatpump.set_time_prog_async.assert_not_awaited()


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
    await call('set_time_program_mode_mapping', program_index=2, mapping={'0':'setback','1':'normal','2':'boost'}, expected_mapping_revision=0, confirmed=True)
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
    await manager.set_mapping({'0':'setback','1':'normal','2':'boost'}, 0, True)
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


async def test_profiles_admin_crud_and_revision_conflicts(hass, hass_admin_user, hass_read_only_user, scratchpad):
    coordinator, entry = scratchpad
    async def call(service, **data):
        return await hass.services.async_call(DOMAIN, service, {'config_entry_id':entry.entry_id, **data},
            blocking=True, return_response=True, context=Context(user_id=hass_admin_user.id))
    loaded = await call('load_time_program_draft', program_index=2)
    for service, payload in (
        ('list_time_program_profiles', {'category':'heating'}),
        ('get_time_program_editor', {'program_index':2}),
        ('save_time_program_profile', {'category':'heating','name':'Test','draft':loaded['draft']}),
        ('set_time_program_mode_mapping', {'program_index':2,'mapping':{'0':'setback','1':'normal','2':'boost'},'expected_mapping_revision':0,'confirmed':True}),
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(DOMAIN, service, {'config_entry_id':entry.entry_id, **payload},
                blocking=True, context=Context(user_id=hass_read_only_user.id))
    before = coordinator.heatpump.get_time_prog_async.await_count
    saved = await call('save_time_program_profile', category='heating', name='Winter <b>&</b>', draft=loaded['draft'])
    profile = saved['saved_profile']
    assert saved['writes_enabled'] is False and not saved['can_apply']
    assert (await call('list_time_program_profiles',category='hot_water'))['profiles'] == []
    with pytest.raises(ServiceValidationError) as err:
        await call('rename_time_program_profile', profile_id=profile['id'], name='New', expected_profile_revision=0)
    assert err.value.translation_key == 'profile_conflict'
    renamed = await call('rename_time_program_profile',profile_id=profile['id'],name='New',expected_profile_revision=1)
    await call('delete_time_program_profile',profile_id=profile['id'],expected_profile_revision=renamed['saved_profile']['revision'],confirm=True)
    assert coordinator.heatpump.get_time_prog_async.await_count == before
    coordinator.heatpump.set_time_prog_async.assert_not_awaited()


async def test_profile_store_restart_and_load_invalidates_approval(hass, scratchpad):
    coordinator, entry = scratchpad
    manager = coordinator.schedule_scratchpad
    await manager.load(2)
    await manager.set_mapping({'0':'setback','1':'normal','2':'boost'}, 0, True)
    saved = await hass.services.async_call(DOMAIN, 'save_time_program_profile',
        {'config_entry_id':entry.entry_id,'category':'heating','name':'Persistent','draft':manager.draft},blocking=True,return_response=True)
    await hass.async_block_till_done()
    # A fresh manager simulates an HA restart; the same Store retains only data.
    hass.data[DOMAIN]['scratchpads'].pop(entry.entry_id)
    await setup_scratchpad(hass, entry, coordinator)
    manager = coordinator.schedule_scratchpad
    assert manager.draft is None and manager.ack_hash is None and not manager.can_apply
    assert manager.library.get(saved['saved_profile']['id'])['name'] == 'Persistent'
    response = await hass.services.async_call(DOMAIN, 'load_time_program_profile',
        {'config_entry_id':entry.entry_id,'profile_id':saved['saved_profile']['id'],'expected_draft_revision':manager.revision,
         'session_id':manager.session_id,'read_only':True},blocking=True,return_response=True)
    assert response['draft'] and response['current_state']=='unknown' and not response['can_apply']
    coordinator.heatpump.set_time_prog_async.assert_not_awaited()


async def test_profile_wrong_entry_and_stale_editor_rejected(hass, scratchpad):
    coordinator, entry = scratchpad
    manager = coordinator.schedule_scratchpad
    await manager.load(2)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN,'load_time_program_profile',
            {'config_entry_id':entry.entry_id,'profile_id':'unknown','expected_draft_revision':manager.revision-1,
             'session_id':manager.session_id,'read_only':True},blocking=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN,'set_time_program_mode_mapping',
            {'config_entry_id':entry.entry_id,'program_index':0,'mapping':{'0':'minimum','1':'charging'},
             'expected_mapping_revision':0,'confirmed':True},blocking=True)
    coordinator.heatpump.set_time_prog_async.assert_not_awaited()


async def test_save_changed_contents_revokes_approval_unchanged_save_keeps_it(hass, scratchpad):
    coordinator, entry = scratchpad
    manager = coordinator.schedule_scratchpad
    await manager.load(2)
    await manager.set_mapping({'0':'setback','1':'normal','2':'boost'},0,True)
    policy = dict(kind='heating',normal_state=1,mapping_confirmed=True)
    report = await manager.check(manager.draft, policy)
    await manager.acknowledge(report['draft_hash'], report['warning_ids'])
    async def save(name, draft):
        return await hass.services.async_call(DOMAIN,'save_time_program_profile',
            {'config_entry_id':entry.entry_id,'category':'heating','name':name,'draft':draft},blocking=True,return_response=True)
    unchanged = await save('Unchanged', manager.draft)
    assert unchanged['draft_hash'] == report['draft_hash'] and unchanged['warnings_acknowledged']
    changed = deepcopy(manager.draft)
    changed['entries'][0][0]['state'] = 2
    response = await save('Changed', changed)
    assert response['status']=='unvalidated' and not response['warnings_acknowledged']
    assert manager.draft == changed
    coordinator.heatpump.set_time_prog_async.assert_not_awaited()
