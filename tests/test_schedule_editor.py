"""v2 pure/editor/Store tests. Fake programs and callbacks only; no network."""
import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from test_schedule_safety import Coordinator, DRAFT, META, POLICY, JsonProgram, safety, confirm_mapping


@pytest.fixture
async def editor():
    c = Coordinator()
    saved = []
    async def persist(record):
        saved.append(deepcopy(record))
    lib = safety.ProfileLibrary(persist)
    m = safety.Scratchpad(c, lambda: True, JsonProgram, library=lib)
    await m.load(2)
    await confirm_mapping(m)
    return m, c, saved


def alternating(count):
    day = [dict(start=safety.clock(i * 15), end=safety.clock((i + 1) * 15 if i < count - 1 else 1440), state=i % 2) for i in range(count)]
    return {'entries': [deepcopy(day) for _ in range(7)]}


@pytest.mark.parametrize('state', [0, 1, 2])
def test_cells_runs_round_trip_all_day_boundaries(state):
    week = [[state] * 96 for _ in range(7)]
    encoded = safety.runs(week)
    assert encoded['entries'][0] == [dict(start='00:00', end='24:00', state=state)]
    assert safety.cells(encoded['entries'], 3) == week


def test_round_trip_all_96_cells_and_separate_midnight_capacity():
    week = [[i % 3 for i in range(96)] for _ in range(7)]
    assert safety.cells(safety.runs(week)['entries'], 3) == week
    assert safety.validate(alternating(7), META, POLICY)['critical_count'] == 0
    report = safety.validate(alternating(8), META, POLICY)
    assert any('Monday needs 8 entries; controller supports 7' in f['message'] for f in report['findings'])
    assert len(report['canonical']['entries'][0]) == 8


def test_same_mode_runs_hash_merge_before_capacity():
    split = {'entries': [[dict(start=safety.clock(i * 15), end=safety.clock((i+1)*15), state=1) for i in range(96)] for _ in range(7)]}
    a, b = safety.validate(DRAFT, META, POLICY), safety.validate(split, META, POLICY)
    assert b['critical_count'] == 0
    assert a['draft_hash'] == b['draft_hash']


@pytest.mark.parametrize('change', [{'state':True}, {'state':'1'}, {'state':None}, {'state':256}, {'start':'24:15'}, {'start':'00:15'}, {'end':'23:45'}, {'extra':'x'}])
def test_bounded_profiles_reject_malformed(change):
    draft = deepcopy(DRAFT)
    draft['entries'][0][0].update(change)
    with pytest.raises(ValueError):
        safety.bounded_draft(draft)


def test_unknown_overlap_gap_and_padding():
    raw = deepcopy(DRAFT['entries'])
    raw[0] = [dict(start='00:00', end='01:00', state=1), dict(start='00:45', end='02:00', state=0)]
    cells = safety.cells(raw, 3)
    assert cells[0][3] is None and cells[0][8] is None
    raw = deepcopy(DRAFT['entries'])
    raw[0].append(dict(start='24:00', end='24:00', state=2))
    assert safety.runs(safety.cells(raw, 3)) == DRAFT


def test_diff_exact_pairs_counts_split_unchanged_and_unknown():
    old, new = deepcopy(DRAFT), deepcopy(DRAFT)
    old['entries'][0] = [dict(start='00:00', end='01:00', state=0), dict(start='01:00', end='24:00', state=1)]
    new['entries'][0] = [dict(start='00:00', end='02:00', state=2), dict(start='02:00', end='24:00', state=1)]
    diff = safety.schedule_diff(old, new, META)
    assert diff['changed_cells'] == 8 and diff['changed_minutes'] == 120
    assert diff['days'][0]['ranges'] == [dict(start='00:00',end='01:00',from_state=0,to_state=2),dict(start='01:00',end='02:00',from_state=1,to_state=2)]
    assert diff['days'][1]['ranges'] == []
    split = deepcopy(DRAFT)
    split['entries'][0] = [dict(start='00:00',end='12:00',state=1),dict(start='12:00',end='24:00',state=1)]
    assert safety.schedule_diff(DRAFT, split, META)['changed_minutes'] == 0
    assert safety.schedule_diff(None, DRAFT, META)['baseline_unknown']


