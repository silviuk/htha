"""Dependency-free unit tests; NEVER connect to hardware."""
import asyncio
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import AsyncMock

spec = importlib.util.spec_from_file_location('schedule_safety', Path(__file__).parents[1] / 'custom_components/htha/schedule_safety.py')
safety = importlib.util.module_from_spec(spec)
spec.loader.exec_module(safety)
META = dict(index=2, name='Heating', ead=7, nos=3, ste=15, nod=7)
POLICY = dict(kind='heating', normal_state=1, mapping_confirmed=True, floor_heating=True)
DRAFT = dict(entries=[[dict(start='00:00', end='24:00', state=1)] for _ in range(7)])


class ValidatorTests(unittest.TestCase):
    def check(self, draft=None, meta=None, policy=None):
        return safety.validate(deepcopy(DRAFT if draft is None else draft), META if meta is None else meta, POLICY if policy is None else policy)

    def test_valid_full_week(self):
        report = self.check()
        self.assertEqual(report['critical_count'], 0)
        self.assertEqual([x['id'].split(':')[0] for x in report['findings'] if x['severity']=='warning'], ['non_atomic'])

    def test_hash_covers_every_day_metadata_and_policy(self):
        original = self.check()['draft_hash']
        draft = deepcopy(DRAFT); draft['entries'][6][0]['state'] = 2
        self.assertNotEqual(original, self.check(draft)['draft_hash'])
        self.assertNotEqual(original, self.check(policy={**POLICY, 'floor_heating':False})['draft_hash'])
        self.assertNotEqual(original, self.check(meta={**META, 'name':'Other'})['draft_hash'])

    def test_malformed_inputs_are_critical(self):
        for draft in (None, [], {}, {'entries':[]}, {'entries':[None]*7}, {'entries':[{}]*7}):
            report = safety.validate(draft, META, POLICY)
            self.assertGreater(report['critical_count'], 0)

    def test_bad_times_states_and_extra_fields(self):
        for change in ({'start':'0:00'}, {'end':'24:15'}, {'end':'23:59'}, {'start':'00:15'}, {'state':3}, {'state':True}, {'state':'1'}, {'end':None}, {'extra':1}, {'start':'24:00'}, {'start':'23:00','end':'22:00'}):
            with self.subTest(change=change):
                draft=deepcopy(DRAFT);draft['entries'][0][0].update(change)
                self.assertGreater(self.check(draft)['critical_count'],0)

    def test_overlap_gap_order(self):
        for first_end, second_start in (('12:00','12:15'), ('12:00','11:45'), ('24:00','00:00')):
            draft=deepcopy(DRAFT);draft['entries'][0]=[dict(start='00:00',end=first_end,state=1),dict(start=second_start,end='24:00',state=0)]
            self.assertGreater(self.check(draft)['critical_count'],0)

    def test_too_many_slots(self):
        draft=deepcopy(DRAFT);draft['entries'][0] *= 8
        self.assertGreater(self.check(draft)['critical_count'],0)

    def test_metadata_fails_closed(self):
        for change in ({'ste':5},{'ead':8},{'nod':5},{'nos':4},{'index':1},{'nos':'3'},{'ead':None},{'nod':True}):
            self.assertGreater(self.check(meta={**META,**change})['critical_count'],0)
        self.assertGreater(self.check(meta={})['critical_count'],0)

    def test_mapping_and_kind_are_not_guessed(self):
        for change in ({'mapping_confirmed':False},{'normal_state':3},{'normal_state':True},{'kind':'hot_water'}):
            self.assertGreater(self.check(policy={**POLICY,**change})['critical_count'],0)

    def test_floor_and_short_window_warnings(self):
        draft=deepcopy(DRAFT);draft['entries'][0]=[dict(start='00:00',end='00:15',state=1),dict(start='00:15',end='24:00',state=0)]
        codes={x['id'].split(':')[0] for x in self.check(draft)['findings']}
        self.assertTrue({'floor_non_normal','short_window'} <= codes)

    def test_dhw_household_risks_and_pv_are_advisory(self):
        report=self.check(meta={**META,'index':0,'nos':2},policy={**POLICY,'kind':'hot_water'})
        self.assertEqual(report['critical_count'],0)
        self.assertFalse(any(x['id'].startswith('demand_') for x in report['findings']))
        draft=deepcopy(DRAFT)
        for day in draft['entries']: day[0]['state']=0
        report=self.check(draft,meta={**META,'index':0,'nos':2},policy={**POLICY,'kind':'hot_water'})
        self.assertEqual(sum(x['id'].startswith('demand_') for x in report['findings']),14)
        self.assertEqual(report['critical_count'],0)

    def test_normalization_discards_padding_merges_equal(self):
        day=[dict(start='00:00',end='12:00',state=1),dict(start='12:00',end='24:00',state=1),dict(start='24:00',end='24:00',state=1),None]
        self.assertEqual(safety.normalized([day]),DRAFT['entries'][:1])


