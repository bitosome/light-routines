# Light Routines

A configurable HACS integration for gentle daily wake-up lighting and bedtime fades. Uses existing Home Assistant lights, with no cloud service, custom dashboard dependency or household identifiers.

## Install

1. In HACS, add `https://github.com/bitosome/light-routines` as a custom **Integration** repository, then download it.
2. Restart Home Assistant if prompted.
3. Add **Light Routines** under Settings → Devices & services → Add integration.
4. Choose a name, one or more dimmable lights, independent automatic start toggles/times, durations and wake-up target.

Each entry is one room. A bulb cannot belong to two entries. Configure parameters at any time; changes apply to the next run. Stop an active routine only before changing the selected bulbs. Settings are stored by Home Assistant and shared by all users. Choose **Configure** on the integration entry to edit wake-up/bedtime automatic start toggles, start times, durations (1–120 minutes), and maximum wake-up brightness (1–100%). New settings apply without a Home Assistant restart.

## Controls

- **Wake up** switch: start immediately at minimum brightness and fade to the selected target, using a smooth sunrise curve. Default: 30 minutes, 80%.
- **Bedtime** switch: fade each bulb from its own current brightness to fully off. Bulbs already off remain off. Default: 30 minutes.
- Turn either switch **off** to cancel and preserve each bulb’s reported current brightness (already-off bulbs stay off). Starting the opposite routine cancels the existing fade first. Starting an already running routine is idempotent.
- **Daily wake-up schedule** switch: independently enable/disable the automatic wake-up. Enabled initially, every day at 07:15 in Home Assistant's local timezone. **Daily bedtime schedule** is off initially, with a configurable 20:00 default start time. Both toggles and start times are also in the integration configuration. Schedule switches and configuration stay synchronized. Manual routine switches remain available when schedules are disabled.
- **Wake up remaining / Bedtime remaining** duration sensors and **Status** sensor expose progress and outcomes. Remaining time is also an attribute on each routine switch. Add these entities to any dashboard, including Space Hub tiles.

## Reliability and limits

The controller uses absolute timestamps and short, five-second steps (native short transitions where supported), so it can cancel a fade instead of leaving a 30-minute Zigbee transition running. Duplicate brightness commands are skipped. Only the selected bulbs are controlled. Each routine can keep the current color, apply a white temperature, or apply RGB. Choose the mode first: the temperature value is used only for White temperature; the color picker is used only for RGB. All selected bulbs must support the chosen mode. White temperature is clamped to each bulb’s supported Kelvin range. Color and starting brightness are sent together, including when an active run resumes; already-off bulbs stay off during bedtime. Existing configurations keep their color until a color mode is selected. A light must be powered and reachable.

An active routine and schedule enablement are persisted before commands are sent. After a Home Assistant restart, an unfinished routine waits for its bulbs to become available after startup and then resumes, retaining its original end time, target and color. An already expired routine is marked interrupted without turning lights on late. Missed daily schedules are not replayed later; one automatic start is allowed per local calendar date. Cancelling during the scheduled minute does not restart it. Disabling the schedule does not cancel an already active fade.

Light failures stop the routine and surface in Status; the last error is retained across restart in its attributes and written to the HA log. Commands have a bounded timeout so one unresponsive bulb cannot hold the controls indefinitely. Other lights may already have received their most recent short step. Manually changing a bulb during a routine does not cancel the routine: use its switch to cancel before taking over. Short transitions depend on device firmware; visible timing can vary by a few seconds. No physical light commands are sent merely by adding or configuring the integration.

## Development

Python 3.14; `pip install -r requirements-test.txt`, then `pytest -q`. Tests use real Home Assistant lifecycle fixtures and mocked light services, never physical devices.

**Current brightness** reports the mean of the configured bulbs’ actual reported brightness (off = 0%), also available as `current_brightness_pct` on the routine switches. Missing/unavailable brightness makes the aggregate unavailable, rather than presenting a misleading percentage. This is actual light telemetry, not elapsed routine progress or a commanded estimate.

## Native setting entities

Each room exposes nine configuration entities, usable from dashboards, automations and Companion:

| Domain | Settings |
| --- | --- |
| `time` | Wake-up start time, bedtime start time (local time, minute resolution) |
| `number` | Wake-up duration, bedtime duration (minutes), wake-up maximum brightness (%), wake-up white temperature, bedtime white temperature (K) |
| `select` | Wake-up color mode, bedtime color mode |

These entities edit the same persistent Home Assistant entry options shown in **Configure**. No separate helper values or browser-local settings are used. Select options reflect capabilities shared by the selected bulbs; tunable-white bulbs offer Keep current color and White temperature. Temperature values are clamped to each bulb's supported range when applied. Temperature entities are unavailable for bulbs without that capability. RGB values for color-capable bulbs remain in Configure.

Parameters can be edited while a routine is running. Changes are saved for the next run; the active run keeps its original settings, including after a Home Assistant restart. Only changing the selected bulbs requires stopping first. Changing settings never sends a light command. Light selection remains in Configure. Existing entity IDs and run switches are preserved.

## Regression checks

The test suite covers settings edits during active fades, restart persistence of the current run versus next-run parameters, delayed bulb availability on startup, invalid saved runs, failed storage before startup, individual cancellation brightness, slow/failed light commands, duplicate starts in a scheduled minute and across the repeated daylight-saving hour, capability validation and monotonic fade endpoints. All device calls are mocked. Firmware-specific transition behavior still requires observation on the actual bulbs.
