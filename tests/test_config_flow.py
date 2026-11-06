"""Tests for the LG Therma V config flow."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import _patch, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusSerialParams,
    ModbusTcpParams,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    get_schema_suggested_value,
)

from custom_components.lg_therma_v.config_flow import (
    STEP_RECONFIGURE_SERIAL,
    STEP_RECONFIGURE_TCP,
)
from custom_components.lg_therma_v.const import (
    CONF_BAUDRATE,
    CONF_FROM_DECEMBER_2023,
    CONF_UNIT_ID,
    DEFAULT_NAME,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)

from . import (
    MOCK_ENTRY_DATA,
    MOCK_ENTRY_DATA_WITH_METER,
    MOCK_SERIAL_ENTRY_DATA,
    MOCK_SERIAL_INPUT,
    MOCK_TCP_INPUT,
    MOCK_TCP_WITH_METER_INPUT,
)


def _patch_temporary_unit(connection: MockModbusConnection) -> _patch:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant,
        params: ModbusSerialParams | ModbusTcpParams,
        unit_id: int,
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(unit_id)

    return patch(
        "custom_components.lg_therma_v.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    )


@pytest.fixture
def probe_connection(mock_connection: MockModbusConnection) -> Callable[[], _patch]:
    """Patch the flow's probe onto the seeded mock connection."""
    return lambda: _patch_temporary_unit(mock_connection)


