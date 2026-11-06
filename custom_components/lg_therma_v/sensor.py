"""Support for LG Therma V sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import LgThermaVConfigEntry
from .entity import LgThermaVEntity, LgThermaVEntityDescription
from .lg_therma_v_modbus import EnergyState, OperationCycle, Sdm120, ThermaV

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LgThermaVSensorEntityDescription[DeviceT: ThermaV | Sdm120](
    LgThermaVEntityDescription, SensorEntityDescription
):
    """Describe an LG Therma V or SDM120 sensor."""

    value_fn: Callable[[DeviceT], StateType]


def _read(component: str, key: str) -> Callable[[ThermaV], StateType]:
    """Read one attribute of one of the heat pump's components."""
    return lambda device: getattr(getattr(device, component), key)


def _temperature(
    component: str,
    key: str,
    *,
    enabled: bool = False,
    category: EntityCategory | None = None,
) -> LgThermaVSensorEntityDescription[ThermaV]:
    return LgThermaVSensorEntityDescription(
        key=key,
        component=component,
        translation_key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=category,
        entity_registry_enabled_default=enabled,
        value_fn=_read(component, key),
    )


def _pressure(
    component: str, key: str, *, category: EntityCategory | None = None
) -> LgThermaVSensorEntityDescription[ThermaV]:
    return LgThermaVSensorEntityDescription(
        key=key,
        component=component,
        translation_key=key,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=category,
        entity_registry_enabled_default=False,
        value_fn=_read(component, key),
    )


def _enum(
    key: str, enum_type: type[IntEnum]
) -> LgThermaVSensorEntityDescription[ThermaV]:
    return LgThermaVSensorEntityDescription(
        key=key,
        component="readings",
        translation_key=key,
        device_class=SensorDeviceClass.ENUM,
        options=[member.name.lower() for member in enum_type],
        value_fn=lambda device: (
            None
            if (value := getattr(device.readings, key)) is None
            else value.name.lower()
        ),
    )


SENSOR_DESCRIPTIONS: tuple[LgThermaVSensorEntityDescription[ThermaV], ...] = (
    _temperature("readings", "water_inlet_temperature", enabled=True),
    _temperature("readings", "water_outlet_temperature"),
    _temperature("readings", "backup_heater_outlet_temperature"),
    _temperature("readings", "dhw_tank_temperature"),
    _temperature("readings", "solar_collector_temperature"),
    _temperature("readings", "circuit_1_room_air_temperature", enabled=True),
    _temperature("readings", "circuit_2_flow_temperature", enabled=True),
    _temperature("readings", "circuit_2_room_air_temperature"),
    _temperature("readings", "outside_air_temperature", enabled=True),
    LgThermaVSensorEntityDescription(
        key="flow_rate",
        component="readings",
        translation_key="flow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_read("readings", "flow_rate"),
    ),
    _enum("operation_cycle", OperationCycle),
    _enum("energy_state", EnergyState),
    LgThermaVSensorEntityDescription(
        key="error_code",
        component="readings",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_read("readings", "error_code"),
    ),
    _pressure("water_pressure", "water_pressure"),
    # The refrigerant circuit; LG's register list names these the way the
    # outdoor unit's service tools do.
    _temperature(
        "refrigerant_cycle", "pipe_in_temperature", category=EntityCategory.DIAGNOSTIC
    ),
    _temperature(
        "refrigerant_cycle", "pipe_out_temperature", category=EntityCategory.DIAGNOSTIC
    ),
    _temperature(
        "refrigerant_cycle", "suction_temperature", category=EntityCategory.DIAGNOSTIC
    ),
    _temperature(
        "refrigerant_cycle", "discharge_temperature", category=EntityCategory.DIAGNOSTIC
    ),
    _temperature(
        "refrigerant_cycle",
        "heat_exchanger_temperature",
        category=EntityCategory.DIAGNOSTIC,
    ),
    _temperature(
        "refrigerant_cycle",
        "evaporator_outlet_temperature",
        category=EntityCategory.DIAGNOSTIC,
    ),
    _pressure("refrigerant_cycle", "high_pressure", category=EntityCategory.DIAGNOSTIC),
    _pressure("refrigerant_cycle", "low_pressure", category=EntityCategory.DIAGNOSTIC),
    LgThermaVSensorEntityDescription(
        key="compressor_frequency",
        component="refrigerant_cycle",
        translation_key="compressor_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_read("refrigerant_cycle", "compressor_frequency"),
    ),
)


def _accumulative(key: str) -> LgThermaVSensorEntityDescription[ThermaV]:
    return LgThermaVSensorEntityDescription(
        key=key,
        component="energy_counters",
        translation_key=key,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_read("energy_counters", key),
    )


def _instantaneous(key: str) -> LgThermaVSensorEntityDescription[ThermaV]:
    # LG gives these in Wh as well, so no device class claims more than that.
    return LgThermaVSensorEntityDescription(
        key=key,
        component="energy_counters",
        translation_key=key,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_read("energy_counters", key),
    )


# Only products from December 2023 on have these registers.
ENERGY_SENSOR_DESCRIPTIONS: tuple[LgThermaVSensorEntityDescription[ThermaV], ...] = (
    _instantaneous("energy_instantaneous_total"),
    _accumulative("energy_accumulative_total"),
    _instantaneous("energy_instantaneous_heat"),
    _accumulative("energy_accumulative_cool"),
    _accumulative("energy_accumulative_dhw"),
)

METER_SENSOR_DESCRIPTIONS: tuple[LgThermaVSensorEntityDescription[Sdm120], ...] = (
    LgThermaVSensorEntityDescription(
        key="meter_voltage",
        component="readings",
        translation_key="meter_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.readings.voltage,
    ),
    LgThermaVSensorEntityDescription(
        key="meter_power",
        component="readings",
        translation_key="meter_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.readings.active_power,
    ),
    LgThermaVSensorEntityDescription(
        key="meter_energy",
        component="readings",
        translation_key="meter_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda device: device.readings.total_energy,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LgThermaVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG Therma V sensor platform."""
    runtime_data = entry.runtime_data
    descriptions = list(SENSOR_DESCRIPTIONS)
    if runtime_data.heat_pump.device.energy_counters is not None:
        descriptions.extend(ENERGY_SENSOR_DESCRIPTIONS)
    entities: list[LgThermaVSensor[ThermaV] | LgThermaVSensor[Sdm120]] = [
        LgThermaVSensor(entry, runtime_data.heat_pump, description)
        for description in descriptions
    ]
    if runtime_data.meter is not None:
        entities.extend(
            LgThermaVSensor(entry, runtime_data.meter, description)
            for description in METER_SENSOR_DESCRIPTIONS
        )
    async_add_entities(entities)


class LgThermaVSensor[DeviceT: ThermaV | Sdm120](
    LgThermaVEntity[DeviceT], SensorEntity
):
    """Defines an LG Therma V sensor."""

    entity_description: LgThermaVSensorEntityDescription[DeviceT]

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.device)
