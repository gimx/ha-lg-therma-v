"""What kind of heat pump this is, input registers 39998 and 39999."""

from __future__ import annotations

from modbus_connection.model import Component, RegisterSpace, enum, integer

from .enums import ProductType


class Product(Component):
    """The product group and type; they never change."""

    register_space: RegisterSpace = "input"
    # Two registers far from anything else.
    max_gap = 0

    product_group = integer(9997, signed=False)  # 39998: 0x80, 0x83, 0x88 or 0x89
    product_type = enum(9998, ProductType)  # 39999
