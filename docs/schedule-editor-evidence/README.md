# Schedule editor v2 — local acceptance record

Run: 7 November 2026, branch `feat/schedule-editor-v2`, Node v24.20.0.
All changes are uncommitted. No push, deployment, HA connection, pump contact,
write-enable change or dependency download was performed.

| Requirement | Implementation status |
| --- | --- |
| 1. Same schedule every day | Implemented: copy entire day to All days, with target preview/confirmation and one-step undo. Also weekdays/weekend/custom targets. |
| 2. Select slots and choose category modes | Implemented: click/Ctrl/Cmd/Shift, row-local drag, touch range/add controls, keyboard, explicit Set action, category-specific numeric catalog and confirmed semantic mapping. |
| 3. Validate errors/risks and summarize changes | Implemented: fresh read retaining draft, canonical capacity check, numeric range diff, counts/minutes, per-warning review and stale-state feedback. |
| 4. Named persistent category profiles | Implemented: versioned per-entry HA Store, UUID/revisions, create/update/rename/delete, category isolation, immutable draft copies and review-only Apply shortcut. Python/HA runtime verification pending below. |
| 5. Confirmed send only with Allow writes | Implemented through the existing guarded apply/restore path, additional mapping/compatibility/session gates, disabled reasons and review dialog. Hardware behavior remains unverified. |
| Visualization | Implemented: separate current/draft week grids, 00–24 ruler, quarter-hours, semantic colors, numeric legend, household-zone time marker, phone range controls/day detail and textual fallback. |

## Exact executed checks

| Command | Result | Exact output |
| --- | --- | --- |
| `node --test tests/schedule-card.test.cjs` | 4 passed, 0 failed | [output](legacy-card-output.txt) |
| `node --test tests/` | 36 passed, 0 failed (includes those four) | [output](node-suite-output.txt) |
| `node tests/capture-schedule-editor.cjs` | 10 screenshots; no page overflow at 1100/360; focus/scroll/draft/cancel checks passed; zero browser runtime errors | [output](chrome-output.txt), [layout checks](layout-checks.json) |
| `python -m pytest` | Could not start: Python absent (`ENOENT`; PowerShell also reports command not found) | [output](python-output.txt) |

[Machine-readable command results](test-results.json). `node --check` and
`git diff --check` also passed. Python tests were **not collected/executed**, so
the current full Python test count and whether they pass cannot be claimed.
The brief's prior 138-test result was not reused as a current result.

Added Node coverage: selection/drag/cancel/touch/keyboard, explicit mode edits,
deep day copy/undo/redo, unknown cells/capacity, profile CRUD/conflicts/shortcut,
dirty replacement, exact warning review, cancelled/duplicate sends, all missing
gate reasons, fresh-read failure, focus/lifecycle, EN/DE safe rendering, zone
formatting, stale diffs and honest profile provenance.

Added Python coverage: cell/run conversion, 7/8 capacity and merge/hash identity,
malformed/unknown/bool/out-of-range/oversized inputs, pair-coalesced numeric diffs,
fresh-read failure, external changes/stale tabs, complete mappings/firmware,
durable Store failures, CRUD/names/revisions/limits/isolation/restart/corruption,
invalid profiles refusing send, permission revoked during durable pre-write
await and frozen timestamps. HA tests add admin-only services, Store restart,
profile conflicts, stale editor/category rejection and unchanged/changed save
approval behavior. Existing 49-slot failure/cancellation/padding/restore tests
remain present; fake mapping attestations were added to their setup to meet the
new additional mapping gate.

## Visual evidence (synthetic data only)

The fixture uses explicitly synthetic numeric mappings, never manufacturer
defaults. It cannot connect to HA: its service stub throws, its CSP forbids
connections, Chrome blocks HTTP/WS URLs/DNS, and CDP uses stdio without a local
server. Screenshot width is the actual emulated viewport; full-page captures
include controls, findings and diff. These are not authenticated controller
screenshots or proof of firmware 2.03N behavior.

| Width/category | EN/light | EN/dark | DE/light | DE/dark |
| --- | --- | --- | --- | --- |
| Desktop 1100, heating | [PNG](1100-en-light.png) | [PNG](1100-en-dark.png) | [PNG](1100-de-light.png) | [PNG](1100-de-dark.png) |
| Phone 360, heating | [PNG](360-en-light.png) | [PNG](360-en-dark.png) | [PNG](360-de-light.png) | [PNG](360-de-dark.png) |
| DHW two-mode examples | [Desktop PNG](1100-en-light-hot-water.png) | — | — | [Phone PNG](360-de-dark-hot-water.png) |

Desktop EN/light and phone DE/dark were visually inspected, as were the two
DHW examples. Automated real DOM checks validate focus/scroll preservation,
dirty-draft preservation and a cancelled real captured pointer gesture.

## Files changed

- `custom_components/htha/schedule_safety.py`: canonical cells/runs/diff, bounded
  durable profile library, mappings, check identity/current state and apply gates.
- `custom_components/htha/schedule_services.py`: admin service schemas/handlers,
  Store setup, cached snapshots, profiles, revisions and translated errors.
- `custom_components/htha/__init__.py`: permanent entry removal cleanup while
  retaining recovery evidence. `sensor.py`: recorder exclusions.
- `custom_components/htha/frontend/htha-schedule-scratchpad-card.js`: compatible
  card type with the new editor, mappings, profiles, review and EN/DE UI.
- `custom_components/htha/services.yaml`, `strings.json`, `translations/en.json`,
  `translations/de.json`: service fields/descriptions/errors and repair issue.
- `docs/schedule-scratchpad.md`, `dashboards/schedule-editor-v2.yaml`: usage,
  safety, limits, API and cache-versioned resource example.
- `tests/schedule-editor.test.cjs`, `tests/index.js`,
  `tests/schedule-card.test.cjs`: new and retained Node regression checks.
- `tests/test_schedule_editor.py`, `test_htha_schedule_services.py`,
  `tests/test_schedule_safety.py`, `tests/test_schedule_recovery.py`: Python
  editor/Store/service coverage and explicit fake mapping setup.
- `tests/fixtures/schedule-editor.html`, `tests/capture-schedule-editor.cjs`,
  this evidence directory: reproducible offline browser fixture/captures/results.
- `.gitignore`: excludes temporary `.schedule-chrome/` browser profile only.

## Deferred verification and uncertainties

Python/HA tests need an environment with Python and the repository's HA test
dependencies. No downloads were allowed here. Run `python -m pytest` there
before treating server behavior as runtime-verified.

The ignored `.schedule-chrome/` fixture profile remains locally. Automatic
command review blocked its recursive cleanup without supplying a further
reason; it is excluded from source changes.

Native schedule-state numeric ordering and schedule writes on 2.03N remain
unverified. Names/colors are family-level references with explicit local
mapping confirmation, never guessed firmware defaults. No controller clock
synchronization or target/hysteresis changes are inferred. Any eventual HA
change needs backup; a supervised unchanged-program round trip needs separate
authorization. No hardware testing or deployment was attempted.
