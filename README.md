# Light Routines

A configurable HACS integration for gentle daily wake-up lighting and manual bedtime fades. Uses existing Home Assistant lights, with no cloud service, custom dashboard dependency or household identifiers.

## Install

1. In HACS, add `https://github.com/bitosome/light-routines` as a custom **Integration** repository, then download it.
2. Restart Home Assistant if prompted.
3. Add **Light Routines** under Settings → Devices & services → Add integration.
4. Choose a name, one or more dimmable lights, daily wake-up time, durations and wake-up target.

Each entry is one room. A bulb cannot belong to two entries. Configure changes through the integration's options after stopping any running routine. Settings are stored by Home Assistant and shared by all users.

## Controls

- **Wake up** switch: start immediately at minimum brightness and fade to the selected target, using a smooth sunrise curve. Default: 30 minutes, 80%.
- **Bedtime** switch: fade each bulb from its own current brightness to fully off. Bulbs already off remain off. Default: 30 minutes.
- Turn either switch **off** to cancel and freeze the calculated current brightness. Starting the opposite routine cancels the existing fade first. Starting an already running routine is idempotent.
- **Daily wake-up schedule** switch: independently enable/disable the automatic wake-up. Enabled initially, every day at 07:15 in Home Assistant's local timezone. Bedtime is manual.
- **Wake up remaining / Bedtime remaining** duration sensors and **Status** sensor expose progress and outcomes. Remaining time is also an attribute on each routine switch. Add these entities to any dashboard, including Space Hub tiles.

## Reliability and limits

The controller uses absolute timestamps and short, five-second steps (native short transitions where supported), so it can cancel a fade instead of leaving a 30-minute Zigbee transition running. Duplicate brightness commands are skipped. Only the selected bulbs are controlled; color temperature is left unchanged. A light must be powered and reachable.

An active routine and schedule enablement are persisted before commands are sent. After a Home Assistant restart, an unfinished routine resumes after startup. An already expired routine is marked interrupted without turning lights on late. Missed daily schedules are not replayed later; one automatic start is allowed per local calendar date. Cancelling during the scheduled minute does not restart it. Disabling the schedule does not cancel an already active fade.

Light failures stop the routine and surface in Status. Other lights may already have received their most recent short step. Manually changing a bulb during a routine does not cancel the routine: use its switch to cancel before taking over. Short transitions depend on device firmware; visible timing can vary by a few seconds. No physical light commands are sent merely by adding or configuring the integration.

## Development

Python 3.14; `pip install -r requirements-test.txt`, then `pytest -q`. Tests use real Home Assistant lifecycle fixtures and mocked light services, never physical devices.
