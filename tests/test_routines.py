from datetime import timedelta
from unittest.mock import patch
import pytest
from homeassistant.util import dt as dt_util
from homeassistant.exceptions import HomeAssistantError
from custom_components.light_routines.controller import levels
from custom_components.light_routines.const import DOMAIN, DEFAULTS

async def test_setup_is_passive_and_entities_exist(hass, routine):
    entry,calls=routine
    assert calls==[]
    switches=[s for s in hass.states.async_all() if s.entity_id.startswith('switch.test_room')]
    assert len(switches)==3
    assert sum(s.state=='on' for s in switches)==1

async def test_wake_target_and_stop(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    await c.start('wake')
    assert len(calls)==3 and all(d['brightness']==1 for _,d in calls)
    assert c.remaining('wake') in (1799,1800)
    await c.tick(dt_util.utcnow()+timedelta(minutes=15))
    assert all(100<=d['brightness']<=104 for _,d in calls[-3:])
    await c.stop('wake')
    assert c.session is None
    assert all(d.get('transition')==0 for _,d in calls[-3:])
    count=len(calls)
    await c.tick(dt_util.utcnow()+timedelta(minutes=20))
    assert len(calls)==count

async def test_bed_preserves_individual_levels_and_reaches_off(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    await c.start('bed')
    assert [d.get('brightness',0) for _,d in calls]==[200,80,0]
    await c.tick(dt_util.utcnow()+timedelta(minutes=15))
    assert [d.get('brightness',0) for _,d in calls[-2:]]==[100,40]
    await c.tick(dt_util.utcnow()+timedelta(minutes=31))
    assert all(s=='turn_off' for s,_ in calls[-2:])
    assert c.session is None and c.status=='Completed'

async def test_replace_mutual_exclusion_and_idempotent_start(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    await c.start('wake');count=len(calls)
    await c.start('wake');assert len(calls)==count
    await c.start('bed');assert c.session['mode']=='bed'
    await c.stop('wake');assert c.session['mode']=='bed'

async def test_daily_schedule_once_and_disable(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    now=dt_util.utcnow();local=dt_util.as_local(now)
    c.config['wake_time']=local.strftime('%H:%M:00')
    await c.tick(now);assert c.session['mode']=='wake'
    await c.stop('wake');count=len(calls)
    await c.tick(now+timedelta(seconds=5));assert len(calls)==count
    c.last_wake_date=None
    await c.set_schedule(False)
    await c.tick(now);assert c.session is None

async def test_restart_restores_session_and_settings(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    await c.start('wake');session=dict(c.session)
    await c.set_schedule(False)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    restored=entry.runtime_data
    assert restored.session==session and not restored.schedule_enabled
    await restored.tick(dt_util.utcnow()+timedelta(minutes=10))
    assert restored.session==session

async def test_expired_restart_never_turns_lights_on_late(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    await c.start('wake')
    await hass.config_entries.async_reload(entry.entry_id)
    c=entry.runtime_data;count=len(calls)
    await c.tick(dt_util.utcnow()+timedelta(hours=2))
    assert c.session is None and len(calls)==count

async def test_unavailable_light_prevents_start(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    hass.states.async_set('light.test_2','unavailable')
    with pytest.raises(HomeAssistantError):await c.start('wake')
    assert not calls and c.session is None

async def test_command_error_stops_sequence(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    await c.start('wake')
    hass.states.async_set('light.test_2','unavailable')
    await c.tick(dt_util.utcnow()+timedelta(minutes=10))
    assert c.session is None and 'failed' in c.status

async def test_options_block_during_run(hass,routine):
    entry,calls=routine
    await entry.runtime_data.start('wake')
    result=await hass.config_entries.options.async_init(entry.entry_id)
    result=await hass.config_entries.options.async_configure(result['flow_id'],dict(entry.data))
    assert result['errors']=={'base':'routine_active'}
    await entry.runtime_data.stop('wake')
    result=await hass.config_entries.options.async_configure(result['flow_id'],{**entry.data,'wake_duration':20})
    assert result['type']=='create_entry'
    await hass.async_block_till_done()
    assert entry.runtime_data.config['wake_duration']==20

async def test_config_rejects_overlapping_lights(hass,routine):
    entry,_=routine
    result=await hass.config_entries.flow.async_init(DOMAIN,context={'source':'user'})
    result=await hass.config_entries.flow.async_configure(result['flow_id'],dict(entry.data))
    assert result['errors']=={'base':'lights_in_use'}

def test_interpolation_endpoints():
    s={'start':0,'end':1800,'mode':'wake','initial':{'light.test':1},'target':204}
    assert levels(s,0)=={'light.test':1}
    assert levels(s,1800)=={'light.test':204}
    assert levels(s,9999)=={'light.test':204}
