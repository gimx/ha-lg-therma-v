"""Data update coordinator for LG Therma V devices."""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusError

from .const import DOMAIN, MANUFACTURER, METER_MANUFACTURER, SCAN_INTERVAL
from .lg_therma_v_modbus import ProductType, Sdm120, ThermaV, UpdateReport

_LOGGER = logging.getLogger(__name__)


class LgThermaVDataUpdateCoordinator[DeviceT: ThermaV | Sdm120](
    DataUpdateCoordinator[UpdateReport]
):
    """Class to manage fetching the data of one Modbus unit."""

    config_entry: LgThermaVConfigEntry
    device: DeviceT

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LgThermaVConfigEntry,
        device: DeviceT,
        device_info: dr.DeviceInfo,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{entry.title} {device_info.get('model', '')}".strip(),
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.device = device
        self.device_info = device_info
        self._failing: set[str] = set()

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self.device.async_update()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        if not report.updated:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_component_answered",
            ) from ExceptionGroup(
                "all components failed to refresh", list(report.failed.values())
            )
        self._log_component_changes(report)
        return report

    def _log_component_changes(self, report: UpdateReport) -> None:
        """Log a component's first failure and its recovery, once each."""
        for name, cause in report.failed.items():
            if name not in self._failing:
                self._failing.add(name)
                _LOGGER.warning(
                    "%s: %s failed to refresh, its entities are unavailable: %s",
                    self.name,
                    name,
                    cause,
                )
        for name in report.updated & self._failing:
            self._failing.discard(name)
            _LOGGER.info("%s: %s is available again", self.name, name)


@dataclass
class LgThermaVRuntimeData:
    """Class to hold runtime data."""

    heat_pump: LgThermaVDataUpdateCoordinator[ThermaV]
    meter: LgThermaVDataUpdateCoordinator[Sdm120] | None


type LgThermaVConfigEntry = ConfigEntry[LgThermaVRuntimeData]


def heat_pump_device_info(
    entry: ConfigEntry, product_type: ProductType | None = None
) -> dr.DeviceInfo:
    """Describe the heat pump of a config entry, as far as its product is known."""
    model = "Therma V"
    if product_type is not None:
        model = f"{model} {product_type.name.replace('_', ' ').title()}"
    return dr.DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        model=model,
        name=entry.title,
    )


def meter_device_info(entry: ConfigEntry, heat_pump_device_id: str) -> dr.DeviceInfo:
    """Describe the energy meter of a config entry, behind its heat pump."""
    return dr.DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_meter")},
        manufacturer=METER_MANUFACTURER,
        model="SDM120",
        translation_key="meter",
        via_device_id=heat_pump_device_id,
    )
