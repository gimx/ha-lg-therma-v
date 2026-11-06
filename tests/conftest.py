"""Fixtures for the LG Therma V integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.syrupy import (
    HomeAssistantSnapshotExtension,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.lg_therma_v.const import DOMAIN

from . import (
    MOCK_ENTRY_DATA,
    MOCK_ENTRY_DATA_2023,
    MOCK_TITLE,
    seed_heat_pump,
    seed_meter,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Enable loading of the custom integration in every test."""


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Load snapshots with Home Assistant's serializer from next to the tests."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Enable every entity, as Home Assistant's own test suite offers."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.lg_therma_v.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connection() -> MockModbusConnection:
    """A fake Modbus connection with a heat pump on unit 1 and a meter on unit 2."""
    connection = MockModbusConnection()
    seed_heat_pump(connection.for_unit(1))
    seed_meter(connection.for_unit(2))
    return connection


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock an LG Therma V config entry: a product from December 2023, with a meter."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_DATA_2023,
        title=MOCK_TITLE,
        entry_id="01JLGTHERMAV0000000000000",
    )


@pytest.fixture
def older_config_entry() -> MockConfigEntry:
    """Mock an LG Therma V config entry for a product from before December 2023."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_DATA,
        title=MOCK_TITLE,
        entry_id="01JLGTHERMAV0000000000001",
    )


@pytest.fixture
def mock_get_unit(mock_connection: MockModbusConnection) -> Generator[None]:
    """Hand out units on the mock connection when the entry sets up."""
    with patch(
        "custom_components.lg_therma_v.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: None,
) -> MockConfigEntry:
    """Set up the LG Therma V integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry
