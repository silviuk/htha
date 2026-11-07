"""Pure schedule validation and guarded transactions; no HA or network on import."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import hashlib
import json
import re
from uuid import uuid4

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MANUAL = "web control 321 customer manual pp.10-13 (7 slots/day, 15-minute steps)"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def minutes(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d|24:00", value):
        raise ValueError("Time must be HH:MM; only the end may be 24:00")
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def normalized(entries):
    """Remove documented unused 24:00 placeholders and merge adjacent equal modes."""
    result = []
    for day in entries:
        blocks = []
        for item in day:
            if item is None or item["start"] == item["end"] == "24:00":
                continue
            item = {k: item[k] for k in ("start", "end", "state")}
            if blocks and blocks[-1]["end"] == item["start"] and blocks[-1]["state"] == item["state"]:
                blocks[-1]["end"] = item["end"]
            else:
                blocks.append(deepcopy(item))
        result.append(blocks)
    return result


def validate(draft, metadata, policy):
    """Fail closed on format/metadata; risk thresholds are explicitly advisory policy."""
    metadata = metadata if isinstance(metadata, dict) else {}
    policy = policy if isinstance(policy, dict) else {}
    capacity = metadata.get("ead") if type(metadata.get("ead")) is int else 0
    states = metadata.get("nos") if type(metadata.get("nos")) is int else 0
    findings = []

    def add(severity, code, message, day=None, source=MANUAL):
        findings.append(dict(id=f"{code}:{day}" if day is not None else code,
                             severity=severity, message=message, day=day, source=source))

    if any(type(metadata.get(k)) is not int for k in ("index", "ead", "nos", "ste", "nod")):
        add("critical", "metadata", "Load valid program metadata from this controller first.")
    elif metadata["index"] not in (0, 2) or metadata["nod"] != 7 or metadata["ead"] not in range(1, 8) or metadata["ste"] != 15 or metadata["nos"] not in (2, 3):
        add("critical", "unsupported_controller", "Unsupported controller format; do not assume newer RCG behavior.")
    if policy.get("kind") != {0: "hot_water", 2: "heating"}.get(metadata.get("index"), "unsupported"):
        add("critical", "program_kind", "Select heating or hot_water explicitly.", source="Integration safety rule")
    names = {0: {"hot water", "warmwasser", "brauchwasser"}, 2: {"heating", "heizung", "heizkreis 1", "heizkreis"}}
    if str(metadata.get("name", "")).strip().casefold() not in names.get(metadata.get("index"), set()):
        add("critical", "program_name", "Controller program name does not identify the selected heating/hot-water program.", source="Integration safety rule")
    if policy.get("mapping_confirmed") is not True or type(policy.get("normal_state")) is not int or policy.get("normal_state") not in range(states):
        add("critical", "mode_mapping", "Verify the Normal-mode numeric code on this controller/firmware; Modbus global operating modes are NOT schedule codes.", source="Integration safety rule")
    rows = draft.get("entries") if isinstance(draft, dict) else None
    if not isinstance(rows, list) or len(rows) != 7:
        add("critical", "days", "Exactly seven complete days are required.")
        rows = []
    for d, day in enumerate(rows):
        if not isinstance(day, list) or not day or len(day) > min(7, capacity):
            add("critical", "slots", "Day must contain 1..7 entries within the controller's reported capacity.", d)
            continue
        cursor = 0
        valid = []
        for e in day:
            try:
                if not isinstance(e, dict) or set(e) != {"start", "end", "state"}:
                    raise ValueError("Each entry requires only start, end, state")
                start, end = minutes(e["start"]), minutes(e["end"])
                if type(e["state"]) is not int or e["state"] not in range(states):
                    raise ValueError("Invalid mode code for this controller's reported state count")
                if start >= end or start >= 1440:
                    raise ValueError("Entry must have positive duration, start before 24:00")
                if start % 15 or end % 15:
                    raise ValueError("Times must be on 15-minute boundaries")
                if start != cursor:
                    raise ValueError("Entries must be ordered, contiguous, non-overlapping and cover 00:00-24:00")
                cursor = end
                valid.append((start, end, e["state"]))
            except (ValueError, KeyError, TypeError) as err:
                add("critical", "format", str(err), d, "Manual granularity/capacity + stricter integration full-coverage rule")
        if cursor != 1440:
            add("critical", "coverage", "Day must end at 24:00; implicit controller fallback is not accepted.", d, "Integration safety rule, stricter than manual fallback")
        if len(valid) != len(day):
            continue
        normal = policy.get("normal_state")
        on = [(a, b) for a, b, mode in valid if mode == normal]
        # Adjacent intervals and the two midnight halves form one window.
        merged = []
        for a, b in on:
            if merged and merged[-1][1] == a:
                merged[-1] = (merged[-1][0], b)
            else:
                merged.append((a, b))
        on = merged
        if len(on) > 1 and on[0][0] == 0 and on[-1][1] == 1440:
            on = [(on[-1][0], 1440 + on[0][1]), *on[1:-1]]
        if any(b - a < 30 for a, b in on):
            add("warning", "short_window", "A Normal window is shorter than 30 min; review comfort/recovery. This is NOT a manufacturer compressor minimum-run limit.", d, "Advisory household review policy (30 min), not a hardware limit")
        if len(on) > 2:
            add("warning", "many_windows", "More than two Normal windows/day; review repeated reheat opportunities. Windows are not compressor starts.", d, "Household policy: two demand periods, optional acknowledged PV period")
        if policy.get("kind") == "heating" and policy.get("floor_heating", True) and any(mode != normal for _, _, mode in valid):
            add("warning", "floor_non_normal", "Non-Normal floor-heating periods: verify whether these are setback or boost and review recovery/comfort. No universal setback-hour limit is established.", d, "General floor-heating practice, not a manufacturer prohibition")
    if policy.get("kind") == "hot_water":
        add("info", "precharge", "For a buffer-fed fresh-water station, plan Normal charging before demand. No household demand windows are enforced.", source="Optional household planning")
    add("info", "mapping_attestation", "The native program reports a state count, not mode labels. The supplied Normal code only affects advice; it does not translate or protect the numeric codes written.", source="Native controller metadata")
    add("warning", "non_atomic", "Applying a week sends multiple independent slot writes. A network failure can leave a partial schedule; inspect recovery evidence and refresh the baseline keeping your draft before deciding what to do. No automatic rollback/retry.", source="htheatpump set_time_prog_async transaction behavior")
    add("info", "pv", "Optional midday PV alignment concerns self-consumption, not warmer-air COP for groundwater equipment. No PV timing requirement is enforced.", source="Household energy advice")
    add("info", "hygiene", "Schedule validation is not a drinking-water hygiene assessment. Verify buffer/fresh-water station and distribution/circulation design.", source="System-specific hygiene review")
    add("info", "cycling", "No exact-model starts/hour/day or minimum on/off-time limit was found; no invented hardware limits are applied.", source="HPW-WEB 2006 model sheet p.5")
    # IDs remain unique even when multiple format errors occur on the same day.
    for number, item in enumerate(findings):
        item["id"] += f":{number}"
    canonical = {"entries": deepcopy(rows), "metadata": {k: metadata.get(k) for k in ("index", "name", "ead", "nos", "ste", "nod")}, "policy": deepcopy(policy)}
    critical = sum(f["severity"] == "critical" for f in findings)
    warnings = [f["id"] for f in findings if f["severity"] == "warning"]
    return dict(status="critical" if critical else "warnings" if warnings else "ready",
                findings=findings, critical_count=critical, warning_ids=warnings,
                draft_hash=digest(canonical), canonical=canonical)


class Scratchpad:
    """One selected weekly draft. Apply always revalidates and independently reads back.

    Writes are non-atomic (up to 49 slot commands). A failure never triggers an
    automatic retry/rollback; review the freshly read controller state first.
    """

    def __init__(self, coordinator, allow_writes, program_factory, notify=lambda: None, recovery=None):
        self.coordinator = coordinator
        self.allow_writes = allow_writes
        self.program_factory = program_factory
        self.notify = notify
        self.lock = asyncio.Lock()
        self.draft = None
        self.policy = {}
        self.metadata = None
        self.baseline_hash = None
        self.report = {"status": "unvalidated", "findings": [], "critical_count": 0, "warning_ids": []}
        self.ack_hash = None
        self.ack_ids = set()
        self.revision = 0
        self.session_id = uuid4().hex
        self.recovery = recovery
        self.previous_program = None
        self.actual_program = None

    async def _save_recovery(self, in_progress):
        if self.recovery:
            await self.recovery({"in_progress": in_progress, "previous_program": self.previous_program,
                                 "actual_program": self.actual_program})

    async def refresh_baseline(self):
        """Read current controller state without replacing the user's edits."""
        async with self.lock:
            if self.metadata is None:
                raise ValueError("Load a program first")
            current = await self._read(self.metadata["index"])
            self.metadata = {k: current[k] for k in ("index", "name", "ead", "nos", "ste", "nod")}
            self.actual_program = current
            self.baseline_hash = digest(normalized(current["entries"]))
            self.report = {"status": "unvalidated", "findings": [], "critical_count": 0, "warning_ids": []}
            self.ack_hash, self.ack_ids = None, set()
            self.changed()

    async def restore(self, expected_hash, confirm):
        """Restore only a separately checked/acknowledged previous program draft."""
        return await self.apply(deepcopy(self.draft), expected_hash, confirm, restoring=True)

    def changed(self):
        self.revision += 1
        self.notify()

    @property
    def can_apply(self):
        return bool(self.allow_writes() and self.report.get("status") in ("ready", "warnings")
                    and not self.report.get("critical_count") and self.report.get("draft_hash")
                    and (not self.report["warning_ids"] or
                         (self.ack_hash == self.report["draft_hash"] and set(self.report["warning_ids"]) <= self.ack_ids)))

    async def _read(self, index):
        c = self.coordinator
        async with c._connection_lock:
            try:
                await c._connect()
                return (await c.heatpump.get_time_prog_async(index, with_entries=True)).as_json()
            finally:
                await c._disconnect()

    async def load(self, index):
        async with self.lock:
            current = await self._read(index)
            self.metadata = {k: current[k] for k in ("index", "name", "ead", "nos", "ste", "nod")}
            self.draft = {"entries": normalized(current["entries"])}
            self.baseline_hash = digest(normalized(current["entries"]))
            self.policy = {}
            self.report = {"status": "unvalidated", "findings": [], "critical_count": 0, "warning_ids": []}
            self.ack_hash, self.ack_ids = None, set()
            self.changed()
            return self.report

    async def check(self, draft, policy):
        async with self.lock:
            if self.metadata is None:
                raise ValueError("Load the current pump program first")
            self.draft, self.policy = deepcopy(draft), deepcopy(policy)
            self.report = validate(draft, self.metadata, policy)
            self.ack_hash, self.ack_ids = None, set()
            self.changed()
            return self.report

    async def acknowledge(self, expected_hash, warning_ids):
        async with self.lock:
            if self.report.get("critical_count") or self.report.get("draft_hash") != expected_hash or set(warning_ids) != set(self.report.get("warning_ids", [])):
                raise ValueError("Validate the current draft and acknowledge exactly its warning IDs")
            self.ack_hash, self.ack_ids = expected_hash, set(warning_ids)
            self.changed()

    async def apply(self, draft, expected_hash, confirm, restoring=False):
        async with self.lock:
            if restoring and (not self.previous_program or not draft or self.metadata is None
                              or normalized(draft["entries"]) != normalized(self.previous_program["entries"])
                              or self.metadata != {k: self.previous_program[k] for k in self.metadata}):
                raise ValueError("Check and acknowledge the previous program as the current draft first")
            if confirm is not True or not self.can_apply:
                raise ValueError("Apply requires confirmation, Allow writes, valid check and warning acknowledgements")
            checked = validate(draft, self.metadata, self.policy)
            if checked["critical_count"] or self.report.get("critical_count") or checked["draft_hash"] != expected_hash or expected_hash != self.report.get("draft_hash"):
                self.ack_hash, self.ack_ids = None, set()
                self.report["status"] = "stale"
                self.changed()
                raise ValueError("Draft changed; check and acknowledge again")
            c = self.coordinator
            async with c._connection_lock:
                writing = False
                try:
                    await c._connect()
                    current = (await c.heatpump.get_time_prog_async(self.metadata["index"], with_entries=True)).as_json()
                    metadata = {k: current[k] for k in self.metadata}
                    if metadata != self.metadata or digest(normalized(current["entries"])) != self.baseline_hash:
                        raise ValueError("Controller schedule/metadata changed since Load; load and validate again")
                    # Final gate after every awaited read/connection operation.
                    if not self.can_apply or not self.allow_writes():
                        raise ValueError("Write permission or validation was revoked")
                    payload = deepcopy(self.metadata)
                    payload["entries"] = []
                    if len(current["entries"]) != 7 or any(
                        not isinstance(day, list) or len(day) != payload["ead"]
                        for day in current["entries"]
                    ):
                        raise ValueError("Controller did not return all native slots; refusing to invent placeholder modes")
                    for d, day in enumerate(draft["entries"]):
                        padded = deepcopy(day)
                        while len(padded) < payload["ead"]:
                            slot = current["entries"][d][len(padded)]
                            if not isinstance(slot, dict) or type(slot.get("state")) is not int or slot["state"] not in range(payload["nos"]):
                                raise ValueError("Controller slot mode unavailable; refusing to invent a placeholder mode")
                            padded.append({"start": "24:00", "end": "24:00", "state": slot["state"]})
                        payload["entries"].append(padded)
                    if restoring:
                        # Restore the actual saved slots, including their original padding.
                        payload = deepcopy(self.previous_program)
                        if any(len(day) != payload["ead"] or any(
                            not isinstance(slot, dict) or type(slot.get("state")) is not int
                            or slot["state"] not in range(payload["nos"])
                            for slot in day) for day in payload["entries"]):
                            raise ValueError("Previous program lacks complete native slots; refusing to invent restore data")
                    self.previous_program = deepcopy(current)
                    self.actual_program = None
                    await self._save_recovery(True)
                    if not self.allow_writes():
                        raise ValueError("Write permission was revoked")
                    self.report["status"] = "applying"
                    self.changed()
                    writing = True
                    await c.heatpump.set_time_prog_async(self.program_factory(payload))
                    actual = (await c.heatpump.get_time_prog_async(self.metadata["index"], with_entries=True)).as_json()
                    if normalized(actual["entries"]) != normalized(draft["entries"]):
                        raise RuntimeError("Independent read-back differs; controller may be partially changed")
                    self.baseline_hash = digest(normalized(actual["entries"]))
                    self.report["status"] = "applied"
                    self.actual_program = actual
                    await self._save_recovery(False)
                except (Exception, asyncio.CancelledError) as err:
                    self.report["status"] = "failed"
                    self.report["apply_error"] = str(err) or type(err).__name__
                    self.report["possible_partial_write"] = writing
                    if writing:
                        try:
                            # Reconnect separately: the failed transport may be unusable.
                            await c._disconnect()
                            await c._connect()
                            self.actual_program = (await c.heatpump.get_time_prog_async(self.metadata["index"], with_entries=True)).as_json()
                        except (Exception, asyncio.CancelledError) as read_err:
                            self.actual_program = None
                            self.report["recovery_read_error"] = str(read_err) or type(read_err).__name__
                        try:
                            await self._save_recovery(True)
                        except (Exception, asyncio.CancelledError) as save_err:
                            # The pre-write marker is already durable. Keep the original
                            # transaction exception (especially cancellation) as the result.
                            self.report["recovery_storage_error"] = str(save_err) or type(save_err).__name__
                    raise
                finally:
                    self.ack_hash, self.ack_ids = None, set()
                    c.time_programs = None
                    c._last_time_programs_update = 0
                    try:
                        await c._disconnect()
                    except (Exception, asyncio.CancelledError) as disconnect_err:
                        self.report["disconnect_error"] = str(disconnect_err) or type(disconnect_err).__name__
                    finally:
                        self.changed()
            await c.async_request_refresh()
            return self.report
