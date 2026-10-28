"""Configuration validation shared by native flows and setting entities."""
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN
from .color import color_command, routine_color

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
        try:
            for mode in ("wake", "bed"):
                color_command(state, routine_color(data, mode))
        except HomeAssistantError:
            return "unsupported_color"
    return None