async def test_fresh_read_preserves_draft_failure_revokes_approval(editor):
    m, c, _ = editor
    report = await m.check(DRAFT, POLICY)
    await m.acknowledge(report['draft_hash'], report['warning_ids'])
    assert m.can_apply
    c.get_time_prog_async = AsyncMock(side_effect=OSError('unavailable'))
    changed = deepcopy(DRAFT)
    changed['entries'][0][0]['state'] = 2
    with pytest.raises(OSError):
        await m.check(changed, POLICY, fresh=True)
    assert m.draft == changed and not m.can_apply
    assert m.current_program is None and m.current_state == 'unavailable'
    assert not c.writes


async def test_fresh_diff_external_change_and_multitab_identity(editor):
    m, c, _ = editor
    report = await m.check(DRAFT, POLICY, fresh=True, revision=m.revision, session=m.session_id, mapping_revision=1)
    first = report['draft_hash']
    stale = m.revision
    report = await m.check(DRAFT, POLICY, fresh=True)
    assert first != report['draft_hash']  # no approval reuse for a new check
    with pytest.raises(ValueError, match='editor_conflict'):
        await m.acknowledge(first, report['warning_ids'], stale, m.session_id)
    await m.acknowledge(report['draft_hash'], report['warning_ids'])
    c.program['entries'][0][0]['state'] = 2
    with pytest.raises(ValueError):
        await m.apply(DRAFT, report['draft_hash'], True)
    assert not c.writes


async def test_all_used_mapping_gate_firmware_and_revision(editor):
    m, c, _ = editor
    await m.set_mapping({'0':None,'1':'normal','2':None}, 1, True)
    draft = deepcopy(DRAFT)
    draft['entries'][0][0]['state'] = 2
    report = await m.check(draft, POLICY)
    assert any(f['id'] == 'complete_mapping' for f in report['findings'])
    with pytest.raises(ValueError):
        await m.acknowledge(report['draft_hash'], report['warning_ids'])
    with pytest.raises(ValueError, match='mapping_conflict'):
        await m.set_mapping({'0':'setback','1':'normal','2':'boost'}, 1, True)
    await confirm_mapping(m)
    report = await m.check(DRAFT, POLICY)
    await m.acknowledge(report['draft_hash'], report['warning_ids'])
    c.sw_version = 'new firmware'
    assert not m.can_apply and not m.mapping_valid
    with pytest.raises(ValueError):
        await m.apply(DRAFT, report['draft_hash'], True)
    assert not c.writes


async def test_mapping_durable_failure_does_not_change_catalog(editor):
    m, _, _ = editor
    previous = m.mapping
    m.library.save = AsyncMock(side_effect=OSError('disk full'))
    with pytest.raises(OSError):
        await m.set_mapping({'0':'boost','1':'normal','2':'setback'}, 1, True)
    assert m.mapping == previous


async def save(m, name='Example', draft=DRAFT, **kwargs):
    return await m.library.save_profile('heating', name, draft, m.metadata, m.controller_identity, m.mapping, **kwargs)


async def test_crud_names_revisions_casefold_and_deep_copy(editor):
    m, c, saved = editor
    p = await save(m, '  <b>Winter & friends</b>  ')
    assert p['name'] == '<b>Winter & friends</b>' and p['revision'] == 1 and saved
    p['draft']['entries'][0][0]['state'] = 2
    assert m.library.get(p['id'])['draft'] == DRAFT
    with pytest.raises(ValueError, match='profile_duplicate'):
        await save(m, '<B>WINTER & FRIENDS</B>')
    with pytest.raises(ValueError, match='profile_conflict'):
        await m.library.rename(p['id'], 'New', 0)
    renamed = await m.library.rename(p['id'], 'New', 1)
    assert renamed['revision'] == 2
    with pytest.raises(ValueError):
        await m.library.delete(p['id'], 2, False)
    await m.library.delete(p['id'], 2, True)
    assert not m.library.listing('heating')['profiles'] and not c.writes


@pytest.mark.parametrize('name', ['', ' '*3, 'a'*81, 42, 'line\nbreak'])
async def test_invalid_profile_names(editor, name):
    with pytest.raises(ValueError, match='profile_name'):
        await save(editor[0], name)


async def test_capacity_invalid_profiles_can_save_never_send(editor):
    m, c, _ = editor
    p = await save(m, draft=alternating(8))
    m.profile_context = p
    report = await m.check(p['draft'], POLICY)
    assert report['critical_count'] and p['needs_validation']
    with pytest.raises(ValueError):
        await m.apply(p['draft'], report['draft_hash'], True)
    assert not c.writes


