"""Shared entities for one room's routines."""
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity
from .const import DOMAIN

class RoutineEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller, key, name, icon):
        self.controller = controller
        self.key = key
        self._attr_unique_id = f"{controller.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, controller.entry.entry_id)},
            name=controller.config["name"], manufacturer="Bitosome", model="Light routines")

    async def async_added_to_hass(self):
        self.controller.listeners.add(self.changed)
        self.async_on_remove(lambda: self.controller.listeners.discard(self.changed))

    @callback
    def changed(self):
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        return {"settings_apply_to": "next_run", "active_routine": self.controller.session["mode"] if self.controller.session else None}
