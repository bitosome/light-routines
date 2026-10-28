"""Persisted native numeric controls, shared with the options flow."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from .entity import RoutineEntity

SETTINGS = [
    ("wake_duration", "Wake-up duration", "mdi:timer-outline", 1, 120, "min"),
    ("bed_duration", "Bedtime duration", "mdi:timer-outline", 1, 120, "min"),
    ("wake_brightness", "Wake-up maximum brightness", "mdi:brightness-6", 1, 100, "%"),
    ("wake_color_temperature", "Wake-up white temperature", "mdi:temperature-kelvin", 1500, 6500, "K"),
    ("bed_color_temperature", "Bedtime white temperature", "mdi:temperature-kelvin", 1500, 6500, "K"),
]

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RoutineNumber(entry.runtime_data, *setting) for setting in SETTINGS])

class RoutineNumber(RoutineEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1

    def __init__(self, controller, key, name, icon, minimum, maximum, unit):
        super().__init__(controller, key, name, icon)
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_unit_of_measurement = unit

    @property
    def available(self):
        return not self.key.endswith("color_temperature") or "temperature" in self.controller.color_modes()

    @property
    def native_value(self):
        return self.controller.config[self.key]

    async def async_set_native_value(self, value):
        await self.controller.set_setting(self.key, value)