class JsonProgram:
    def __init__(self,payload):self.payload=deepcopy(payload)
    def as_json(self):return deepcopy(self.payload)


class Coordinator:
    def __init__(self):
        self._connection_lock=asyncio.Lock()
        self.program={**deepcopy(META),**deepcopy(DRAFT)}
        self.heatpump=self
        self.time_programs=[deepcopy(self.program)]
        self.reads=0;self.writes=[];self.fail=False;self.mismatch=False
        self.async_request_refresh=AsyncMock()
        self._connect=AsyncMock();self._disconnect=AsyncMock()
    async def get_time_prog_async(self,index,with_entries):
        self.reads+=1
        self.assert_locked()
        if self.writes and self.mismatch:
            value=deepcopy(self.program);value['entries'][0][0]['state']=0;return JsonProgram(value)
        return JsonProgram(self.program)
    def assert_locked(self):assert self._connection_lock.locked()
    async def set_time_prog_async(self,program):
        self.assert_locked();self.writes.append(program.as_json())
        if self.fail:raise OSError('partial network failure')
        self.program=program.as_json()


class TransactionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.c=Coordinator();self.enabled=False
        self.manager=safety.Scratchpad(self.c,lambda:self.enabled,JsonProgram)
        await self.manager.load(2)
    async def ready(self):
        report=await self.manager.check(DRAFT,POLICY)
        await self.manager.acknowledge(report['draft_hash'],report['warning_ids'])
        return report['draft_hash']
    async def test_load_check_and_ack_never_write(self):
        await self.ready();self.assertEqual(self.c.writes,[])
    async def test_disabled_and_missing_confirmation_refuse(self):
        hash_=await self.ready()
        with self.assertRaises(ValueError):await self.manager.apply(DRAFT,hash_,True)
        self.enabled=True
        with self.assertRaises(ValueError):await self.manager.apply(DRAFT,hash_,False)
        self.assertEqual(self.c.writes,[])
    async def test_unacknowledged_warning_refuses(self):
        self.enabled=True;report=await self.manager.check(DRAFT,POLICY)
        with self.assertRaises(ValueError):await self.manager.apply(DRAFT,report['draft_hash'],True)
        with self.assertRaises(ValueError):await self.manager.acknowledge(report['draft_hash'],[])
        self.assertEqual(self.c.writes,[])
    async def test_critical_cannot_ack_or_apply(self):
        self.enabled=True;report=await self.manager.check(DRAFT,{**POLICY,'mapping_confirmed':False})
        with self.assertRaises(ValueError):await self.manager.acknowledge(report['draft_hash'],report['warning_ids'])
        with self.assertRaises(ValueError):await self.manager.apply(DRAFT,report['draft_hash'],True)
        self.assertEqual(self.c.writes,[])
    async def test_dirty_hash_refuses(self):
        self.enabled=True;hash_=await self.ready();changed=deepcopy(DRAFT);changed['entries'][0][0]['state']=2
        with self.assertRaises(ValueError):await self.manager.apply(changed,hash_,True)
        self.assertEqual(self.c.writes,[]);self.assertFalse(self.manager.can_apply)
    async def test_wrong_hash_and_ack_invalidated_on_check(self):
        self.enabled=True;hash_=await self.ready()
        with self.assertRaises(ValueError):await self.manager.acknowledge('bad',self.manager.report['warning_ids'])
        await self.manager.check(DRAFT,POLICY)
        self.assertFalse(self.manager.can_apply)
        with self.assertRaises(ValueError):await self.manager.apply(DRAFT,hash_,True)
    async def test_controller_changed_refuses_before_write(self):
        self.enabled=True;hash_=await self.ready();self.c.program['entries'][0][0]['state']=2
        with self.assertRaises(ValueError):await self.manager.apply(DRAFT,hash_,True)
        self.assertEqual(self.c.writes,[]);self.assertEqual(self.manager.report['status'],'failed')
    async def test_metadata_changed_refuses(self):
        self.enabled=True;hash_=await self.ready();self.c.program['ste']=30
        with self.assertRaises(ValueError):await self.manager.apply(DRAFT,hash_,True)
        self.assertEqual(self.c.writes,[])
    async def test_permission_rechecked_after_await(self):
        self.enabled=True;hash_=await self.ready()
        async def revoke():self.enabled=False
        self.c._connect.side_effect=revoke
        with self.assertRaises(ValueError):await self.manager.apply(DRAFT,hash_,True)
        self.assertEqual(self.c.writes,[])
    async def test_apply_pads_all_slots_and_reads_independently(self):
        self.enabled=True;hash_=await self.ready();reads=self.c.reads
        await self.manager.apply(DRAFT,hash_,True)
        self.assertEqual(self.c.reads,reads+2)
        self.assertEqual(len(self.c.writes),1)
        for day in self.c.writes[0]['entries']:
            self.assertEqual(len(day),7)
            self.assertTrue(all(e['start']==e['end']=='24:00' for e in day[1:]))
        self.assertEqual(self.manager.report['status'],'applied')
        self.assertFalse(self.manager.can_apply)
        self.c.async_request_refresh.assert_awaited_once()
        with self.assertRaises(ValueError):await self.manager.apply(DRAFT,hash_,True)
    async def test_readback_mismatch_is_failure_no_retry(self):
        self.enabled=True;hash_=await self.ready();self.c.mismatch=True
        with self.assertRaises(ValueError):await self.manager.apply(DRAFT,hash_,True)
        self.assertEqual(len(self.c.writes),1)
        self.assertTrue(self.manager.report['possible_partial_write'])
        self.assertFalse(self.manager.can_apply)
    async def test_partial_write_failure_no_retry_or_rollback(self):
        self.enabled=True;hash_=await self.ready();self.c.fail=True
        with self.assertRaises(OSError):await self.manager.apply(DRAFT,hash_,True)
        self.assertEqual(len(self.c.writes),1)
        self.assertTrue(self.manager.report['possible_partial_write'])
        self.assertFalse(self.manager.can_apply)
    async def test_concurrent_applies_serialize_and_only_one_can_write(self):
        self.enabled=True;hash_=await self.ready()
        results=await asyncio.gather(self.manager.apply(DRAFT,hash_,True),self.manager.apply(DRAFT,hash_,True),return_exceptions=True)
        self.assertEqual(sum(isinstance(x,ValueError) for x in results),1)
        self.assertEqual(len(self.c.writes),1)
    async def test_restart_resets_all_approvals(self):
        self.enabled=True;await self.ready()
        new=safety.Scratchpad(self.c,lambda:self.enabled,JsonProgram)
        self.assertFalse(new.can_apply)
        with self.assertRaises(ValueError):await new.check(DRAFT,POLICY)
