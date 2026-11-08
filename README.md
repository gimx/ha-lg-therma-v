# LG Therma V for Home Assistant

Custom integration for [LG Therma V](https://www.lg.com/global/business/hvac/) heat pumps,
read and controlled over Modbus, with an optional Eastron SDM120 energy meter on the same line.

It is the community-test build of the `lg_therma_v` integration proposed for Home Assistant
core. It talks to the heat pump through the
[lg-therma-v-modbus](https://github.com/gimx/lg-therma-v-modbus) device library, which is
vendored into this repository so HACS needs nothing else.

## Requirements

- Home Assistant **2026.10.4** or newer. The integration is built on Home Assistant's shared
  Modbus connection (`modbus` integration), which older versions do not have.
- A Modbus connection to the heat pump: an RS485 USB adapter, a serial port shared over the
  network, or an RS485-to-network bridge speaking Modbus TCP.
- Modbus enabled on the heat pump. Its unit ID is set on the control panel under
  *Connectivity > Modbus address*.

## Installation

This integration is a community-test build of the `lg_therma_v` integration proposed for
Home Assistant core, so it is installed as a **custom repository** in
[HACS](https://hacs.xyz/):

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=gimx&repository=ha-lg-therma-v&category=integration)

1. Click the button above. Or, in HACS, open the menu, choose *Custom repositories*, add
   `https://github.com/gimx/ha-lg-therma-v` with the type *Integration*.
1. Download **LG Therma V** in HACS.
1. Restart Home Assistant.
1. Go to *Settings > Devices & services > Add integration* and choose **LG Therma V**.

If the integration is accepted into Home Assistant core, remove this repository from HACS and
set the integration up again from the built-in one.

## Setup

Choose how the heat pump is reached:

| Choice | Needs |
| :--- | :--- |
| Modbus TCP | host, port (502), unit ID |
| Serial port (Modbus RTU) | serial port, baud rate (9600), unit ID |

Both also ask for:

- **Product from December 2023 or later.** Turn it on if your heat pump was made in
  December 2023 or later. It adds the heat pump's own energy measurement and the compressor
  modulation, which older products do not have and refuse to answer. If you turn it on for
  an older product, setup tells you so and you can turn it off again. It can be changed later
  with *Reconfigure*.
- **Energy meter unit ID** (optional). Enter the Modbus address of an SDM120 on the same line
  to get its voltage, power and energy as a second device behind the heat pump.

The heat pump is probed once while you set it up, so a wrong address or baud rate shows up
immediately. *Reconfigure* on the integration changes the connection later, including switching
between serial and network, without losing the entities.

## Entities

The names are LG's own, from its Modbus register list. Every register in that list has an
entity; most are **disabled by default** so a fresh install stays readable. Enable the ones
you want from the entity's settings.

| Platform | Enabled by default | Disabled by default |
| :--- | :--- | :--- |
| Climate | Circuit 1, Circuit 2 and DHW: current and target temperature and, for the two circuits, the heat pump's operation mode (cool, heat, auto) | |
| Sensor | Water inlet, circuit 1 room air, circuit 2 flow and outside air temperature, water flow rate, operation cycle, energy state, error code | Water outlet, backup heater outlet, DHW tank, solar collector and circuit 2 room air temperature, water pressure, the refrigerant circuit (pipe in/out, suction, discharge, heat exchanger and evaporator outlet temperature, high and low pressure, compressor frequency) |
| Sensor, December 2023 or later | | Total, heating, cooling and DHW energy, instantaneous and accumulated |
| Binary sensor | Compressor, defrosting, DHW heating, backup heater step 1, water flow, error | Backup heater step 2, DHW boost heater, pumps, DHW tank disinfection, cooling, silent mode, emergency operation available |
| Switch | Heating/cooling, DHW, silent mode | Emergency stop |
| Button | Trigger DHW disinfection | Trigger emergency operation |
| Number | Circuit 1 auto mode shift | Circuit 2 auto mode shift, the room air temperature inputs of both circuits |
| Number, December 2023 or later | Compressor modulation (0 or 40 to 100) | |
| Select | Energy state input | Control method |
| Sensor (meter) | Voltage, power, energy | |

The heat pump's own energy measurement is known to read too high; a separate meter is more
accurate. LG's register list calls two of the energy values "instantaneous" yet gives all of
them in Wh, so those two are plain Wh values.

The operation mode and the control method are one register each for the whole heat pump, so
setting them on either circuit sets them for both. The DHW tank only heats and has no mode of
its own. Disinfection and emergency operation are *triggers*: pressing the button starts the
operation, and the heat pump keeps its status otherwise.

## Good to know

- **Keep polling.** The heat pump shows the error `CH 03` when nothing asks it for data for
  five minutes, and only cutting its power clears that. The integration polls every 20 seconds
  and keeps doing so while the heat pump does not answer. If Home Assistant itself is
  switched off for longer, put a bridge between them that keeps polling, or expect `CH 03`.
- **It answers from the third request.** The first requests on a fresh link go unanswered, so
  the first refresh after a restart can be slower than later ones.
- **One link, many devices.** A serial line can only be used by one program at a time. Home
  Assistant shares it between the integrations that ask for the same one, so other Modbus
  integrations on the same adapter work next to this one.

## Development

```bash
scripts/setup      # install the dependencies
scripts/develop    # start Home Assistant with this integration loaded
scripts/lint       # format and lint
scripts/test       # run the tests with coverage
```

The Home Assistant version in `hacs.json` is the one the tests run against. It moves together
with `pytest-homeassistant-custom-component` in `requirements_test.txt`.

### The vendored library

`custom_components/lg_therma_v/lg_therma_v_modbus/` is a copy of the
[lg-therma-v-modbus](https://github.com/gimx/lg-therma-v-modbus) library, unchanged. Do not
edit it here; change the library and copy it in again:

```bash
scripts/vendor_library 0.1.0                                          # a PyPI release
scripts/vendor_library ../lg-therma-v-modbus/src/lg_therma_v_modbus   # a local checkout
```

The integration imports it relatively (`from .lg_therma_v_modbus import ThermaV`). The
`modbus-connection` package it builds on comes with Home Assistant's `modbus` integration,
which this integration depends on, so `manifest.json` lists no requirements.

### Relation to Home Assistant core

The integration code is the same as the core pull request's, apart from how the library is
imported, how setup reports success and where the translations come from. Fixes belong in both.
