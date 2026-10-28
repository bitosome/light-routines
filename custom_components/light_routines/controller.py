"""Single-writer, persisted light fades. No commands during entry setup."""
import asyncio
import math
from datetime import timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DEFAULTS
from .color import color_command, routine_color, RGB_MODES
from .settings import validate


def levels(session, now):
    """Absolute-time interpolation avoids accumulated scheduler drift."""
    progress = min(1.0, max(0.0, (now - session["start"]) / (session["end"] - session["start"])))
    # A smooth sunrise, without an abrupt initial increase; bedtime stays linear.
    fraction = progress * progress * (3 - 2 * progress) if session["mode"] == "wake" else progress
    return {light: round(value + (session["target"] - value) * fraction)
            for light, value in session["initial"].items()}


class Controller:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.config = {**DEFAULTS, **entry.data, **entry.options}
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.session = None
        self.schedule_enabled = self.config["wake_enabled"]
        self.bed_schedule_enabled = self.config["bed_enabled"]
        self.last_bed_date = None
        self.last_wake_date = None
        self.status = "Idle"
        self.listeners = set()
        self.lock = asyncio.Lock()
        self.last_levels = {}
        self.unsub = None
        self.closed = False
        self.color_applied = set()
        self.light_unsub = None

    async def setup(self):
        data = await self.store.async_load() or {}
        self.session = data.get("session")
        self.schedule_enabled = self.entry.options.get("wake_enabled", self.entry.data.get("wake_enabled", data.get("schedule_enabled", True)))
        self.config["wake_enabled"] = self.schedule_enabled
        self.last_bed_date = data.get("last_bed_date")
        self.last_wake_date = data.get("last_wake_date")
        if self.session:
            self.status = "Resuming"
        self.watch_lights()
        if self.hass.state == CoreState.running:
            self.activate()
        else:
            self.unsub = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self.activate)

    @callback
    def watch_lights(self):
        if self.light_unsub:
            self.light_unsub()
        self.light_unsub = async_track_state_change_event(self.hass, self.config["lights"], self.light_changed)

    @callback
    def light_changed(self, event):
        self.notify()

    def brightness(self):
        values = []
        for light in self.config["lights"]:
            state = self.hass.states.get(light)
            if not state or state.state not in ("on", "off"):
                return None
            value = state.attributes.get("brightness") if state.state == "on" else 0
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                return None
            values.append(max(0, min(255, value)) * 100 / 255)
        return round(sum(values) / len(values), 1) if values else None

    @callback
    def activate(self, event=None):
        self.unsub = async_track_time_interval(self.hass, self.tick, timedelta(seconds=5))

    @callback
    def notify(self):
        for listener in tuple(self.listeners):
            listener()

    async def save(self):
        await self.store.async_save({"session": self.session, "schedule_enabled": self.schedule_enabled,
                                     "last_wake_date": self.last_wake_date, "last_bed_date": self.last_bed_date})

    async def close(self):
        self.closed = True
        if self.unsub:
            self.unsub()
        if self.light_unsub:
            self.light_unsub()
            self.light_unsub = None
        async with self.lock:
            await self.save()

    def remaining(self, mode):
        if not self.session or self.session["mode"] != mode:
            return 0
        return max(0, math.ceil(self.session["end"] - dt_util.utcnow().timestamp()))

    async def update_config(self):
        async with self.lock:
            if self.closed:
                return
            self.config = {**self.config, **self.entry.data, **self.entry.options}
            self.schedule_enabled = self.config["wake_enabled"]
            self.bed_schedule_enabled = self.config["bed_enabled"]
            self.watch_lights()
            await self.save()
            self.notify()

    def color_modes(self):
        states = [self.hass.states.get(light) for light in self.config["lights"]]
        modes = [set(s.attributes.get("supported_color_modes", [])) if s else set() for s in states]
        result = ["unchanged"]
        if modes and all("color_temp" in mode for mode in modes):
            result.append("temperature")
        if modes and all(mode & RGB_MODES for mode in modes):
            result.append("rgb")
        return result

    async def set_setting(self, key, value):
        async with self.lock:
            if self.closed:
                raise HomeAssistantError("Integration is unloading")
            if self.session:
                raise HomeAssistantError("Stop the active routine before changing its settings")
            bounds = {"wake_duration": (1, 120), "bed_duration": (1, 120), "wake_brightness": (1, 100),
                      "wake_color_temperature": (1500, 6500), "bed_color_temperature": (1500, 6500)}
            if key in bounds:
                low, high = bounds[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not float(value).is_integer():
                    raise HomeAssistantError("Use a whole-number setting")
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not low <= value <= high:
                    raise HomeAssistantError(f"Setting must be between {low} and {high}")
                value = int(value)
            elif key in ("wake_time", "bed_time"):
                parsed = dt_util.parse_time(value) if isinstance(value, str) else None
                if parsed is None:
                    raise HomeAssistantError("Use a valid start time")
                value = parsed.replace(second=0, microsecond=0).isoformat()
            elif key in ("wake_color_mode", "bed_color_mode"):
                if value not in self.color_modes():
                    raise HomeAssistantError("The configured bulbs do not support this color mode")
            else:
                raise HomeAssistantError("Unknown routine setting")
            updated = {**self.config, key: value}
            error = validate(self.hass, updated, self.entry.entry_id)
            if error:
                raise HomeAssistantError({"same_start_time": "Choose different start times when both schedules are enabled",
                                          "unsupported_color": "The configured bulbs do not support this color mode"}.get(error, "Check the configured lights before changing settings"))
            # Entry options are the single durable configuration for entities and Configure.
            self.hass.config_entries.async_update_entry(self.entry, options={**self.entry.options,
                "wake_enabled": self.schedule_enabled, "bed_enabled": self.bed_schedule_enabled, key: value})
            self.config = updated
            self.notify()

    async def set_schedule(self, enabled, mode="wake"):
        async with self.lock:
            other_enabled = self.bed_schedule_enabled if mode == "wake" else self.schedule_enabled
            if enabled and other_enabled and self.config["wake_time"][:5] == self.config["bed_time"][:5]:
                raise HomeAssistantError("Choose different start times before enabling both schedules")
            if mode == "wake":
                self.schedule_enabled = enabled
            else:
                self.bed_schedule_enabled = enabled
            self.config[f"{mode}_enabled"] = enabled
            self.hass.config_entries.async_update_entry(self.entry, options={**self.entry.options, "wake_enabled": self.schedule_enabled, "bed_enabled": self.bed_schedule_enabled})
            await self.save()
            self.notify()

    async def start(self, mode):
        async with self.lock:
            if self.closed:
                raise HomeAssistantError("Integration is unloading")
            await self._start(mode)

    async def _start(self, mode):
        if self.session and self.session["mode"] == mode:
            return
        # Check all bulbs before replacing a running sequence.
        initial = {}
        color = routine_color(self.config, mode)
        for light in self.config["lights"]:
            state = self.hass.states.get(light)
            if not state or state.state not in ("on", "off"):
                raise HomeAssistantError(f"Light unavailable: {light}")
            if mode == "bed" and state.state == "on" and not isinstance(state.attributes.get("brightness"), (int, float)):
                raise HomeAssistantError(f"Brightness unavailable: {light}")
            color_command(state, color)
            initial[light] = (state.attributes.get("brightness", 0) or 0) if state.state == "on" else 0
        if self.session:
            await self._stop()
            # Stop freezes the old fade at its calculated level; use that level.
            if mode == "bed":
                initial.update(self.last_levels)
        now = dt_util.utcnow().timestamp()
        self.session = {"mode": mode, "start": now, "end": now + 60 * self.config[f"{mode}_duration"],
                        "initial": initial if mode == "bed" else {light: 1 for light in initial},
                        "target": round(self.config["wake_brightness"] * 255 / 100) if mode == "wake" else 0, "color": color}
        self.last_levels = {}
        self.color_applied = set()
        self.status = "Waking up" if mode == "wake" else "Going to bed"
        await self.save()  # Persist intent before commanding lights.
        try:
            await self.apply(now, transition=0)
        except Exception:
            await self.failed()
            raise
        self.notify()

    async def stop(self, mode):
        async with self.lock:
            if self.session and self.session["mode"] == mode:
                await self._stop()

    async def _stop(self):
        # Cancel queued work first. Freeze any in-flight bulb transition explicitly.
        session = self.session
        self.session = None
        self.status = "Cancelled"
        await self.save()
        self.notify()
        if session:
            values = levels(session, dt_util.utcnow().timestamp())
            self.last_levels = values
            errors = []
            for light, value in values.items():
                try:
                    await self.command(light, value, 0)
                except HomeAssistantError as err:
                    errors.append(str(err))
            if errors:
                self.status = "Cancelled · some lights unavailable"
                self.notify()
                raise HomeAssistantError("; ".join(errors))

    async def command(self, light, value, transition, color=None):
        state = self.hass.states.get(light)
        if not state or state.state not in ("on", "off"):
            raise HomeAssistantError(f"Light unavailable: {light}")
        data = {"entity_id": light}
        if state.attributes.get("supported_features", 0) & 32:
            data["transition"] = transition
        if value > 0:
            data["brightness"] = max(1, min(255, value))
            if color:
                data.update(color_command(state, color))
        await self.hass.services.async_call("light", "turn_on" if value > 0 else "turn_off", data, blocking=True)

    async def apply(self, now, transition=5):
        values = levels(self.session, now)
        for light, value in values.items():
            if self.last_levels.get(light) != value:
                await self.command(light, value, 0 if now >= self.session["end"] else transition,
                                   self.session.get("color") if light not in self.color_applied else None)
                if value > 0:
                    self.color_applied.add(light)
                self.last_levels[light] = value
        if now >= self.session["end"]:
            self.session = None
            self.status = "Completed"
            await self.save()

    async def failed(self):
        self.session = None
        self.status = "Stopped · light command failed"
        await self.save()
        self.notify()

    async def tick(self, now):
        async with self.lock:
            if self.closed:
                return
            try:
                if self.session:
                    # Resume a still-current fade; do not switch lights on hours after a missed wake-up.
                    if self.status == "Resuming" and now.timestamp() > self.session["end"]:
                        self.session = None
                        self.status = "Interrupted while Home Assistant was offline"
                        await self.save()
                    else:
                        self.status = "Waking up" if self.session["mode"] == "wake" else "Going to bed"
                        await self.apply(now.timestamp())
                local = dt_util.as_local(now)
                date = local.date().isoformat()
                for mode, enabled, last_date in [("wake", self.schedule_enabled, self.last_wake_date), ("bed", self.bed_schedule_enabled, self.last_bed_date)]:
                    if enabled and local.strftime("%H:%M") == self.config[f"{mode}_time"][:5] and last_date != date:
                        setattr(self, f"last_{mode}_date", date)
                        await self.save()
                        await self._start(mode)
            except HomeAssistantError:
                await self.failed()
            self.notify()
