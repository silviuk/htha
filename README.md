# Ht HA: Heliotherm heat pump for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/silviuk/htha?style=for-the-badge)](https://github.com/silviuk/htha/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge)](https://hacs.xyz/)
[![Last commit](https://img.shields.io/github/last-commit/silviuk/htha/master?style=for-the-badge)](https://github.com/silviuk/htha/commits/master)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)

Monitor and control a **Heliotherm** heat pump from Home Assistant over a serial-to-TCP link: live temperatures and states, compressor statistics, setpoints, and weekly heating and hot-water schedules, with a ready-made dashboard included.

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=silviuk&repository=htha&category=integration)
[![Open your Home Assistant instance and start setting up Ht HA.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=htha)

![Heat pump dashboard overview](docs/screenshots/dashboard-overview.png)

## Highlights

- Live temperatures, operating state, pumps, setpoints, counters and the controller clock.
- Ready-made dashboard that finds your heat pump's entities automatically, on desktop and phone.
- Daily compressor starts and runtimes as long-term statistics.
- Built-in heating curve check with an informational comparison and separate problem flag.
- Optional weekly schedule editor with validation and a comparison against the pump's current schedule.
- Writes are off by default and need an explicit two-step confirmation.
- English and German labels.

## Screenshots

<table>
  <tr>
    <td width="68%"><img src="docs/screenshots/dashboard-charts-controls.png" alt="History charts, statistics and read-only controls"></td>
    <td width="32%"><img src="docs/screenshots/dashboard-phone.png" alt="Dashboard on a phone"></td>
  </tr>
  <tr>
    <td>History charts, daily statistics and controls (read-only until writes are allowed)</td>
    <td>The same dashboard on a phone</td>
  </tr>
</table>

Screenshots are from a live HP07S08W-S-WEB. The schedule editor is shown further down under [Schedule editor](#schedule-editor).

## Supported hardware and connection

Verified with **Heliotherm HP07S08W-S-WEB, firmware 2.03N** for monitoring and the documented mode mapping. Other Heliotherm and Brotje models supported by [htheatpump](https://github.com/silviuk/htheatpump) may work; available parameters and commands depend on the controller. Schedule writes on 2.03N remain unverified on hardware.

Connect the serial port through a serial-to-TCP adapter or [ser2net](https://github.com/cminyard/ser2net). Example:

```yaml
connection: &htheatpump
  accepter: tcp,9999
  connector: serialdev,/dev/ttyUSB0,9600n81,local
  options:
    max-connections: 2
```

Use the serial settings required by your controller (typically 9600 baud, 8N1). The integration installs its pinned [htheatpump](https://github.com/silviuk/htheatpump) dependency automatically.

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=silviuk&repository=htha&category=integration)

Or add it by hand: in HACS open the menu, choose **Custom repositories**, add `https://github.com/silviuk/htha` with type **Integration**, then download **Ht HA**. Restart Home Assistant afterwards.

### Manual

 Copy [`custom_components/htha`](custom_components/htha) into your Home Assistant `custom_components` directory, then restart.

## Setup

[![Open your Home Assistant instance and start setting up Ht HA.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=htha)

Or go to **Settings > Devices & services > Add integration** and search for **Ht HA**. Enter:

| Field | Value |
| --- | --- |
| Host | Serial/TCP server hostname or IP address |
| Port | Default `9999` |
| Timeout | Default `10` seconds |
| Scan interval | Default `600` seconds |
| Enable writes | Optional second step; disabled by default |

Under the integration's **Configure** options, choose exposed parameters, adjust the scan interval and optionally enter the model from the nameplate. Model is display-only. Serial number and firmware are read once per load and cached; unsupported identity reads do not stop polling. Saving options reloads the integration.

The same options include three heating curve reference values, initially 22 / 27 / 30 °C. These affect the comparison only; they never change pump settings.

## Dashboard

**Do I get the dashboard when I install htha? Yes:** the dashboard strategy and schedule editor card are bundled and loaded automatically. **Home Assistant does not create a dashboard by itself.** Add one using the configuration below.

For a whole dashboard, go to **Settings > Dashboards > Add dashboard**, create a dashboard from scratch, then open **Edit > Raw configuration editor** and paste:

```yaml
strategy:
  type: custom:htha-heatpump
```

For a single view, add this view configuration under an existing dashboard's `views:` list:

```yaml
- strategy:
    type: custom:htha-heatpump
```

For a single section, add this under `sections:` in a `type: sections` view:

```yaml
- strategy:
    type: custom:htha-heatpump
    section: schedule
```

The strategy discovers entities by integration and translation key, so renamed entity IDs work. A whole dashboard creates one view per heat pump. Sections are `overview`, `heating`, `hot_water`, `source`, `statistics`, `controls`, `schedule` and `diagnostics`. Use `device_id` to select a pump, or `sections: [overview, heating, hot_water, controls, schedule]` to choose sections on a dashboard/view strategy.

The controls section includes return setpoints at +18 / 0 / -15 °C outdoor and a compact heating curve status. Its small help button opens the explanation and adjustment advice; advice is hidden initially. The status updates with entity data and wraps on phones.

The **schedule** section shows the editor automatically when it can discover the schedule validation sensor and its config entry ID. Set `schedule_editor: false` in the strategy configuration to use the read-only time-program view. That view also serves as a fallback when editor discovery is incomplete. Its `time_programs` option accepts `full`, `summary` or `collapsible`; the last uses `input_boolean.htha_show_time_programs` by default when that helper exists, or a helper named by `time_programs_toggle`.

Prefer explicit cards? Copy [`dashboards/heliotherm_heatpump.yaml`](dashboards/heliotherm_heatpump.yaml) into the raw editor and adjust entity IDs. This static dashboard uses built-in cards. You can also use **Take control** on a strategy dashboard to customize its generated cards.

To add the editor independently, use [`dashboards/schedule-editor-v2.yaml`](dashboards/schedule-editor-v2.yaml), replacing the validation sensor and config entry ID:

```yaml
type: custom:htha-schedule-scratchpad-card
entity: sensor.heliotherm_schedule_validation
config_entry_id: YOUR_HTHA_CONFIG_ENTRY_ID
```

No manual resource is normally needed. Both scripts are served under `/htha_frontend/`, loaded through the frontend and registered as versioned JavaScript modules in storage-mode resources. Existing matching resources are updated; only resources created by htha are removed when its last entry is deleted. YAML resource lists are not edited; if explicit resources are needed, add these with `type: module`:

```yaml
- url: /htha_frontend/htha-heatpump-strategy.js?v=1.3.7
  type: module
- url: /htha_frontend/htha-schedule-scratchpad-card.js?v=1.3.7
  type: module
```

## Schedule editor

![Weekly schedule editor](docs/schedule-editor-evidence/1100-en-light.png)

Opening the card automatically shows **Current schedule (on pump)** with its read time.
Each category loads once per card instance: a baseline or coordinator cache no older than
three minutes costs **zero pump reads**; a cache miss costs **one read** through the existing
read path. Rendering, HA updates, tab visibility and reconnects never repeat that read.
Use **Reload from pump** or **Retry** for an explicit new read.

Separately, the coordinator caches the time-program collection and refreshes it during polling at most once per hour after a successful read (failed reads may retry on the next poll). The editor's per-open read and three-minute baseline freshness check are separate from that hourly cache. The heating curve check itself adds no pump reads.

The editor is closed by default. Choose **Edit a copy of current schedule**,
**Start from profile… → Use as starting point / Apply profile…**, or **New schedule**.
New uses the category's factory preset: all-day Normal for heating, all-day On for
hot water (unspecified hot-water periods use Off/minimum maintenance semantics).
**Discard draft / Close editor** returns to the current schedule after the existing
unsaved-changes confirmation. A server draft from another tab is offered as
**Resume draft** and **Discard draft**; opening the card never replaces it.

Edit recurring quarter-hour cells in a weekly grid, select multiple cells, assign modes and copy days. Validate to see findings and a diff before sending. Save personal profiles or start from the read-only **Factory default (Heliotherm)** profiles for heating and hot water.
On phones, tap slots or enable **Select** (**Auswählen**) to drag a range;
turn it off to scroll normally. **Multi-select** (**Mehrfachauswahl**),
**Select day** (**Tag auswählen**) and **Clear selection** (**Auswahl aufheben**)
work without modifier keys. Draft slots have large, horizontally scrollable
touch targets. Selection alone makes no changes or service calls.

The profile list refreshes automatically on card load, category changes, profile actions,
opening the dropdown and returning to the tab. Refreshes preserve edits and only read the HA profile library.

Changed draft slots keep the new mode color in the top 40%; the lower part shows the replaced pump mode tinted against the card background with an ×. Both the week overview and expanded day update as you edit, using the current pump schedule already available in the card. Unknown baseline slots have no replacement mark.

Verified mapping for **firmware 2.03N**: heating **0 Setback / 1 Normal / 2 Boost**; hot water **0 Off / 1 On**. Other firmware or incompatible metadata requires a verified mapping override. Hot water Off retains the controller's minimum-temperature maintenance; Normal does not mean continuous compressor operation.

Sending requires Allow writes, fresh validation, verified modes, acknowledgement of warnings and explicit confirmation. Writes are read back for verification and can fail partially; there is no automatic retry or rollback. Firmware 2.03N schedule writes remain unverified on hardware. See [schedule editor details and recovery](docs/schedule-scratchpad.md).

## Entities

Names follow the device name and are translated into English and German.

| Type | Examples |
| --- | --- |
| Sensors | Outdoor, hot water, flow/return, heat source and refrigerant temperatures; pressures |
| Derived sensors | Operating state, heating spread, heat source spread |
| Heating curve | Heating curve check (enum), Heating curve problem (problem binary sensor) |
| Statistics | Compressor starts and runtimes for compressor, heating/source pumps and hot water |
| Binary sensors | Fault, compressor, heating/source/circulation pumps, hot water mode |
| Numbers | Room and hot water setpoints, heating curve and other selected settings |
| Select | Operating mode |
| Configuration | Allow writes switch, heat pump clock, Sync clock button |
| Schedules | Time programs and schedule validation |

Read-only sensor twins of number/select parameters are diagnostic and disabled by default on new installs. Enable them if you need long-term setpoint statistics. Existing entity IDs and custom names are retained across display-name updates.

## Heating curve check

Web Control 321, customer manual section 6.2 (May 2022), defines **return** setpoints at **+18 / 0 / -15 °C outdoor**. The floor-heating factory curve is **22 / 27 / 30 °C**. The corresponding manufacturer setting ranges are **15–40 / 20–50 / 25–60 °C**. Upper/lower refer to the outdoor points, not variable heating limits. Existing number and mirror entity IDs/unique IDs are unchanged; their English/German display names now identify the outdoor temperature.

**Heating curve check** has enum states `factory`, `differs_from_factory` and `check_recommended`. A difference alone is informational. Attributes contain each point's value, factory value and delta in K, reference value/delta, monotonicity and a short English explanation. When outdoor temperature is available, attributes also show the linear, endpoint-clamped return setpoint, the factory/reference setpoints at that temperature and their deltas. This is a comparison model; the controller's actual target can also depend on mode, offsets and other settings.

**Heating curve problem** turns on only when any of these **htha heuristics** apply:

- The points are non-monotonic: +18 °C point > 0 °C point, or 0 °C point > -15 °C point.
- Any point is **more than 5 K** above its factory value (strictly above 27 / 32 / 35 °C respectively).
- The -15 °C point is **above 35 °C**.

These are review prompts for floor heating, **not manufacturer limits or a diagnosis**. Higher return temperatures can reduce efficiency and comfort; +5 K represents several of the manual's recommended 1–2 K adjustments. The manual advises adjusting by **1–2 K every 1–2 days**, observing room temperature in the most frequently occupied room and allowing the system to settle.

Both entities remain unavailable before the first complete reading, after a failed coordinator update, or while any point is missing/unknown/unavailable/invalid. They never substitute zero. Missing outdoor temperature only removes interpolation attributes. Keep all three curve parameters selected in integration options.

For radiators, set the three **Reference** values under Configure to the appropriate design curve. Comparison attributes then include both factory and custom reference deltas; `factory` means matching the configured reference and `differs_from_factory` means differing from it (the dashboard says “Reference curve” / “Differs from reference”). The fixed floor-heating problem heuristics still use 22 / 27 / 30 °C and need individual interpretation for radiators.

## Services

Schedule services take `config_entry_id`; use the [service field reference](custom_components/htha/services.yaml) for required draft hashes, revisions, sessions and confirmations. All are admin services and support optional responses. In a YAML action, use `response_variable: result` to retain the result; callers using `hass.services.async_call` must request `return_response=True` (WebSocket `call_service`: `return_response: true`). Without a requested response, the action still runs but its result is not returned.

| Service (`htha.` prefix) | Purpose |
| --- | --- |
| `get_current_time_program` | Read the current schedule; may use a fresh cached baseline |
| `get_time_program_editor` | Get editor state and profile listing |
| `start_time_program_draft` | Start from current schedule, factory preset or profile |
| `discard_time_program_draft` | Close/discard the server draft |
| `load_time_program_draft` | Load a supplied draft into the scratchpad |
| `validate_time_program` | Validate modes, risks and diff against a baseline |
| `acknowledge_time_program_warnings` | Acknowledge the current report's warnings |
| `refresh_time_program_baseline` | Re-read the baseline and invalidate prior approval |
| `apply_time_program` | Apply only with all safety gates satisfied |
| `restore_previous_time_program` | Apply a separately validated and acknowledged previous-program draft through the same write gates |
| `list_time_program_profiles` | List factory and named personal profiles |
| `save_time_program_profile` | Save a named profile in Home Assistant storage |
| `rename_time_program_profile` | Rename a personal profile |
| `delete_time_program_profile` | Delete a personal profile |
| `load_time_program_profile` | Load a profile as a draft, without applying it |
| `set_time_program_mode_mapping` | Confirm a controller-specific mode mapping |

## Write protection

Writes are disabled by default. Turn on **Allow writes to heat pump**, then turn it on again within 10 seconds to confirm. With writes off, settings remain visible but input controls are hidden and changes are rejected. Turn writes off when finished. The schedule editor displays this permission but cannot enable it; its separate validation and confirmation gates still apply.

Toggling Allow writes updates permission and controls immediately without reloading the integration. Schedule apply re-reads the pump before writing and rejects a changed baseline; it also checks the draft hash, revisions, mode mapping, warning acknowledgements and explicit confirmation. A readback verifies the result after writing. Interrupted or partial writes leave recovery information and invalidate approval; recovery requires a fresh read and review. There is no automatic retry or rollback. Personal profiles live in Home Assistant storage; unsaved draft approvals do not survive a restart.

## Known limitations

- Parameter support, mode codes and write behavior vary with controller/firmware. Verified monitoring does not establish hardware verification of schedule writes.
- A schedule write can be partial; inspect the recovery report and actual pump schedule before another apply.
- Heating curve warnings target floor heating. Reference overrides do not turn them into radiator limits, and interpolation does not reproduce every controller adjustment.
- The editor works in recurring quarter-hour slots; runtime counter updates and optional identity commands depend on the controller.

See [GitHub releases](https://github.com/silviuk/htha/releases) for version history.

## Troubleshooting

- **Cannot connect / unavailable entities:** Check the configured host/port, serial server, cable and serial settings, then inspect Home Assistant logs. Reload the integration after correcting the connection.
- **Cannot change a setting:** Confirm Allow writes is on and the parameter is writable. For schedules, review every missing gate shown by the editor.
- **Heating curve check unavailable:** Select all three curve parameters and check that each has a valid reading. Missing outdoor temperature affects interpolation only. A changed reference does not suppress the fixed floor-heating heuristics.
- **Schedule apply interrupted or baseline changed:** Reload the current schedule, review the risks and diff, validate again and acknowledge the new report before applying. Use the recovery details in the schedule guide for partial writes.
- **Strategy registration timeout** (`ll-strategy-section-htha-heatpump`): Restart Home Assistant and reload the page. In the Companion app, refresh or clear the frontend cache under its troubleshooting settings. Check that the current versioned modules load; the static YAML dashboard is an alternative.
- **Daily runtime bars:** Controller hour counters generally update shortly after midnight, so the current day can stay at zero. Reusing old entity IDs can resume an old statistics series and book a gap in one hour, producing a bar above 24 h. Correct that hour using **Developer tools > Statistics > Adjust sum** rather than deleting statistics.

For debug logs:

```yaml
logger:
  logs:
    custom_components.htha: debug
    htheatpump: debug
```

## Development and tests

Use a Python environment compatible with Home Assistant, the pinned integration dependency, `pytest`, `pytest-asyncio` and `pytest-homeassistant-custom-component`. Run from the repository root:

```bash
pytest
node --test tests/
```

The Node suite uses built-in test tools and offline fixtures; Python integration tests use mocked transport. See [schedule verification details](docs/schedule-scratchpad.md#offline-verification) for optional local visual checks.

`node tests/check-curve-layout.cjs` checks the curve card at 412 px in English/German with installed Chrome, blocked network access and no controller connection. It verifies status wrapping, the initially collapsed help, help toggling and updates.

## Credits

Based on [htheatpump](https://github.com/silviuk/htheatpump) by Daniel Strigl and inspired by the [original Home Assistant integration](https://github.com/dstrigl/htheatpump).

## License

[MIT](LICENSE), copyright 2026 Silviu Vlasceanu.

## Disclaimer

Incorrect settings can damage equipment or reduce efficiency. Use at your own risk; the software is provided without warranty. Review changes against your controller's documentation before sending them.
