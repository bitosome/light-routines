"""Native daily start-time controls."""
from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.util import dt as dt_util
from .entity import RoutineEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RoutineTime(entry.runtime_data, "wake_time", "Wake-up start time", "mdi:alarm"),
                        RoutineTime(entry.runtime_data, "bed_time", "Bedtime start time", "mdi:alarm")])

class RoutineTime(RoutineEntity, TimeEntity):
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self):
        return dt_util.parse_time(self.controller.config[self.key])

    async def async_set_value(self, value):
        await self.controller.set_setting(self.key, value.isoformat())
