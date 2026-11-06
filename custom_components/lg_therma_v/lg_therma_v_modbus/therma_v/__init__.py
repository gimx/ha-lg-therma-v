"""The LG Therma V register map."""

from .controls import Controls
from .december_2023 import (
    MODULATION_MAX,
    MODULATION_MIN,
    MODULATION_NOT_USED,
    CompressorModulation,
    EnergyCounters,
    validate_compressor_modulation,
)
from .device import (
    DECEMBER_2023_COMPONENTS,
    READING_COMPONENTS,
    SETTING_COMPONENTS,
    WARM_UP_REQUESTS,
    ThermaV,
)
from .enums import (
    ControlMethod,
    EnergyState,
    OperationCycle,
    OperationMode,
    ProductType,
)
from .product import Product
from .readings import Readings, RefrigerantCycle, WaterPressure
from .settings import Settings
from .status import Status

__all__ = [
    "DECEMBER_2023_COMPONENTS",
    "MODULATION_MAX",
    "MODULATION_MIN",
    "MODULATION_NOT_USED",
    "READING_COMPONENTS",
    "SETTING_COMPONENTS",
    "WARM_UP_REQUESTS",
    "CompressorModulation",
    "ControlMethod",
    "Controls",
    "EnergyCounters",
    "EnergyState",
    "OperationCycle",
    "OperationMode",
    "Product",
    "ProductType",
    "Readings",
    "RefrigerantCycle",
    "Settings",
    "Status",
    "ThermaV",
    "WaterPressure",
    "validate_compressor_modulation",
]
