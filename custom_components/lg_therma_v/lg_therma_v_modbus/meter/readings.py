"""What an Eastron SDM120 measures, its input registers."""

from __future__ import annotations

from modbus_connection.model import Component, RegisterSpace, float32


class Sdm120Readings(Component):
    """Voltage, power and the lifetime energy counter."""

    register_space: RegisterSpace = "input"
    # Three register pairs far apart: each is its own request, not one read
    # across the 340 addresses between them.
    max_gap = 0

    voltage = float32(0, unit="V")
    active_power = float32(12, unit="W")
    total_energy = float32(342, unit="kWh")
