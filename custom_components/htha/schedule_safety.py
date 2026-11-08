"""Pure schedule validation and guarded transactions; no HA or network on import."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import hashlib
import json
import logging
import re
from uuid import UUID, uuid4
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MANUAL = "web control 321 customer manual pp.10-13 (7 slots/day, 15-minute steps)"
META_KEYS = ("index", "name", "ead", "nos", "ste", "nod")
SEMANTICS = {2: ("setback", "normal", "boost"), 0: ("minimum", "charging")}
# Owner-verified HP07S08W-S-WEB, firmware 2.03N. Internal DHW semantic
# names are retained for stored-profile compatibility: minimum=Off, charging=On.
VERIFIED_MODES = {2: {"0": "setback", "1": "normal", "2": "boost"},
                  0: {"0": "minimum", "1": "charging"}}
FACTORY_PRESETS = {
    "factory_default_heating": dict(category="heating", program_index=2, mode_name="Normal", semantic="normal"),
    "factory_default_hot_water": dict(category="hot_water", program_index=0, mode_name="On", semantic="charging"),
}
FACTORY_SOURCE = "https://www.heliotherm.com/media/bedienungsanleitung-regelgeraet-web-control321/Bedienungsanleitung-Waermepumpenregler-Heliotherm.pdf"
GERMAN_DAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
FINDINGS_DE = {
    "metadata": "Zuerst gültige Programmdaten dieses Reglers laden.",
    "unsupported_controller": "Nicht unterstütztes Reglerformat. Verhalten neuerer RCG-Regler darf nicht vorausgesetzt werden.",
    "program_kind": "Heizung oder Warmwasser ausdrücklich passend zum Programm wählen.",
    "program_name": "Der Programmname identifiziert kein unterstütztes Heizungs-/Warmwasserprogramm.",
    "mode_mapping": "Normal-Code an diesem Regler und dieser Firmware prüfen. Modbus-Betriebsarten sind keine Zeitprogramm-Codes.",
    "slots": "Ein Tag benötigt 1 bis 96 begrenzte Intervalle.",
    "format": "Ungültiges Intervall: Zahlencodes, Viertelstunden, Reihenfolge und lückenlose Abdeckung prüfen.",
    "coverage": "Tag muss bei 24:00 enden. Impliziter Rückfallbetrieb wird im Entwurf nicht akzeptiert.",
    "short_window": "Normal-Zeitfenster kürzer als 30 Minuten: Komfort und Erholung prüfen. Keine Mindestlaufzeit des Kompressors.",
    "many_windows": "Mehr als zwei Normal-Zeitfenster pro Tag: wiederholtes Nachladen prüfen. Zeitfenster sind keine Kompressorstarts.",
    "floor_non_normal": "Nicht-Normal-Zeiten bei Fußbodenheizung: Absenkung/Aufheizen sowie Erholung und Komfort prüfen. Keine allgemeine Absenkdauer ist belegt.",
    "precharge": "Bei pufferbetriebener Frischwasserstation vor dem Bedarf normal laden. Keine festen Haushaltszeiten werden erzwungen.",
    "non_atomic": "Mehrere unabhängige Schreibvorgänge können teilweise fehlschlagen. Wiederherstellungsdaten prüfen und Vergleichsbasis mit erhaltenem Entwurf aktualisieren. Kein automatischer Wiederholungsversuch oder Rücksetzen.",
    "pv": "Optionale PV-Ausrichtung betrifft Eigenverbrauch, nicht wärmere Außenluft bei Grundwasseranlagen. Keine feste PV-Zeit wird erzwungen.",
    "hygiene": "Zeitprogrammprüfung bewertet keine Trinkwasserhygiene. Puffer, Frischwasserstation, Verteilung und Zirkulation separat prüfen.",
    "cycling": "Keine belegten Starts/Stunde/Tag oder Mindest-Ein-/Auszeiten für dieses Modell: keine erfundenen Gerätegrenzen.",
    "complete_mapping": "Alle im Entwurf verwendeten Zahlencodes am Regler prüfen und Moduszuordnung bestätigen.",
    "normal_mapping_conflict": "Der bestätigte Normal-Code muss zur gespeicherten Zuordnung Normalbetrieb bzw. Normal laden passen.",
    "profile_incompatible": "Profilmetadaten, Regler/Firmware oder Zuordnung passen nicht zusammen. Nach Prüfung ausdrücklich neu speichern oder aktuellen Pumpenstand laden.",
    "factory_mapping": "Werkseinstellung: Die Zuordnung für Normalbetrieb (Heizung) bzw. Ein (Warmwasser) ist nicht bestätigt oder wurde geändert. Zuordnung am Regler prüfen, bestätigen und die Vorlage erneut laden. Senden ist gesperrt.",
}


def supported_metadata(metadata):
    return (isinstance(metadata, dict) and set(metadata) == set(META_KEYS)
            and all(type(metadata[k]) is int for k in ("index", "ead", "nos", "ste", "nod"))
            and metadata["index"] in (0, 2) and metadata["ead"] in range(1, 8)
            and metadata["nos"] in (2, 3) and metadata["ste"] == 15 and metadata["nod"] == 7
            and isinstance(metadata["name"], str) and len(metadata["name"]) <= 80)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def clock(value):
    return f"{value // 60:02d}:{value % 60:02d}"


def bounded_draft(draft):
    """Validate structure before copying/hashing; allow capacity/risk-invalid work."""
    if not isinstance(draft, dict) or set(draft) != {"entries"}:
        raise ValueError("draft_shape")
    rows = draft["entries"]
    if not isinstance(rows, list) or len(rows) != 7:
        raise ValueError("draft_shape")
    for day in rows:
        if not isinstance(day, list) or not 1 <= len(day) <= 96:
            raise ValueError("draft_shape")
        cursor = 0
        for item in day:
            if not isinstance(item, dict) or set(item) != {"start", "end", "state"}:
                raise ValueError("draft_shape")
            a, b = minutes(item["start"]), minutes(item["end"])
            if a != cursor or a >= b or a % 15 or b % 15 or type(item["state"]) is not int or not 0 <= item["state"] <= 255:
                raise ValueError("draft_shape")
            cursor = b
        if cursor != 1440:
            raise ValueError("draft_shape")
    return {"entries": normalized(rows)}


def cells(entries, states=256):
    """Project raw native slots; gaps, overlaps and invalid slots remain unknown."""
    week = [[None] * 96 for _ in range(7)]
    if not isinstance(entries, list) or len(entries) != 7:
        return week
    for d, day in enumerate(entries):
        if not isinstance(day, list):
            continue
        touched = set()
        for item in day[:97]:
            try:
                if item is None or item["start"] == item["end"] == "24:00":
                    continue
                a, b, mode = minutes(item["start"]), minutes(item["end"]), item["state"]
                if a >= b or a % 15 or b % 15 or type(mode) is not int or mode not in range(states):
                    # An invalid region cannot establish controller truth.
                    return [[None] * 96 for _ in range(7)]
                for i in range(a // 15, b // 15):
                    week[d][i] = None if i in touched else mode
                    touched.add(i)
            except (KeyError, ValueError, TypeError):
                return [[None] * 96 for _ in range(7)]
    return week


def runs(week):
    """96 recurring wall-time cells per day; never advance UTC through DST."""
    if len(week) != 7 or any(len(day) != 96 for day in week):
        raise ValueError("draft_shape")
    result = []
    for day in week:
        row = []
        for i, state in enumerate(day):
            if row and row[-1]["state"] == state:
                row[-1]["end"] = clock((i + 1) * 15)
            else:
                row.append(dict(start=clock(i * 15), end=clock((i + 1) * 15), state=state))
        result.append(row)
    return {"entries": result}


def schedule_diff(current, draft, metadata):
    old = cells(current.get("entries") if current else None, metadata.get("nos", 0))
    new = cells(draft.get("entries") if isinstance(draft, dict) else None, metadata.get("nos", 0))
    result = []
    for d, (before, after) in enumerate(zip(old, new)):
        changes = []
        for i, (a, b) in enumerate(zip(before, after)):
            if a == b:
                continue
            if changes and changes[-1]["end"] == clock(i * 15) and (changes[-1]["from_state"], changes[-1]["to_state"]) == (a, b):
                changes[-1]["end"] = clock((i + 1) * 15)
            else:
                changes.append(dict(start=clock(i * 15), end=clock((i + 1) * 15), from_state=a, to_state=b))
        count = sum(a != b for a, b in zip(before, after))
        positive = lambda row: None if None in row else 1 + sum(a != b for a, b in zip(row, row[1:]))
        result.append(dict(day=d, ranges=changes, changed_cells=count, changed_minutes=count * 15,
                           old_entries=positive(before), new_entries=positive(after), capacity=min(metadata.get("ead", 0), 7),
                           baseline_unknown=None in before))
    return dict(days=result, changed_cells=sum(d["changed_cells"] for d in result),
                changed_minutes=sum(d["changed_minutes"] for d in result), baseline_unknown=any(d["baseline_unknown"] for d in result))


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
    policy = {"normal_state": 1, "mapping_confirmed": True, **(policy if isinstance(policy, dict) else {})}
    capacity = metadata.get("ead") if type(metadata.get("ead")) is int else 0
    states = metadata.get("nos") if type(metadata.get("nos")) is int else 0
    findings = []

    def add(severity, code, message, day=None, source=MANUAL):
        findings.append(dict(id=f"{code}:{day}" if day is not None else code,
                             severity=severity, message=message, message_de=FINDINGS_DE.get(code, message),
                             day=day, source=source,
                             source_de="web control 321 Kundenhandbuch, S.10–13" if source == MANUAL else "Integrationsregel / ausdrücklich gekennzeichnete Beratung"))

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
        if not isinstance(day, list) or not day or len(day) > 96:
            add("critical", "slots", "Day must contain 1..96 bounded intervals.", d)
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
        compressed = normalized([day])[0]
        if len(compressed) > min(7, capacity):
            add("critical", "capacity", f"{DAYS[d]} needs {len(compressed)} entries; controller supports {min(7, capacity)}. Merge or remove one change.", d)
            findings[-1]["message_de"] = f"{GERMAN_DAYS[d]} benötigt {len(compressed)} Einträge; Regler unterstützt {min(7, capacity)}. Einen Wechsel zusammenführen oder entfernen."
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

    add("warning", "non_atomic", "Applying a week sends multiple independent slot writes. A network failure can leave a partial schedule; inspect recovery evidence and refresh the baseline keeping your draft before deciding what to do. No automatic rollback/retry.", source="htheatpump set_time_prog_async transaction behavior")
    add("info", "pv", "Optional midday PV alignment concerns self-consumption, not warmer-air COP for groundwater equipment. No PV timing requirement is enforced.", source="Household energy advice")
    add("info", "hygiene", "Schedule validation is not a drinking-water hygiene assessment. Verify buffer/fresh-water station and distribution/circulation design.", source="System-specific hygiene review")
    add("info", "cycling", "No exact-model starts/hour/day or minimum on/off-time limit was found; no invented hardware limits are applied.", source="HPW-WEB 2006 model sheet p.5")
    # Stable scoped IDs, including separate malformed intervals within a day.
    seen = {}
    for item in findings:
        key = item["id"]
        seen[key] = seen.get(key, 0) + 1
        item["id"] += f":{seen[key]}"
    try:
        canonical_rows = bounded_draft({"entries": rows})["entries"]
    except (ValueError, TypeError):
        canonical_rows = deepcopy(rows)
    canonical = {"entries": canonical_rows, "metadata": {k: metadata.get(k) for k in META_KEYS}, "policy": deepcopy(policy)}
    critical = sum(f["severity"] == "critical" for f in findings)
    warnings = [f["id"] for f in findings if f["severity"] == "warning"]
    return dict(status="critical" if critical else "warnings" if warnings else "ready",
                findings=findings, critical_count=critical, warning_ids=warnings,
                draft_hash=digest(canonical), canonical=canonical)


class ProfileLibrary:
    """Versioned, bounded entry-local Store. Caller holds the manager lock.

    Copy-on-save makes a failed durable save visible as failure, never success.
    No validation result, write permission or approval is persisted here.
    """

    LIMIT = 50  # per category
    STORE_LIMIT = 8_000_000  # accommodates 100 maximum-size bounded profiles
    BUILTIN_NAMES = ("Factory default (Heliotherm)", "Werkseinstellung (Heliotherm)")

    def __init__(self, save, load=None):
        self.save = save
        self.read_store = load
        self.data = dict(schema_version=1, revision=0, profiles=[], mappings={})
        self.error = None

    def load(self, record):
        if record is None:
            return
        try:
            if not isinstance(record, dict) or set(record) != set(self.data) or type(record["schema_version"]) is not int or record["schema_version"] != 1 or type(record["revision"]) is not int or record["revision"] < 0:
                raise ValueError("library_corrupt")
            if not isinstance(record["profiles"], list) or len(record["profiles"]) > 100 or not isinstance(record["mappings"], dict) or set(record["mappings"]) - {"0", "2"}:
                raise ValueError("library_corrupt")
            ids, names = set(), set()
            for p in record["profiles"]:
                if type(p["schema_version"]) is not int or p["schema_version"] != 1 or p["category"] not in ("heating", "hot_water") or type(p["program_index"]) is not int or p["program_index"] != {"heating": 2, "hot_water": 0}[p["category"]] or type(p["revision"]) is not int or p["revision"] < 1:
                    raise ValueError("library_corrupt")
                UUID(p["id"])
                if any(not isinstance(p[k], str) or len(p[k]) > 80 for k in ("created_at", "updated_at")):
                    raise ValueError("library_corrupt")
                if self.name(p["name"]) != p["name"] or p["id"] in ids or (p["category"], p["name"].casefold()) in names:
                    raise ValueError("library_corrupt")
                bounded_draft(p["draft"])
                if not supported_metadata(p["compatibility"]) or p["compatibility"]["index"] != p["program_index"] or not isinstance(p["source_controller"], dict):
                    raise ValueError("library_corrupt")
                if any(e["state"] >= p["compatibility"]["nos"] for day in p["draft"]["entries"] for e in day):
                    raise ValueError("library_corrupt")
                if not isinstance(p["mapping_snapshot"], dict) or p["mapping_fingerprint"] != digest(p["mapping_snapshot"]) or len(p.get("description", "")) > 1000:
                    raise ValueError("library_corrupt")
                ids.add(p["id"])
                names.add((p["category"], p["name"].casefold()))
            for category in ("heating", "hot_water"):
                if sum(p["category"] == category for p in record["profiles"]) > self.LIMIT:
                    raise ValueError("library_corrupt")
            for index, m in record["mappings"].items():
                if type(m["revision"]) is not int or m["revision"] < 1 or not isinstance(m["binding"], dict) or not supported_metadata(m["binding"]["metadata"]) or m["binding"]["metadata"]["index"] != int(index):
                    raise ValueError("library_corrupt")
                self.validate_mapping(int(index), m["mapping"], m["binding"]["metadata"]["nos"])
            # Reject oversized/unexpected stored values without migrating implicitly.
            if len(json.dumps(record)) > self.STORE_LIMIT:
                raise ValueError("library_corrupt")
            self.data = deepcopy(record)
        except (ValueError, KeyError, TypeError, AttributeError):
            self.error = "library_corrupt"

    @staticmethod
    def name(name):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or any(ord(c) < 32 or 127 <= ord(c) < 160 for c in name):
            raise ValueError("profile_name")
        return name.strip()

    @staticmethod
    def validate_mapping(index, mapping, nos):
        if not isinstance(mapping, dict) or type(nos) is not int or nos not in (2, 3) or set(mapping) != {str(i) for i in range(nos)}:
            raise ValueError("mapping_invalid")
        values = [v for v in mapping.values() if v is not None]
        if any(v not in SEMANTICS[index] for v in values) or len(values) != len(set(values)):
            raise ValueError("mapping_invalid")

    async def commit(self, data):
        if self.error:
            raise ValueError(self.error)
        if data["revision"] != self.data["revision"]:
            raise ValueError("profile_conflict")
        if self.read_store:
            stored = await self.read_store()
            empty = dict(schema_version=1, revision=0, profiles=[], mappings={})
            # Compare the whole snapshot, including same-revision replacements.
            # Never merge a stale deletion/update or reset a missing Store.
            if stored != self.data and not (stored is None and self.data == empty):
                _LOGGER.warning("Refusing stale profile library commit at revision %s", self.data["revision"])
                raise ValueError("profile_conflict")
        data = deepcopy(data)
        data["revision"] += 1
        if len(json.dumps(data)) > self.STORE_LIMIT:
            raise ValueError("payload_too_large")
        await self.save(deepcopy(data))
        self.data = data

    def listing(self, category):
        if category not in ("heating", "hot_water"):
            raise ValueError("profile_category")
        return dict(library_revision=self.data["revision"], library_error=self.error,
                    builtin_profiles=[self.get(key) for key, p in FACTORY_PRESETS.items() if p["category"] == category],
                    profiles=[{k: deepcopy(p[k]) for k in ("id", "name", "category", "revision", "updated_at", "needs_validation")} for p in self.data["profiles"] if p["category"] == category])

    def get(self, profile_id):
        if profile_id in FACTORY_PRESETS:
            return dict(id=profile_id, name="Factory default (Heliotherm)", revision=1,
                        read_only=True, needs_validation=True, source=FACTORY_SOURCE,
                        source_pages="10–11", **FACTORY_PRESETS[profile_id])
        if self.error:
            raise ValueError(self.error)
        for p in self.data["profiles"]:
            if p["id"] == profile_id:
                return deepcopy(p)
        raise ValueError("profile_missing")

    async def save_profile(self, category, name, draft, metadata, source, mapping, profile_id=None, expected=None, description=""):
        if profile_id in FACTORY_PRESETS:
            raise ValueError("profile_read_only")
        name = self.name(name)
        draft = bounded_draft(draft)
        if not supported_metadata(metadata) or any(e["state"] >= metadata["nos"] for day in draft["entries"] for e in day):
            raise ValueError("draft_shape")
        if category != {0: "hot_water", 2: "heating"}.get(metadata.get("index")):
            raise ValueError("profile_category")
        if not isinstance(description, str) or len(description) > 1000:
            raise ValueError("profile_description")
        old = self.get(profile_id) if profile_id else None
        if old and (old["category"] != category or type(expected) is not int or old["revision"] != expected):
            raise ValueError("profile_conflict")
        if not old and expected is not None:
            raise ValueError("profile_conflict")
        names = {p["name"].strip().casefold() for p in self.data["profiles"]
                 if p["category"] == category and p["id"] != profile_id}
        # Existing copies with a factory name remain editable without migration.
        if not old or old["name"].casefold() != name.casefold():
            names.update(n.casefold() for n in self.BUILTIN_NAMES)
        if old and name.casefold() in names:
            raise ValueError("profile_duplicate")
        base, number = name, 2
        while name.casefold() in names:
            suffix = f" ({number})"
            name = base[:80 - len(suffix)].rstrip() + suffix
            number += 1
        if not old and sum(p["category"] == category for p in self.data["profiles"]) >= self.LIMIT:
            raise ValueError("profile_limit")
        now = utcnow()
        profile = dict(id=profile_id or str(uuid4()), name=name, category=category, program_index=metadata["index"],
                       schema_version=1, revision=old["revision"] + 1 if old else 1,
                       created_at=old["created_at"] if old else now, updated_at=now, draft=draft,
                       compatibility=deepcopy(metadata), source_controller=deepcopy(source),
                       mapping_fingerprint=digest(mapping), mapping_snapshot=deepcopy(mapping),
                       description=description, needs_validation=True)
        data = deepcopy(self.data)
        data["profiles"] = [p for p in data["profiles"] if p["id"] != profile_id] + [profile]
        await self.commit(data)
        _LOGGER.info("Profile %s id=%s name=%r category=%s library_revision=%s",
                     "updated" if old else "saved", profile["id"], name, category, self.data["revision"])
        return deepcopy(profile)

    async def rename(self, profile_id, name, expected):
        if profile_id in FACTORY_PRESETS:
            raise ValueError("profile_read_only")
        p = self.get(profile_id)
        return await self.save_profile(p["category"], name, p["draft"], p["compatibility"], p["source_controller"], p["mapping_snapshot"], profile_id, expected, p.get("description", ""))

    async def delete(self, profile_id, expected, confirm):
        if profile_id in FACTORY_PRESETS:
            raise ValueError("profile_read_only")
        p = self.get(profile_id)
        if confirm is not True or type(expected) is not int or p["revision"] != expected:
            raise ValueError("profile_conflict")
        data = deepcopy(self.data)
        data["profiles"] = [p for p in data["profiles"] if p["id"] != profile_id]
        await self.commit(data)
        _LOGGER.info("Profile deleted id=%s name=%r category=%s library_revision=%s",
                     p["id"], p["name"], p["category"], self.data["revision"])
        return self.listing(p["category"])


class Scratchpad:
    """One selected weekly draft. Apply always revalidates and independently reads back.

    Writes are non-atomic (up to 49 slot commands). A failure never triggers an
    automatic retry/rollback; review the freshly read controller state first.
    """

    def __init__(self, coordinator, allow_writes, program_factory, notify=lambda: None, recovery=None, library=None):
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
        self.current_program = None
        self.baseline_read_at = None
        self.current_state = "unknown"
        self.library = library
        self.profile_context = None

    @property
    def controller_identity(self):
        return {k: str(getattr(self.coordinator, attr, "") or "") for k, attr in (("serial", "serial_number"), ("firmware", "sw_version"))}

    @property
    def mapping(self):
        if not supported_metadata(self.metadata):
            return {}
        override = self.library.data["mappings"].get(str(self.metadata["index"])) if self.library else None
        if override is not None:
            return deepcopy(override)
        modes = VERIFIED_MODES[self.metadata["index"]]
        if self.controller_identity["firmware"] != "2.03N" or len(modes) != self.metadata["nos"]:
            return {}
        return dict(mapping=deepcopy(modes), revision=0, binding=self.mapping_binding)

    @property
    def mapping_binding(self):
        return dict(metadata=deepcopy(self.metadata), controller=self.controller_identity)

    @property
    def mapping_valid(self):
        return bool(self.mapping and self.mapping.get("binding") == self.mapping_binding and not (self.library and self.library.error))

    @property
    def catalog(self):
        return [dict(state=i, semantic=self.mapping.get("mapping", {}).get(str(i)) if self.mapping_valid else None,
                     confirmed=self.mapping_valid and self.mapping.get("mapping", {}).get(str(i)) is not None)
                for i in range(self.metadata["nos"] if supported_metadata(self.metadata) else 0)]

    def factory_profile(self, profile_id):
        """Resolve a semantic template only against the verified active mapping.

        Unknown is deliberately not a guessed numeric state. Loading never reads
        or writes hardware; confirming a mapping requires explicitly reloading.
        Caller holds the manager lock, as for ordinary profile loads.
        """
        p = self.library.get(profile_id)
        if not supported_metadata(self.metadata) or self.metadata["index"] != p["program_index"]:
            raise ValueError("baseline_unavailable")
        state = next((c["state"] for c in self.catalog if c["confirmed"] and c["semantic"] == p["semantic"]), None)
        return dict(**p, draft={"entries": [[dict(start="00:00", end="24:00", state=state)] for _ in range(7)]},
                    resolved_state=state, compatibility=deepcopy(self.metadata),
                    source_controller=self.controller_identity, mapping_fingerprint=digest(self.mapping))

    def invalidate(self):
        self.report = {"status": "unvalidated", "findings": [], "critical_count": 0, "warning_ids": []}
        self.ack_hash, self.ack_ids = None, set()

    def expect(self, revision=None, session=None, mapping_revision=None):
        if revision is not None and (type(revision) is not int or revision != self.revision):
            raise ValueError("editor_conflict")
        if session is not None and session != self.session_id:
            raise ValueError("editor_conflict")
        if mapping_revision is not None and (type(mapping_revision) is not int or mapping_revision != self.mapping.get("revision", 0)):
            raise ValueError("mapping_conflict")

    async def set_mapping(self, mapping, expected, confirmed, index=None, revision=None, session=None):
        async with self.lock:
            self.expect(revision, session)
            if self.metadata is None or self.library is None or confirmed is not True:
                raise ValueError("mapping_invalid")
            if not supported_metadata(self.metadata):
                raise ValueError("mapping_invalid")
            if index is not None and index != self.metadata["index"]:
                raise ValueError("profile_category")
            if type(expected) is not int or expected != self.mapping.get("revision", 0):
                raise ValueError("mapping_conflict")
            self.library.validate_mapping(self.metadata["index"], mapping, self.metadata["nos"])
            data = deepcopy(self.library.data)
            data["mappings"][str(self.metadata["index"])] = dict(mapping=deepcopy(mapping), revision=expected + 1, binding=self.mapping_binding)
            await self.library.commit(data)
            self.invalidate()
            self.changed()

    def _accept_current(self, current):
        self.metadata = {k: current[k] for k in META_KEYS}
        self.current_program = deepcopy(current)
        self.baseline_read_at = utcnow()
        self.current_state = "read"
        self.baseline_hash = digest(normalized(current["entries"]))

    async def _fresh(self, index):
        # Approval is revoked before awaiting transport, also on cancellation/failure.
        self.invalidate()
        try:
            current = await self._read(index)
            if not supported_metadata({k: current.get(k) for k in META_KEYS}) or type(current.get("index")) is not int or current["index"] != index:
                raise ValueError("Unsupported or mismatched controller program metadata")
            self._accept_current(current)
            return current
        except (Exception, asyncio.CancelledError):
            self.current_state = "unavailable"
            self.current_program = None
            self.baseline_hash = None
            raise
        finally:
            self.changed()

    def _checked(self, draft, policy):
        normal = next((c["state"] for c in self.catalog if c["confirmed"] and c["semantic"] ==
                       ("normal" if self.metadata["index"] == 2 else "charging")), 1)
        policy = {"normal_state": normal, "mapping_confirmed": self.mapping_valid, **policy}
        bound_policy = {**policy, "_mapping": self.mapping, "_baseline": self.baseline_hash,
                        "_session": self.session_id, "_check_revision": self.revision + 1}
        report = validate(draft, self.metadata, bound_policy)
        used = {e.get("state") if type(e.get("state")) is int else None for day in draft.get("entries", []) for e in day if isinstance(e, dict)}
        reasons = []
        if not self.mapping_valid or any(type(mode) is not int or self.mapping["mapping"].get(str(mode)) is None for mode in used):
            reasons.append("complete_mapping")
        elif self.mapping["mapping"].get(str(policy.get("normal_state"))) != ("normal" if self.metadata["index"] == 2 else "charging"):
            reasons.append("normal_mapping_conflict")
        if self.profile_context:
            p = self.profile_context
            incompatible = (p["compatibility"] != self.metadata or p["source_controller"] != self.controller_identity or p["mapping_fingerprint"] != digest(self.mapping))
            if p["id"] in FACTORY_PRESETS:
                if p["resolved_state"] is None or incompatible or not self.mapping_valid:
                    reasons.append("factory_mapping")
            elif incompatible:
                reasons.append("profile_incompatible")
        for reason in reasons:
            messages = {"complete_mapping": "Confirm the semantic mapping for every numeric mode used in the draft.",
                        "factory_mapping": "Factory default: the mapping for Normal (heating) / On (hot water) is unverified or changed. Verify and confirm the controller mapping, then reload the preset. Sending is blocked.",
                        "normal_mapping_conflict": "The attested Normal code conflicts with the confirmed semantic mapping.",
                        "profile_incompatible": "Profile metadata, source controller/firmware or mapping differs; review and explicitly update provenance before validation."}
            report["findings"].append(dict(id=reason, severity="critical", message=messages[reason], message_de=FINDINGS_DE[reason],
                                           day=None, source="Integration safety rule", source_de="Sicherheitsregel der Integration"))
            report["critical_count"] += 1
            report["status"] = "critical"
        report.update(diff=schedule_diff(self.current_program, draft, self.metadata), baseline_hash=self.baseline_hash,
                      baseline_read_at=self.baseline_read_at, mapping_revision=self.mapping.get("revision", 0))
        report["diff"].update(baseline_read_at=self.baseline_read_at, baseline_hash=self.baseline_hash,
                              mapping_revision=self.mapping.get("revision", 0))
        return report

    async def _save_recovery(self, in_progress):
        if self.recovery:
            await self.recovery({"in_progress": in_progress, "previous_program": self.previous_program,
                                 "actual_program": self.actual_program})

    async def refresh_baseline(self, revision=None, session=None):
        """Read current controller state without replacing the user's edits."""
        async with self.lock:
            self.expect(revision, session)
            if self.metadata is None:
                raise ValueError("Load a program first")
            await self._fresh(self.metadata["index"])

    async def restore(self, expected_hash, confirm, revision=None, session=None):
        """Restore only a separately checked/acknowledged previous program draft."""
        return await self.apply(deepcopy(self.draft), expected_hash, confirm, restoring=True, revision=revision, session=session)

    def changed(self):
        self.revision += 1
        self.notify()

    @property
    def can_apply(self):
        return bool(self.allow_writes() and self.mapping_valid and self.current_state == "read"
                    and self.report.get("mapping_revision") == self.mapping.get("revision")
                    and self.report.get("canonical", {}).get("policy", {}).get("_mapping") == self.mapping
                    and self.report.get("status") in ("ready", "warnings")
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

    async def load(self, index, revision=None, session=None):
        async with self.lock:
            self.expect(revision, session)
            if type(index) is not int or index not in (0, 2):
                raise ValueError("profile_category")
            current = await self._fresh(index)
            self.draft = {"entries": normalized(current["entries"])}
            self.policy = {}
            self.profile_context = None
            self.invalidate()
            self.changed()
            return self.report

    async def check(self, draft, policy, fresh=False, revision=None, session=None, mapping_revision=None):
        async with self.lock:
            self.expect(revision, session, mapping_revision)
            if self.metadata is None:
                raise ValueError("Load the current pump program first")
            # Enforce bounds before retaining input. Malformed drafts get a report,
            # but cannot create unbounded manager/sensor/Store data.
            if not isinstance(draft, dict) or set(draft) != {"entries"} or not isinstance(draft["entries"], list) or len(draft["entries"]) != 7 or any(not isinstance(day, list) or len(day) > 96 for day in draft["entries"]) or len(json.dumps(draft)) > 65536:
                raise ValueError("draft_shape")
            self.draft, self.policy = deepcopy(draft), deepcopy(policy)
            self.invalidate()
            if fresh:
                await self._fresh(self.metadata["index"])
            self.report = self._checked(draft, policy)
            self.ack_hash, self.ack_ids = None, set()
            self.changed()
            return self.report

    async def acknowledge(self, expected_hash, warning_ids, revision=None, session=None):
        async with self.lock:
            self.expect(revision, session)
            if not expected_hash or self.report.get("status") not in ("ready", "warnings") or self.report.get("critical_count") or self.report.get("draft_hash") != expected_hash or set(warning_ids) != set(self.report.get("warning_ids", [])):
                raise ValueError("Validate the current draft and acknowledge exactly its warning IDs")
            self.ack_hash, self.ack_ids = expected_hash, set(warning_ids)
            self.changed()

    async def apply(self, draft, expected_hash, confirm, restoring=False, revision=None, session=None):
        async with self.lock:
            self.expect(revision, session)
            if restoring and (not self.previous_program or not draft or self.metadata is None
                              or normalized(draft["entries"]) != normalized(self.previous_program["entries"])
                              or self.metadata != {k: self.previous_program[k] for k in self.metadata}):
                raise ValueError("Check and acknowledge the previous program as the current draft first")
            if confirm is not True or not self.can_apply:
                raise ValueError("Apply requires confirmation, Allow writes, valid check and warning acknowledgements")
            checked = validate(draft, self.metadata, self.report["canonical"]["policy"])
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
                        self.current_program = None
                        self.current_state = "conflict"
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
                    for d, day in enumerate(checked["canonical"]["entries"]):
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
                    if not self.allow_writes() or not self.can_apply:
                        raise ValueError("Write permission was revoked")
                    self.report["status"] = "applying"
                    self.changed()
                    writing = True
                    self.current_program = None
                    self.current_state = "unknown"
                    await c.heatpump.set_time_prog_async(self.program_factory(payload))
                    actual = (await c.heatpump.get_time_prog_async(self.metadata["index"], with_entries=True)).as_json()
                    if normalized(actual["entries"]) != normalized(draft["entries"]):
                        raise RuntimeError("Independent read-back differs; controller may be partially changed")
                    if {k: actual[k] for k in META_KEYS} != self.metadata:
                        raise RuntimeError("Independent read-back metadata differs")
                    self._accept_current(actual)
                    self.report["status"] = "applied"
                    self.actual_program = actual
                    await self._save_recovery(False)
                except (Exception, asyncio.CancelledError) as err:
                    # A diagnostic recovery read is not successful verification.
                    if writing:
                        self.current_program = None
                        self.current_state = "unknown"
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