async def test_category_entry_isolation_limits_and_restart(editor):
    m, c, saved = editor
    for n in range(50):
        await save(m, f'Profile {n}')
    with pytest.raises(ValueError, match='profile_limit'):
        await save(m, 'Overflow')
    hot = {**META, 'index':0, 'name':'Warmwasser', 'nos':2}
    await m.library.save_profile('hot_water', 'Profile 0', DRAFT, hot, {}, {})
    assert len(m.library.listing('hot_water')['profiles']) == 1
    other = safety.ProfileLibrary(AsyncMock())
    assert other.listing('heating')['profiles'] == []
    restarted = safety.ProfileLibrary(AsyncMock())
    restarted.load(saved[-1])
    assert restarted.error is None and len(restarted.listing('heating')['profiles']) == 50
    manager = safety.Scratchpad(c, lambda: True, JsonProgram, library=restarted)
    assert not manager.can_apply and manager.draft is None and manager.ack_hash is None
    await manager.load(2)
    assert manager.mapping_valid and not manager.can_apply


@pytest.mark.parametrize('record', [{}, {'schema_version':99,'revision':0,'profiles':[],'mappings':{}}, {'schema_version':1,'revision':0,'profiles':[{}],'mappings':{}}, {'schema_version':1,'revision':0,'profiles':[],'mappings':{'2':{}}}])
def test_corrupt_or_future_store_fails_closed(record):
    lib = safety.ProfileLibrary(AsyncMock())
    lib.load(record)
    assert lib.error == 'library_corrupt' and lib.data['profiles'] == []


async def test_profile_metadata_mapping_controller_mismatch_blocks_send(editor):
    m, c, _ = editor
    p = await save(m)
    m.profile_context = p
    await m.set_mapping({'0':'boost','1':'normal','2':'setback'}, 1, True)
    report = await m.check(p['draft'], POLICY)
    assert any(f['id']=='profile_incompatible' for f in report['findings'])
    with pytest.raises(ValueError):
        await m.apply(p['draft'], report['draft_hash'], True)
    assert not c.writes


async def test_profile_save_disk_failure_and_unknown_states(editor):
    m, _, _ = editor
    previous = deepcopy(m.library.data)
    m.library.save = AsyncMock(side_effect=OSError('disk full'))
    with pytest.raises(OSError):
        await save(m)
    assert m.library.data == previous
    malformed = deepcopy(DRAFT)
    malformed['entries'][0][0]['state'] = None
    with pytest.raises(ValueError):
        await save(m, draft=malformed)


async def test_allow_writes_off_edit_validate_save_zero_native_sets(editor):
    m, c, _ = editor
    m.allow_writes = lambda: False
    await save(m)
    report = await m.check(DRAFT, POLICY, fresh=True)
    assert not report['critical_count']
    await m.acknowledge(report['draft_hash'], report['warning_ids'])
    with pytest.raises(ValueError):
        await m.apply(DRAFT, report['draft_hash'], True)
    assert not c.writes


async def test_permission_revoked_during_durable_prewrite_marker(editor):
    m, c, _ = editor
    report = await m.check(DRAFT, POLICY)
    await m.acknowledge(report['draft_hash'], report['warning_ids'])
    async def revoke(_record):
        m.allow_writes = lambda: False
    m.recovery = revoke
    with pytest.raises(ValueError):
        await m.apply(DRAFT, report['draft_hash'], True)
    assert not c.writes and not m.can_apply


async def test_profile_rejects_out_of_native_range_and_oversized_payload(editor):
    m, _, _ = editor
    draft = deepcopy(DRAFT)
    draft['entries'][0][0]['state'] = 3
    with pytest.raises(ValueError, match='draft_shape'):
        await save(m, draft=draft)
    draft['entries'][0] = draft['entries'][0] * 97
    with pytest.raises(ValueError, match='draft_shape'):
        await m.check(draft, POLICY)


async def test_normal_attestation_must_agree_with_confirmed_semantics(editor):
    m, c, _ = editor
    report = await m.check(DRAFT, {**POLICY, 'normal_state':0})
    assert any(f['id']=='normal_mapping_conflict' for f in report['findings'])
    assert all('message_de' in f and 'source_de' in f for f in report['findings'])
    assert not m.can_apply and not c.writes


async def test_stored_time_and_diff_are_frozen_from_validation(editor):
    from unittest.mock import patch
    m, _, _ = editor
    with patch.object(safety, 'utcnow', return_value='2026-11-07T12:00:00+00:00'):
        report = await m.check(DRAFT, POLICY, fresh=True)
        p = await save(m)
    assert report['diff']['baseline_read_at'] == '2026-11-07T12:00:00+00:00'
    assert p['created_at'] == p['updated_at'] == '2026-11-07T12:00:00+00:00'
