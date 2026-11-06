"""Integrate LG Therma V heat pumps into Home Assistant."""

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from modbus_connection import ModbusError

from .const import (
    CONF_FROM_DECEMBER_2023,
    CONF_METER_UNIT_ID,
    CONF_UNIT_ID,
    DECEMBER_2023_KEYS,
)
from .coordinator import (
    LgThermaVConfigEntry,
    LgThermaVDataUpdateCoordinator,
    LgThermaVRuntimeData,
    heat_pump_device_info,
    meter_device_info,
)
from .helpers import create_modbus_params
from .lg_therma_v_modbus import ProductType, Sdm120, ThermaV

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: LgThermaVConfigEntry) -> bool:
    """Set up LG Therma V from a config entry."""
    params = create_modbus_params(entry.data)
    if not entry.data.get(CONF_FROM_DECEMBER_2023, False):
        _async_remove_december_2023_entities(hass, entry)

    heat_pump_unit = ThermaV(
        async_get_unit(hass, entry, params, entry.data[CONF_UNIT_ID]),
        from_december_2023=entry.data.get(CONF_FROM_DECEMBER_2023, False),
    )
    heat_pump = LgThermaVDataUpdateCoordinator(
        hass, entry, heat_pump_unit, heat_pump_device_info(entry)
    )
    # A heat pump that is off or still warming up is retried by Home Assistant.
    await heat_pump.async_config_entry_first_refresh()

    # Up front: the meter's device names the heat pump's as its parent.
    heat_pump.device_info = heat_pump_device_info(
        entry, await _async_read_product_type(heat_pump_unit)
    )
    heat_pump_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **heat_pump.device_info
    )

    meter: LgThermaVDataUpdateCoordinator[Sdm120] | None = None
    if (meter_unit_id := entry.data.get(CONF_METER_UNIT_ID)) is not None:
        meter = LgThermaVDataUpdateCoordinator(
            hass,
            entry,
            Sdm120(async_get_unit(hass, entry, params, meter_unit_id)),
            meter_device_info(entry, heat_pump_device.id),
        )
        # The meter is a bonus, so it must not keep the heat pump from setting up.
        try:
            await meter.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            await meter.async_refresh()

    entry.runtime_data = LgThermaVRuntimeData(heat_pump, meter)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


@callback
def _async_remove_december_2023_entities(
    hass: HomeAssistant, entry: LgThermaVConfigEntry
) -> None:
    """Drop the entities of registers the product is no longer said to have."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id.removeprefix(f"{entry.entry_id}_") in DECEMBER_2023_KEYS:
            registry.async_remove(entity.entity_id)


async def _async_read_product_type(device: ThermaV) -> ProductType | None:
    """Read what kind of heat pump this is, if it says."""
    try:
        await device.async_read_product()
    except ModbusError:
        return None
    return device.product.product_type


async def async_unload_entry(hass: HomeAssistant, entry: LgThermaVConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
