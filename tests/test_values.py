"""Tests for what the entities report from the registers."""

import pytest
from homeassistant.core import HomeAssistant
from modbus_connection import ModbusError
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    ("entity_id", "state"),
    [
        ("sensor.lg_therma_v_water_inlet_temperature", "30.1"),
        ("sensor.lg_therma_v_water_outlet_temperature", "35.2"),
        ("sensor.lg_therma_v_dhw_tank_temperature", "47.8"),
        ("sensor.lg_therma_v_circuit_1_room_air_temperature", "21.5"),
        ("sensor.lg_therma_v_circuit_2_flow_temperature", "33.1"),
        ("sensor.lg_therma_v_circuit_2_room_air_temperature", "18.7"),
        ("sensor.lg_therma_v_outside_air_temperature", "-3.5"),
        ("sensor.lg_therma_v_water_flow_rate", "12.3"),
        ("sensor.lg_therma_v_operation_cycle", "heating"),
        ("sensor.lg_therma_v_energy_state", "normal_operation"),
        ("sensor.lg_therma_v_error_code", "0"),
        ("sensor.lg_therma_v_water_pressure", "1.8"),
        ("sensor.lg_therma_v_pipe_in_temperature", "30.1"),
        ("sensor.lg_therma_v_pipe_out_temperature", "25.2"),
        ("sensor.lg_therma_v_suction_temperature", "4.1"),
        ("sensor.lg_therma_v_discharge_temperature", "61.2"),
        ("sensor.lg_therma_v_heat_exchanger_temperature", "9.0"),
        ("sensor.lg_therma_v_evaporator_outlet_temperature", "8.5"),
        ("sensor.lg_therma_v_high_pressure", "24.5"),
        ("sensor.lg_therma_v_low_pressure", "8.1"),
        ("sensor.lg_therma_v_compressor_frequency", "63"),
        ("sensor.lg_therma_v_total_energy_instantaneous", "1500"),
        ("sensor.lg_therma_v_total_energy_accumulated", "65.536"),
        ("sensor.lg_therma_v_heating_energy_instantaneous", "3200"),
        ("sensor.lg_therma_v_cooling_energy_accumulated", "0.012"),
        ("sensor.lg_therma_v_dhw_energy_accumulated", "4.096"),
        ("sensor.energy_meter_voltage", "231.5"),
        ("sensor.energy_meter_power", "1250.0"),
        ("sensor.energy_meter_energy", "4321.75"),
        ("binary_sensor.lg_therma_v_compressor", "on"),
        ("binary_sensor.lg_therma_v_defrosting", "off"),
        ("binary_sensor.lg_therma_v_backup_heater_step_1", "on"),
        ("binary_sensor.lg_therma_v_mix_pump", "on"),
        ("binary_sensor.lg_therma_v_error", "off"),
        ("binary_sensor.lg_therma_v_water_flow", "off"),
        ("switch.lg_therma_v_heating_cooling", "on"),
        ("switch.lg_therma_v_silent_mode", "off"),
        ("switch.lg_therma_v_emergency_stop", "off"),
        ("number.lg_therma_v_compressor_modulation", "60"),
        ("number.lg_therma_v_circuit_1_auto_mode_shift", "2"),
        ("number.lg_therma_v_circuit_1_room_air_temperature_input", "21.0"),
        ("select.lg_therma_v_energy_state_input", "normal_operation"),
        ("select.lg_therma_v_control_method", "water_outlet_temperature"),
        ("climate.lg_therma_v_circuit_1", "heat"),
        ("climate.lg_therma_v_circuit_2", "heat"),
        ("climate.lg_therma_v_dhw", "heat"),
    ],
)
async def test_state(hass: HomeAssistant, entity_id: str, state: str) -> None:
    """Test an entity reads its register."""
    assert (entity := hass.states.get(entity_id)) is not None
    assert entity.state == state


@pytest.mark.usefixtures("init_integration")
async def test_climate_temperatures(hass: HomeAssistant) -> None:
    """Test each climate entity pairs its own measurement with its own target."""
    circuit_1 = hass.states.get("climate.lg_therma_v_circuit_1")
    circuit_2 = hass.states.get("climate.lg_therma_v_circuit_2")
    dhw = hass.states.get("climate.lg_therma_v_dhw")

    assert circuit_1 is not None
    assert circuit_1.attributes["current_temperature"] == 35.2
    assert circuit_1.attributes["temperature"] == 40.0
    assert circuit_2 is not None
    assert circuit_2.attributes["current_temperature"] == 18.7
    assert circuit_2.attributes["temperature"] == 35.0
    assert dhw is not None
    assert dhw.attributes["current_temperature"] == 47.8
    assert dhw.attributes["temperature"] == 48.0
    assert dhw.attributes["min_temp"] == 40
    assert dhw.attributes["max_temp"] == 55


@pytest.mark.parametrize(
    ("register_type", "address", "entity_id"),
    [
        ("input", 1, "sensor.lg_therma_v_operation_cycle"),
        ("input", 11, "sensor.lg_therma_v_energy_state"),
        ("holding", 0, "climate.lg_therma_v_circuit_1"),
        ("holding", 9, "select.lg_therma_v_energy_state_input"),
    ],
)
async def test_an_unknown_code_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection,
    mock_get_unit: None,
    register_type: str,
    address: int,
    entity_id: str,
) -> None:
    """Test a code the library does not know reads as unknown."""
    getattr(mock_connection.for_unit(1), register_type)[address] = 99
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unknown"


@pytest.mark.parametrize(("register_type", "address"), [("holding", 0), ("input", 5)])
async def test_climate_needs_both_its_target_and_its_measurement(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection,
    mock_get_unit: None,
    register_type: str,
    address: int,
) -> None:
    """Test a climate entity is unavailable if either of its blocks failed."""
    mock_connection.for_unit(1).fail_read(
        address, ModbusError(), register_type=register_type
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("climate.lg_therma_v_circuit_1").state == "unavailable"
