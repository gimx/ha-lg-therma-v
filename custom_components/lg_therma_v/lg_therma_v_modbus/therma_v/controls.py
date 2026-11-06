"""What the heat pump can be switched, its coils (0xxxx)."""

from __future__ import annotations

from modbus_connection.model import Component, coil


class Controls(Component):
    """The heat pump's switches and one-shot triggers.

    The two ``trigger_`` coils start an operation when set and keep the
    heat pump's status when cleared; they are not states to read back.
    """

    heating_cooling_enabled = coil(0, writable=True)  # 00001
    dhw_enabled = coil(1, writable=True)  # 00002
    silent_mode = coil(2, writable=True)  # 00003
    trigger_dhw_disinfection = coil(3, writable=True)  # 00004
    emergency_stop = coil(4, writable=True)  # 00005
    trigger_emergency_operation = coil(5, writable=True)  # 00006
