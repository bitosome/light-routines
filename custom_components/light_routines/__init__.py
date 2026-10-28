"""Configurable wake-up and bedtime lighting."""
from .controller import Controller

PLATFORMS = ["switch", "sensor"]

async def async_setup_entry(hass, entry):
    controller = entry.runtime_data = Controller(hass, entry)
    await controller.setup()
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.close()
        return True
    return False

async def async_update_options(hass, entry):
    await entry.runtime_data.update_config()
