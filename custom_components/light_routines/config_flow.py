"""Native Home Assistant configuration and options."""
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DOMAIN, DEFAULTS
from .settings import validate, normalize


def color_schema(values, mode):
    return {
        vol.Required(f"{mode}_color_mode", default=values[f"{mode}_color_mode"]): selector.SelectSelector(selector.SelectSelectorConfig(options=[{"value": "unchanged", "label": "Keep current color"}, {"value": "temperature", "label": "White temperature"}, {"value": "rgb", "label": "RGB color (color bulbs only)"}], mode="dropdown")),
        vol.Required(f"{mode}_color_temperature", default=values[f"{mode}_color_temperature"]): selector.NumberSelector(selector.NumberSelectorConfig(min=1500, max=6500, step=1, mode="box", unit_of_measurement="K")),
        vol.Required(f"{mode}_color_rgb", default=values[f"{mode}_color_rgb"]): selector.ColorRGBSelector(),
    }


def schema(values):
    return vol.Schema({
        vol.Required("name", default=values["name"]): selector.TextSelector(),
        vol.Required("lights", default=values["lights"]): selector.EntitySelector(selector.EntitySelectorConfig(domain="light", multiple=True)),
        vol.Required("wake_enabled", default=values["wake_enabled"]): selector.BooleanSelector(),
        vol.Required("wake_time", default=values["wake_time"]): selector.TimeSelector(),
        vol.Required("wake_duration", default=values["wake_duration"]): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=120, step=1, mode="box", unit_of_measurement="min")),
        vol.Required("wake_brightness", default=values["wake_brightness"]): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=100, step=1, mode="box", unit_of_measurement="%")),
        **color_schema(values, "wake"),
        vol.Required("bed_enabled", default=values["bed_enabled"]): selector.BooleanSelector(),
        vol.Required("bed_time", default=values["bed_time"]): selector.TimeSelector(),
        vol.Required("bed_duration", default=values["bed_duration"]): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=120, step=1, mode="box", unit_of_measurement="min")),
        **color_schema(values, "bed"),
    })




class LightRoutinesFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            error = validate(self.hass, user_input)
            if not error:
                return self.async_create_entry(title=user_input["name"], data=normalize(user_input))
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
            lights_changed = controller and controller.session and set(user_input["lights"]) != set(controller.session["initial"])
            error = "routine_active" if lights_changed else validate(self.hass, user_input, self.config_entry.entry_id)
            if not error:
                return self.async_create_entry(data=normalize(user_input))
            errors["base"] = error
        controller = getattr(self.config_entry, "runtime_data", None)
        current = {"wake_enabled": controller.schedule_enabled, "bed_enabled": controller.bed_schedule_enabled} if controller else {}
        values = {**DEFAULTS, **self.config_entry.data, **self.config_entry.options, **current, **(user_input or {})}
        return self.async_show_form(step_id="init", data_schema=schema(values), errors=errors)
