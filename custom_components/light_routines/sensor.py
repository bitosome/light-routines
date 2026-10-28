"""Live remaining time and last outcome."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfTime
from .entity import RoutineEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Remaining(entry.runtime_data, "wake", "Wake up remaining", "mdi:timer-sand"),
                        Remaining(entry.runtime_data, "bed", "Bedtime remaining", "mdi:timer-sand"),
                        Status(entry.runtime_data, "status", "Status", "mdi:information-outline")])

class Remaining(RoutineEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    @property
    def native_value(self):
        return self.controller.remaining(self.key)

class Status(RoutineEntity, SensorEntity):
    @property
    def native_value(self):
        return self.controller.status
