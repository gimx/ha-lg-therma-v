"""Config flow for LG Therma V heat pumps."""

import logging
from collections.abc import Mapping
from typing import Any, override

import probatio
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
    TextSelector,
)
from modbus_connection import ModbusError, ModbusTimeoutError

from .const import (
    CONF_BAUDRATE,
    CONF_FROM_DECEMBER_2023,
    CONF_METER_UNIT_ID,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .helpers import create_modbus_params
from .lg_therma_v_modbus import Sdm120, ThermaV
from .lg_therma_v_modbus.therma_v import DECEMBER_2023_COMPONENTS

_LOGGER = logging.getLogger(__name__)

STEP_RECONFIGURE_SERIAL = "reconfigure_serial"
STEP_RECONFIGURE_TCP = "reconfigure_tcp"

UNIT_ID_SELECTOR = probatio.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)),
    probatio.Coerce(int),
)

STEP_TCP_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
        probatio.Required(CONF_FROM_DECEMBER_2023, default=False): BooleanSelector(),
        probatio.Optional(CONF_METER_UNIT_ID): UNIT_ID_SELECTOR,
    }
)

STEP_SERIAL_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): SerialPortSelector(),
        probatio.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): probatio.All(
            NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1)),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
        probatio.Required(CONF_FROM_DECEMBER_2023, default=False): BooleanSelector(),
        probatio.Optional(CONF_METER_UNIT_ID): UNIT_ID_SELECTOR,
    }
)


class _HeatPumpSilentError(Exception):
    """The adapter is reachable, but the heat pump behind it is not answering."""


class _December2023NotSupportedError(Exception):
    """The heat pump refuses the registers only products from December 2023 have."""


class _MeterSilentError(Exception):
    """The adapter is reachable, but the meter behind it is not answering."""


async def _async_probe(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Connect to the heat pump, and the meter if there is one, or raise."""
    params = create_modbus_params(data)
    async with async_get_temporary_unit(hass, params, data[CONF_UNIT_ID]) as unit:
        from_december_2023 = data.get(CONF_FROM_DECEMBER_2023, False)
        try:
            report = await ThermaV(
                unit, from_december_2023=from_december_2023
            ).async_update()
        except ModbusTimeoutError as err:
            if unit.connected:
                raise _HeatPumpSilentError from err
            raise
        if from_december_2023 and report.failed.keys() & set(DECEMBER_2023_COMPONENTS):
            raise _December2023NotSupportedError

    if (meter_unit_id := data.get(CONF_METER_UNIT_ID)) is None:
        return
    async with async_get_temporary_unit(hass, params, meter_unit_id) as unit:
        try:
            await Sdm120(unit).async_update()
        except ModbusTimeoutError as err:
            if unit.connected:
                raise _MeterSilentError from err
            raise


def _same_link(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    """Whether two entries' data reach the same unit of the same link."""
    return (
        create_modbus_params(first).endpoint == create_modbus_params(second).endpoint
        and first[CONF_UNIT_ID] == second[CONF_UNIT_ID]
    )


class LgThermaVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an LG Therma V config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how the heat pump is reached."""
        return self.async_show_menu(
            step_id="user", menu_options=[TYPE_TCP, TYPE_SERIAL]
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a heat pump reached over the network."""
        return await self._async_step_link(TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a heat pump reached over a serial port."""
        return await self._async_step_link(
            TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_link(
        self,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then probe the heat pump behind them."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: connection_type, **user_input}
            self._abort_if_same_unit(data)
            errors, description_placeholders = await self._async_validate(data)
            if not errors:
                return self.async_create_entry(title=DEFAULT_NAME, data=data)

        return self.async_show_form(
            step_id=connection_type,
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    def _abort_if_same_unit(
        self, data: Mapping[str, Any], *, ignore_entry_id: str | None = None
    ) -> None:
        """Abort when another entry already reaches this unit of this link."""
        for entry in self._async_current_entries(include_ignore=False):
            if entry.entry_id != ignore_entry_id and _same_link(entry.data, data):
                raise AbortFlow("already_configured")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how the heat pump is reached from now on."""
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[STEP_RECONFIGURE_TCP, STEP_RECONFIGURE_SERIAL],
        )

    async def async_step_reconfigure_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reach this heat pump over the network from now on."""
        return await self._async_step_reconfigure_link(
            STEP_RECONFIGURE_TCP, TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input
        )

    async def async_step_reconfigure_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reach this heat pump over a serial port from now on."""
        return await self._async_step_reconfigure_link(
            STEP_RECONFIGURE_SERIAL, TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_reconfigure_link(
        self,
        step_id: str,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then probe the entry's own heat pump."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: connection_type, **user_input}
            self._abort_if_same_unit(data, ignore_entry_id=entry.entry_id)

            # A connection holds one set of link settings, so the entry has to
            # let go of its own before the probe asks for the same link again.
            relinking = False
            if entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY):
                current = create_modbus_params(entry.data)
                new = create_modbus_params(data)
                if new.endpoint == current.endpoint and new != current:
                    relinking = await self.hass.config_entries.async_unload(
                        entry.entry_id
                    )

            errors, description_placeholders = await self._async_validate(data)

            if relinking and errors:
                await self.hass.config_entries.async_setup(entry.entry_id)

            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)

        suggested = user_input or (
            entry.data
            if entry.data.get(CONF_TYPE, TYPE_TCP) == connection_type
            else {CONF_UNIT_ID: entry.data[CONF_UNIT_ID]}
        )

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Probe the devices, returning the errors to show if it fails."""
        try:
            await _async_probe(self.hass, data)
        except _HeatPumpSilentError:
            return {"base": "heat_pump_silent"}, {}
        except _December2023NotSupportedError:
            return {"base": "december_2023_not_supported"}, {}
        except _MeterSilentError:
            return {"base": "meter_silent"}, {}
        except (ModbusError, HomeAssistantError) as err:
            return {"base": "cannot_connect"}, {"error": str(err)}
        return {}, {}
