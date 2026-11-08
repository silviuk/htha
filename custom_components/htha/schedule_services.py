"""Admin-only scratchpad services. Registration never enables pump writes."""
from copy import deepcopy
import asyncio
import json

import voluptuous as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.storage import Store
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from htheatpump.httimeprog import TimeProgram

from .const import DOMAIN, CONF_WRITE_ENABLED
from .schedule_safety import Scratchpad, ProfileLibrary, normalized, bounded_draft, FACTORY_PRESETS

SERVICES = ("load_time_program_draft", "validate_time_program", "acknowledge_time_program_warnings", "apply_time_program", "refresh_time_program_baseline", "restore_previous_time_program",
            "get_time_program_editor", "list_time_program_profiles", "save_time_program_profile", "rename_time_program_profile", "delete_time_program_profile", "load_time_program_profile", "set_time_program_mode_mapping")


def snapshot(manager):
    missing = []
    if not manager.allow_writes():
        missing.append("writes_off")
    if manager.current_state != "read":
        missing.append("baseline_unavailable")
    if manager.report.get("status") not in ("ready", "warnings"):
        missing.append("validation_required")
    if manager.report.get("critical_count"):
        missing.append("critical_findings")
    if not manager.mapping_valid:
        missing.append("complete_mapping")
    for finding in manager.report.get("findings", []):
        code = finding["id"].split(":")[0]
        if code in ("complete_mapping", "profile_incompatible", "normal_mapping_conflict", "mode_mapping", "factory_mapping") and code not in missing:
            missing.append(code)
    if manager.report.get("warning_ids") and manager.ack_hash != manager.report.get("draft_hash"):
        missing.append("warnings_required")
    library = manager.library
    matches = [p for p in library.data["profiles"] if manager.metadata and p["program_index"] == manager.metadata["index"] and manager.current_program and p["draft"]["entries"] == normalized(manager.current_program["entries"])] if library else []
    return {**deepcopy(manager.report), "draft": deepcopy(manager.draft),
            "metadata": deepcopy(manager.metadata), "policy": deepcopy(manager.policy),
            "warnings_acknowledged": manager.ack_hash == manager.report.get("draft_hash") and manager.ack_hash is not None,
            "can_apply": manager.can_apply, "writes_enabled": manager.allow_writes(), "revision": manager.revision, "session_id": manager.session_id,
            "previous_program": deepcopy(manager.previous_program), "actual_program": deepcopy(manager.actual_program),
            "current_program": deepcopy(manager.current_program), "current_state": manager.current_state,
            "baseline_read_at": manager.baseline_read_at, "baseline_hash": manager.baseline_hash,
            "mode_catalog": manager.catalog, "mode_mapping": manager.mapping,
            "mapping_revision": manager.mapping.get("revision", 0), "mapping_valid": manager.mapping_valid,
            "controller": manager.controller_identity, "missing_gates": missing,
            "current_profile_names": [p["name"] for p in matches],
            "profile_context": {k: manager.profile_context[k] for k in ("id", "name", "revision", "read_only", "mode_name", "source", "source_pages") if k in manager.profile_context} if manager.profile_context else None,
            "library_error": library.error if library else None}


async def setup_scratchpad(hass, entry, coordinator):
    """Serialize setup, including awaited Store loads, to guarantee one manager."""
    lock = hass.data.setdefault(DOMAIN, {}).setdefault("scratchpad_setup_lock", asyncio.Lock())
    async with lock:
        await _setup_scratchpad(hass, entry, coordinator)


async def _setup_scratchpad(hass, entry, coordinator):
    """Keep drafts on reload; profiles/mappings and recovery use separate Stores."""
    managers = hass.data.setdefault(DOMAIN, {}).setdefault("scratchpads", {})
    store = Store(hass, 1, f"{DOMAIN}_schedule_recovery_{entry.entry_id}")

    async def recovery(record):
        await store.async_save(record)
        if record["in_progress"]:
            ir.async_create_issue(hass, DOMAIN, f"schedule_recovery_{entry.entry_id}",
                                  is_fixable=False, severity=ir.IssueSeverity.ERROR,
                                  translation_key="schedule_recovery",
                                  translation_placeholders={"entry": entry.title})
        else:
            ir.async_delete_issue(hass, DOMAIN, f"schedule_recovery_{entry.entry_id}")

    manager = managers.get(entry.entry_id)
    if manager is None:
        profile_store = Store(hass, 1, f"{DOMAIN}_schedule_profiles_{entry.entry_id}")
        async def read_profiles():
            return await Store(hass, 1, f"{DOMAIN}_schedule_profiles_{entry.entry_id}").async_load()

        library = ProfileLibrary(profile_store.async_save, read_profiles)
        try:
            library.load(await profile_store.async_load())
        except Exception:  # corrupt JSON / unsupported HA Store version
            library.error = "library_corrupt"
        if library.error:
            ir.async_create_issue(hass, DOMAIN, f"schedule_profiles_{entry.entry_id}",
                                  is_fixable=False, severity=ir.IssueSeverity.ERROR,
                                  translation_key="schedule_profiles", translation_placeholders={"entry": entry.title})
        manager = Scratchpad(coordinator, lambda: bool(entry.data.get(CONF_WRITE_ENABLED, False)),
                             TimeProgram.from_json, coordinator.async_update_listeners, recovery, library)
        record = await store.async_load()
        if record:
            manager.previous_program = record.get("previous_program")
            manager.actual_program = record.get("actual_program")
            if record.get("in_progress"):
                manager.report.update(status="failed", possible_partial_write=True,
                                      apply_error="Previous apply was interrupted or failed; inspect recovery evidence")
                await recovery(record)
        managers[entry.entry_id] = manager
    else:
        async with manager.lock:
            manager.coordinator = coordinator
            manager.allow_writes = lambda: bool(entry.data.get(CONF_WRITE_ENABLED, False))
            manager.notify = coordinator.async_update_listeners
            manager.recovery = recovery
            manager.changed()
    coordinator.schedule_scratchpad = manager
    hass.data[DOMAIN][entry.entry_id]["scratchpad"] = manager


