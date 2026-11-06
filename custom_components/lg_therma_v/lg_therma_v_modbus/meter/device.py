"""The top-level object for an Eastron SDM120 energy meter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from modbus_connection.model import Device

from ..model import UpdateReport
from .readings import Sdm120Readings

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit


class Sdm120(Device):
    """An Eastron SDM120 single-phase meter reached through a ``ModbusUnit``."""

    def __init__(self, unit: ModbusUnit) -> None:
        """Set up the sub-systems."""
        super().__init__(unit)
        self.readings = Sdm120Readings(unit)

    async def async_update(self) -> UpdateReport:
        """Poll the meter."""
        return await self.async_poll(("readings",))
