"""Offline slot-by-slot recovery tests, including interruption at each slot."""
import asyncio
from copy import deepcopy
import pytest

from test_schedule_safety import Coordinator, DRAFT, POLICY, JsonProgram, safety


class SlotCoordinator(Coordinator):
    def __init__(self, fail_at=None, cancel=False, fail_read=False):
        super().__init__()
        self.fail_at, self.cancel, self.fail_read = fail_at, cancel, fail_read
        self.slot_writes = 0

    async def set_time_prog_async(self, program):
        self.writes.append(program.as_json())
        for d, day in enumerate(program.as_json()['entries']):
            for n, slot in enumerate(day):
                self.assert_locked()
                if self.slot_writes == self.fail_at:
                    if self.cancel:
                        raise asyncio.CancelledError()
                    raise OSError('slot failed')
                self.program['entries'][d][n] = deepcopy(slot)
                self.slot_writes += 1

    async def get_time_prog_async(self, index, with_entries):
        if self.writes and self.fail_read:
            raise OSError('read unavailable')
        return await super().get_time_prog_async(index, with_entries)


async def prepared(coordinator):
    records = []
    async def save(record):
        records.append(deepcopy(record))
    manager = safety.Scratchpad(coordinator, lambda: True, JsonProgram, recovery=save)
    await manager.load(2)
    draft = deepcopy(DRAFT)
    for day in draft['entries']:
        day[0]['state'] = 2
    report = await manager.check(draft, POLICY)
    await manager.acknowledge(report['draft_hash'], report['warning_ids'])
    return manager, draft, report['draft_hash'], records


@pytest.mark.parametrize('slot', range(49))
async def test_failure_at_each_native_slot(slot):
    coordinator = SlotCoordinator(fail_at=slot)
    manager, draft, hash_, records = await prepared(coordinator)
    previous = deepcopy(coordinator.program)
    with pytest.raises(OSError):
        await manager.apply(draft, hash_, True)
    assert coordinator.slot_writes == slot
    assert len(coordinator.writes) == 1
    assert manager.previous_program == previous
    assert manager.actual_program == coordinator.program
    assert manager.report['status'] == 'failed'
    assert manager.report['possible_partial_write']
    assert records[0]['previous_program'] == previous
    assert records[-1]['in_progress']
    assert coordinator.time_programs is None
    assert coordinator._last_time_programs_update == 0
    assert not manager.can_apply


async def test_cancellation_marks_failed_and_rereads_before_reraising():
    coordinator = SlotCoordinator(fail_at=9, cancel=True)
    manager, draft, hash_, records = await prepared(coordinator)
    with pytest.raises(asyncio.CancelledError):
        await manager.apply(draft, hash_, True)
    assert manager.report['status'] == 'failed'
    assert manager.report['apply_error'] == 'CancelledError'
    assert manager.actual_program == coordinator.program
    assert records[-1]['in_progress']
    assert coordinator.time_programs is None


async def test_readback_and_recovery_read_failure_keeps_evidence():
    coordinator = SlotCoordinator(fail_read=True)
    manager, draft, hash_, records = await prepared(coordinator)
    with pytest.raises(OSError):
        await manager.apply(draft, hash_, True)
    assert manager.actual_program is None
    assert manager.previous_program
    assert manager.report['recovery_read_error'] == 'read unavailable'
    assert records[-1]['in_progress']


async def test_refresh_keeps_edits_and_restore_requires_new_review():
    coordinator = SlotCoordinator(fail_at=9)
    manager, draft, hash_, records = await prepared(coordinator)
    with pytest.raises(OSError):
        await manager.apply(draft, hash_, True)
    previous = deepcopy(manager.previous_program)
    await manager.refresh_baseline()
    assert manager.draft == draft
    assert not manager.can_apply
    with pytest.raises(ValueError):
        await manager.restore(hash_, True)
    restore_draft = {'entries': safety.normalized(previous['entries'])}
    report = await manager.check(restore_draft, POLICY)
    await manager.acknowledge(report['draft_hash'], report['warning_ids'])
    with pytest.raises(ValueError):
        await manager.restore(report['draft_hash'], False)
    coordinator.fail_at = None
    await manager.restore(report['draft_hash'], True)
    assert safety.normalized(coordinator.program['entries']) == restore_draft['entries']
    assert not records[-1]['in_progress']


async def test_padding_retains_each_controller_slot_mode():
    coordinator = SlotCoordinator()
    for day in coordinator.program['entries']:
        for n, slot in enumerate(day[1:], 1):
            slot['state'] = n % 3
    manager, draft, hash_, _ = await prepared(coordinator)
    previous = deepcopy(coordinator.program)
    await manager.apply(draft, hash_, True)
    for d, day in enumerate(coordinator.writes[0]['entries']):
        assert day[1:] == previous['entries'][d][1:]


def test_precharge_and_midnight_windows_and_identity():
    from test_schedule_safety import META
    precharge = {'entries': [[
        dict(start='00:00', end='05:00', state=0),
        dict(start='05:00', end='07:00', state=1),
        dict(start='07:00', end='18:00', state=0),
        dict(start='18:00', end='20:00', state=1),
        dict(start='20:00', end='24:00', state=0)] for _ in range(7)]}
    report = safety.validate(precharge, {**META, 'index': 0, 'name': 'Hot water'}, {**POLICY, 'kind': 'hot_water'})
    assert report['critical_count'] == 0
    assert [f['id'].split(':')[0] for f in report['findings'] if f['severity'] == 'warning'] == ['non_atomic']
    day = [dict(start='00:00', end='00:15', state=1), dict(start='00:15', end='23:45', state=0), dict(start='23:45', end='24:00', state=1)]
    report = safety.validate({'entries': [day]*7}, META, POLICY)
    assert not any(f['id'].startswith('short_window') for f in report['findings'])
    assert safety.validate(DRAFT, {**META, 'name': 'Cooling'}, POLICY)['critical_count']


async def test_missing_placeholder_mode_blocks_before_any_write():
    coordinator = SlotCoordinator()
    manager, draft, hash_, records = await prepared(coordinator)
    coordinator.program['entries'][0][6] = None
    with pytest.raises(ValueError, match='placeholder mode'):
        await manager.apply(draft, hash_, True)
    assert not coordinator.writes
    assert not records


async def test_durable_marker_failure_blocks_before_any_write():
    coordinator = SlotCoordinator()
    manager, draft, hash_, records = await prepared(coordinator)
    async def fail_save(_record):
        raise OSError('storage unavailable')
    manager.recovery = fail_save
    with pytest.raises(OSError, match='storage unavailable'):
        await manager.apply(draft, hash_, True)
    assert not coordinator.writes
    assert manager.report['status'] == 'failed'
