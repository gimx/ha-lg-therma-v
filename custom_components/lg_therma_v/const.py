"""Constants for the LG Therma V integration."""

DOMAIN = "lg_therma_v"
MANUFACTURER = "LG Electronics"
METER_MANUFACTURER = "Eastron"

DEFAULT_NAME = "LG Therma V"
DEFAULT_BAUDRATE = 9600
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1

# The heat pump faults after five minutes without a request, so polling has to
# stay well inside that. Its sensors do not move faster than this.
SCAN_INTERVAL = 20

CONF_BAUDRATE = "baudrate"
CONF_UNIT_ID = "unit_id"
CONF_METER_UNIT_ID = "meter_unit_id"
CONF_FROM_DECEMBER_2023 = "from_december_2023"

TYPE_SERIAL = "serial"
TYPE_TCP = "tcp"

HEAT_PUMP = "heat_pump"
METER = "meter"

# The entities that exist only for products from December 2023 or later.
DECEMBER_2023_KEYS = frozenset(
    {
        "compressor_modulation",
        "energy_accumulative_cool",
        "energy_accumulative_dhw",
        "energy_accumulative_total",
        "energy_instantaneous_heat",
        "energy_instantaneous_total",
    }
)
