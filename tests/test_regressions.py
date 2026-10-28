"""Regression scenarios found during the production/error review."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock
from zoneinfo import ZoneInfo

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util


async def test_bedtime_all_off_completes_without_commands(hass,routine):
    entry,calls=routine
    for i in range(1,4):
        hass.states.async_set(f'light.test_{i}','off',{'supported_color_modes':['brightness']})
    await entry.runtime_data.start('bed')
    assert entry.runtime_data.session is None
    assert entry.runtime_data.status=='Completed'
    assert calls==[]


async def test_cancel_preserves_reported_levels_and_does_not_relight_off_bulbs(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    await c.start('wake')
    hass.states.async_set('light.test_1','on',{'brightness':67,'supported_features':32})
    hass.states.async_set('light.test_2','off',{'brightness':200,'supported_features':32})
    hass.states.async_set('light.test_3','on',{'brightness':101,'supported_features':32})
    await c.stop('wake')
    assert calls[-3:]==[
        ('turn_on',{'entity_id':'light.test_1','brightness':67,'transition':0}),
        ('turn_off',{'entity_id':'light.test_2','transition':0}),
        ('turn_on',{'entity_id':'light.test_3','brightness':101,'transition':0}),
    ]
    assert c.session is None


async def test_cancel_unavailable_bulb_still_cancels_and_preserves_error(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    await c.start('wake')
    hass.states.async_set('light.test_2','unavailable')
    with pytest.raises(HomeAssistantError,match='Light unavailable'):
        await c.stop('wake')
    assert c.session is None and 'light.test_2' in c.last_error
    assert calls[-1][1]['entity_id']=='light.test_3'
    await hass.config_entries.async_reload(entry.entry_id)
    assert 'light.test_2' in entry.runtime_data.last_error
    assert 'Cancelled' in entry.runtime_data.status


async def test_recovery_waits_for_startup_lights_then_resumes(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    await c.start('wake');session=deepcopy(c.session)
    hass.states.async_set('light.test_2','unavailable')
    await hass.config_entries.async_reload(entry.entry_id)
    c=entry.runtime_data;count=len(calls)
    await c.tick(dt_util.utcnow()+timedelta(minutes=1))
    assert c.session==session and c.recovering
    assert c.status=='Waiting for lights after restart' and len(calls)==count
    hass.states.async_set('light.test_2','off',{'supported_features':32,'supported_color_modes':['brightness']})
    await c.tick(dt_util.utcnow()+timedelta(minutes=2))
    assert c.session==session and not c.recovering and len(calls)==count+3


async def test_recovery_timeout_does_not_late_start_lights(hass,routine):
    entry,calls=routine
    await entry.runtime_data.start('wake')
    await hass.config_entries.async_reload(entry.entry_id)
    c=entry.runtime_data;count=len(calls)
    hass.states.async_set('light.test_2','unavailable')
    await c.tick(dt_util.utcnow()+timedelta(minutes=1))
    await c.tick(dt_util.utcnow()+timedelta(hours=1))
    assert c.session is None and not c.recovering and len(calls)==count
    assert 'offline' in c.status


async def test_slow_command_does_not_queue_timer_ticks(hass,routine):
    entry,_=routine;c=entry.runtime_data
    entered=asyncio.Event();release=asyncio.Event();commands=[]
    async def delayed(call):
        commands.append(dict(call.data));entered.set();await release.wait()
    hass.services.async_register('light','turn_on',delayed)
    task=asyncio.create_task(c.start('wake'))
    await entered.wait()
    await asyncio.wait_for(c.tick(dt_util.utcnow()+timedelta(minutes=10)),0.2)
    assert len(commands)==1
    release.set();await task
    assert len(commands)==3
    assert all(d['brightness']==1 for d in commands)


async def test_service_timeout_reports_error_and_releases_controls(hass,routine):
    entry,_=routine;c=entry.runtime_data;release=asyncio.Event()
    async def hang(call):await release.wait()
    hass.services.async_register('light','turn_on',hang)
    try:
        with patch('custom_components.light_routines.controller.COMMAND_TIMEOUT',0.01):
            with pytest.raises(HomeAssistantError,match='timed out'):
                await c.start('wake')
        assert not c.lock.locked() and c.session is None
        assert 'light.test_1' in c.last_error
    finally:
        release.set()
        await hass.async_block_till_done()


async def test_manual_cancel_in_scheduled_minute_does_not_restart(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    now=dt_util.utcnow();c.config['wake_time']=dt_util.as_local(now).strftime('%H:%M:00')
    await c.start('wake');await c.stop('wake');count=len(calls)
    await c.tick(now+timedelta(seconds=1))
    assert c.session is None and len(calls)==count


async def test_schedule_runs_once_across_repeated_dst_hour(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    c.config['wake_time']='03:30:00'
    zone=ZoneInfo('Europe/Tallinn')
    first=datetime(2026,10,25,0,30,tzinfo=timezone.utc)
    second=first+timedelta(hours=1)
    with patch('custom_components.light_routines.controller.dt_util.as_local',side_effect=lambda t:t.astimezone(zone)):
        with patch('custom_components.light_routines.controller.dt_util.utcnow',return_value=first):
            await c.tick(first);await c.stop('wake')
        count=len(calls)
        with patch('custom_components.light_routines.controller.dt_util.utcnow',return_value=second):
            await c.tick(second)
        assert len(calls)==count and c.session is None


async def test_parameters_edited_midrun_survive_restart_without_changing_active_run(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    for i in range(1,4):
        hass.states.async_set(f'light.test_{i}','off',{'supported_color_modes':['color_temp'],'min_color_temp_kelvin':2202,'max_color_temp_kelvin':4000})
    await c.set_setting('wake_color_mode','temperature')
    await c.start('wake');session=deepcopy(c.session)
    await c.set_setting('wake_duration',10)
    await c.set_setting('wake_brightness',50)
    await c.set_setting('wake_color_temperature',3500)
    await hass.config_entries.async_reload(entry.entry_id)
    c=entry.runtime_data
    assert c.session==session and c.config['wake_color_temperature']==3500
    await c.tick(dt_util.utcnow()+timedelta(minutes=5))
    assert all(d['color_temp_kelvin']==2700 for _,d in calls[-3:])
    assert c.session['target']==204


async def test_config_blocks_only_light_changes_during_run(hass,routine):
    entry,_=routine;c=entry.runtime_data
    await c.start('wake')
    form=await hass.config_entries.options.async_init(entry.entry_id)
    data={**entry.data,'lights':['light.test_1']}
    result=await hass.config_entries.options.async_configure(form['flow_id'],data)
    assert result['errors']=={'base':'routine_active'}
    result=await hass.config_entries.options.async_configure(form['flow_id'],{**entry.data,'bed_duration':15})
    assert result['type']=='create_entry'
    await hass.async_block_till_done()
    assert c.config['bed_duration']==15 and c.session['mode']=='wake'


@pytest.mark.parametrize('bad_session',[{},[],{'mode':'wake','start':10,'end':10,'target':20,'initial':{'light.test_1':1}},
    {'mode':'wake','start':1,'end':100,'target':float('nan'),'initial':{'light.test_1':1}},
    {'mode':'wake','start':1,'end':100,'target':20,'initial':{'light.test_1':1},'color':[]}])
async def test_invalid_persisted_session_never_runs(hass,routine,bad_session):
    entry,calls=routine
    with patch('custom_components.light_routines.controller.Store.async_load',new=AsyncMock(return_value={'session':bad_session,'last_wake_date':'2026-10-28'})):
        await hass.config_entries.async_reload(entry.entry_id)
    c=entry.runtime_data
    assert c.session is None and 'could not be restored' in c.status and not calls
    assert c.last_wake_date=='2026-10-28'


@pytest.mark.parametrize('bad_value',[12.5,0,121])
async def test_options_and_entities_reject_same_invalid_durations(hass,routine,bad_value):
    entry,_=routine
    # validate is shared; the UI selector can reject out-of-range values before the flow.
    from custom_components.light_routines.settings import validate
    assert validate(hass,{**entry.data,'wake_duration':bad_value},entry.entry_id)=='invalid_number'
    with pytest.raises(HomeAssistantError):await entry.runtime_data.set_setting('wake_duration',bad_value)


async def test_options_normalizes_time_to_minute_resolution(hass,routine):
    entry,_=routine
    form=await hass.config_entries.options.async_init(entry.entry_id)
    result=await hass.config_entries.options.async_configure(form['flow_id'],{**entry.data,'wake_time':'06:45:59'})
    assert result['type']=='create_entry'
    await hass.async_block_till_done()
    assert entry.options['wake_time']=='06:45:00'


@pytest.mark.parametrize('brightness',[float('nan'),float('inf'),True,'200'])
async def test_invalid_reported_brightness_rejects_bed_start(hass,routine,brightness):
    entry,calls=routine
    hass.states.async_set('light.test_1','on',{'brightness':brightness,'supported_color_modes':['brightness']})
    with pytest.raises(HomeAssistantError,match='Brightness unavailable'):
        await entry.runtime_data.start('bed')
    assert not calls and entry.runtime_data.session is None

async def test_failed_initial_persistence_never_sends_later_commands(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    with patch.object(c.store,'async_save',new=AsyncMock(side_effect=OSError('disk unavailable'))):
        with pytest.raises(HomeAssistantError,match='no light commands were sent'):
            await c.start('wake')
    await c.tick(dt_util.utcnow()+timedelta(minutes=1))
    assert c.session is None and calls==[]
    assert 'could not save' in c.status


@pytest.mark.parametrize('mode',['wake','bed'])
@pytest.mark.parametrize('duration',[60,1800,7200])
@pytest.mark.parametrize('initial',[0,1,80,255])
def test_fade_is_bounded_monotonic_and_reaches_target(mode,duration,initial):
    from custom_components.light_routines.controller import levels
    target=204 if mode=='wake' else 0
    start=1 if mode=='wake' else initial
    session={'mode':mode,'start':100,'end':100+duration,'initial':{'light.test':start},'target':target}
    values=[levels(session,t)['light.test'] for t in range(95,106+duration,5)]
    assert values[0]==start and values[-1]==target
    assert all(min(start,target)<=v<=max(start,target) for v in values)
    assert values==sorted(values,reverse=mode=='bed')


async def test_duplicate_schedule_guard_survives_reload(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    now=dt_util.utcnow()
    c.config['wake_time']=dt_util.as_local(now).strftime('%H:%M:00')
    await c.tick(now);await c.stop('wake');count=len(calls)
    await hass.config_entries.async_reload(entry.entry_id)
    c=entry.runtime_data
    c.config['wake_time']=dt_util.as_local(now).strftime('%H:%M:00')
    await c.tick(now)
    assert c.session is None and len(calls)==count
