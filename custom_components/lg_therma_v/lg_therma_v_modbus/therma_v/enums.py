"""Register values the Therma V names."""

from __future__ import annotations

from enum import IntEnum


class OperationMode(IntEnum):
    """What the heat pump is asked to do, holding register 40001."""

    COOL = 0
    AUTO = 3
    HEAT = 4


class OperationCycle(IntEnum):
    """What the outdoor unit is doing right now, input register 30002."""

    STANDBY = 0
    COOLING = 1
    HEATING = 2


class ControlMethod(IntEnum):
    """What a circuit's target temperature is held against, holding register 40002."""

    WATER_OUTLET_TEMPERATURE = 0
    WATER_INLET_TEMPERATURE = 1
    ROOM_AIR = 2


class EnergyState(IntEnum):
    """The energy state of input register 30012 and holding register 40010.

    The four states from ``FORCED_OFF`` to ``ON_COMMAND`` are the SG Ready
    states, selected on the heat pump's terminal block by the contacts
    TB_SG1 and TB_SG2. The states 5 to 8 are set through this register only.
    """

    NOT_USED = 0
    FORCED_OFF = 1  # TB_SG1 closed, TB_SG2 open
    NORMAL_OPERATION = 2  # both open
    ON_RECOMMENDATION = 3  # TB_SG1 open, TB_SG2 closed
    ON_COMMAND = 4  # both closed
    ON_COMMAND_STEP_2 = 5  # much more electricity than normal operation
    ON_RECOMMENDATION_STEP_1 = 6  # more electricity than normal operation
    POWER_SAVING = 7  # less electricity than normal operation
    SUPER_POWER_SAVING = 8  # much less electricity than normal operation


class ProductType(IntEnum):
    """The kind of heat pump, input register 39999."""

    SPLIT = 0
    MONOBLOC = 3
    HIGH_TEMPERATURE = 4
    MEDIUM_TEMPERATURE = 5
    SYSTEM_BOILER = 6
