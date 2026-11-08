"""Read-only autoload and explicit draft transitions; fake transport only."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from test_schedule_safety import Coordinator, DRAFT, META, POLICY, JsonProgram, safety


def manager():
    c = Coordinator()
    c.sw_version = '2.03N'
    m = safety.Scratchpad(c, lambda: True, JsonProgram,
                          library=safety.ProfileLibrary(AsyncMock()))
    return m, c


async def test_current_cache_miss_single_read_and_no_session_creation():
    m, c = manager()
    before = (m.revision, m.session_id, deepcopy(m.report))
    first, second = await asyncio.gather(m.get_current(2), m.get_current(2))
    assert c.reads == 1 and c.writes == []
    assert first == second and first['read_at']
    assert m.draft is None and m.current_program is None and m.metadata is None
    assert (m.revision, m.session_id, m.report) == before
    first['current_program']['entries'].clear()
    assert len((await m.get_current(2))['current_program']['entries']) == 7


async def test_coordinator_fresh_cache_zero_reads_and_original_timestamp():
    m, c = manager()
    c._last_time_programs_update = asyncio.get_running_loop().time() - 60
    view = await m.get_current(2)
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(view['read_at'])).total_seconds()
    assert 59 <= age <= 62
    assert c.reads == 0 and c.writes == [] and m.draft is None
    assert view['mode_catalog'][1]['semantic'] == 'normal'


async def test_old_coordinator_cache_and_expired_current_cache_read_once():
    m, c = manager()
    c._last_time_programs_update = asyncio.get_running_loop().time() - 300
    stale = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    m._current_cache[2] = (deepcopy(c.program), stale)
    await m.get_current(2)
    assert c.reads == 1 and c.writes == []


async def test_current_read_preserves_existing_draft_approval_revision_and_baseline():
    m, c = manager()
    await m.load(2)
    report = await m.check(DRAFT, POLICY)
    await m.acknowledge(report['draft_hash'], report['warning_ids'])
    assert m.can_apply
    before = deepcopy((m.draft, m.report, m.revision, m.session_id, m.metadata,
                       m.current_program, m.baseline_read_at, m.ack_hash, m.ack_ids))
    c.program = {**deepcopy(c.program), 'index': 0, 'name': 'Hot water', 'nos': 2}
    await m.get_current(0)
    assert (m.draft, m.report, m.revision, m.session_id, m.metadata,
            m.current_program, m.baseline_read_at, m.ack_hash, m.ack_ids) == before
    assert m.can_apply and c.writes == []


@pytest.mark.parametrize('index,category', [(2, 'heating'), (0, 'hot_water')])
@pytest.mark.parametrize('source', ['current', 'factory', 'profile'])
async def test_explicit_draft_sources_use_pump_baseline_without_second_read(index, category, source):
    m, c = manager()
    c.program.update(index=index, name='Heating' if index == 2 else 'Hot water', nos=3 if index == 2 else 2)
    view = await m.get_current(index)
    profile_id = None
    if source == 'factory':
        profile_id = 'factory_default_' + category
    elif source == 'profile':
        # Save a synthetic compatible profile against a temporary view.
        from copy import copy
        v = copy(m)
        v.metadata = {k: c.program[k] for k in safety.META_KEYS}
        custom = deepcopy(DRAFT)
        custom['entries'][0][0]['state'] = 0
        profile = await m.library.save_profile(category, 'Example', custom, v.metadata,
                                                m.controller_identity, v.mapping)
        profile_id = profile['id']
    await m.start_draft(index, profile_id, m.revision, m.session_id)
    assert c.reads == 1 and c.writes == []
    assert m.current_program == view['current_program'] and m.baseline_read_at == view['read_at']
    assert m.draft['entries'][0][0]['state'] == (0 if source == 'profile' else 1)
    assert not m.can_apply and m.report['status'] == 'unvalidated'
    assert bool(m.profile_context) == (source != 'current')
    rev = m.revision
    await m.discard_draft(rev, m.session_id)
    assert m.draft is None and m.profile_context is None and m.revision > rev and not m.can_apply
    assert c.reads == 1 and c.writes == []


async def test_start_discard_revision_conflicts_do_not_overwrite_another_tab():
    m, c = manager()
    await m.start_draft(2, revision=m.revision, session=m.session_id)
    before = deepcopy(m.draft)
    with pytest.raises(ValueError, match='editor_conflict'):
        await m.start_draft(2, revision=m.revision - 1, session=m.session_id)
    with pytest.raises(ValueError, match='editor_conflict'):
        await m.discard_draft(m.revision, 'another-session')
    assert m.draft == before and c.reads == 1 and c.writes == []


async def test_forced_read_bypasses_cache_and_failure_never_changes_server_draft():
    m, c = manager()
    await m.start_draft(2)
    before = deepcopy((m.draft, m.report, m.revision, m.baseline_read_at))
    c.get_time_prog_async = AsyncMock(side_effect=OSError('unavailable'))
    with pytest.raises(OSError, match='unavailable'):
        await m.get_current(2, force=True)
    assert (m.draft, m.report, m.revision, m.baseline_read_at) == before
    assert c.writes == []
