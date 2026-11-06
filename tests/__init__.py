"""Tests for the LG Therma V integration."""

import struct

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from modbus_connection.mock import MockModbusUnit

from custom_components.lg_therma_v.const import (
    CONF_BAUDRATE,
    CONF_FROM_DECEMBER_2023,
    CONF_METER_UNIT_ID,
    CONF_UNIT_ID,
    DEFAULT_NAME,
    TYPE_SERIAL,
    TYPE_TCP,
)

MOCK_TITLE = DEFAULT_NAME

MOCK_TCP_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_UNIT_ID: 1,
}
MOCK_TCP_WITH_METER_INPUT = {**MOCK_TCP_INPUT, CONF_METER_UNIT_ID: 2}
MOCK_SERIAL_INPUT = {
    CONF_DEVICE: "/dev/ttyUSB0",
    CONF_BAUDRATE: 9600,
    CONF_UNIT_ID: 1,
}

MOCK_ENTRY_DATA = {CONF_TYPE: TYPE_TCP, **MOCK_TCP_INPUT}
MOCK_ENTRY_DATA_WITH_METER = {CONF_TYPE: TYPE_TCP, **MOCK_TCP_WITH_METER_INPUT}
# A product from December 2023 or later, with a meter.
MOCK_ENTRY_DATA_2023 = {**MOCK_ENTRY_DATA_WITH_METER, CONF_FROM_DECEMBER_2023: True}
MOCK_SERIAL_ENTRY_DATA = {CONF_TYPE: TYPE_SERIAL, **MOCK_SERIAL_INPUT}


def float_words(value: float) -> list[int]:
    """A float32 as two registers, most significant word first."""
    raw = struct.unpack(">I", struct.pack(">f", value))[0]
    return [raw >> 16, raw & 0xFFFF]


def seed_heat_pump(unit: MockModbusUnit) -> None:
    """Seed a heating heat pump on a mild winter morning."""
    unit.discrete.update(
        {
            3: True,  # compressor
            4: False,  # defrost
            5: False,  # hot water heating
            10: True,  # backup heater 1
            13: False,  # error
            16: True,  # mixing pump
        }
    )
    unit.coil.update({0: True, 1: True, 2: False, 3: False, 5: False})
    unit.input.update(
        {
            0: 0,  # error code
            1: 2,  # heating
            2: 301,  # inlet 30.1 °C
            3: 352,  # outlet 35.2 °C
            5: 478,  # hot water 47.8 °C
            7: 215,  # circuit 1 room 21.5 °C
            8: 123,  # flow 12.3 l/min
            9: 331,  # circuit 2 water 33.1 °C
            10: 187,  # circuit 2 room 18.7 °C
            11: 2,  # energy state
            12: (-35) & 0xFFFF,  # outside -3.5 °C
            13: 18,  # water pressure 1.8 bar
            16: 301,  # pipe in 30.1 °C
            17: 252,  # pipe out 25.2 °C
            18: 41,  # suction 4.1 °C
            19: 612,  # discharge 61.2 °C
            20: 90,  # heat exchanger 9.0 °C
            21: 85,  # evaporator outlet 8.5 °C
            22: 2450,  # high pressure 24.5 bar
            23: 810,  # low pressure 8.1 bar
            24: 63,  # compressor frequency 63 Hz
            36: [0, 1500],  # instantaneous total
            38: [0x0001, 0x0000],  # accumulative total, 65536 Wh
            40: [0, 3200],  # instantaneous heat
            42: [0, 12],  # accumulative cool
            44: [0, 4096],  # accumulative DHW
            9997: 0x83,  # product group
            9998: 3,  # monobloc
        }
    )
    unit.holding.update(
        {
            0: 4,  # heat
            1: 0,  # water outlet
            2: 400,  # circuit 1 target 40.0 °C
            3: 210,  # circuit 1 room air temperature input 21.0 °C
            4: 2,  # circuit 1 auto shift
            5: 350,  # circuit 2 target 35.0 °C
            6: 180,  # circuit 2 room air temperature input 18.0 °C
            7: 1,  # circuit 2 auto shift
            8: 480,  # hot water target 48.0 °C
            9: 2,  # energy state input
            23: 60,  # compressor modulation
        }
    )


def seed_meter(unit: MockModbusUnit) -> None:
    """Seed an SDM120 behind a running heat pump."""
    unit.input[0] = float_words(231.5)
    unit.input[12] = float_words(1250.0)
    unit.input[342] = float_words(4321.75)
