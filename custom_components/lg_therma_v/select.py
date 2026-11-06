"""Support for LG Therma V selects."""

from dataclasses import dataclass
from enum import IntEnum
from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from modbus_connection import ModbusError

from .const import DOMAIN
from .coordinator import LgThermaVConfigEntry
from .entity import LgThermaVEntity, LgThermaVEntityDescription
from .lg_therma_v_modbus import ControlMethod, EnergyState, ThermaV

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LgThermaVSelectEntityDescription(
    LgThermaVEntityDescription, SelectEntityDescription
):
    """Describe an LG Therma V select; the key is the holding register it sets."""

    enum_type: type[IntEnum]


SELECT_DESCRIPTIONS: tuple[LgThermaVSelectEntityDescription, ...] = (
    LgThermaVSelectEntityDescription(
        key="control_method",
        component="settings",
        translation_key="control_method",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        enum_type=ControlMethod,
        options=[method.name.lower() for method in ControlMethod],
    ),
    LgThermaVSelectEntityDescription(
        key="energy_state_input",
        component="settings",
        translation_key="energy_state_input",
        entity_category=EntityCategory.CONFIG,
        enum_type=EnergyState,
        options=[state.name.lower() for state in EnergyState],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LgThermaVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG Therma V select platform."""
    coordinator = entry.runtime_data.heat_pump
    async_add_entities(
        LgThermaVSelect(entry, coordinator, description)
        for description in SELECT_DESCRIPTIONS
    )


class LgThermaVSelect(LgThermaVEntity[ThermaV], SelectEntity):
    """Defines an LG Therma V select."""

    entity_description: LgThermaVSelectEntityDescription

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected value."""
        value: IntEnum | None = getattr(
            self.device.settings, self.entity_description.key
        )
        return None if value is None else value.name.lower()

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selection, then read back what took effect."""
        try:
            await self.device.settings.write(
                self.entity_description.key,
                self.entity_description.enum_type[option.upper()],
            )
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="write_failed"
            ) from err
        await self.coordinator.async_request_refresh()
