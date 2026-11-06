"""Diagnostics support for LG Therma V."""

from typing import Any

from homeassistant.core import HomeAssistant
from modbus_connection import ModbusError

from .coordinator import LgThermaVConfigEntry
from .lg_therma_v_modbus import Sdm120, ThermaV


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LgThermaVConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    raw: dict[str, Any] = {}
    read_error: dict[str, str] = {}

    names: dict[str, tuple[ThermaV | Sdm120, tuple[str, ...]]] = {
        "heat_pump": (
            runtime_data.heat_pump.device,
            ("status", "readings", "controls", "settings"),
        ),
    }
    if runtime_data.meter is not None:
        names["meter"] = (runtime_data.meter.device, ("readings",))
    for key, (device, components) in names.items():
        try:
            raw[key] = await device.async_read_raw(components)
        except ModbusError as err:
            read_error[key] = type(err).__name__

    return {
        "has_meter": runtime_data.meter is not None,
        "failed": {
            "heat_pump": sorted(runtime_data.heat_pump.data.failed),
            **(
                {"meter": sorted(runtime_data.meter.data.failed)}
                if runtime_data.meter is not None
                else {}
            ),
        },
        "read_error": read_error,
        "raw": raw,
    }
