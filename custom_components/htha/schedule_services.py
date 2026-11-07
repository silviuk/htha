"""Admin-only scratchpad services. Registration never enables pump writes."""
from copy import deepcopy

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
from .schedule_safety import Scratchpad

SERVICES = ("load_time_program_draft", "validate_time_program", "acknowledge_time_program_warnings", "apply_time_program", "refresh_time_program_baseline", "restore_previous_time_program")


def snapshot(manager):
    return {**deepcopy(manager.report), "draft": deepcopy(manager.draft),
            "metadata": deepcopy(manager.metadata), "policy": deepcopy(manager.policy),
            "warnings_acknowledged": manager.ack_hash == manager.report.get("draft_hash") and manager.ack_hash is not None,
            "can_apply": manager.can_apply, "writes_enabled": manager.allow_writes(), "revision": manager.revision, "session_id": manager.session_id,
            "previous_program": deepcopy(manager.previous_program), "actual_program": deepcopy(manager.actual_program)}


async def setup_scratchpad(hass, entry, coordinator):
    """Keep drafts outside the reload lifecycle; persist only recovery evidence."""
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
        manager = Scratchpad(coordinator, lambda: bool(entry.data.get(CONF_WRITE_ENABLED, False)),
                             TimeProgram.from_json, coordinator.async_update_listeners, recovery)
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
    schemas = {
        "load_time_program_draft": vol.Schema({**base, vol.Required("program_index"): vol.All(vol.Coerce(int), vol.In((0, 2)))}),
        "validate_time_program": vol.Schema({**base, vol.Required("draft"): dict, vol.Required("policy"): vol.Schema({
            vol.Required("kind"): vol.In(("heating", "hot_water")),
            vol.Required("normal_state"): vol.All(int, vol.Range(min=0, max=2)),
            vol.Required("mapping_confirmed"): bool,
            vol.Optional("floor_heating", default=True): bool,
        })}),
        "acknowledge_time_program_warnings": vol.Schema({**base, vol.Required("draft_hash"): cv.string, vol.Required("warning_ids"): [cv.string]}),
        "apply_time_program": vol.Schema({**base, vol.Required("draft_hash"): cv.string, vol.Required("draft"): dict, vol.Required("confirm"): bool}),
        "refresh_time_program_baseline": vol.Schema(base),
        "restore_previous_time_program": vol.Schema({**base, vol.Required("draft_hash"): cv.string, vol.Required("confirm"): bool}),
    }

    async def handle(call):
        data = call.data
        entry = hass.config_entries.async_get_entry(data["config_entry_id"])
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_not_loaded")
        target = entry.runtime_data.schedule_scratchpad
        try:
            if call.service == "load_time_program_draft":
                await target.load(data["program_index"])
            elif call.service == "validate_time_program":
                await target.check(data["draft"], data["policy"])
            elif call.service == "acknowledge_time_program_warnings":
                await target.acknowledge(data["draft_hash"], data["warning_ids"])
            elif call.service == "refresh_time_program_baseline":
                await target.refresh_baseline()
            elif call.service == "restore_previous_time_program":
                await target.restore(data["draft_hash"], data["confirm"])
            else:
                await target.apply(data["draft"], data["draft_hash"], data["confirm"])
        except ValueError as err:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="schedule_gate",
                                         translation_placeholders={"reason": str(err)}) from err
        except Exception as err:
            raise HomeAssistantError(str(err)) from err
        return snapshot(target)

    for service in SERVICES:
        if not hass.services.has_service(DOMAIN, service):
            async_register_admin_service(hass, DOMAIN, service, handle,
                                         schema=schemas[service], supports_response=SupportsResponse.OPTIONAL)
