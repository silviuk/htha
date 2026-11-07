"""Admin-only scratchpad services. Registration never enables pump writes."""
from copy import deepcopy

import voluptuous as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from htheatpump.httimeprog import TimeProgram

from .const import DOMAIN, CONF_WRITE_ENABLED
from .schedule_safety import Scratchpad

SERVICES = ("load_time_program_draft", "validate_time_program", "acknowledge_time_program_warnings", "apply_time_program")


def snapshot(manager):
    return {**deepcopy(manager.report), "draft": deepcopy(manager.draft),
            "metadata": deepcopy(manager.metadata), "policy": deepcopy(manager.policy),
            "warnings_acknowledged": manager.ack_hash == manager.report.get("draft_hash") and manager.ack_hash is not None,
            "can_apply": manager.can_apply, "revision": manager.revision}


def setup_scratchpad(hass, entry, coordinator):
    """Create per-entry isolated session and globally register guarded services once."""
    manager = Scratchpad(coordinator, lambda: bool(entry.data.get(CONF_WRITE_ENABLED, False)),
                         TimeProgram.from_json, coordinator.async_update_listeners)
    coordinator.schedule_scratchpad = manager
    hass.data[DOMAIN][entry.entry_id]["scratchpad"] = manager
    base = {vol.Required("config_entry_id"): cv.string}
    schemas = {
        "load_time_program_draft": vol.Schema({**base, vol.Required("program_index"): vol.In((0, 2))}),
        "validate_time_program": vol.Schema({**base, vol.Required("draft"): dict, vol.Required("policy"): vol.Schema({
            vol.Required("kind"): vol.In(("heating", "hot_water")),
            vol.Required("normal_state"): vol.All(int, vol.Range(min=0, max=2)),
            vol.Required("mapping_confirmed"): bool,
            vol.Optional("floor_heating", default=True): bool,
        })}),
        "acknowledge_time_program_warnings": vol.Schema({**base, vol.Required("draft_hash"): cv.string, vol.Required("warning_ids"): [cv.string]}),
        "apply_time_program": vol.Schema({**base, vol.Required("draft_hash"): cv.string, vol.Required("draft"): dict, vol.Required("confirm"): bool}),
    }

    async def handle(call):
        data = call.data
        target = hass.data.get(DOMAIN, {}).get(data["config_entry_id"], {}).get("scratchpad")
        if target is None:
            raise HomeAssistantError("HTHA entry is not loaded")
        try:
            if call.service == "load_time_program_draft":
                await target.load(data["program_index"])
            elif call.service == "validate_time_program":
                await target.check(data["draft"], data["policy"])
            elif call.service == "acknowledge_time_program_warnings":
                await target.acknowledge(data["draft_hash"], data["warning_ids"])
            else:
                await target.apply(data["draft"], data["draft_hash"], data["confirm"])
        except Exception as err:
            raise HomeAssistantError(str(err)) from err
        return snapshot(target)

    for service in SERVICES:
        if not hass.services.has_service(DOMAIN, service):
            async_register_admin_service(hass, DOMAIN, service, handle,
                                         schema=schemas[service], supports_response=SupportsResponse.OPTIONAL)
