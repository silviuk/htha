# Schedule scratchpad (proposed; not deployed)

## Safety and workflow

This PR adds **no automatic schedule writer**. Integration startup, loading,
editing, checking and acknowledgement never set a pump value. Existing Allow
writes remains unchanged. Keep it **OFF** while reviewing/testing.

1. Add the bundled custom card resource as a JavaScript Module:
   `/htha_frontend/htha-schedule-scratchpad-card.js?v=1`.
2. Find the integration's **Schedule draft validation** sensor in HA (entity ID
   depends on the device name). Fill that ID and the config entry ID into
   `schedule-scratchpad-dashboard.yaml`.
3. Choose Heating (native program 2) or Hot water (0); **Load from pump** reads
   all seven days and clears old validation/acknowledgements. The scratchpad is
   **in-memory, one selected program per integration entry**. It does not survive
   HA restart/reload. The current live binary `schedule.htha_*_draft` helpers are
   left untouched: they cannot losslessly represent three heating modes.
4. Edit HH:MM boundaries and numeric modes. Up to seven explicit intervals/day;
   use 24:00 as the final end. Add/remove intervals; checking points out gaps.
   No frontend edit calls any pump service. Unchecked local edits invalidate the
   card's Save/acknowledge controls immediately.
5. Verify the **Normal numeric code on the actual controller/firmware**, then
   explicitly confirm the mapping. The card initially shows numeric codes,
   not invented Normal/Setback labels. Modbus register 100 global operating
   modes are **not** time-program mode codes. This is a user attestation, not
   an automatically established mapping; do not guess it.
6. **Check** sends the whole draft and policy to HA. The server returns findings
   and a SHA-256 binding the draft, program metadata and review policy.
7. Fix critical errors; read **all** warnings and explicitly acknowledge their
   exact IDs for that hash. Any check/load/hash change invalidates approval.
8. Only after separate user authorization to turn Allow writes ON does Save
   become available. Save has an additional confirmation and supplies the full
   current draft and hash. The server independently enforces every gate.
9. Under the existing connection lock, the server re-reads current metadata and
   schedule to detect external changes, rechecks write permission, writes, then
   independently re-reads and compares normalized schedules. All seven slots
   per day are explicitly supplied, including 24:00 placeholders, so stale
   slots cannot remain from a previously longer program. Refresh coordinator.

**Non-atomic operation:** htheatpump writes individual slots, not one atomic
week. A network failure may leave a partial schedule. No blind retry or rollback
is attempted. A failed/mismatched write clears acknowledgements and reports
`possible_partial_write`; inspect the controller, Load, and review again.
A successful write consumes the approval; another Save requires another check.
Sessions are serialized; concurrent Apply calls cannot both consume approval.
The controller lock protects this integration, not unrelated external clients;
a remote controller change between the final read and writes cannot be excluded.

Services are admin-only and targeted by `config_entry_id`:
`load_time_program_draft`, `validate_time_program`,
`acknowledge_time_program_warnings`, `apply_time_program`.
The diagnostic sensor exposes draft, metadata, report, findings, hash,
acknowledgement, revision and `can_apply`. Draft/report changes notify listeners.
EN/DE service, sensor and card-control translations are included. Technical
finding messages/source citations currently remain English.

## Rules and their authority

| Severity | Rule | Basis |
|---|---|---|
| Critical | Seven days; 1..7 positive-duration slots/day within reported capacity; 15-minute boundaries; integer modes in reported range | Customer manual pp.10–13 plus live native metadata |
| Critical | Explicit sorted contiguous 00:00–24:00 coverage; no gaps/overlap | **Stricter integration safety policy**; manual describes fallback Normal outside specified heating periods |
| Critical | Only seven-day, 15-minute, 2/3-state formats and primary heating/DHW supported; mapping explicitly verified; kind matches program | Fail-closed compatibility policy, not assumed RCGX compatibility |
| Apply refusal | Writes OFF, missing confirmation, wrong/stale hash, unacknowledged warnings, pump/metadata changed since Load | Integration guardrails |
| Warning | Any non-Normal heating interval with floor-heating policy | General thermal-mass/comfort review; **not** manufacturer ban on setback |
| Warning | Normal interval <30 min; >2 Normal intervals/day | Household advisory thresholds, **not compressor min-run/start limits**; schedule windows do not equal compressor starts |
| Warning | DHW Normal does not cover 06:15–09:00 or 20:00–22:00 | This household's demand; minimum-temperature reheating may still occur |
| Warning | Multi-slot apply can partially fail | Library transaction behavior; applies even to otherwise valid Normal-24h drafts |
| Info | Optional PV alignment; hygiene/plumbing review; no verified manufacturer cycling limit | No spurious hardware threshold or mandatory PV hours |

