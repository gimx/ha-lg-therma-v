"""Support for LG Therma V numbers."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from modbus_connection import ModbusError

from .const import DOMAIN
from .coordinator import LgThermaVConfigEntry
from .entity import LgThermaVEntity, LgThermaVEntityDescription
from .lg_therma_v_modbus import ThermaV
from .lg_therma_v_modbus.therma_v import (
    MODULATION_MAX,
    MODULATION_MIN,
    MODULATION_NOT_USED,
)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LgThermaVNumberEntityDescription(
    LgThermaVEntityDescription, NumberEntityDescription
):
    """Describe an LG Therma V number; the key is the holding register it sets."""


def _shift(key: str, *, enabled: bool) -> LgThermaVNumberEntityDescription:
    return LgThermaVNumberEntityDescription(
        key=key,
        component="settings",
        translation_key=key,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=enabled,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        native_min_value=-5,
        native_max_value=5,
        native_step=1,
        mode=NumberMode.BOX,
    )


def _room_air(key: str) -> LgThermaVNumberEntityDescription:
    return LgThermaVNumberEntityDescription(
        key=key,
        component="settings",
        translation_key=key,
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        mode=NumberMode.BOX,
    )


NUMBER_DESCRIPTIONS: tuple[LgThermaVNumberEntityDescription, ...] = (
    _shift("circuit_1_auto_mode_shift", enabled=True),
    _shift("circuit_2_auto_mode_shift", enabled=False),
    _room_air("circuit_1_room_air_temperature"),
    _room_air("circuit_2_room_air_temperature"),
)

# Only products from December 2023 on have the register.
MODULATION_DESCRIPTION = LgThermaVNumberEntityDescription(
    key="compressor_modulation",
    component="compressor_modulation",
    translation_key="compressor_modulation",
    entity_category=EntityCategory.CONFIG,
    native_min_value=MODULATION_NOT_USED,
    native_max_value=MODULATION_MAX,
    native_step=1,
    mode=NumberMode.BOX,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LgThermaVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG Therma V number platform."""
    coordinator = entry.runtime_data.heat_pump
    descriptions = list(NUMBER_DESCRIPTIONS)
    if coordinator.device.compressor_modulation is not None:
        descriptions.append(MODULATION_DESCRIPTION)
    async_add_entities(
        LgThermaVNumber(entry, coordinator, description) for description in descriptions
    )


class LgThermaVNumber(LgThermaVEntity[ThermaV], NumberEntity):
    """Defines an LG Therma V number."""

    entity_description: LgThermaVNumberEntityDescription

    @property
    @override
    def native_value(self) -> float | None:
        """Return the register value."""
        component = getattr(self.device, self.entity_description.component)
        value: float | None = getattr(component, self.entity_description.key)
        return value

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write the register, then read back what took effect."""
        component = getattr(self.device, self.entity_description.component)
        written = value if self.native_step != 1 else int(value)
        try:
            await component.write(self.entity_description.key, written)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_compressor_modulation",
                translation_placeholders={
                    "minimum": str(MODULATION_MIN),
                    "maximum": str(MODULATION_MAX),
                },
            ) from err
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="write_failed"
            ) from err
        await self.coordinator.async_request_refresh()
