"""Tests for the LG Therma V diagnostics."""

from homeassistant.core import HomeAssistant
from modbus_connection import ModbusError
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag == snapshot


async def test_diagnostics_when_a_unit_stops_answering(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a failed raw read is reported instead of failing the download."""
    mock_connection.for_unit(2).fail_requests(ModbusError())

    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag["read_error"] == {"meter": "ModbusError"}
    assert "meter" not in diag["raw"]
    assert diag["raw"]["heat_pump"]
