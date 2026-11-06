"""The registers only products from December 2023 on have."""

from __future__ import annotations

from typing import Any

from modbus_connection.model import (
    Component,
    RegisterSpace,
    integer,
    uint32,
)

MODULATION_NOT_USED = 0
MODULATION_MIN = 40
MODULATION_MAX = 100


def validate_compressor_modulation(value: Any) -> int:
    """Accept 0 (not used) or 40 to 100, the values the register defines.

    Raises ``ValueError`` for anything else.
    """
    modulation = int(value)
    if modulation != MODULATION_NOT_USED and not (
        MODULATION_MIN <= modulation <= MODULATION_MAX
    ):
        raise ValueError(
            f"compressor modulation is {MODULATION_NOT_USED} (not used) or "
            f"{MODULATION_MIN} to {MODULATION_MAX}, not {modulation}"
        )
    return modulation


class EnergyCounters(Component):
    """The heat pump's own energy measurement, input registers 30037 to 30046.

    Each value is 32 bits wide, high word first, in Wh. LG's names for the
    five values are ``ENERGY_INSTANTANEOUS_TOTAL``,
    ``ENERGY_ACCUMULATIVE_TOTAL``, ``ENERGY_INSTANTANEOUS_HEAT``,
    ``ENERGY_ACCUMULATIVE_COOL`` and ``ENERGY_ACCUMULATIVE_DHW``. Heat pumps
    from before December 2023 do not have them. The heat pump's own
    measurement is known to read too high, so a separate meter is more
    accurate.
    """

    register_space: RegisterSpace = "input"

    energy_instantaneous_total = uint32(36, unit="Wh")  # 30037, 30038
    energy_accumulative_total = uint32(38, unit="Wh")  # 30039, 30040
    energy_instantaneous_heat = uint32(40, unit="Wh")  # 30041, 30042
    energy_accumulative_cool = uint32(42, unit="Wh")  # 30043, 30044
    energy_accumulative_dhw = uint32(44, unit="Wh")  # 30045, 30046


class CompressorModulation(Component):
    """Limit on the compressor, holding register 40024.

    0 leaves the compressor alone, 40 to 100 limits its modulation. Heat
    pumps from before December 2023 do not have it.
    """

    register_space: RegisterSpace = "holding"

    compressor_modulation = integer(
        23, signed=False, writable=validate_compressor_modulation
    )  # 40024
