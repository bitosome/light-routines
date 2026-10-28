"""Real HA entity services with mocked light devices, never physical actions."""
import pytest
from homeassistant.exceptions import HomeAssistantError
from custom_components.light_routines.const import DEFAULTS

async def test_entities_and_config_are_synchronized(hass,routine):
    entry,calls=routine
    assert hass.states.get('number.test_room_wake_up_duration').state=='30'
    assert hass.states.get('time.test_room_wake_up_start_time').state=='07:15:00'
    await hass.services.async_call('number','set_value',{'entity_id':'number.test_room_wake_up_duration','value':45},blocking=True)
    await hass.services.async_call('number','set_value',{'entity_id':'number.test_room_wake_up_maximum_brightness','value':65},blocking=True)
    await hass.services.async_call('time','set_value',{'entity_id':'time.test_room_wake_up_start_time','time':'06:45:00'},blocking=True)
    await hass.async_block_till_done()
    assert entry.options['wake_duration']==45
    assert entry.options['wake_time']=='06:45:00'
    form=await hass.config_entries.options.async_init(entry.entry_id)
    values=form['data_schema']({})
    assert values['wake_duration']==45 and values['wake_brightness']==65
    saved=await hass.config_entries.options.async_configure(form['flow_id'],{**values,'bed_duration':20})
    assert saved['type']=='create_entry'
    await hass.async_block_till_done()
    assert float(hass.states.get('number.test_room_bedtime_duration').state)==20
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert float(hass.states.get('number.test_room_wake_up_duration').state)==45
    assert hass.states.get('time.test_room_wake_up_start_time').state=='06:45:00'
    assert calls==[]

async def test_color_entity_capabilities_and_persistence(hass,routine):
    entry,calls=routine
    for i in range(1,4):
        hass.states.async_set(f'light.test_{i}','off',{'supported_color_modes':['color_temp'],'min_color_temp_kelvin':2202,'max_color_temp_kelvin':4000})
    await hass.async_block_till_done()
    select=hass.states.get('select.test_room_wake_up_color_mode')
    assert select.attributes['options']==['unchanged','temperature']
    await hass.services.async_call('select','select_option',{'entity_id':select.entity_id,'option':'temperature'},blocking=True)
    await hass.services.async_call('number','set_value',{'entity_id':'number.test_room_wake_up_white_temperature','value':3000},blocking=True)
    await hass.async_block_till_done()
    assert entry.options['wake_color_mode']=='temperature'
    assert entry.options['wake_color_temperature']==3000
    assert calls==[]
    await entry.runtime_data.start('wake')
    assert all(d['color_temp_kelvin']==3000 for _,d in calls[-3:])

async def test_active_fade_saves_settings_without_changing_running_snapshot(hass,routine):
    entry,calls=routine
    await entry.runtime_data.start('wake')
    session=dict(entry.runtime_data.session);count=len(calls)
    await hass.services.async_call('number','set_value',{'entity_id':'number.test_room_wake_up_duration','value':10},blocking=True)
    await hass.services.async_call('number','set_value',{'entity_id':'number.test_room_wake_up_maximum_brightness','value':50},blocking=True)
    await hass.async_block_till_done()
    assert entry.runtime_data.config['wake_duration']==10
    assert entry.runtime_data.session==session and len(calls)==count
    await entry.runtime_data.stop('wake')
    await entry.runtime_data.start('wake')
    assert entry.runtime_data.session['target']==128
    assert entry.runtime_data.session['end']-entry.runtime_data.session['start']==600


async def test_invalid_numbers_and_schedule_conflicts_rejected(hass,routine):
    entry,_=routine;c=entry.runtime_data
    for value in [0,121,12.5,float('nan'),True,'30']:
        with pytest.raises(HomeAssistantError):await c.set_setting('wake_duration',value)
    await c.set_schedule(True,'bed')
    with pytest.raises(HomeAssistantError,match='different start times'):
        await c.set_setting('bed_time','07:15:00')
    assert c.config['bed_time']=='20:00:00'
    assert c.config['wake_duration']==30

async def test_concurrent_setting_edits_preserve_both_values(hass,routine):
    import asyncio
    entry,_=routine;c=entry.runtime_data
    await asyncio.gather(c.set_setting('wake_duration',50),c.set_setting('bed_duration',15))
    await hass.async_block_till_done()
    assert entry.options['wake_duration']==50 and entry.options['bed_duration']==15
    assert c.config['wake_duration']==50 and c.config['bed_duration']==15
