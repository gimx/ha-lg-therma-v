"""Support for LG Therma V buttons."""

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from modbus_connection import ModbusError

from .const import DOMAIN
from .coordinator import LgThermaVConfigEntry
from .entity import LgThermaVEntity, LgThermaVEntityDescription
from .lg_therma_v_modbus import ThermaV

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LgThermaVButtonEntityDescription(
    LgThermaVEntityDescription, ButtonEntityDescription
):
    """Describe an LG Therma V button; the key is the trigger coil it sets."""


BUTTON_DESCRIPTIONS: tuple[LgThermaVButtonEntityDescription, ...] = (
    LgThermaVButtonEntityDescription(
        key="trigger_dhw_disinfection",
        component="controls",
        translation_key="trigger_dhw_disinfection",
    ),
    LgThermaVButtonEntityDescription(
        key="trigger_emergency_operation",
        component="controls",
        translation_key="trigger_emergency_operation",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LgThermaVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG Therma V button platform."""
    coordinator = entry.runtime_data.heat_pump
    async_add_entities(
        LgThermaVButton(entry, coordinator, description)
        for description in BUTTON_DESCRIPTIONS
    )


class LgThermaVButton(LgThermaVEntity[ThermaV], ButtonEntity):
    """Defines an LG Therma V button."""

    entity_description: LgThermaVButtonEntityDescription

    async def async_press(self) -> None:
        """Start the operation; the heat pump keeps its status otherwise."""
        try:
            await self.device.controls.write(self.entity_description.key, True)
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="write_failed"
            ) from err
        await self.coordinator.async_request_refresh()
