# Changelog

## 0.4.0

- Expose two time, five number and two color-mode select entities for routine configuration.
- Share persistent options between entities and Configure, with serialized writes and active-run guards.
- Filter native color-mode choices by bulb capabilities; preserve existing controls and entity identities.

## 0.3.0

- Add independent routine white-temperature/RGB color settings, applied with the starting brightness and restored with an active run. Validate bulb capabilities before sending commands.
- Expose live average brightness as a sensor and switch attribute, updated on bulb-state changes.
- Safely remove light-state listeners during reload and ignore queued option updates after unload.

## 0.2.1

- Preserve a previously disabled wake-up schedule when upgrading and enabling the new bedtime schedule.

## 0.2.0

- Expose independent daily wake-up and bedtime start toggles/times in native configuration.
- Keep schedule switches synchronized with configuration; apply settings without reloading the integration.
- Retain durations in minutes and maximum wake-up brightness; reject identical automatic start times. Bedtime remains manual by default.

## 0.1.1

- Classify Light Routines as a service integration so it appears in Devices & services → Integrations instead of Helpers. Existing entries, settings and entities are preserved.

## 0.1.0

- Configurable daily sunrise and manual bedtime routines for multiple dimmable lights.
- Independent start/stop switches, remaining-time sensors and schedule enable switch.
- Serialized cancellable steps, individual bedtime brightness, shared persistent settings and active-run restart recovery.
