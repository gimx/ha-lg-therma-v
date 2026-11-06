"""Tests for the LG Therma V integration setup."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from modbus_connection import ModbusConnectionError, ModbusError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.lg_therma_v.const import (
    CONF_FROM_DECEMBER_2023,
    DECEMBER_2023_KEYS,
    DOMAIN,
    SCAN_INTERVAL,
)

from . import MOCK_ENTRY_DATA, MOCK_TITLE


async def test_load_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test loading and unloading an entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the meter is a device behind the heat pump."""
    heat_pump = device_registry.async_get_device_by_identifier(
        (DOMAIN, init_integration.entry_id), init_integration.entry_id
    )
    meter = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{init_integration.entry_id}_meter"), init_integration.entry_id
    )

    assert heat_pump is not None
    assert heat_pump.manufacturer == "LG Electronics"
    assert heat_pump.model == "Therma V Monobloc"
    assert heat_pump.name == MOCK_TITLE
    assert meter is not None
    assert meter.manufacturer == "Eastron"
    assert meter.model == "SDM120"
    assert meter.via_device_id == heat_pump.id


async def test_no_meter_without_unit_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test an entry without a meter creates neither its device nor its sensors."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA, title=MOCK_TITLE)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.lg_therma_v.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{entry.entry_id}_meter"), entry.entry_id
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_meter_power"
        )
        is None
    )


@pytest.mark.parametrize("error", [ModbusTimeoutError, ModbusConnectionError])
async def test_setup_retries_while_the_heat_pump_is_silent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    mock_get_unit: None,
    error: type[Exception],
) -> None:
    """Test a heat pump that does not answer is retried, not given up on."""
    mock_connection.for_unit(1).fail_requests(error())
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_silent_meter_does_not_block_the_heat_pump(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    mock_get_unit: None,
) -> None:
    """Test the heat pump sets up even if its meter is not answering."""
    mock_connection.for_unit(2).fail_requests(ModbusTimeoutError())
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.lg_therma_v_water_inlet_temperature").state == "30.1"
    assert hass.states.get("sensor.energy_meter_power").state == "unavailable"


async def test_one_failing_component_only_blanks_its_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    mock_get_unit: None,
) -> None:
    """Test a refused block makes only its own entities unavailable."""
    mock_connection.for_unit(1).fail_read(0, ModbusTimeoutError(), register_type="coil")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("switch.lg_therma_v_heating_cooling").state == "unavailable"
    assert hass.states.get("sensor.lg_therma_v_water_inlet_temperature").state == "30.1"


async def test_refused_warm_up_is_a_setup_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    mock_get_unit: None,
) -> None:
    """Test a heat pump refusing even its warm-up is retried like a silent one."""
    mock_connection.for_unit(1).fail_requests(ModbusError())
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_no_component_answering_is_a_setup_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    mock_get_unit: None,
) -> None:
    """Test a heat pump answering its warm-up but no block is retried."""
    unit = mock_connection.for_unit(1)
    unit.fail_read(0, ModbusError(), register_type="discrete")
    # The warm-up reads input register 0 alone, so it still passes.
    for address in (5, 13, 16, 36):
        unit.fail_read(address, ModbusError(), register_type="input")
    unit.fail_read(0, ModbusError(), register_type="coil")
    unit.fail_read(0, ModbusError(), register_type="holding")
    unit.fail_read(23, ModbusError(), register_type="holding")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_component_failure_and_recovery_are_logged_once(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a component's first failure and its recovery are each logged once."""
    unit = mock_connection.for_unit(1)
    unit.fail_read(0, ModbusError(), register_type="coil")

    for _ in range(2):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=SCAN_INTERVAL + 1)
        )
        await hass.async_block_till_done()
    assert caplog.text.count("controls failed to refresh") == 1
    assert hass.states.get("switch.lg_therma_v_heating_cooling").state == "unavailable"

    unit.fail_read(0, None, register_type="coil")
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=2 * SCAN_INTERVAL + 2)
    )
    await hass.async_block_till_done()

    assert caplog.text.count("controls is available again") == 1
    assert hass.states.get("switch.lg_therma_v_heating_cooling").state == "on"


async def test_model_is_plain_when_the_product_is_not_reported(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    mock_get_unit: None,
) -> None:
    """Test a heat pump that does not report its product is still set up."""
    await hass.config_entries.async_unload(init_integration.entry_id)
    mock_connection.for_unit(1).fail_read(
        9997, ModbusTimeoutError(), register_type="input"
    )

    await hass.config_entries.async_setup(init_integration.entry_id)
    await hass.async_block_till_done()

    heat_pump = device_registry.async_get_device_by_identifier(
        (DOMAIN, init_integration.entry_id), init_integration.entry_id
    )
    assert init_integration.state is ConfigEntryState.LOADED
    assert heat_pump is not None
    assert heat_pump.model == "Therma V"


async def test_a_dead_link_while_reading_the_product_is_not_fatal(
    hass: HomeAssistant,
    older_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    mock_get_unit: None,
) -> None:
    """Test a link that drops right after the first refresh leaves the model unknown."""
    older_config_entry.add_to_hass(hass)
    unit = mock_connection.for_unit(1)
    read = unit.read_input_registers

    async def read_input_registers(address: int, count: int) -> list[int]:
        if address == 9997:
            raise ModbusConnectionError
        return await read(address, count)

    with patch.object(unit, "read_input_registers", read_input_registers):
        await hass.config_entries.async_setup(older_config_entry.entry_id)
        await hass.async_block_till_done()

    assert older_config_entry.state is ConfigEntryState.LOADED


async def test_an_older_product_gets_neither_newer_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    older_config_entry: MockConfigEntry,
    mock_get_unit: None,
) -> None:
    """Test December 2023 entities exist only when the product is chosen as one."""
    older_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(older_config_entry.entry_id)
    await hass.async_block_till_done()

    keys = {
        entry.unique_id.removeprefix(f"{older_config_entry.entry_id}_")
        for entry in er.async_entries_for_config_entry(
            entity_registry, older_config_entry.entry_id
        )
    }
    assert "compressor_modulation" not in keys
    assert not {key for key in keys if key.startswith("energy_accumulative")}
    assert "water_pressure" in keys


async def test_a_newer_product_gets_both(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the entities of December 2023 products exist when it is chosen."""
    keys = {
        entry.unique_id.removeprefix(f"{init_integration.entry_id}_")
        for entry in er.async_entries_for_config_entry(
            entity_registry, init_integration.entry_id
        )
    }
    assert "compressor_modulation" in keys
    assert {
        "energy_instantaneous_total",
        "energy_accumulative_total",
        "energy_instantaneous_heat",
        "energy_accumulative_cool",
        "energy_accumulative_dhw",
    } <= keys


async def test_turning_the_option_off_removes_the_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the entities of December 2023 registers go when the option does."""
    assert entity_registry.async_get_entity_id(
        "number", DOMAIN, f"{init_integration.entry_id}_compressor_modulation"
    )
    hass.config_entries.async_update_entry(
        init_integration,
        data={**init_integration.data, CONF_FROM_DECEMBER_2023: False},
    )

    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    for key in DECEMBER_2023_KEYS:
        assert not [
            entity
            for entity in er.async_entries_for_config_entry(
                entity_registry, init_integration.entry_id
            )
            if entity.unique_id == f"{init_integration.entry_id}_{key}"
        ]
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{init_integration.entry_id}_water_pressure"
    )