async def _start(hass: HomeAssistant, menu_option: str) -> dict[str, Any]:
    """Open the flow and choose how the heat pump is reached."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [TYPE_TCP, TYPE_SERIAL]
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": menu_option}
    )


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("menu_option", "user_input", "data"),
    [
        (
            TYPE_TCP,
            MOCK_TCP_INPUT,
            {CONF_TYPE: TYPE_TCP, **MOCK_TCP_INPUT, CONF_FROM_DECEMBER_2023: False},
        ),
        (
            TYPE_TCP,
            MOCK_TCP_WITH_METER_INPUT,
            {
                CONF_TYPE: TYPE_TCP,
                **MOCK_TCP_WITH_METER_INPUT,
                CONF_FROM_DECEMBER_2023: False,
            },
        ),
        (
            TYPE_TCP,
            {**MOCK_TCP_INPUT, CONF_FROM_DECEMBER_2023: True},
            {CONF_TYPE: TYPE_TCP, **MOCK_TCP_INPUT, CONF_FROM_DECEMBER_2023: True},
        ),
        (
            TYPE_SERIAL,
            MOCK_SERIAL_INPUT,
            {
                CONF_TYPE: TYPE_SERIAL,
                **MOCK_SERIAL_INPUT,
                CONF_FROM_DECEMBER_2023: False,
            },
        ),
    ],
)
async def test_full_flow(
    hass: HomeAssistant,
    probe_connection: Callable[[], _patch],
    menu_option: str,
    user_input: dict[str, Any],
    data: dict[str, Any],
) -> None:
    """Test the flow creates an entry for each way of reaching the heat pump."""
    result = await _start(hass, menu_option)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == menu_option

    with probe_connection():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == data


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ModbusConnectionError, "cannot_connect"),
        (HomeAssistantError, "cannot_connect"),
    ],
)
async def test_cannot_connect_then_recovers(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    error: type[Exception],
    reason: str,
) -> None:
    """Test a link that cannot be opened is reported, and a retry can succeed."""
    result = await _start(hass, TYPE_TCP)

    with patch(
        "custom_components.lg_therma_v.config_flow.async_get_temporary_unit",
        side_effect=error("no route"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_TCP_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}
    assert result["description_placeholders"] == {"error": "no route"}

    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_TCP_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize("chosen", [False, True])
async def test_newer_registers_are_only_probed_when_chosen(
    hass: HomeAssistant, mock_connection: MockModbusConnection, chosen: bool
) -> None:
    """Test the flow reads the newer registers only for a newer product."""
    unit = mock_connection.for_unit(1)
    result = await _start(hass, TYPE_TCP)

    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_TCP_INPUT, CONF_FROM_DECEMBER_2023: chosen}
        )

    reads = {(e.register_type, e.address) for e in unit.read_events}
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (("input", 36) in reads) is chosen
    assert (("holding", 23) in reads) is chosen


@pytest.mark.parametrize(("register_type", "address"), [("input", 36), ("holding", 23)])
async def test_an_older_product_refusing_the_newer_registers(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    register_type: str,
    address: int,
) -> None:
    """Test choosing "December 2023 or later" on an older product is caught."""
    mock_connection.for_unit(1).fail_read(
        address, IllegalDataAddressError(), register_type=register_type
    )
    result = await _start(hass, TYPE_TCP)

    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_TCP_INPUT, CONF_FROM_DECEMBER_2023: True}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "december_2023_not_supported"}

    # The same product is fine once the option is off again.
    with (
        _patch_temporary_unit(mock_connection),
        patch("custom_components.lg_therma_v.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_TCP_INPUT, CONF_FROM_DECEMBER_2023: False}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("unit_id", "user_input", "reason"),
    [
        (1, MOCK_TCP_INPUT, "heat_pump_silent"),
        (2, MOCK_TCP_WITH_METER_INPUT, "meter_silent"),
    ],
)
async def test_silent_device(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    unit_id: int,
    user_input: dict[str, Any],
    reason: str,
) -> None:
    """Test a reachable link with a silent device says which device is silent."""
    mock_connection.for_unit(unit_id).fail_requests(ModbusTimeoutError())
    # The link itself is up; only the device behind it is quiet.
    await mock_connection.connect()
    result = await _start(hass, TYPE_TCP)

    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}


@pytest.mark.parametrize(
    ("unit_id", "user_input"),
    [(1, MOCK_TCP_INPUT), (2, MOCK_TCP_WITH_METER_INPUT)],
)
async def test_timeout_without_a_link_is_cannot_connect(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    unit_id: int,
    user_input: dict[str, Any],
) -> None:
    """Test a timeout on a link that never came up is not blamed on the device."""
    mock_connection.for_unit(unit_id).fail_requests(ModbusTimeoutError())
    result = await _start(hass, TYPE_TCP)

    with (
        _patch_temporary_unit(mock_connection),
        patch.object(MockModbusUnit, "connected", False),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize("existing", [MOCK_ENTRY_DATA, MOCK_ENTRY_DATA_WITH_METER])
async def test_same_unit_twice_is_aborted(
    hass: HomeAssistant,
    probe_connection: Callable[[], _patch],
    existing: dict[str, Any],
) -> None:
    """Test the same unit of the same link cannot be set up twice."""
    MockConfigEntry(domain=DOMAIN, data=existing).add_to_hass(hass)
    result = await _start(hass, TYPE_TCP)

    with probe_connection():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_TCP_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_another_unit_on_the_same_link_is_allowed(
    hass: HomeAssistant, probe_connection: Callable[[], _patch]
) -> None:
    """Test two heat pumps on one bus are two entries."""
    MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA).add_to_hass(hass)
    result = await _start(hass, TYPE_TCP)

    with probe_connection():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_TCP_INPUT, CONF_UNIT_ID: 2}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.fixture
def reconfigurable_entry(
    hass: HomeAssistant, mock_connection: MockModbusConnection, mock_get_unit: None
) -> MockConfigEntry:
    """A heat pump entry to reconfigure, already added to hass."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_ENTRY_DATA_WITH_METER, title=DEFAULT_NAME
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_tcp(
    hass: HomeAssistant,
    reconfigurable_entry: MockConfigEntry,
    probe_connection: Callable[[], _patch],
) -> None:
    """Test moving a heat pump to another address keeps the entry."""
    result = await reconfigurable_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [STEP_RECONFIGURE_TCP, STEP_RECONFIGURE_SERIAL]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": STEP_RECONFIGURE_TCP}
    )
    assert result["type"] is FlowResultType.FORM
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HOST)
        == (MOCK_ENTRY_DATA_WITH_METER[CONF_HOST])
    )

    with probe_connection():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_TCP_INPUT, CONF_HOST: "192.168.1.101"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert reconfigurable_entry.data == {
        CONF_TYPE: TYPE_TCP,
        CONF_HOST: "192.168.1.101",
        CONF_PORT: 502,
        CONF_UNIT_ID: 1,
        CONF_FROM_DECEMBER_2023: False,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_from_tcp_to_serial(
    hass: HomeAssistant,
    reconfigurable_entry: MockConfigEntry,
    probe_connection: Callable[[], _patch],
) -> None:
    """Test switching between network and serial keeps the entry."""
    result = await reconfigurable_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": STEP_RECONFIGURE_SERIAL}
    )
    # Nothing of the network link carries over, but the unit ID does.
    assert get_schema_suggested_value(result["data_schema"].schema, CONF_UNIT_ID) == 1
    assert get_schema_suggested_value(result["data_schema"].schema, CONF_DEVICE) is None

    with probe_connection():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_SERIAL_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert reconfigurable_entry.data == {
        **MOCK_SERIAL_ENTRY_DATA,
        CONF_FROM_DECEMBER_2023: False,
    }


