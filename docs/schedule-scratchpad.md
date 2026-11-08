# Schedule editor

The card keeps `custom:htha-schedule-scratchpad-card`, `entity` and
`config_entry_id`. The integration auto-loads the card and manages its storage-mode
resource. The strategy shows it in the schedule section; `schedule_editor: false`
selects the read-only view. For an explicit YAML resource, use
`/htha_frontend/htha-schedule-scratchpad-card.js?v=1.3.6` (JavaScript Module).
See [dashboard example](../dashboards/schedule-editor-v2.yaml).
Existing binary schedule helpers remain separate.

**Saved in HA** means a persistent profile. **Sent to heat pump** means a
confirmed, independently verified apply. Edits/selection/copy/undo never call HA
services. Profile operations, mapping, loading, refresh and validation never
write to the pump. Allow writes is a read-only indicator; there is no implicit
enable-writes button.

## Use

1. Choose Heating (2) or Hot water (0). Opening the card and the first visit to
   each category automatically show **Current schedule (on pump)** and **read at**.
   The dedicated admin response service `get_current_time_program` returns a
   separate `current_view` (program, metadata, mode catalog and timestamp). It
   never changes the server draft, baseline, session, revision or approval.
   A baseline read or coordinator `time_programs` cache no older than 180 seconds
   costs zero pump reads. A miss performs one read of that category through the
   existing serialized transport path. Concurrent requests share the fresh cache.
   Each card instance loads each category at most once automatically; rendering,
   HA updates, visibility and reconnects never re-read. **Reload from pump** and
   the error **Retry** button explicitly request another read. In an open editor,
   Reload/Refresh baseline preserve edits and revoke validation as before.
2. No draft grid or editing controls appear until an explicit choice:
   **Edit a copy of current schedule**, **Start from profile…** followed by
   **Use as starting point** / **Apply profile…**, or **New schedule**.
   `start_time_program_draft` atomically captures the current baseline and copies
   the selected source under the manager lock with required revision/session checks.
   New resolves the category factory preset: heating Normal all day, hot water On
   all day. Unspecified hot-water periods mean Off/minimum maintenance, as in the
   factory preset documentation below. Unknown mappings remain unknown and block send.
   Existing server drafts (including another category) are offered for **Resume draft**
   or **Discard draft**. Starting a replacement asks for confirmation. Opening the
   dashboard never adopts or overwrites them silently.
   **Discard draft / Close editor** uses `discard_time_program_draft` with required
   revision/session checks and the existing unsaved-work confirmation, returning
   to the read-only grid. Draft and current grids have Monday–Sunday rows, an
   hour ruler and quarter-hour geometry; draft changes retain the old-color/X diff.

   The profile list refreshes automatically on first load, category changes and
   profile actions. Opening its dropdown and returning to a visible tab refresh
   at most once per two seconds without overlapping catalog requests. These
   refreshes only call `list_time_program_profiles` and preserve local work.
3. Click selects; Ctrl/Cmd-click toggles; Shift-click extends an inclusive range
   within one day; Ctrl/Cmd+Shift adds it. Shift to another day starts a new
   row-local selection. Drag selects only, with pointer capture and safe cancel.
   Arrows navigate, Shift+arrows extend, Space toggles, Escape clears. Selection
   does not invalidate a check. Choose a mode and explicitly **Set mode for
   selection** to change the local draft; dropdown selection alone changes nothing.
4. Mouse, pen and touch use Pointer Events with pointer capture. On phones,
   tap a draft slot to select it; tap the sole selected slot again to clear it.
   Enable **Multi-select** (**Mehrfachauswahl**) to add/remove individual slots.
   **Select day** (**Tag auswählen**) selects the last touched/focused day or
   the Day picker value; Multi-select keeps other selected days. **Clear
   selection** (**Auswahl aufheben**) clears all slots.
   Enable **Select** (**Auswählen**) before touch-dragging an inclusive range
   within one day. Only editable cells then use `touch-action:none`; scrolling
   outside the grid remains available. Turn Select off (the default) to scroll
   normally, horizontally or vertically; taps still select. This explicit mode
   avoids confusing a scroll gesture with a range selection. Cancellation or
   lost pointer capture restores the selection from before the gesture.
   At 412px the draft week scrolls horizontally with slot targets at least
   44 × 44 CSS pixels. The read-only current overview stays compact. The
   focused-day detail also has large slots and textual intervals. Day, Start,
   End, Add selection and **Select range** remain available for long ranges;
   End can be 24:00. Selection never changes the draft, validation or services;
   setting a mode remains a separate explicit action.
