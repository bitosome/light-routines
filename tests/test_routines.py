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
    assert len(switches)==4
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

async def test_options_exposes_each_schedule_duration_and_brightness(hass, routine):
    entry,_=routine
    form=await hass.config_entries.options.async_init(entry.entry_id)
    values=form['data_schema']({})
    assert values['wake_enabled'] is True and values['bed_enabled'] is False
    assert values['wake_time']=='07:15:00'
    assert values['wake_duration']==30 and values['bed_duration']==30
    assert values['wake_brightness']==80
    result=await hass.config_entries.options.async_configure(form['flow_id'],{**values,'wake_enabled':False,'bed_enabled':True,'bed_time':'21:30:00','bed_duration':15,'wake_duration':45,'wake_brightness':60})
    assert result['type']=='create_entry'
    await hass.async_block_till_done()
    c=entry.runtime_data
    assert not c.schedule_enabled and c.bed_schedule_enabled
    assert c.config['wake_brightness']==60 and c.config['bed_duration']==15
    await c.set_schedule(False,'bed')
    await hass.async_block_till_done()
    form=await hass.config_entries.options.async_init(entry.entry_id)
    assert form['data_schema']({})['bed_enabled'] is False

async def test_bed_schedule_runs_once_and_manual_wake_works_when_disabled(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    await c.set_schedule(False)
    await hass.async_block_till_done()
    c.config['bed_time']=dt_util.as_local(dt_util.utcnow()).strftime('%H:%M:00')
    c.bed_schedule_enabled=True
    await c.tick(dt_util.utcnow())
    assert c.session['mode']=='bed'
    await c.stop('bed');count=len(calls)
    await c.tick(dt_util.utcnow())
    assert len(calls)==count
    await c.start('wake')
    assert c.session['mode']=='wake'

async def test_same_enabled_schedule_time_rejected(hass,routine):
    entry,_=routine
    form=await hass.config_entries.options.async_init(entry.entry_id)
    data={**DEFAULTS,**entry.data,'bed_enabled':True,'bed_time':'07:15:00'}
    result=await hass.config_entries.options.async_configure(form['flow_id'],data)
    assert result['errors']=={'base':'same_start_time'}

async def test_legacy_disabled_schedule_survives_bed_switch(hass,routine):
    entry,_=routine;c=entry.runtime_data
    # Old releases persisted schedule enablement only in the runtime store.
    c.schedule_enabled=False
    await c.save()
    from unittest.mock import AsyncMock
    from types import SimpleNamespace
    from custom_components.light_routines.controller import Controller
    data={k:v for k,v in entry.data.items() if k not in ('wake_enabled','bed_enabled','bed_time')}
    legacy=Controller(hass,SimpleNamespace(data=data,options={},entry_id='legacy'))
    legacy.store.async_load=AsyncMock(return_value={'schedule_enabled':False})
    await legacy.setup()
    assert legacy.config['wake_enabled'] is False
    await legacy.update_config()
    assert legacy.schedule_enabled is False
    await legacy.close()

async def test_routine_temperature_applied_at_start_and_restored(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    for i in range(1,4):
        hass.states.async_set(f'light.test_{i}','off',{'supported_color_modes':['color_temp'],'supported_features':32,'min_color_temp_kelvin':2202,'max_color_temp_kelvin':4000})
    c.config.update(wake_color_mode='temperature',wake_color_temperature=2700)
    await c.start('wake')
    assert all(d['color_temp_kelvin']==2700 and d['brightness']==1 for _,d in calls[-3:])
    await c.tick(dt_util.utcnow()+timedelta(minutes=5))
    assert all('color_temp_kelvin' not in d for _,d in calls[-3:])
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await entry.runtime_data.tick(dt_util.utcnow()+timedelta(minutes=10))
    assert all(d['color_temp_kelvin']==2700 for _,d in calls[-3:])

async def test_bed_color_keeps_off_bulbs_off(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    for i,b in enumerate([200,80,0],1):
        hass.states.async_set(f'light.test_{i}','on' if b else 'off',{'brightness':b,'supported_color_modes':['rgb'],'supported_features':32})
    c.config.update(bed_color_mode='rgb',bed_color_rgb=[255,80,10])
    await c.start('bed')
    assert all(d['rgb_color']==[255,80,10] for _,d in calls[:2])
    assert calls[2][0]=='turn_off' and 'rgb_color' not in calls[2][1]

async def test_unsupported_color_does_not_partially_start(hass,routine):
    entry,calls=routine;c=entry.runtime_data
    c.config.update(wake_color_mode='rgb')
    with pytest.raises(HomeAssistantError):await c.start('wake')
    assert not calls and c.session is None

async def test_brightness_uses_actual_states_and_reports_missing(hass,routine):
    entry,_=routine;c=entry.runtime_data
    assert c.brightness()==36.6
    hass.states.async_set('light.test_1','on',{'brightness':255})
    await hass.async_block_till_done()
    assert c.brightness()==43.8
    assert hass.states.get('switch.test_room_wake_up').attributes['current_brightness_pct']==43.8
    hass.states.async_set('light.test_2','unavailable')
    await hass.async_block_till_done()
    assert c.brightness() is None
    assert hass.states.get('switch.test_room_wake_up').attributes['current_brightness_pct'] is None

async def test_color_validation_in_options(hass,routine):
    entry,_=routine
    result=await hass.config_entries.options.async_init(entry.entry_id)
    data={**DEFAULTS,**entry.data,'wake_color_mode':'rgb'}
    result=await hass.config_entries.options.async_configure(result['flow_id'],data)
    assert result['errors']=={'base':'unsupported_color'}


def test_temperature_clamps_to_bulb_range():
    from types import SimpleNamespace
    from custom_components.light_routines.color import color_command
    state=SimpleNamespace(attributes={'supported_color_modes':['color_temp'],'min_color_temp_kelvin':2202,'max_color_temp_kelvin':4000})
    assert color_command(state,{'mode':'temperature','kelvin':1800})=={'color_temp_kelvin':2202}
    assert color_command(state,{'mode':'temperature','kelvin':6500})=={'color_temp_kelvin':4000}