def register_services(hass):
    """Register services once at integration setup, independent of config entries."""
    base = {vol.Required("config_entry_id"): cv.string}
    def integer(value):
        if type(value) is not int:
            raise vol.Invalid("Expected integer, not bool/string")
        return value
    def legacy_index(value):
        if type(value) is bool or value not in (0, 2, "0", "2"):
            raise vol.Invalid("Expected program index 0 or 2")
        return int(value)
    revision = {vol.Optional("expected_draft_revision"): integer, vol.Optional("session_id"): cv.string}
    category = vol.In(("heating", "hot_water"))
    profile = {vol.Required("profile_id"): vol.All(cv.string, vol.Length(max=80))}
    expected = {vol.Required("expected_profile_revision"): integer}
    profile_name = vol.All(cv.string, vol.Length(min=1, max=80))
    schemas = {
        "load_time_program_draft": vol.Schema({**base, **revision, vol.Required("program_index"): legacy_index}),
        "validate_time_program": vol.Schema({**base, **revision, vol.Optional("fresh_read", default=False): bool,
            vol.Optional("expected_mapping_revision"): integer, vol.Required("draft"): dict, vol.Required("policy"): vol.Schema({
            vol.Required("kind"): vol.In(("heating", "hot_water")),
            vol.Required("normal_state"): vol.All(integer, vol.Range(min=0, max=2)),
            vol.Required("mapping_confirmed"): bool,
            vol.Optional("floor_heating", default=True): bool,
        })}),
        "acknowledge_time_program_warnings": vol.Schema({**base, **revision, vol.Required("draft_hash"): cv.string, vol.Required("warning_ids"): [cv.string]}),
        "apply_time_program": vol.Schema({**base, **revision, vol.Required("draft_hash"): cv.string, vol.Required("draft"): dict, vol.Required("confirm"): bool}),
        "refresh_time_program_baseline": vol.Schema({**base, **revision}),
        "restore_previous_time_program": vol.Schema({**base, **revision, vol.Required("draft_hash"): cv.string, vol.Required("confirm"): bool}),
        "get_time_program_editor": vol.Schema({**base, vol.Required("program_index"): vol.All(integer, vol.In((0, 2)))}),
        "list_time_program_profiles": vol.Schema({**base, vol.Required("category"): category}),
        "save_time_program_profile": vol.Schema({**base, **revision, vol.Required("category"): category, vol.Required("name"): profile_name,
            vol.Required("draft"): dict, vol.Optional("profile_id"): cv.string, vol.Optional("expected_profile_revision"): integer,
            vol.Optional("description", default=""): vol.All(cv.string, vol.Length(max=1000))}),
        "rename_time_program_profile": vol.Schema({**base, **profile, **expected, vol.Required("name"): profile_name}),
        "delete_time_program_profile": vol.Schema({**base, **profile, **expected, vol.Required("confirm"): bool}),
        "load_time_program_profile": vol.Schema({**base, **profile, vol.Required("expected_draft_revision"): integer,
            vol.Required("session_id"): cv.string, vol.Optional("read_only", default=False): bool}),
        "set_time_program_mode_mapping": vol.Schema({**base, **revision, vol.Required("program_index"): vol.All(integer, vol.In((0, 2))),
            vol.Required("mapping"): dict, vol.Required("expected_mapping_revision"): integer, vol.Required("confirmed"): bool}),
    }

    async def handle(call):
        data = call.data
        entry = hass.config_entries.async_get_entry(data["config_entry_id"])
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_not_loaded")
        target = entry.runtime_data.schedule_scratchpad
        try:
            if len(json.dumps(dict(data))) > 70000:
                raise ValueError("payload_too_large")
            rev, session = data.get("expected_draft_revision"), data.get("session_id")
            if call.service == "load_time_program_draft":
                await target.load(data["program_index"], rev, session)
            elif call.service == "validate_time_program":
                await target.check(data["draft"], data["policy"], data["fresh_read"], rev, session, data.get("expected_mapping_revision"))
            elif call.service == "acknowledge_time_program_warnings":
                await target.acknowledge(data["draft_hash"], data["warning_ids"], rev, session)
            elif call.service == "refresh_time_program_baseline":
                await target.refresh_baseline(rev, session)
            elif call.service == "restore_previous_time_program":
                await target.restore(data["draft_hash"], data["confirm"], rev, session)
            elif call.service == "apply_time_program":
                await target.apply(data["draft"], data["draft_hash"], data["confirm"], revision=rev, session=session)
            elif call.service == "set_time_program_mode_mapping":
                await target.set_mapping(data["mapping"], data["expected_mapping_revision"], data["confirmed"], data["program_index"], rev, session)
            else:
                # All library and snapshot transitions use the SAME manager lock.
                async with target.lock:
                    target.expect(rev, session)
                    library = target.library
                    if call.service == "list_time_program_profiles":
                        return library.listing(data["category"])
                    if call.service == "get_time_program_editor":
                        return {**snapshot(target), **library.listing({0: "hot_water", 2: "heating"}[data["program_index"]]), "requested_program_index": data["program_index"]}
                    if call.service == "save_time_program_profile":
                        if target.metadata is None:
                            raise ValueError("baseline_unavailable")
                        try:
                            active_draft = bounded_draft(target.draft)
                        except (ValueError, KeyError, TypeError):
                            active_draft = None
                        old_profile = library.get(data["profile_id"]) if data.get("profile_id") else None
                        saved = await library.save_profile(data["category"], data["name"], data["draft"], target.metadata,
                            target.controller_identity, target.mapping, data.get("profile_id"), data.get("expected_profile_revision"), data["description"])
                        if saved["draft"] != active_draft:
                            target.draft = deepcopy(saved["draft"])
                            target.invalidate()
                        if old_profile and old_profile["draft"] != saved["draft"]:
                            target.invalidate()
                        if target.profile_context and target.profile_context["id"] in FACTORY_PRESETS:
                            target.profile_context = deepcopy(saved)
                        elif target.profile_context and target.profile_context["id"] == saved["id"]:
                            if target.profile_context["mapping_fingerprint"] != saved["mapping_fingerprint"] or target.profile_context["compatibility"] != saved["compatibility"]:
                                target.invalidate()
                            target.profile_context = deepcopy(saved)
                        target.changed()
                        return {**snapshot(target), **library.listing(data["category"]), "saved_profile": saved}
                    if call.service == "rename_time_program_profile":
                        saved = await library.rename(data["profile_id"], data["name"], data["expected_profile_revision"])
                        if target.profile_context and target.profile_context["id"] == saved["id"]:
                            target.profile_context = deepcopy(saved)
                        target.changed()
                        return {**snapshot(target), **library.listing(saved["category"]), "saved_profile": saved}
                    if call.service == "delete_time_program_profile":
                        listing = await library.delete(data["profile_id"], data["expected_profile_revision"], data["confirm"])
                        # Keep an active immutable draft/provenance after deletion.
                        target.changed()
                        return {**snapshot(target), **listing}
                    if call.service == "load_time_program_profile":
                        builtin = data["profile_id"] in FACTORY_PRESETS
                        p = target.factory_profile(data["profile_id"]) if builtin else library.get(data["profile_id"])
                        if not data["read_only"] and (target.metadata != p["compatibility"] or target.current_state != "read"):
                            raise ValueError("profile_incompatible")
                        if data["read_only"] and (target.metadata != p["compatibility"] or target.current_state != "read"):
                            target.metadata = deepcopy(p["compatibility"])
                            target.current_program, target.baseline_hash, target.baseline_read_at = None, None, None
                            target.current_state = "unknown"
                        target.draft = deepcopy(p["draft"])
                        target.profile_context = deepcopy(p)
                        target.policy = {}
                        target.invalidate()
                        target.changed()
        except ValueError as err:
            key = str(err)
            known = {"editor_conflict", "mapping_conflict", "mapping_invalid", "profile_conflict", "profile_incompatible", "profile_missing", "profile_category", "profile_duplicate", "profile_limit", "profile_name", "profile_description", "profile_read_only", "draft_shape", "payload_too_large", "library_corrupt", "baseline_unavailable"}
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key=key if key in known else "schedule_gate",
                                         translation_placeholders={} if key in known else {"reason": key}) from err
        except Exception as err:
            raise HomeAssistantError(str(err)) from err
        return snapshot(target)

    for service in SERVICES:
        if not hass.services.has_service(DOMAIN, service):
            async_register_admin_service(hass, DOMAIN, service, handle,
                                         schema=schemas[service], supports_response=SupportsResponse.OPTIONAL)
