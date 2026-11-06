"""What the heat pump has been told to do, its holding registers (4xxxx)."""

from __future__ import annotations

from modbus_connection.model import Component, RegisterSpace, enum, gauge, integer

from .enums import ControlMethod, EnergyState, OperationMode


class Settings(Component):
    """Operating mode, target temperatures and the energy state input.

    Holding registers 40001 to 40010. The operation mode and the control
    method apply to both circuits. The room air temperatures of the two
    circuits are inputs: a room thermostat's reading handed to the heat pump
    for the room air control method.
    """

    register_space: RegisterSpace = "holding"

    operation_mode = enum(0, OperationMode, writable=True)  # 40001
    control_method = enum(1, ControlMethod, writable=True)  # 40002
    circuit_1_target_temperature = gauge(2, 0.1, writable=True, unit="°C")  # 40003
    circuit_1_room_air_temperature = gauge(3, 0.1, writable=True, unit="°C")  # 40004
    circuit_1_auto_mode_shift = integer(4, writable=True, unit="K")  # 40005
    circuit_2_target_temperature = gauge(5, 0.1, writable=True, unit="°C")  # 40006
    circuit_2_room_air_temperature = gauge(6, 0.1, writable=True, unit="°C")  # 40007
    circuit_2_auto_mode_shift = integer(7, writable=True, unit="K")  # 40008
    dhw_target_temperature = gauge(8, 0.1, writable=True, unit="°C")  # 40009
    energy_state_input = enum(9, EnergyState, writable=True)  # 40010
