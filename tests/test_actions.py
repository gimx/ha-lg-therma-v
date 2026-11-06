"""Tests for the entities that write to the heat pump."""

from datetime import timedelta

import pytest
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.components.number import (
    ATTR_VALUE,
    SERVICE_SET_VALUE,
)
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util
from modbus_connection import ModbusError
from modbus_connection.mock import MockModbusConnection, WriteEvent
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)


def _record(
    connection: MockModbusConnection,
) -> list[tuple[str, int, list[int] | list[bool]]]:
    """Record every write the heat pump's unit receives."""
    writes: list[tuple[str, int, list[int] | list[bool]]] = []

    def on_write(event: WriteEvent) -> None:
        writes.append((event.register_type, event.address, event.values))

    connection.for_unit(1).on_write(on_write)
    return writes


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    ("entity_id", "coil"),
    [
        ("switch.lg_therma_v_heating_cooling", 0),
        ("switch.lg_therma_v_dhw", 1),
        ("switch.lg_therma_v_silent_mode", 2),
        ("switch.lg_therma_v_emergency_stop", 4),
    ],
)
@pytest.mark.parametrize(
    ("service", "value"), [(SERVICE_TURN_ON, True), (SERVICE_TURN_OFF, False)]
)
async def test_switch_writes_its_coil(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    entity_id: str,
    coil: int,
    service: str,
    value: bool,
) -> None:
    """Test turning a switch on or off writes the coil and reads it back."""
    writes = _record(mock_connection)

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert writes == [("coil", coil, [value])]


async def test_switch_reads_back_the_written_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test the state after a write is the one the heat pump holds."""
    entity_id = "switch.lg_therma_v_silent_mode"
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    mock_connection.for_unit(1).coil[2] = True
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_write_failure_is_reported(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a refused write raises an error instead of passing silently."""
    mock_connection.for_unit(1).fail_write(2, ModbusError(), register_type="coil")

    with pytest.raises(HomeAssistantError, match="Failed to write to the heat pump"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.lg_therma_v_silent_mode"},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "register", "temperature", "raw"),
    [
        ("climate.lg_therma_v_circuit_1", 2, 42, 420),
        ("climate.lg_therma_v_circuit_2", 5, 30, 300),
        ("climate.lg_therma_v_dhw", 8, 50, 500),
    ],
)
async def test_climate_sets_its_target(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    entity_id: str,
    register: int,
    temperature: int,
    raw: int,
) -> None:
    """Test each climate entity writes the register of its own target."""
    writes = _record(mock_connection)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: temperature},
        blocking=True,
    )

    assert writes == [("holding", register, [raw])]


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("hvac_mode", "raw"),
    [(HVACMode.COOL, 0), (HVACMode.AUTO, 3), (HVACMode.HEAT, 4)],
)
async def test_climate_sets_the_operation_mode(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    hvac_mode: HVACMode,
    raw: int,
) -> None:
    """Test the operation mode of the whole heat pump is written."""
    writes = _record(mock_connection)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.lg_therma_v_circuit_1", ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    assert writes == [("holding", 0, [raw])]


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_with_a_mode_writes_both(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a combined call writes the mode and the target."""
    writes = _record(mock_connection)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.lg_therma_v_circuit_1",
            ATTR_TEMPERATURE: 38,
            ATTR_HVAC_MODE: HVACMode.AUTO,
        },
        blocking=True,
    )

    assert writes == [("holding", 0, [3]), ("holding", 2, [380])]


@pytest.mark.usefixtures("init_integration")
async def test_hot_water_has_no_mode_to_set(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test the hot-water tank does not write the heat pump's operation mode."""
    writes = _record(mock_connection)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.lg_therma_v_dhw",
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    assert writes == []


@pytest.mark.usefixtures("init_integration")
async def test_climate_write_failure_is_reported(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a refused climate write raises an error."""
    mock_connection.for_unit(1).fail_write(2, ModbusError())

    with pytest.raises(HomeAssistantError, match="Failed to write to the heat pump"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.lg_therma_v_circuit_1",
                ATTR_TEMPERATURE: 40,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "register", "value", "raw"),
    [
        ("number.lg_therma_v_circuit_1_auto_mode_shift", 4, -2, 65534),
        ("number.lg_therma_v_compressor_modulation", 23, 75, 75),
        ("number.lg_therma_v_compressor_modulation", 23, 0, 0),
    ],
)
async def test_number_writes_its_register(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    entity_id: str,
    register: int,
    value: int,
    raw: int,
) -> None:
    """Test a number writes the register of its own setting."""
    writes = _record(mock_connection)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    assert writes == [("holding", register, [raw])]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_room_air_temperature_input_is_scaled(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test the room air temperature handed to the heat pump is written in tenths."""
    writes = _record(mock_connection)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.lg_therma_v_circuit_2_room_air_temperature_input",
            ATTR_VALUE: 19.5,
        },
        blocking=True,
    )

    assert writes == [("holding", 6, [195])]


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("value", [1, 39])
async def test_modulation_the_register_does_not_define_is_refused(
    hass: HomeAssistant, mock_connection: MockModbusConnection, value: int
) -> None:
    """Test a modulation between 1 and 39 is refused before anything is written."""
    writes = _record(mock_connection)

    with pytest.raises(ServiceValidationError, match="0 \\(not used\\) or 40 to 100"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.lg_therma_v_compressor_modulation",
                ATTR_VALUE: value,
            },
            blocking=True,
        )

    assert writes == []


@pytest.mark.usefixtures("init_integration")
async def test_number_write_failure_is_reported(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a refused number write raises an error."""
    mock_connection.for_unit(1).fail_write(23, ModbusError())

    with pytest.raises(HomeAssistantError, match="Failed to write to the heat pump"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.lg_therma_v_compressor_modulation",
                ATTR_VALUE: 60,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    ("entity_id", "option", "register", "raw"),
    [
        ("select.lg_therma_v_control_method", "room_air", 1, 2),
        ("select.lg_therma_v_energy_state_input", "power_saving", 9, 7),
        ("select.lg_therma_v_energy_state_input", "super_power_saving", 9, 8),
    ],
)
async def test_select_writes_its_register(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    entity_id: str,
    option: str,
    register: int,
    raw: int,
) -> None:
    """Test a select writes the code of the option."""
    writes = _record(mock_connection)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    assert writes == [("holding", register, [raw])]


@pytest.mark.usefixtures("init_integration")
async def test_select_write_failure_is_reported(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a refused select write raises an error."""
    mock_connection.for_unit(1).fail_write(9, ModbusError())

    with pytest.raises(HomeAssistantError, match="Failed to write to the heat pump"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.lg_therma_v_energy_state_input",
                ATTR_OPTION: "forced_off",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    ("entity_id", "coil"),
    [
        ("button.lg_therma_v_trigger_dhw_disinfection", 3),
        ("button.lg_therma_v_trigger_emergency_operation", 5),
    ],
)
async def test_button_sets_its_trigger_coil(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    entity_id: str,
    coil: int,
) -> None:
    """Test pressing a button starts the operation."""
    writes = _record(mock_connection)

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert writes == [("coil", coil, [True])]


@pytest.mark.usefixtures("init_integration")
async def test_button_write_failure_is_reported(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a refused trigger raises an error."""
    mock_connection.for_unit(1).fail_write(3, ModbusError(), register_type="coil")

    with pytest.raises(HomeAssistantError, match="Failed to write to the heat pump"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.lg_therma_v_trigger_dhw_disinfection"},
            blocking=True,
        )
