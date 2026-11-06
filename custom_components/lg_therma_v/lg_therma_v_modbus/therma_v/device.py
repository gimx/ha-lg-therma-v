"""The top-level object for an LG Therma V heat pump."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from modbus_connection import ModbusConnectionError, ModbusError, ModbusTimeoutError
from modbus_connection.model import Device

from ..model import UpdateReport
from .controls import Controls
from .december_2023 import CompressorModulation, EnergyCounters
from .product import Product
from .readings import Readings, RefrigerantCycle, WaterPressure
from .settings import Settings
from .status import Status

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

_LOGGER = logging.getLogger(__name__)

# The heat pump ignores its first requests on a fresh link and answers from
# the third. They have to go to an input register or a coil, so the warm-up
# reads input register 30001.
WARM_UP_REQUESTS: Final = 3
_WARM_UP_ADDRESS: Final = 0

READING_COMPONENTS: Final[tuple[str, ...]] = (
    "status",
    "readings",
    "water_pressure",
    "refrigerant_cycle",
    "energy_counters",
)
SETTING_COMPONENTS: Final[tuple[str, ...]] = (
    "controls",
    "settings",
    "compressor_modulation",
)
# What only products from December 2023 on have.
DECEMBER_2023_COMPONENTS: Final[tuple[str, ...]] = (
    "energy_counters",
    "compressor_modulation",
)


class ThermaV(Device):
    """An LG Therma V heat pump reached through a ``ModbusUnit``.

    The heat pump faults with ``CH 03`` when nothing polls it for five
    minutes, so a caller that starts polling should keep going.

    ``from_december_2023`` says the product is from December 2023 or later,
    which adds the energy counters and the compressor modulation. Older
    products refuse those registers, so they are left alone unless asked
    for: ``energy_counters`` and ``compressor_modulation`` are ``None``.
    """

    def __init__(self, unit: ModbusUnit, *, from_december_2023: bool = False) -> None:
        """Set up the sub-systems."""
        super().__init__(unit)
        self.from_december_2023 = from_december_2023
        self.status = Status(unit)
        self.readings = Readings(unit)
        self.water_pressure = WaterPressure(unit)
        self.refrigerant_cycle = RefrigerantCycle(unit)
        self.controls = Controls(unit)
        self.settings = Settings(unit)
        self.product = Product(unit)
        self.energy_counters: EnergyCounters | None = None
        self.compressor_modulation: CompressorModulation | None = None
        if from_december_2023:
            self.energy_counters = EnergyCounters(unit)
            self.compressor_modulation = CompressorModulation(unit)

    async def _async_setup(self) -> None:
        """Send the requests a fresh link has to spend before it is answered."""
        for attempt in range(1, WARM_UP_REQUESTS + 1):
            try:
                await self.modbus_unit.read_input_registers(_WARM_UP_ADDRESS, 1)
            except ModbusConnectionError:
                raise
            except ModbusTimeoutError:
                _LOGGER.debug("Warm-up request %d was not answered", attempt)

    async def async_update_readings(self) -> UpdateReport:
        """Poll what the heat pump reports: its state bits and its sensors."""
        return await self.async_poll(READING_COMPONENTS)

    async def async_update_settings(self) -> UpdateReport:
        """Poll what the heat pump has been told: its switches and targets.

        Run it after a write to read back what took effect.
        """
        return await self.async_poll(SETTING_COMPONENTS)

    async def async_update(self) -> UpdateReport:
        """Poll readings and settings in one merged report."""
        report = await self.async_update_readings()
        return await self.async_poll(SETTING_COMPONENTS, report)

    async def async_read_product(self) -> bool:
        """Read the product group and type once; ``False`` if it did not answer.

        Not part of a poll, as it never changes. A heat pump that does not
        serve the two registers, or does not answer, is not an error: the
        product is just unknown. A dead link still raises.
        """
        await self.async_ensure_setup()
        try:
            await self.product.async_update()
        except ModbusConnectionError:
            raise
        except ModbusError as err:
            _LOGGER.debug("The product registers were not read: %s", err)
            return False
        return True
