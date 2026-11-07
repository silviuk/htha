"""Factory templates resolve names through verified mappings; fake transport only."""
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from test_schedule_safety import Coordinator, JsonProgram, safety


async def factory_editor(index, mapping=None, enabled=False):
    c = Coordinator()
    c.program.update(index=index, name='Heating' if index == 2 else 'Hot water', nos=3 if index == 2 else 2)
    lib = safety.ProfileLibrary(AsyncMock())
    m = safety.Scratchpad(c, lambda: enabled, JsonProgram, library=lib)
    await m.load(index)
    if mapping is not None:
        await m.set_mapping(mapping, 0, True)
    return m, c


def load_factory(m):
    """Same immutable-copy transition as the locked service, without HA imports."""
    key = 'factory_default_heating' if m.metadata['index'] == 2 else 'factory_default_hot_water'
    p = m.factory_profile(key)
    m.draft, m.profile_context = deepcopy(p['draft']), p
    m.invalidate()
    m.changed()
    return p


@pytest.mark.parametrize('index,mapping,state', [
    (2, {'0':'normal', '1':'boost', '2':'setback'}, 0),
    (2, {'0':'boost', '1':'setback', '2':'normal'}, 2),
    (0, {'0':'charging', '1':'minimum'}, 0),
    (0, {'0':'minimum', '1':'charging'}, 1),
    (2, {'0':None, '1':None, '2':'normal'}, 2),
])
async def test_factory_all_week_resolves_semantic_not_assumed_code(index, mapping, state):
    m, c = await factory_editor(index, mapping)
    p = load_factory(m)
    assert p['read_only'] and p['mode_name'] == ('Normal' if index == 2 else 'On')
    assert p['draft'] == {'entries': [[dict(start='00:00', end='24:00', state=state)] for _ in range(7)]}
    policy = dict(kind=p['category'], normal_state=state, mapping_confirmed=True)
    report = await m.check(p['draft'], policy)
    assert report['critical_count'] == 0
    assert not m.can_apply  # Allow writes remains OFF
    assert c.writes == []
    p['draft']['entries'][0][0]['state'] = 255
    assert m.draft['entries'][0][0]['state'] == state
    assert m.factory_profile(p['id'])['draft']['entries'][0][0]['state'] == state


@pytest.mark.parametrize('index,mapping', [
    (2, None), (0, None),
    (2, {'0':'boost', '1':None, '2':'setback'}),
    (0, {'0':'minimum', '1':None}),
])
async def test_factory_unverified_can_load_but_is_critical_and_cannot_send(index, mapping):
    m, c = await factory_editor(index, mapping, enabled=True)
    p = load_factory(m)
    assert all(day[0]['state'] is None for day in m.draft['entries'])
    report = await m.check(p['draft'], dict(kind=p['category'], normal_state=1, mapping_confirmed=True))
    finding = next(f for f in report['findings'] if f['id'] == 'factory_mapping')
    assert finding['severity'] == 'critical'
    assert 'unverified' in finding['message'] and 'bestätigt' in finding['message_de']
    assert not m.can_apply
    with pytest.raises(ValueError):
        await m.acknowledge(report['draft_hash'], report['warning_ids'])
    with pytest.raises(ValueError):
        await m.apply(m.draft, report['draft_hash'], True)
    assert c.writes == []


async def test_factory_mapping_confirmation_requires_explicit_reload_no_translation():
    m, c = await factory_editor(2)
    p = load_factory(m)
    await m.set_mapping({'0':'normal', '1':'setback', '2':'boost'}, 0, True)
    assert m.draft == p['draft']  # no silent replacement of unknown cells
    report = await m.check(m.draft, dict(kind='heating', normal_state=0, mapping_confirmed=True))
    assert any(f['id'] == 'factory_mapping' for f in report['findings'])
    reloaded = load_factory(m)
    assert reloaded['draft']['entries'][0][0]['state'] == 0 and c.writes == []


@pytest.mark.parametrize('change', ['firmware', 'metadata', 'mapping'])
async def test_factory_binding_changes_revoke_validation(change):
    m, c = await factory_editor(2, {'0':'normal', '1':'setback', '2':'boost'}, enabled=True)
    load_factory(m)
    policy = dict(kind='heating', normal_state=0, mapping_confirmed=True)
    report = await m.check(m.draft, policy)
    await m.acknowledge(report['draft_hash'], report['warning_ids'])
    if change == 'firmware':
        c.sw_version = 'changed'
    elif change == 'metadata':
        m.metadata['ead'] = 6
    else:
        await m.set_mapping({'0':'normal', '1':'boost', '2':'setback'}, 1, True)
    assert not m.can_apply
    report = await m.check(m.draft, policy)
    assert any(f['id'] == 'factory_mapping' for f in report['findings'])
    assert not m.can_apply and c.writes == []


@pytest.mark.parametrize('key', list(safety.FACTORY_PRESETS))
async def test_factory_library_is_read_only_not_persisted_or_counted(key):
    lib = safety.ProfileLibrary(AsyncMock())
    builtin = lib.get(key)
    listing = lib.listing(builtin['category'])
    assert listing['profiles'] == [] and listing['builtin_profiles'] == [builtin]
    assert lib.data['profiles'] == [] and lib.data['revision'] == 0
    with pytest.raises(ValueError, match='profile_read_only'):
        await lib.rename(key, 'Changed', 1)
    with pytest.raises(ValueError, match='profile_read_only'):
        await lib.delete(key, 1, True)
    with pytest.raises(ValueError, match='profile_read_only'):
        await lib.save_profile(builtin['category'], 'Changed', {}, {}, {}, {}, key, 1)
    lib.save.assert_not_awaited()
    restarted = safety.ProfileLibrary(AsyncMock())
    restarted.load(deepcopy(lib.data))
    assert restarted.listing(builtin['category'])['builtin_profiles'] == [builtin]


async def test_factory_requires_selected_program_metadata():
    m, c = await factory_editor(2)
    with pytest.raises(ValueError, match='baseline_unavailable'):
        m.factory_profile('factory_default_hot_water')
    m.metadata = None
    with pytest.raises(ValueError, match='baseline_unavailable'):
        m.factory_profile('factory_default_heating')
    assert c.writes == []


async def test_factory_still_requires_ack_confirmation_and_allow_writes():
    m, c = await factory_editor(2, {'0':'boost', '1':'setback', '2':'normal'}, enabled=True)
    load_factory(m)
    report = await m.check(m.draft, dict(kind='heating', normal_state=2, mapping_confirmed=True), fresh=True)
    with pytest.raises(ValueError):
        await m.apply(m.draft, report['draft_hash'], True)
    await m.acknowledge(report['draft_hash'], report['warning_ids'])
    with pytest.raises(ValueError):
        await m.apply(m.draft, report['draft_hash'], False)
    m.allow_writes = lambda: False
    with pytest.raises(ValueError):
        await m.apply(m.draft, report['draft_hash'], True)
    assert c.writes == []
    m.allow_writes = lambda: True
    await m.apply(m.draft, report['draft_hash'], True)
    assert len(c.writes) == 1 and m.report['status'] == 'applied'
    assert all(day[0]['state'] == 2 and len(day) == 7 for day in c.writes[0]['entries'])
