"""What the heat pump measures, its input registers (3xxxx)."""

from __future__ import annotations

from modbus_connection.model import (
    Component,
    RegisterSpace,
    enum,
    gauge,
    integer,
)

from .enums import EnergyState, OperationCycle


class Readings(Component):
    """Temperatures, flow, error code and the heat pump's current state.

    Input registers 30001 to 30013, the ones LG's register list names for
    every product.
    """

    register_space: RegisterSpace = "input"

    error_code = integer(0, signed=False)  # 30001
    operation_cycle = enum(1, OperationCycle)  # 30002: ODU operation cycle
    water_inlet_temperature = gauge(2, 0.1, unit="°C")  # 30003
    water_outlet_temperature = gauge(3, 0.1, unit="°C")  # 30004
    backup_heater_outlet_temperature = gauge(4, 0.1, unit="°C")  # 30005
    dhw_tank_temperature = gauge(5, 0.1, unit="°C")  # 30006
    solar_collector_temperature = gauge(6, 0.1, unit="°C")  # 30007
    circuit_1_room_air_temperature = gauge(7, 0.1, unit="°C")  # 30008
    flow_rate = gauge(8, 0.1, unit="l/min")  # 30009
    circuit_2_flow_temperature = gauge(9, 0.1, unit="°C")  # 30010
    circuit_2_room_air_temperature = gauge(10, 0.1, unit="°C")  # 30011
    energy_state = enum(11, EnergyState)  # 30012: energy state input
    outside_air_temperature = gauge(12, 0.1, unit="°C")  # 30013


class WaterPressure(Component):
    """The water circuit's pressure, input register 30014."""

    register_space: RegisterSpace = "input"

    water_pressure = gauge(13, 0.1, unit="bar")  # 30014


class RefrigerantCycle(Component):
    """The refrigerant circuit and the compressor, input registers 30017 to 30025.

    LG's register list names 30017 to 30021 "pipe in", "pipe out", "suction",
    "INV1 dis." (inverter 1 discharge) and "HEX" (heat exchanger)
    temperature. It leaves 30022 unnamed; the community documentation calls
    it the vapor temperature after the evaporator.
    """

    register_space: RegisterSpace = "input"

    pipe_in_temperature = gauge(16, 0.1, unit="°C")  # 30017
    pipe_out_temperature = gauge(17, 0.1, unit="°C")  # 30018
    suction_temperature = gauge(18, 0.1, unit="°C")  # 30019
    discharge_temperature = gauge(19, 0.1, unit="°C")  # 30020: INV1 dis. temp
    heat_exchanger_temperature = gauge(20, 0.1, unit="°C")  # 30021: HEX temp
    evaporator_outlet_temperature = gauge(21, 0.1, unit="°C")  # 30022
    # LG's list gives both pressures in mBar. On a 9 kW monobloc the raw
    # values only make sense at 0.01 bar per step: at rest the two are equal
    # and while running they follow a heating cycle.
    high_pressure = gauge(22, 0.01, unit="bar")  # 30023
    low_pressure = gauge(23, 0.01, unit="bar")  # 30024
    compressor_frequency = integer(
        24, signed=False, unit="Hz"
    )  # 30025: inverter frequency
