# Factory preset addendum — local acceptance record

7 November 2026. No commits, pushes, dependency downloads, network requests,
Home Assistant access or heat-pump contact. Existing editor work remains
uncommitted together with this addendum.

Implemented both built-in templates, semantic-only numeric resolution,
critical unresolved/changed mapping checks, server-enforced read-only profiles,
Save as, EN/DE presentation and documentation. Existing user profiles, profile
limits and the guarded apply workflow remain in place.

| Command | Result |
| --- | --- |
| `node --test tests/` | 43 passed, 0 failed, including 7 added preset tests |
| `node --test tests/schedule-card.test.cjs` | 4 passed, 0 failed (included above) |
| `node tests/capture-schedule-editor.cjs --factory` | 10 offline screenshots; no page overflow at 1100/360px; focus/scroll/draft/cancel checks passed; zero runtime errors; read-only mutation buttons disabled and Save as enabled |
| `node --check custom_components/htha/frontend/htha-schedule-scratchpad-card.js` | Passed |
| `git diff --check` | Passed; Git emitted only Windows line-ending notices |
| `python -m pytest` | Could not start: `python` command not found |

Added 17 parameterized pure/backend test cases in
`tests/test_schedule_factory.py` and 2 parameterized HA service cases in
`test_htha_schedule_services.py`. They cover both categories, different numeric
orders and partial mappings, unknown drafts, mapping/metadata/firmware changes,
explicit reload, immutable definitions, restart, mutation rejection, Save as,
admin access, approval clearing, Allow writes, warnings and confirmation.
These Python tests have **not been collected or executed**. Run the full suite
in an environment with the existing HA test dependencies; no packages were
downloaded here.

The screenshots use synthetic, explicitly confirmed fixture mappings. All HA
service calls throw in the fixture, CSP forbids connections, HTTP/WS URLs and
DNS are blocked, and Chrome CDP uses stdio. They make no firmware/hardware
claims. The default schedule comes from the owner-provided manual reference;
the manual was not fetched during this offline task.

| Width/category | EN/light | EN/dark | DE/light | DE/dark |
| --- | --- | --- | --- | --- |
| 1100, heating | [PNG](1100-en-light.png) | [PNG](1100-en-dark.png) | [PNG](1100-de-light.png) | [PNG](1100-de-dark.png) |
| 360, heating | [PNG](360-en-light.png) | [PNG](360-en-dark.png) | [PNG](360-de-light.png) | [PNG](360-de-dark.png) |
| Hot water | [1100 PNG](1100-en-light-hot-water.png) | — | — | [360 PNG](360-de-dark-hot-water.png) |

Desktop EN/light heating and 360px DE/dark hot water were visually inspected.
[Machine-readable layout checks](layout-checks.json) record every screenshot
and the real DOM checks.

Touched implementation: `schedule_safety.py`, `schedule_services.py`, the card,
`services.yaml`, `strings.json`, EN/DE translations, usage docs/dashboard cache
version, backend/service/Node tests, and the optional fixture/capture harness.
The five original editor requirements and visualization remain implemented;
this addendum extends requirement 4's profile picker and requirement 5's guarded
profile application. Python runtime verification remains the only deferred
local check. Firmware 2.03N numeric ordering and hardware writes remain
unverified and require separately authorized work.
