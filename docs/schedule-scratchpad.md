# Schedule scratchpad (not deployed)

Editing, checking, acknowledgement, loading and baseline refresh never write to
the controller. Keep Allow writes OFF during initial UI/service testing.
Time-program writes remain **unverified on firmware 2.03N**. The first real apply
must be a supervised re-apply of the unchanged current program, with separate
owner authorization. This PR does not authorize installation or hardware tests.

1. Add `/htha_frontend/htha-schedule-scratchpad-card.js?v=2` as a JavaScript Module
   resource. Configure the card with the Schedule draft validation sensor entity
   and its integration config entry ID (see the dashboard YAML example).
2. Choose Heating (2) or Hot water (0), then Load from pump. Load replaces the
   selected draft. One in-memory draft per entry survives integration reloads,
   including toggling Allow writes, but not HA restart. Approvals are never
   restored from disk. The existing binary schedule helpers remain separate.
3. Edit using quarter-hour time selectors, including 24:00 as the final end.
   Add/remove intervals or copy a day to all other days. The server requires seven
   days, 1..7 positive intervals within controller capacity, full 00:00-24:00
   coverage, no gaps/overlaps, and numeric modes within the reported state count.
   Full coverage is stricter than the manual's implicit fallback behavior.
4. Verify the Normal numeric code on this controller and attest to it. Native
   time-program metadata reports a state count, not mode labels; no verified
   label mapping is available from this interface. The attestation changes
   **advisory findings only**: it does not translate or protect numeric modes
   written. Other mode labels remain unverified instead of being invented.
   Modbus global operating mode codes are not schedule-entry codes.
5. Check the whole draft. Fix all critical findings, read all warnings and
   acknowledge exactly their IDs for the checked hash. Edits/checks/loads/refreshes
   invalidate approval. Program index and controller name must identify a
   supported primary heating or hot-water program; unknown names fail closed.
6. When separately authorized, enable Allow writes. Reload preserves the draft
   and its server check; if the card requires another check, check/acknowledge
   again. Save stays visible and explains missing requirements.
7. Save asks for explicit confirmation. The server revalidates, compares the
   baseline and metadata, checks permission, durably saves recovery evidence,
   writes and independently reads back. Approval is consumed. Unused slots are
   written as 24:00-24:00 with the controller's mode from that same day/slot,
   never a mode inferred from the draft's last real interval. Unavailable slot
   modes block apply. The time-program cache is invalidated even on failure.

Warnings include non-Normal floor-heating periods, Normal windows shorter than
30 minutes, more than two Normal windows per day, and non-atomic writes. Adjacent
Normal intervals and the two halves of a midnight window count as one. These are
advisory review thresholds, not manufacturer compressor limits. DHW demand
windows are not configured or enforced: one information note explains charging
before demand for buffer-fed fresh-water stations. A 05:00-07:00 / 18:00-20:00
pre-charge schedule gets no demand-coverage warnings.

## Failed or interrupted apply

Up to 49 independent writes may partially succeed. There is no automatic retry
or rollback. Cancellation marks the transaction failed and propagates after
recovery read-back is attempted over a fresh connection. A failed read is shown
separately; unavailable actual state is not presented as verified.

HA Store retains `in_progress`, the complete `previous_program` and the latest
`actual_program`. The marker is saved before the first write and cleared only
after verified success. An outstanding marker creates a repair issue at startup
and after failure. Inspect the sensor/service recovery evidence. Large attributes
are excluded from recorder. A draft/approval is never restored from this record.

Use **Refresh pump baseline, keep my draft** to read the actual program without
discarding edits. It clears validation and acknowledgements. To restore, load or
refresh the baseline for the previous program's index, choose **Use previous
program as draft**, verify the mapping, Check, acknowledge all warnings, enable
Allow writes when authorized and confirm **Restore previous program**. The server
requires the checked draft to equal the saved previous program and enforces all
normal apply gates. Restore itself can fail partially and uses the same recovery
mechanism. Merely opening the repair issue never writes anything.

Services are registered once, admin-only, and require a loaded HTHA entry:
`load_time_program_draft`, `refresh_time_program_baseline`,
`validate_time_program`, `acknowledge_time_program_warnings`,
`apply_time_program`, `restore_previous_time_program`. For service-only recovery,
use `previous_program.entries` with 24:00 placeholders removed as the validation
draft, then pass its checked hash and `confirm: true` to restore.

The integration lock serializes transactions for each entry, but cannot exclude
changes from unrelated controller clients. The new recovery evidence cannot
make this protocol atomic. No temperature, curve, hysteresis or global operating
mode setting is changed by these services.

## Offline verification

`pytest` uses automatic asyncio mode. Mocked tests exercise every slot failure,
cancellation, failed read-back, reload preservation, entry isolation, durable
recovery markers and guarded restore. Card tests run with
`node --test tests/schedule-card.test.cjs`. No tests access HA or pump hardware.
