# Ht HA - Home Assistant Integration for Heliotherm heatpumps

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacs-shield]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]

A Home Assistant integration for Heliotherm heat pumps using the [htheatpump](https://github.com/silviuk/htheatpump) library over TCP socket connections.

## Project Structure

```
htha/
|-- custom_components/
|   |-- htha/                    # Home Assistant integration
|       |-- __init__.py          # Integration setup and unload
|       |-- binary_sensor.py     # Binary sensor entities (fault, pump status, etc.)
|       |-- config_flow.py       # UI configuration flow
|       |-- const.py             # Constants and parameter definitions
|       |-- coordinator.py       # Data coordinator for polling
|       |-- entity.py            # Base entity classes
|       |-- manifest.json        # Home Assistant manifest
|       |-- number.py            # Number entities (setpoints)
|       |-- select.py            # Select entities (operating mode)
|       |-- sensor.py            # Sensor entities (temperatures, etc.)
|       |-- switch.py            # Switch entities (write protection)
|       |-- translations/        # Localization files
|       |   |-- de.json          # German translations
|       |   |-- en.json          # English translations
|       |-- README.md            # Integration documentation
|-- plans/
|   |-- home-assistant-integration-plan.md  # Development plan
|-- test_htha_config_flow.py     # Config flow tests
|-- test_htha_coordinator.py     # Coordinator tests
|-- .gitignore
|-- README.md                    # This file
```

## Features

- **Temperature Sensors**: Monitor outdoor, hot water, flow, return, and other temperatures
- **Binary Sensors**: Track fault status, pump status, compressor status, and more
- **Number Entities**: Control setpoints like room temperature and hot water temperature
- **Select Entity**: Change operating mode (Heating, Cooling, Hot Water, Auto, etc.)
- **Write Protection**: Safety switch to prevent accidental changes to heat pump settings
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

## Development

### Setting Up a Development Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/silviuk/htha.git
   cd htha
   ```

2. Install development dependencies (if using Home Assistant development environment):
   ```bash
   pip install homeassistant
   pip install pytest pytest-asyncio pytest-homeassistant-custom-component
   ```

### Running Tests

The project includes tests for the config flow and coordinator:

```bash
# Run all tests
pytest

# Run specific test file
pytest test_htha_config_flow.py

# Run with verbose output
pytest -v
```

### Test Files

- [`test_htha_config_flow.py`](test_htha_config_flow.py) - Tests for the UI configuration flow
- [`test_htha_coordinator.py`](test_htha_coordinator.py) - Tests for the data coordinator

## Entities

### Default Entities

The following entities are created by default:

#### Sensors
- Outdoor Temperature
- Hot Water Temperature
- Flow Temperature
- Return Temperature

#### Binary Sensors
- Fault Status
- Heating Circuit Pump
- Compressor
- Hot Water Priority

#### Number Entities
- Room Setpoint Temperature
- Hot Water Normal Temperature

#### Select Entities
- Operating Mode

#### Switches
- Write Protection (controls whether changes are allowed)

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

## Write Protection

For safety, the integration includes a write protection feature:

- By default, writes are **disabled**
- Enable writes by turning on the "Write Protection" switch
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

Contributions are welcome! Please feel free to submit a pull request.

### Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Add docstrings to functions and classes
- Write tests for new functionality

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
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[hacs]: https://hacs.xyz/
[license-shield]: https://img.shields.io/github/license/silviuk/htha.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40silviuk-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/silviuk/htha.svg?style=for-the-badge
[releases]: https://github.com/silviuk/htha/releases
[user_profile]: https://github.com/silviuk