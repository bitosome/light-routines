# Changelog

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
