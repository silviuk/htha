"""HA service wiring with mocked native transport; no hardware/network access."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized

from custom_components.htha.const import CONF_WRITE_ENABLED, DOMAIN
from custom_components.htha.schedule_services import setup_scratchpad


@pytest.fixture
def scratchpad(hass):
    program = dict(index=2, name='Heating', ead=7, nos=3, ste=15, nod=7,
                   entries=[[dict(start='00:00', end='24:00', state=1)] for _ in range(7)])
    pump = SimpleNamespace(get_time_prog_async=AsyncMock(return_value=SimpleNamespace(as_json=lambda:deepcopy(program))),
                           set_time_prog_async=AsyncMock())
    coordinator = SimpleNamespace(_connection_lock=asyncio.Lock(), _connect=AsyncMock(),
                                  _disconnect=AsyncMock(), heatpump=pump, time_programs=[program],
                                  async_update_listeners=MagicMock(), async_request_refresh=AsyncMock())
    entry = SimpleNamespace(entry_id='test-htha', data={CONF_WRITE_ENABLED:False})
    hass.data[DOMAIN] = {entry.entry_id:{}}
    setup_scratchpad(hass, entry, coordinator)
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
    entry.data[CONF_WRITE_ENABLED]=True
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
    with pytest.raises(HomeAssistantError,match='not loaded'):
        await hass.services.async_call(DOMAIN,'load_time_program_draft',{'config_entry_id':'not-loaded','program_index':2},blocking=True)
