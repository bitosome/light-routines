"""Validate and translate explicit routine color settings to light capabilities."""
from homeassistant.exceptions import HomeAssistantError

RGB_MODES = {"hs", "xy", "rgb", "rgbw", "rgbww"}


def color_command(state, color):
    mode = color.get("mode", "unchanged")
    modes = set(state.attributes.get("supported_color_modes", []))
    if mode == "unchanged":
        return {}
    if mode == "temperature" and "color_temp" in modes:
        low = state.attributes.get("min_color_temp_kelvin", 2000)
        high = state.attributes.get("max_color_temp_kelvin", 6500)
        return {"color_temp_kelvin": max(low, min(high, int(color["kelvin"])))}
    if mode == "rgb" and modes & RGB_MODES:
        return {"rgb_color": list(color["rgb"])}
    raise HomeAssistantError("Selected light does not support this routine color mode")


def routine_color(config, mode):
    return {"mode": config.get(f"{mode}_color_mode", "unchanged"),
            "kelvin": config.get(f"{mode}_color_temperature", 2700),
            "rgb": config.get(f"{mode}_color_rgb", [255, 180, 100])}
