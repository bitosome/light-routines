import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.light_routines.const import DEFAULTS, DOMAIN

@pytest.fixture
async def routine(hass, enable_custom_integrations):
    for i, brightness in enumerate([200, 80, 0], 1):
        hass.states.async_set(f"light.test_{i}", "on" if brightness else "off", {"brightness":brightness,"supported_features":32,"supported_color_modes":["brightness"]})
    calls = []
    async def service(call):
        calls.append((call.service, dict(call.data)))
    hass.services.async_register("light", "turn_on", service)
    hass.services.async_register("light", "turn_off", service)
    entry = MockConfigEntry(domain=DOMAIN, title="Test room", data={**DEFAULTS,"name":"Test room","lights":[f"light.test_{i}" for i in range(1,4)]})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    yield entry, calls
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
