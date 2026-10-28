"""Native Home Assistant configuration and options."""
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DOMAIN, DEFAULTS


def schema(values):
    return vol.Schema({
        vol.Required("name", default=values["name"]): selector.TextSelector(),
        vol.Required("lights", default=values["lights"]): selector.EntitySelector(selector.EntitySelectorConfig(domain="light", multiple=True)),
        vol.Required("wake_enabled", default=values["wake_enabled"]): selector.BooleanSelector(),
        vol.Required("wake_time", default=values["wake_time"]): selector.TimeSelector(),
        vol.Required("wake_duration", default=values["wake_duration"]): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=120, step=1, mode="box", unit_of_measurement="min")),
        vol.Required("wake_brightness", default=values["wake_brightness"]): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=100, step=1, mode="box", unit_of_measurement="%")),
        vol.Required("bed_enabled", default=values["bed_enabled"]): selector.BooleanSelector(),
        vol.Required("bed_time", default=values["bed_time"]): selector.TimeSelector(),
        vol.Required("bed_duration", default=values["bed_duration"]): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=120, step=1, mode="box", unit_of_measurement="min")),
    })


def validate(hass, data, entry_id=None):
    if not data["name"].strip() or not data["lights"]:
        return "required_values"
    if data.get("wake_enabled", True) and data.get("bed_enabled", False) and data["wake_time"][:5] == data["bed_time"][:5]:
        return "same_start_time"
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id != entry_id and set(data["lights"]) & set(entry.options.get("lights", entry.data.get("lights", []))):
            return "lights_in_use"
    for light in data["lights"]:
        state = hass.states.get(light)
        if not state or not set(state.attributes.get("supported_color_modes", [])) - {"onoff", "unknown"}:
            return "not_dimmable"
    return None


class LightRoutinesFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            error = validate(self.hass, user_input)
            if not error:
                return self.async_create_entry(title=user_input["name"], data=user_input)
            errors["base"] = error
        return self.async_show_form(step_id="user", data_schema=schema({**DEFAULTS, **(user_input or {})}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return RoutineOptions()


class RoutineOptions(OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            controller = getattr(self.config_entry, "runtime_data", None)
            error = "routine_active" if controller and controller.session else validate(self.hass, user_input, self.config_entry.entry_id)
            if not error:
                return self.async_create_entry(data=user_input)
            errors["base"] = error
        controller = getattr(self.config_entry, "runtime_data", None)
        current = {"wake_enabled": controller.schedule_enabled, "bed_enabled": controller.bed_schedule_enabled} if controller else {}
        values = {**DEFAULTS, **self.config_entry.data, **self.config_entry.options, **current, **(user_input or {})}
        return self.async_show_form(step_id="init", data_schema=schema(values), errors=errors)
