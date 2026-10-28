"""Shared configuration keys."""
DOMAIN = "light_routines"
DEFAULTS = {"name": "Light routines", "lights": [], "wake_time": "07:15:00", "wake_duration": 30, "bed_duration": 30, "wake_brightness": 80, "wake_enabled": True, "bed_enabled": False, "bed_time": "20:00:00"}

for _routine in ("wake", "bed"):
    DEFAULTS.update({f"{_routine}_color_mode": "unchanged", f"{_routine}_color_temperature": 2700, f"{_routine}_color_rgb": [255, 180, 100]})
