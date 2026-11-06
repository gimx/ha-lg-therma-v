"""Support for LG Therma V binary sensors."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LgThermaVConfigEntry
from .entity import LgThermaVEntity, LgThermaVEntityDescription
from .lg_therma_v_modbus import ThermaV

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LgThermaVBinarySensorEntityDescription(
    LgThermaVEntityDescription, BinarySensorEntityDescription
):
    """Describe an LG Therma V binary sensor; the key is the field it reads."""


def _running(
    key: str, *, enabled: bool = True
) -> LgThermaVBinarySensorEntityDescription:
    return LgThermaVBinarySensorEntityDescription(
        key=key,
        component="status",
        translation_key=key,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_registry_enabled_default=enabled,
    )


def _diagnostic(
    key: str,
    device_class: BinarySensorDeviceClass | None = None,
    *,
    enabled: bool = False,
) -> LgThermaVBinarySensorEntityDescription:
    return LgThermaVBinarySensorEntityDescription(
        key=key,
        component="status",
        translation_key=key,
        device_class=device_class,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=enabled,
    )


BINARY_SENSOR_DESCRIPTIONS: tuple[LgThermaVBinarySensorEntityDescription, ...] = (
    _running("compressor"),
    _running("defrosting"),
    _running("dhw_heating"),
    _running("backup_heater_step_1"),
    _running("backup_heater_step_2", enabled=False),
    _running("dhw_boost_heater", enabled=False),
    _running("mix_pump", enabled=False),
    _running("water_pump", enabled=False),
    _running("external_water_pump", enabled=False),
    _running("solar_pump", enabled=False),
    _running("dhw_tank_disinfection", enabled=False),
    _running("cooling", enabled=False),
    _running("silent_mode", enabled=False),
    _diagnostic("error", BinarySensorDeviceClass.PROBLEM, enabled=True),
    _diagnostic("water_flow_too_low", BinarySensorDeviceClass.PROBLEM, enabled=True),
    _diagnostic("emergency_operation_available_space"),
    _diagnostic("emergency_operation_available_dhw"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LgThermaVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG Therma V binary sensor platform."""
    coordinator = entry.runtime_data.heat_pump
    async_add_entities(
        LgThermaVBinarySensor(entry, coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class LgThermaVBinarySensor(LgThermaVEntity[ThermaV], BinarySensorEntity):
    """Defines an LG Therma V binary sensor."""

    entity_description: LgThermaVBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the bit is set."""
        value: bool | None = getattr(self.device.status, self.entity_description.key)
        return value