DHW flow/capacity, drinking-water hygiene, actual room influence and compressor
control are outside this schedule-only validator. No temperature, heating-curve,
hysteresis, mode or electric-heater value is altered by it.

## Setback vs continuous Normal — source-grounded explanation

[web control 321 customer manual](https://www.heliotherm.com/media/bedienungsanleitung-regelgeraet-web-control321/Bedienungsanleitung-Waermepumpenregler-Heliotherm.pdf):

- **pp.7–8,19:** Setback reduces the **heating return-water target** relative to
  the curve by the configured offset, factory **3 K**. That does not promise a
  3 °C room-temperature reduction. The target also depends on room correction.
- **p.7:** `Raum` is a parallel curve shift. Actual room temperature is displayed
  only if a room sensor is attached. A displayed/set “21 °C room” value therefore
  must not be treated as proof of actual 21 °C room-temperature feedback.
- **p.10:** Factory heating program is **Normal 00:00–24:00 every day**. The manual
  supports setback; it does not categorically prohibit it for floor heating.
- **p.7:** Do not confuse that with global **Dauerbetrieb**: the described global
  mode raises the curve by **3 K**. For this recommendation use Auto with a
  Normal-all-day program, **not global boosted Dauerbetrieb**.
- **p.20:** The manual's floor-heating example uses return targets 22 °C at +18 °C
  outside, 27 °C at 0 °C, 30 °C at −15 °C. These are examples, not safety limits.
  It advises adjustments of **1–2 K with 1–2 days between changes**.
- **p.31:** Heating limit (`Heizgrenze`) is a configurable item (listed range
  0–45 °C). This is not a recommended setting or verified current value.
  Confirm actual heating-limit / Auto–Summer behavior and room influence before
  relying on them to avoid unwanted heat. Mixer settings have separate limits.

[2019 RCGX professional Modbus excerpt](https://forum.iobroker.net/assets/uploads/files/1657798802648-20191213_fachmannebene_rcgx_1.0.3.2_de.pdf),
PDF pp.5–6/8 (printed pp.23–24/26), lists global operating modes at register 100,
not schedule-entry mode mappings. It does not establish floor-heating setback
or compressor cycling recommendations for this pump's firmware 2.03N.

**Recommendation for this house (general practice):** start with Auto + stable
Normal heating all day while resolving the reported ~19 °C vs target20–20.5 °C.
Normal24h is *permission to meet the weather-dependent demand*, not a command to
run the compressor24h. Floor screed's thermal mass can make short setbacks reduce
room temperature very little; recovery can need higher water temperature and
worsen COP/comfort. Longer genuine room-temperature reductions reduce heat loss,
so continuous heating is not universally the lowest-energy choice. There is no
verified manufacturer universal setback-duration or starts/day limit here.

Tune the relevant curve point **or** parallel shift in the documented small
steps; observe measured rooms over the documented waiting interval. Do not raise
both at once. First check floor-loop flow/balancing, active Auto/time-program mode,
actual room measurement, internal/solar gains and sensor configuration.
Continuous Normal does not itself cause overheating, but an overly high curve,
incorrect heating limit or absent room feedback can. We have **not** verified
those protections; do not promise the controller will always prevent it.

[HPW-WEB 2006 model-family sheet](https://byggeboligblobstorage.blob.core.windows.net/imageoriginals/e2e8c150db9b4099beb20740a749a9b4.pdf),
p.5 lists HP07S08W-WEB (full -S suffix applicability not independently confirmed):
COP6.50 at W10/W35 vs4.38 at W10/W50 illustrates the temperature-lift penalty,
not a prediction of seasonal savings. The 55 °C heating-water maximum is not a
recommended floor-heating operating temperature. The sheet gives no exact
compressor start/hour/day or minimum on/off-time limit.

## Verification / remaining deployment

Mocked protocol tests cover locks, no writes during draft operations, all gates,
hash invalidation, changed pump metadata, independent read-back, explicit slot
padding, partial failure and concurrent Apply. No tests write real hardware.
Browser visual/hardware testing remains necessary after separate approval to
install this PR; keep Allow writes OFF for all initial UI/service tests.
Do not add these undeployed services/entities to the live dashboard now.
