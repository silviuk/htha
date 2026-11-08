# Profile refresh and disappearance investigation — 1.3.3

## Incident finding: NOT PROVEN

The supplied facts describe hot-water profile `4f6afa89-b138-427e-827f-356ea5d9827a`,
“Family default (hot water)”, saved on November 8 around 01:05 Berlin time,
after deleting duplicate `cfb13c80...`. At 18:41, the hot-water listing was empty,
with `library_revision: 4` and `library_error: null`.

No live Home Assistant, pump, Store file, historical log or backup was accessed.
The specific disappearance cannot be attributed to a particular operation from
these facts. Revision 4 counts library mutations, including mapping changes;
it does not identify their IDs, categories or order. An empty category listing
with no library error does not establish that the whole library was empty.

## Code-path audit

| Path | Finding |
| --- | --- |
| `ProfileLibrary.load` | Loads the complete validated record. Invalid schema/metadata/fingerprint makes the library erroneous and blocks commits; it never persists a filtered subset. This would report `library_corrupt`, unlike the supplied response. |
| `commit` | Replaces the complete Store snapshot after awaiting save. Previously lacked a comparison with stored content. A stale instance could overwrite newer profiles. |
| `save_profile` / editor saves | Replaces only an explicitly supplied profile UUID, or appends a new UUID. Category/revision checks apply to updates; unrelated UUIDs are retained. |
| `rename` | Uses the same save/update path, retaining UUID, draft and provenance. |
| `delete` | Requires explicit confirmation and the exact profile revision; removes only the supplied UUID. |
| Manager setup | Ordinary reload reuses the retained manager/library under its lock. However, creation checked the manager dictionary before awaiting Store loads and only published the manager afterward. Overlapping setup calls could create independent instances. Whether this happened in the incident is unknown. |
| Entry unload/removal | Unload leaves the retained manager/library. `async_remove_entry` explicitly removes the profile Store and manager; this is the permanent entry-deletion cleanup path. Removing and re-adding an entry would lose that entry's library. No evidence establishes such removal here. |
| Schema/compatibility/mapping | Structural corruption fails closed. Changed controller/firmware/metadata/mapping blocks validation or requires review; it does not delete stored profiles. `needs_validation` is retained in listings. |
| Category filtering | Listing selects the saved `category` exactly; the hot-water list says nothing about heating profiles or a different config entry. Update cannot move an existing profile to another category. |
| Card selection / Delete | Selection is held by UUID, with no code choosing another profile automatically after a refresh. Delete already captured the selected record before confirming, but the confirmation omitted its name. There is no demonstrated wrong-ID deletion in this incident. |
| Restart / Store timing | Saves await `Store.async_save` before updating library memory or reporting success; no delayed-save API is used here. A normal restart reloads that record. Disk failure, abrupt termination and external Store replacement cannot be assessed without historical evidence. |

**SUSPECTED, not established as the incident cause:** stale snapshot overwrite,
explicit deletion, entry removal/re-creation, another entry/category, or external
storage loss. The setup interleaving and missing stale-commit check are concrete
code weaknesses, with regression tests added, but the Python tests could not be
executed in this environment.

## Changes

- Removed the standalone Profiles button. Initial card load, category switch,
  save/rename/delete/apply and Load from pump refresh the list automatically.
  Focus/open and tab visibility refreshes are throttled to two seconds. Catalog
  requests serialize; late responses for another category/entry are ignored.
- Automatic refresh calls only `list_time_program_profiles`. It preserves local
  edits, history, validation, selected cells and the selected profile UUID when
  present. A missing UUID clears selection instead of choosing another profile.
  Focused controls and active gestures defer rendering.
- Serialized manager setup through a shared setup lock. Each library commit
  rereads storage through a new Store instance and rejects changed, newer,
  same-revision-replaced or unexpectedly missing data with `profile_conflict`.
  This is an in-process safeguard, not a filesystem compare-and-swap across
  multiple HA processes. Reload alone still retains the manager and draft.
- Delete confirms the captured profile name and sends its captured UUID/revision.
  Successful saves, updates/renames and deletes log ID/name/category/library
  revision at INFO; stale commit rejection logs a warning.
- Updated manifest, strategy version, resource URLs, version assertion, README
  and schedule documentation to 1.3.3. The Profiles translation remains in use
  by the dropdown and its accessible label, in both languages.
- Pump transport, write services, apply/restore transaction code and approval
  gates were not changed.

## Verification

- `node --test tests/`: **73 passed, 0 failed**. Covers existing write gates plus
  initial refresh, lifecycle cleanup, focus/visibility throttling, request
  serialization, late category responses, draft/selection/approval retention,
  list failures, category/pump-load follow-up and exact-ID named deletion EN/DE.
- Python regression tests added for stale save/rename/delete/mapping commits,
  missing/corrupt/same-revision Store replacement, old commit candidates,
  operation logging and overlapping manager setup.
- `python -m pytest tests/ -q`: **not executed**; `python` is not on PATH, other
  Python/pytest launchers were unavailable, the local Python directory was
  inaccessible and WSL enumeration was denied. Python pass status is unknown.
- `git diff --check`: passed.

Changed files: `README.md`, `custom_components/htha/manifest.json`,
`custom_components/htha/frontend/htha-heatpump-strategy.js`,
`custom_components/htha/frontend/htha-schedule-scratchpad-card.js`,
`custom_components/htha/schedule_safety.py`,
`custom_components/htha/schedule_services.py`, `dashboards/schedule-editor-v2.yaml`,
`docs/schedule-scratchpad.md`, this investigation,
`tests/dashboard-strategy.test.cjs`, `tests/schedule-editor.test.cjs`,
`tests/test_schedule_editor.py`, and `test_htha_schedule_services.py`.

All work remained local. No commit, push, deployment or live HA/pump contact.
