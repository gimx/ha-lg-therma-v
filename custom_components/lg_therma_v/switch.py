"""Support for LG Therma V switches."""

from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
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
class LgThermaVSwitchEntityDescription(
    LgThermaVEntityDescription, SwitchEntityDescription
):
    """Describe an LG Therma V switch; the key is the coil it drives."""


SWITCH_DESCRIPTIONS: tuple[LgThermaVSwitchEntityDescription, ...] = (
    LgThermaVSwitchEntityDescription(
        key="heating_cooling_enabled",
        component="controls",
        translation_key="heating_cooling_enabled",
    ),
    LgThermaVSwitchEntityDescription(
        key="dhw_enabled", component="controls", translation_key="dhw_enabled"
    ),
    LgThermaVSwitchEntityDescription(
        key="silent_mode", component="controls", translation_key="silent_mode"
    ),
    LgThermaVSwitchEntityDescription(
        key="emergency_stop",
        component="controls",
        translation_key="emergency_stop",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LgThermaVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG Therma V switch platform."""
    coordinator = entry.runtime_data.heat_pump
    async_add_entities(
        LgThermaVSwitch(entry, coordinator, description)
        for description in SWITCH_DESCRIPTIONS
    )


class LgThermaVSwitch(LgThermaVEntity[ThermaV], SwitchEntity):
    """Defines an LG Therma V switch."""

    entity_description: LgThermaVSwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the coil is on."""
        value: bool | None = getattr(self.device.controls, self.entity_description.key)
        return value

    async def _async_write(self, value: bool) -> None:
        """Write the coil, then read back what took effect."""
        try:
            await self.device.controls.write(self.entity_description.key, value)
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="write_failed"
            ) from err
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_write(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_write(False)
