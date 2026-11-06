"""Base entity for LG Therma V devices."""

from dataclasses import dataclass
from typing import override

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import LgThermaVConfigEntry, LgThermaVDataUpdateCoordinator
from .lg_therma_v_modbus import Sdm120, ThermaV


@dataclass(frozen=True, kw_only=True)
class LgThermaVEntityDescription(EntityDescription):
    """Describe an LG Therma V entity."""

    component: str  # attribute name on the device, e.g. 'readings', 'controls'


class LgThermaVEntity[DeviceT: ThermaV | Sdm120](
    CoordinatorEntity[LgThermaVDataUpdateCoordinator[DeviceT]]
):
    """Defines a base LG Therma V entity."""

    _attr_has_entity_name = True
    entity_description: LgThermaVEntityDescription

    def __init__(
        self,
        entry: LgThermaVConfigEntry,
        coordinator: LgThermaVDataUpdateCoordinator[DeviceT],
        entity_description: LgThermaVEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def device(self) -> DeviceT:
        """The device this entity reads."""
        return self.coordinator.device

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        if not super().available or self.coordinator.data is None:
            return False
        return self.entity_description.component not in self.coordinator.data.failed
