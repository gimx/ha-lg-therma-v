"""What the heat pump reports as on or off, its discrete inputs (1xxxx)."""

from __future__ import annotations

from modbus_connection.model import Component, discrete_input


class Status(Component):
    """Pumps, compressor, heaters and alarms, one bit each."""

    # 10001: LG documents "0 flow rate ok, 1 too low", but firmware 3.0.6.5 sets it
    # exactly while water is flowing (pump running) and clears it when the pump stops
    water_flow = discrete_input(0)  # 10001: 1 water flowing, 0 no flow
    water_pump = discrete_input(1)  # 10002
    external_water_pump = discrete_input(2)  # 10003
    compressor = discrete_input(3)  # 10004
    defrosting = discrete_input(4)  # 10005
    dhw_heating = discrete_input(5)  # 10006: DHW thermal on/off
    dhw_tank_disinfection = discrete_input(6)  # 10007
    silent_mode = discrete_input(7)  # 10008
    cooling = discrete_input(8)  # 10009
    solar_pump = discrete_input(9)  # 10010
    backup_heater_step_1 = discrete_input(10)  # 10011
    backup_heater_step_2 = discrete_input(11)  # 10012
    dhw_boost_heater = discrete_input(12)  # 10013
    error = discrete_input(13)  # 10014
    emergency_operation_available_space = discrete_input(14)  # 10015: heating/cooling
    emergency_operation_available_dhw = discrete_input(15)  # 10016
    mix_pump = discrete_input(16)  # 10017