async def test_reconfigure_error_keeps_the_entry(
    hass: HomeAssistant,
    reconfigurable_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a failed probe leaves the entry as it was."""
    result = await reconfigurable_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": STEP_RECONFIGURE_TCP}
    )

    with patch(
        "custom_components.lg_therma_v.config_flow.async_get_temporary_unit",
        side_effect=ModbusConnectionError("no route"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_TCP_INPUT, CONF_HOST: "192.168.1.101"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert reconfigurable_entry.data == MOCK_ENTRY_DATA_WITH_METER


async def test_reconfigure_into_another_entry_is_aborted(
    hass: HomeAssistant,
    reconfigurable_entry: MockConfigEntry,
    probe_connection: Callable[[], _patch],
) -> None:
    """Test an entry cannot be moved onto a unit another entry already uses."""
    MockConfigEntry(
        domain=DOMAIN, data={**MOCK_ENTRY_DATA, CONF_UNIT_ID: 5}
    ).add_to_hass(hass)
    result = await reconfigurable_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": STEP_RECONFIGURE_TCP}
    )

    with probe_connection():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_TCP_INPUT, CONF_UNIT_ID: 5}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_the_same_unit_is_not_a_duplicate(
    hass: HomeAssistant,
    reconfigurable_entry: MockConfigEntry,
    probe_connection: Callable[[], _patch],
) -> None:
    """Test saving an entry's own settings again is not flagged as a duplicate."""
    result = await reconfigurable_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": STEP_RECONFIGURE_TCP}
    )

    with (
        probe_connection(),
        patch("homeassistant.config_entries.ConfigEntries.async_schedule_reload"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_TCP_WITH_METER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_baudrate_releases_the_link_first(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_get_unit: None,
) -> None:
    """Test a loaded entry lets go of its link before the probe asks for it again."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SERIAL_ENTRY_DATA, title=DEFAULT_NAME
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": STEP_RECONFIGURE_SERIAL}
    )
    states_during_probe: list[ConfigEntryState] = []

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant, params: Any, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        states_during_probe.append(entry.state)
        yield mock_connection.for_unit(unit_id)

    with (
        patch(
            "custom_components.lg_therma_v.config_flow.async_get_temporary_unit",
            side_effect=_get_temporary_unit,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_schedule_reload"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}
        )

    assert result["type"] is FlowResultType.ABORT
    assert states_during_probe == [ConfigEntryState.NOT_LOADED]
    assert entry.data[CONF_BAUDRATE] == 19200


async def test_reconfigure_failure_after_releasing_sets_the_entry_up_again(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_get_unit: None,
) -> None:
    """Test a failed probe puts the released entry back to work."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SERIAL_ENTRY_DATA, title=DEFAULT_NAME
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": STEP_RECONFIGURE_SERIAL}
    )

    with patch(
        "custom_components.lg_therma_v.config_flow.async_get_temporary_unit",
        side_effect=ModbusConnectionError("no route"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}
        )
    await hass.async_block_till_done()

    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_BAUDRATE] == 9600
