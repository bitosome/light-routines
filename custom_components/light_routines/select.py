"""Capability-aware native color-mode selection."""
from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from .entity import RoutineEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RoutineColorMode(entry.runtime_data, "wake_color_mode", "Wake-up color mode", "mdi:palette"),
                        RoutineColorMode(entry.runtime_data, "bed_color_mode", "Bedtime color mode", "mdi:palette")])

class RoutineColorMode(RoutineEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "routine_color_mode"

    @property
    def current_option(self):
        return self.controller.config[self.key]

    @property
    def options(self):
        return self.controller.color_modes()

    async def async_select_option(self, option):
        await self.controller.set_setting(self.key, option)
