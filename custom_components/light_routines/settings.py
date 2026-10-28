"""Configuration validation shared by native flows and setting entities."""
import math
from homeassistant.util import dt as dt_util
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN
from .color import color_command, routine_color

def validate(hass, data, entry_id=None):
    if not data["name"].strip() or not data["lights"]:
        return "required_values"
    for key, low, high in [("wake_duration", 1, 120), ("bed_duration", 1, 120), ("wake_brightness", 1, 100),
                           ("wake_color_temperature", 1500, 6500), ("bed_color_temperature", 1500, 6500)]:
        value = data.get(key, 2700 if key.endswith("temperature") else None)
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                or not float(value).is_integer() or not low <= value <= high):
            return "invalid_number"
    for key in ("wake_time", "bed_time"):
        if not isinstance(data.get(key), str) or dt_util.parse_time(data[key]) is None:
            return "invalid_time"
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



def normalize(data):
    """The scheduler and native time entities operate at minute resolution."""
    result = dict(data)
    for key in ("wake_time", "bed_time"):
        result[key] = dt_util.parse_time(result[key]).replace(second=0, microsecond=0).isoformat()
    return result
