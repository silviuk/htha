# Dashboard cleanup evidence

All work and captures were offline. No Home Assistant instance or heat pump
was contacted. No network, commit or push was used.

## Changes

No Comfort dashboard/view, registration or panel exists in the supplied working
tree. Searches covered dashboard files, strategy, integration initialization,
documentation, translations, manifest and configuration. Non-dashboard comfort
advice remains. The old generic Comfort schedule legend was corrected to the
owner-verified heating/hot-water state codes.

Removed duplicate live displays:

- Outdoor temperature and operating state heading badges.
- Operating mode in Overview; it appears once in Controls.
- Heating pump in Overview and its heading badge; it appears in Heating.
- Hot water mode in Overview and its heading badge; it appears in Hot water.
- Source pump/fan in Overview and its heading badge; it appears in Heat source.
- Room setpoint and three heating-curve setpoints in Heating; they appear in Controls.
- Normal/minimum hot-water setpoints in Hot water; they appear in Controls.
- Allow writes heading badge; the switch remains in Controls.
- Two separate Advice / Why disclosures; help and informational findings now
  share one closed-by-default 28px question-mark control.

Historical graphs retain trends and daily changes, which are distinct from
current values. Controls use mutually exclusive read-only and write-enabled
cards in the same location, so one value is visible at a time. Input features
still require Allow writes. The editor's current and draft schedules remain
separate because they are needed for comparison.

Tiles use the full section width; sections collapse through HA's native layout.
The editor has tighter spacing, wrapping controls, readable labels and HA theme
variables. Heating defaults to 0 Setback, 1 Normal, 2 Boost; hot water to 0 Off,
1 On for firmware 2.03N with matching state counts. Optional stored overrides
take precedence. Both factory presets resolve to code 1 without a Normal-code
checkbox. Other validation, warning, write-enable, confirmation and read-back
requirements remain. Service schemas and pump write commands are unchanged.

## Captures and checks

- `before/`: 10 original editor screenshots, desktop and 360px, both languages
  and themes, including hot water.
- `after/`: 14 updated screenshots, adding 412px checks.
- `after-factory/`: 14 updated factory-preset screenshots with the same coverage.
- Each directory contains its measured `layout-checks.json`.

Examples: [before German dark at 360px](before/360-de-dark.png),
[after German dark at 360px](after/360-de-dark.png),
[after English light at 412px](after/412-en-light.png),
[factory preset at 360px](after-factory/360-en-light.png).

These are synthetic editor fixtures, not Home Assistant dashboard screenshots.
The native HA strategy/YAML output is checked structurally by Node tests;
native HA card rendering and Android WebView were not exercised.

Executed:

- `node --test tests/`: **52 passed, 0 failed**.
- Offline Chrome: **38 screenshots**, no page overflow; after captures verify
  the 28px closed help control, hidden informational recommendations, absent
  Normal checkbox, disabled send with writes off, focus/scroll/draft preservation
  and safe pointer cancellation. Factory actions remain read-only.
- JavaScript syntax, translation JSON parsing and `git diff --check` pass.
- Python validator, factory and service tests were kept consistent and extended;
  **not executed**, as Python is unavailable on this machine.

Reproduce updated captures without a server or network sockets:

```powershell
node tests/capture-schedule-editor.cjs --out=docs/dashboard-cleanup-evidence/after
node tests/capture-schedule-editor.cjs --factory --out=docs/dashboard-cleanup-evidence/after-factory
```

The runner uses installed Chrome via stdio CDP, blocks HTTP/HTTPS/WS/WSS,
disables background networking and DNS resolution, and uses a fixture whose
CSP prohibits connections and whose service stub throws on every call.