5. **Copy this day to…** supports All days, Weekdays, Weekend and selected days.
   Confirmation previews the targets. The whole day is deep-copied as one undo
   operation. Undo/redo are local (100-operation limit). Over-capacity edits are
   retained, never truncated or smoothed.
6. Expand mode mapping, verify numeric meanings on the actual controller and
   firmware, choose semantic labels and explicitly confirm. Every used mode
   must be confirmed before send. Also attest the numeric Normal code used for
   advisory checks; it must agree with Normal/Normal charging in the mapping.
   Labels never translate numeric payloads.
7. **Validate** submits a local copy, requests a fresh read under the manager
   lock, then validates and computes the diff. Failure preserves the draft and
   revokes approval. Review criticals, risks, per-day old/new numeric ranges,
   minutes/cells and entry counts; unchanged days say No changes. The read time
   identifies the comparison baseline. Edits mark an old comparison stale.
   Individually check every warning before acknowledging its exact IDs/hash.
8. **Save profile / Save as** creates a profile. **Update profile** explicitly
   overwrites its UUID/revision after confirmation. Capacity/risk-invalid work
   may be saved without write permission. Unknown/malformed cells must first be
   explicitly resolved. Saving unchanged contents need not revoke a check and
   never grants approval.
9. **Use as starting point** loads an independent draft copy. **Apply profile…**
   means copy → fresh read/validation/diff → stop for review, never automatic
   acknowledgement/send. Category, metadata, mapping or firmware mismatch blocks
   sending. After explicitly reviewing an incompatible source/mapping, an
   explicit profile update records new provenance and requires another check.
   Numeric codes are never silently translated.
10. When hardware work is separately authorized, enable Allow writes outside
    this card. Send stays visible with missing gate reasons including Allow
    writes OFF. It opens a review of controller, category/profile, numeric modes,
    changed days/ranges/minutes, baseline time and partial-write risk. Cancel
    sends nothing. **Send schedule** uses the existing guarded apply workflow,
    consumes approval and never retries automatically.

Names/external text are escaped. HA locale/time zone are used for timestamps
and current-time markers (Europe/Berlin fallback). Cells are recurring wall-clock
quarter-hours, never UTC durations advanced through DST. The marker shows time,
not compressor activity; global mode/overrides can supersede the program. HA
updates preserve dirty edits, focus, selection, gestures and scroll. Repeated
setConfig is idempotent; the minute marker timer is cleaned up on disconnect.

## Confidence, modes and advice

### Factory default (Heliotherm)

Each category's profile picker also offers a built-in, read-only template:

| Category | Monday–Sunday switching period | Manual fallback outside switching periods |
| --- | --- | --- |
| Heating (2) | 00:00–24:00 Normal / Normalbetrieb | Normal |
| Hot water (0) | 00:00–24:00 On / Ein | Off / Aus; minimum maintenance at WW_min, +5 K |

