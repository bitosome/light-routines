"""Start/stop switches and independent daily schedule enable switch."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from .entity import RoutineEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RoutineSwitch(entry.runtime_data, "wake", "Wake up", "mdi:weather-sunset-up"),
                        RoutineSwitch(entry.runtime_data, "bed", "Bedtime", "mdi:weather-night"),
                        RoutineSwitch(entry.runtime_data, "schedule", "Daily wake-up schedule", "mdi:alarm")])

class RoutineSwitch(RoutineEntity, SwitchEntity):
    @property
    def entity_category(self):
        return EntityCategory.CONFIG if self.key == "schedule" else None

    @property
    def is_on(self):
        if self.key == "schedule":
            return self.controller.schedule_enabled
        return bool(self.controller.session and self.controller.session["mode"] == self.key)

    @property
    def extra_state_attributes(self):
        return {"remaining_seconds": self.controller.remaining(self.key), "routine_status": self.controller.status,
                "scheduled_time": self.controller.config["wake_time"] if self.key in ("wake", "schedule") else None}

    async def async_turn_on(self, **kwargs):
        if self.key == "schedule":
            await self.controller.set_schedule(True)
        else:
            await self.controller.start(self.key)

    async def async_turn_off(self, **kwargs):
        if self.key == "schedule":
            await self.controller.set_schedule(False)
        else:
            await self.controller.stop(self.key)
