"""Support for LG Therma V climate entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from modbus_connection import ModbusError

from .const import DOMAIN
from .coordinator import LgThermaVConfigEntry
from .entity import LgThermaVEntity, LgThermaVEntityDescription
from .lg_therma_v_modbus import OperationMode, ThermaV

PARALLEL_UPDATES = 1

_HVAC_MODES = {
    OperationMode.COOL: HVACMode.COOL,
    OperationMode.HEAT: HVACMode.HEAT,
    OperationMode.AUTO: HVACMode.AUTO,
}
_OPERATION_MODES = {mode: operation for operation, mode in _HVAC_MODES.items()}


@dataclass(frozen=True, kw_only=True)
class LgThermaVClimateEntityDescription(
    LgThermaVEntityDescription, ClimateEntityDescription
):
    """Describe an LG Therma V climate entity."""

    current_temperature_fn: Callable[[ThermaV], float | None]
    target_temperature_fn: Callable[[ThermaV], float | None]
    target_temperature_field: str
    min_temp: float
    max_temp: float
    # The operation mode is one register for the whole heat pump; the hot-water
    # tank does not follow it, so it only ever heats.
    follows_operation_mode: bool = True


CLIMATE_DESCRIPTIONS: tuple[LgThermaVClimateEntityDescription, ...] = (
    LgThermaVClimateEntityDescription(
        key="circuit_1",
        component="settings",
        translation_key="circuit_1",
        current_temperature_fn=lambda device: device.readings.water_outlet_temperature,
        target_temperature_fn=lambda device: (
            device.settings.circuit_1_target_temperature
        ),
        target_temperature_field="circuit_1_target_temperature",
        min_temp=16,
        max_temp=55,
    ),
    LgThermaVClimateEntityDescription(
        key="circuit_2",
        component="settings",
        translation_key="circuit_2",
        current_temperature_fn=lambda device: (
            device.readings.circuit_2_room_air_temperature
        ),
        target_temperature_fn=lambda device: (
            device.settings.circuit_2_target_temperature
        ),
        target_temperature_field="circuit_2_target_temperature",
        min_temp=16,
        max_temp=55,
    ),
    LgThermaVClimateEntityDescription(
        key="dhw",
        component="settings",
        translation_key="dhw",
        current_temperature_fn=lambda device: device.readings.dhw_tank_temperature,
        target_temperature_fn=lambda device: device.settings.dhw_target_temperature,
        target_temperature_field="dhw_target_temperature",
        min_temp=40,
        max_temp=55,
        follows_operation_mode=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LgThermaVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG Therma V climate platform."""
    coordinator = entry.runtime_data.heat_pump
    async_add_entities(
        LgThermaVClimate(entry, coordinator, description)
        for description in CLIMATE_DESCRIPTIONS
    )


class LgThermaVClimate(LgThermaVEntity[ThermaV], ClimateEntity):
    """Defines an LG Therma V heating circuit or hot-water tank."""

    entity_description: LgThermaVClimateEntityDescription
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_precision = PRECISION_TENTHS

    @override
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the climate entity."""
        super().__init__(*args, **kwargs)
        description = self.entity_description
        self._attr_min_temp = description.min_temp
        self._attr_max_temp = description.max_temp
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_hvac_modes = (
            list(_HVAC_MODES.values())
            if description.follows_operation_mode
            else [HVACMode.HEAT]
        )

    @property
    @override
    def available(self) -> bool:
        """Whether both the settings and the readings answered the last poll."""
        if not super().available or self.coordinator.data is None:
            return False
        return "readings" not in self.coordinator.data.failed

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the measured temperature."""
        return self.entity_description.current_temperature_fn(self.device)

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self.entity_description.target_temperature_fn(self.device)

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return the operation mode of the heat pump."""
        if not self.entity_description.follows_operation_mode:
            return HVACMode.HEAT
        mode = self.device.settings.operation_mode
        return None if mode is None else _HVAC_MODES[mode]

    async def _async_write(self, field: str, value: Any) -> None:
        """Write a holding register, then read back what took effect."""
        try:
            await self.device.settings.write(field, value)
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="write_failed"
            ) from err

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature, and the mode if one comes along."""
        if (mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self._async_set_mode(HVACMode(mode))
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._async_write(
                self.entity_description.target_temperature_field, temperature
            )
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the operation mode of the heat pump."""
        await self._async_set_mode(hvac_mode)
        await self.coordinator.async_request_refresh()

    async def _async_set_mode(self, hvac_mode: HVACMode) -> None:
        """Write the operation mode, unless this entity has none to set."""
        if not self.entity_description.follows_operation_mode:
            return
        await self._async_write("operation_mode", _OPERATION_MODES[hvac_mode])