Source supplied by the owner: [web control 321 manual, pp.10–11](https://www.heliotherm.com/media/bedienungsanleitung-regelgeraet-web-control321/Bedienungsanleitung-Waermepumpenregler-Heliotherm.pdf).
This represents that manual's default, not a universal recommendation across
controller revisions. Drafts still require complete coverage; these fallback
descriptions do not relax validation or change targets/hysteresis.

Load metadata for the selected program first. **Use as starting point** copies
the preset without any hardware calls. Normal resolves through the verified
`normal` mapping; On through `charging`. Firmware 2.03N has a built-in verified
mapping: heating 0 = Setback, 1 = Normal, 2 = Boost; hot water 0 = Off, 1 = On.
Both factory presets therefore resolve to code 1 without a checkbox or manual
mapping step. An optional partial override can leave a mode unverified; in that
case validation still blocks sending. Reload the preset after changing an
override; mapping changes never silently rewrite an existing numeric draft.
Changed metadata/controller/firmware or mapping requires another review/load.

**Apply profile…** uses the same fresh validation/diff,
warning acknowledgements, confirmation and guarded apply as user profiles.
It stops for review and cannot send an unresolved preset. All existing server
write gates remain required, including Allow writes.

Rename, Delete and Update are disabled for built-ins and rejected server-side
(`profile_read_only`). **Save as** creates an ordinary editable user copy once
unknown cells have been resolved. Built-ins are not stored in HA Store, do not
consume the 50-user-profile limit and do not alter duplicate-name behavior.
The listing API returns them in `builtin_profiles` alongside the unchanged
user `profiles` array; load uses `factory_default_heating` or
`factory_default_hot_water` with the existing session/revision checks.

Preset regression tests are in `tests/test_schedule_factory.py`,
`test_htha_schedule_services.py` and `tests/schedule-editor.test.cjs`.
See the [preset acceptance record](schedule-editor-evidence/factory-preset/README.md)
for executed checks and offline desktop/phone evidence.

The owner verified the numeric ordering for HP07S08W-S-WEB firmware 2.03N:
unused slots are padded with the program default state, the manual defines
undefined heating time as Normal and undefined hot water as Off, and the pump
pads heating with 1 and hot water with 0. Heating reports three states
(Aufheizen/Normal/Absenken) and uses 0 for the daily 09:00–18:30 setback.
This supplied verification requires no live access. The built-in mapping applies
when firmware is exactly `2.03N` and the program reports three heating states or
two hot-water states. Other firmware/counts still require an explicit override.
The native v1.3.5 interface reports counts, not label enums. Unknown numeric codes display
**Mode N (unverified)** / **Modus N (nicht bestätigt)** with neutral hatching.
The mapping offers family-level manufacturer vocabulary:

| Program | Semantic choices | Confirmed colors |
| --- | --- | --- |
| Heating 2 | Setback / Absenken; Normal / Normalbetrieb; Boost / Aufheizen | Blue; purple; red |
| Hot water 0 | 0 Off / Aus; 1 On / Ein | Grey; green |

Exactly the numeric choices in live `nos` are offered. Partial mappings can be
saved as optional overrides, but all used modes must be confirmed before send.
The editor derives the Normal/On code from the active mapping; no separate
Normal-code checkbox is needed. Stored overrides take precedence over the
built-in default. Internal DHW semantics `minimum` and `charging` remain stable
for existing profiles and represent Off and On respectively. Mappings bind exact
program metadata and serial/firmware where known; incompatible changes require
reconfirmation. Mapping revision enters check identity and profile compatibility.
Mappings persist; approvals do not.

DHW Aus retains WW minimum maintenance; it is not hard-Off. No third DHW mode
exists here. Heating Boost is not global Dauerbetrieb. Normal follows the
existing curve, not continuous compressor operation. No temperatures, offsets,
curves, hysteresis or global modes are written.

Longer help and recommendations are hidden behind the small **?** control:
slow floor-heating comfort/recovery,
short Normal windows (<30 minutes), more than two daily Normal windows and
non-atomic writes retain their advisory role. These are not compressor starts
or manufacturer minimum on/off limits. Adjacent Normal intervals/midnight halves
may count as one advisory window; native capacities remain separate per day.
Buffer-fed fresh-water stations may need pre-charge before demand; plumbing and
hygiene require separate assessment. No household times/targets are enforced
and no energy savings are promised.

The weekly view adapts selected-day manufacturer timelines; it is not a verified
RCG2/2.03N screenshot. Sources supplied in the brief (not fetched in this offline
run): [web control 321 manual pp.10–12/22](https://www.heliotherm.com/media/bedienungsanleitung-regelgeraet-web-control321/Bedienungsanleitung-Waermepumpenregler-Heliotherm.pdf),
[Touchdisplay manual pp.15–19/22](https://www.heliotherm.com/media/bedienungsanleitung-touchdisplay-kunden/Touchdisplay-Bedienungsanleitung-Kunden-Heliotherm.pdf),
[webcontrolAT brochure](https://www.heliotherm.com/media/prospekte/Prospekt-Systemsteuerung.pdf),
[pinned native model](https://raw.githubusercontent.com/silviuk/htheatpump/v1.3.5/htheatpump/httimeprog.py).
Newer diagrams do not verify 2.03N numeric meanings. Modbus global Betriebsart
codes are not schedule codes; manual revisions have differing defaults.

## Persistence and API

Version-1 HA Store `htha_schedule_profiles_<entry_id>` is separate from recovery.
Limits: **50 profiles/category**, 100/entry; trimmed names 1–80 characters with
no control characters; optional descriptions ≤1000; seven complete days with
≤96 runs/day. Requests are bounded to 70 KB; checked drafts to 64 KiB. Names
are unique by casefold per category. Update/rename/delete require exact profile
revision; delete also requires confirmation and affects neither pump nor draft.

Records include UUID, category/index, schema/profile revision, UTC timestamps,
canonical draft, compatibility metadata (`index,name,ead,nos,ste,nod`), source
serial/firmware, mapping fingerprint/snapshot, description and Needs validation
status. They contain neither approvals nor write permission. Save success is
returned only after durable Store save; failed saves leave memory unchanged.
The manager lock serializes mutations/revisions. Corrupt/future Store versions
create a repair issue, block mutations/send approval and require inspection and
repair from a verified backup; no implicit migration or reset occurs.

Setup is serialized across awaited Store loads so concurrent setup cannot publish
two independent managers. Before every library commit, a new Store instance reads
the saved snapshot; a changed revision/content or unexpectedly removed Store
rejects the mutation with `profile_conflict`. This prevents stale snapshots from
overwriting newer data; it is not a cross-process filesystem transaction. Successful
profile saves/updates/renames/deletions log ID, name, category and library revision
at INFO. The Delete confirmation includes the name and sends that exact UUID.

See the [1.3.3 investigation and checks](profiles-1.3.3-investigation.md).

Restart retains profiles/mappings, without draft/approval. Reload and Allow-writes
toggle retain the manager/draft. Permanent entry removal deletes its profile
Store/manager and retains recovery evidence for manual inspection. Unloaded
entries reject calls; entries/categories isolate profile catalogs and UUIDs.
Full profiles are fetched on demand. Profile libraries, cells and full diffs are
never routinely recorded; current/draft/mapping/recovery blobs are excluded from
recorder attributes as well.

All services are admin-only/response-capable and require a loaded HTHA entry:

| Service | Hardware behavior |
| --- | --- |
| `get_time_program_editor` | Cached current/draft/catalog/gates/profile summaries; no read |
| `list_time_program_profiles` | Category summaries/revision; no pump calls |
| `save_time_program_profile` | Durable create/update; no pump calls |
| `rename_time_program_profile`, `delete_time_program_profile` | Library only |
| `load_time_program_profile` | Copy/invalidate; optional numeric read-only preview |
| `set_time_program_mode_mapping` | Persist binding/revision, invalidate; no write |
| `load_time_program_draft` | Read and replace draft |
| `refresh_time_program_baseline` | Read, retain draft, invalidate |
| `validate_time_program` | Check/diff; `fresh_read: true` reads first |
| `acknowledge_time_program_warnings` | Exact current warning IDs/hash; no write |
| `apply_time_program`, `restore_previous_time_program` | Only confirmed guarded schedule writes |

See `services.yaml` and EN/DE service translations for fields. New card mutations
send expected editor revision/session; validation also sends mapping revision.
Legacy services accept optional new fields. Check hash binds canonical numeric
payload, metadata, policy, mapping/binding, baseline, session and check revision,
so a new check cannot reuse an old approval. Stale revisions fail with conflict.

Canonicalization merges adjacent equal **numeric** states before counting
against `min(ead,7)` per day. It excludes padding 24:00–24:00 from visible runs
and behavioral diffs. Gaps/overlaps/unknown modes never become guessed Normal.
Full 00:00–24:00 coverage is stricter integration policy than implicit manual
fallback. Unsupported index/name/nod/ste/nos/ead fails closed.

Apply independently rereads schedule/metadata and aborts on external change. It
keeps manager → connection lock order, final permission/mapping/validation gates
after awaits, durable pre-write recovery, same-day/same-slot padding states,
consumed approval and independent read-back (numeric content and metadata).
There is no new privileged profile path, auto-rebase/send, retry or rollback.

## Interrupted writes and restore

Up to 49 independent slot commands may partially succeed. Cancellation marks
failure and propagates after a recovery read over a fresh connection. Failed
verification leaves current visualization unknown. Diagnostic `actual_program`
is separate from verified current state.

`htha_schedule_recovery_<entry_id>` retains `in_progress`, exact raw
`previous_program` including native padding and diagnostic `actual_program`.
The marker is saved before writing and cleared only on verified success.
Outstanding markers create repair notices at startup/failure. Pre-write Store
failure blocks native sets. No automatic recovery occurs.

Open **Recovery evidence**, inspect previous/actual and errors, refresh baseline
while keeping edits, choose **Use previous program as draft**, verify mapping,
Validate, acknowledge all warnings and explicitly confirm **Restore previous
program**. Restore requires the exact saved previous content/metadata and every
normal apply gate. Restore can also fail partially. Opening a repair never writes.

## Offline verification

From the root, with the repository HA test dependencies already installed:

```powershell
python -m pytest
node --test tests/schedule-card.test.cjs
node --test tests/
node tests/check-schedule-layout.cjs
```

Python requires Home Assistant, pytest-homeassistant-custom-component, pytest,
pytest-asyncio and pinned integration dependencies. This run downloads nothing.
`pytest.ini` sets automatic asyncio mode. Existing recovery tests cover all 49
slot failures, cancellation, read failure, padding and guarded restore. Autoload tests cover cache hit/miss/expiry, shared requests, draft preservation,
explicit source/close/resume transitions and no-write behavior. The layout check
uses blocked-network Chrome fixtures at 412px in EN/DE, light/dark, both categories
and both editor states; it creates no screenshots. It also checks 44px touch
targets, grid-only touch-action changes and native Chrome touch input for tap,
additive tap, captured drag and cancellation. Node touch-pointer tests verify
Select day, Clear selection, scrolling gestures and zero selection service calls
or draft/validation changes. New
tests cover cells/diffs, profiles/revisions/restarts/corruption, mapping/firmware,
stale tabs and permission revocation during durable marker await. HA service
tests use fake native transport and temporary HA Store.

Node uses built-in tests/DOM stubs; `tests/index.js` makes the requested directory
command work on Windows. Optional rendering uses installed Chrome via CDP stdio,
no HTTP server/sockets, blocked HTTP/WS URLs/DNS and connection-forbidding CSP.
Chrome sandbox is disabled only for this local synthetic fixture within the
execution sandbox. Set `CHROME_PATH` for another installed Chrome. The temporary
`.schedule-chrome/` profile is not source.

See [run results and visual evidence](schedule-editor-evidence/README.md).
These are synthetic desktop/360px EN/DE/light/dark screenshots and real DOM
checks, never controller screenshots/hardware verification.

**Firmware 2.03N schedule writes remain unverified.** No live HA/pump access,
deployment, push, merge, release or write-enable change was performed. Eventual
HA changes require backup. The first unchanged-program round trip must be
supervised and separately approved. Native serial-over-TCP remains unchanged;
no Modbus or newer-controller behavior is substituted.
