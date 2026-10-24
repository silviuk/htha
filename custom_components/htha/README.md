# Ht HA - Home Assistant Integration for Heliotherm Heat Pumps

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacs-shield]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]

[![Community Forum][forum-shield]][forum]

A Home Assistant integration for Heliotherm heat pumps using the [htheatpump](https://github.com/silviuk/htheatpump) library over TCP socket connections.

## Features

- **Temperature Sensors**: Monitor outdoor, hot water, flow, return, and other temperatures
- **Binary Sensors**: Track fault status, pump status, compressor status, and more
- **Number Entities**: Control setpoints like room temperature and hot water temperature
- **Select Entity**: Change operating mode (Heating, Cooling, Hot Water, Auto, etc.)
- **Write Protection**: Safety switch to prevent accidental changes to heat pump settings
- **Ready-made dashboard**: `custom:htha-heatpump` dashboard strategy, loaded automatically
- **Configurable Parameters**: Choose which parameters to expose through the options flow

## Supported Heat Pumps

This integration has been tested with:

- Heliotherm HP07S08W-S-WEB
- Heliotherm HP08S10W-WEB
- Heliotherm HP10S12W-WEB
- Heliotherm HP08E-K-BC
- Heliotherm HP05S07W-WEB
- Heliotherm HP12L-M-BC
- Heliotherm HP-30-L-M-WEB
- Brötje BSW NEO 8

Other Heliotherm and Brötje heat pumps with a serial or TCP interface should also work.

## Prerequisites

### Hardware Setup

You need a serial-to-TCP converter (like [ser2net](https://github.com/cminyard/ser2net) or a hardware serial server) to connect your heat pump's serial port to your network.

Example ser2net configuration:

```yaml
connection: &htheatpump
  accepter: tcp,9999
  connector: serialdev,/dev/ttyUSB0,9600n81,local
  options:
    max-connections: 2
```

### Software Requirements

- Home Assistant >= 2024.1.0
- htheatpump >= 1.3.4 (installed automatically)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the "+" button
4. Search for "Ht HA"
5. Click "Download"
6. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/htha` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "Ht HA"
4. Enter your connection details:
   - **Host**: IP address or hostname of your TCP/serial server
   - **Port**: TCP port (default: 9999)
   - **Timeout**: Connection timeout in seconds (default: 10)
   - **Scan Interval**: How often to poll for data (default: 30 seconds)
5. Click **Submit**
6. Choose whether to enable writes (allows changing heat pump settings)
7. Click **Submit** to complete setup

### Options Configuration

After initial setup, you can configure:

1. Go to **Settings** > **Devices & Services**
2. Find your Ht HA integration
3. Click **Configure**
4. Select which parameters to expose as entities

## Entities

Entity names are translated (English and German) and follow Home Assistant's
naming rules, so they read as *device name + entity name*, for example
"Heliotherm Heat Pump Heating flow temperature".

### Default entities

| Type | Entities |
|------|----------|
| Sensors | Outdoor temperature, Outdoor temperature (damped), Hot water temperature, Heating flow temperature, Heating return temperature, Heat source inlet temperature, Heat source outlet temperature, Refrigerant suction gas temperature |
| Derived sensors | Operating state (off / standby / heating / hot water / cooling / fault), Heating flow/return spread, Heat source inlet/outlet spread |
| Statistics (diagnostic) | Compressor starts, Heating circuit pump runtime, Heat source pump runtime, Hot water mode runtime |
| Binary sensors | Fault, Compressor, Hot water mode, Heating circuit pump, Heat source pump/fan, Hot water circulation pump; Main switch and Fresh water station flow switch (diagnostic) |
| Numbers | Room temperature setpoint, Hot water setpoint (normal), Hot water setpoint (minimum), Heating curve return setpoint at upper heating limit / at 0 °C outdoor / at lower heating limit (configuration) |
| Select | Operating mode |
| Configuration | Allow writes to heat pump (switch), Heat pump clock (datetime), Sync heat pump clock (button) |

Every number/select parameter also has a read-only sensor twin, e.g.
"Room temperature setpoint (read-only)". These are diagnostic and disabled by
default on new installs; enable them if you need long-term statistics of a
setpoint.

### Upgrading from 1.0.11 or older

Version 1.0.12 only changes *display names*, icons, categories and units;
`entity_id`s and `unique_id`s stay the same, so history and automations keep
working. Entities you renamed yourself keep your name. Entity_ids that were
generated from the old names (e.g. `sensor.heliotherm_heat_pump_temperature_2`)
are not renamed automatically; you can rename them in the UI if you like. The
three derived sensors are new entities.

### Operating Modes

The operating mode select entity supports the following options:

| Mode | Description |
|------|-------------|
| Off | Heat pump is off |
| Heating | Heating mode only |
| Cooling | Cooling mode only |
| Hot Water | Hot water mode only |
| Heating + Cooling | Both heating and cooling |
| Auto | Automatic mode selection |
| Emergency | Emergency operation |
| Standby | Standby mode |

## Dashboard

The integration ships a ready-made, modern heat pump dashboard that uses only
built-in Home Assistant cards. There are two ways to use it:

- **Explicit cards (most robust, recommended for your main dashboard).** Copy
  [`dashboards/heliotherm_heatpump.yaml`](https://github.com/silviuk/htha/blob/master/dashboards/heliotherm_heatpump.yaml)
  into a dashboard (Raw configuration editor). It does not depend on any
  JavaScript, works in every browser and app version and is easy to tweak.
  It uses the entity_ids of a default install; adjust them if yours differ.
  You can also generate it from the strategy: add the strategy (below), then
  use "Take control" in the dashboard editor to turn it into explicit cards.
- **Strategy (most convenient).** The `custom:htha-heatpump` dashboard / view
  / section strategy builds itself from your entities, so it works with any
  entity_ids, languages and several heat pumps, and picks up improvements with
  every integration update. Its module is loaded automatically: Ht HA serves
  it, adds it to the frontend and (in storage mode) also adds it as a
  dashboard resource (`/htha_frontend/htha-heatpump-strategy.js?v=<version>`,
  type JavaScript module). The resource is removed again when the last Ht HA
  entry is deleted, if Ht HA added it. With YAML mode resources, add it
  yourself.

<!-- Screenshot placeholder: add docs/dashboard.png here -->

Sections: **overview** (state, mode, compressor, pumps, fault alert, 24 h
activity), **heating** (flow/return/spread, room setpoint, 48 h graph, heating
curve), **hot_water** (gauge, setpoints, 72 h graph), **source** (heat source
and refrigerant temperatures/pressures), **statistics** (compressor starts and
runtimes per day), **controls** (only shown while *Allow writes* is on),
**schedule** (time programs) and **diagnostics** (everything else).

Whole dashboard: Settings -> Dashboards -> Add dashboard -> New dashboard from
scratch, open it, then three dots -> Edit -> three dots -> Raw configuration
editor and paste:

```yaml
strategy:
  type: custom:htha-heatpump
```

A single view in an existing dashboard:

```yaml
views:
  - title: Heat pump
    icon: mdi:heat-pump
    strategy:
      type: custom:htha-heatpump
      # device_id: 0123abcd...           # optional: only this heat pump
      # sections: [overview, heating, hot_water, controls]  # optional subset
```

Single sections inside your own `type: sections` view:

```yaml
sections:
  - strategy:
      type: custom:htha-heatpump
      section: overview   # overview | heating | hot_water | source |
                          # statistics | controls | schedule | diagnostics
```

**Time programs (schedule section).** By default the full week of every time
program is shown. To make it collapsible, create a toggle helper (Settings ->
Devices & services -> Helpers -> Toggle) with the entity_id
`input_boolean.htha_show_time_programs`. The section then shows only today's
programs, and the full week when you switch the toggle on (tap the heading or the
"Show full week" tile). Options for the section, view or dashboard strategy:

```yaml
strategy:
  type: custom:htha-heatpump
  time_programs: collapsible   # full | summary | collapsible (default: collapsible
                               # when a toggle exists, otherwise full)
  time_programs_toggle: input_boolean.my_toggle   # optional, another toggle helper
```

**Runtime and starts per day.** The heat pump's hour counters (compressor,
heating pump, source pump and hot water operating hours) are only updated by the
controller about once a day, shortly after midnight. A daily bar therefore shows
the previous day's runtime, and the current day stays at 0 until then. If you
rename these entities and later rename them back to old entity_ids, Home
Assistant resumes the old statistics series and books the whole gap in one hour,
so one day can show more than 24 h. Fix that bar with Developer tools ->
Statistics -> "Adjust sum" for that hour. Don't delete the statistics.

**If a strategy section shows "Timeout waiting for strategy element
ll-strategy-section-htha-heatpump to be registered":** update to 1.0.13 or
newer, restart Home Assistant and reload the page. In the Companion app,
pull down to refresh, or clear the app's frontend cache (Settings ->
Companion app -> Troubleshooting). Older versions defined the strategy before the
frontend's custom element registry was set up, which always fails with the
legacy browser build (older Android WebViews) and sometimes on a cold cache.
If you keep seeing it, use the explicit cards.

To customise the cards, use "Take control" in the dashboard editor, or start
from [`dashboards/heliotherm_heatpump.yaml`](https://github.com/silviuk/htha/blob/master/dashboards/heliotherm_heatpump.yaml)
(the same layout as explicit cards for a default install).

## Write Protection

For safety, the integration includes a write protection feature:

- By default, writes are **disabled**
- Enable writes by turning on the "Allow writes to heat pump" switch (switch it on again within 10 s to confirm)
- When writes are disabled, number and select entities will show an error if you try to change them

## Troubleshooting

### Connection Issues

1. **Check network connectivity**: Ensure your Home Assistant instance can reach the TCP server
2. **Verify port**: Make sure the port is correct and not blocked by a firewall
3. **Check serial settings**: Ensure the serial port settings match your heat pump (typically 9600 baud, 8N1)

### Debug Logging

Enable debug logging for more details:

```yaml
logger:
  logs:
    custom_components.htha: debug
    htheatpump: debug
```

### Common Issues

**"Cannot connect" error during setup**:
- Verify the host and port are correct
- Check that the TCP server is running
- Ensure the serial cable is properly connected

**Entities show "unavailable"**:
- Check the Home Assistant logs for errors
- Verify the heat pump is powered on
- Try restarting the integration

**Cannot change setpoints**:
- Make sure write protection is disabled
- Check that the parameter is writable (some are read-only)

## Contributing

Contributions are welcome! Please read the [contributing guidelines](CONTRIBUTING.md) before submitting a pull request.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Credits

- Based on the [htheatpump](https://github.com/silviuk/htheatpump) library by Daniel Strigl
- Inspired by the original [htheatpump Home Assistant integration](https://github.com/dstrigl/htheatpump)

## Disclaimer

**WARNING**: This integration allows you to control your heat pump. Incorrect settings could damage your heat pump or cause it to operate inefficiently. Use at your own risk!

The author does not provide any guarantee or warranty concerning correctness, functionality, or performance and does not accept any liability for damage caused by this integration.

[buymecoffee-shield]: https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png
[buymecoffee]: https://www.buymeacoffee.com/silviuk
[commits-shield]: https://img.shields.io/github/commit-activity/y/silviuk/htha.svg?style=for-the-badge
[commits]: https://github.com/silviuk/htha/commits/main
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[hacs]: https://hacs.xyz/
[license-shield]: https://img.shields.io/github/license/silviuk/htha.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40silviuk-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/silviuk/htha.svg?style=for-the-badge
[releases]: https://github.com/silviuk/htha/releases
[user_profile]: https://github.com/silviuk
