"""Tests for entity naming, derived sensors and the bundled dashboard strategy."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory

from custom_components.htha import (
    DATA_FRONTEND_REGISTERED,
    async_register_frontend,
    async_remove_entry,
)
from custom_components.htha import lovelace_resource
from custom_components.htha.const import (
    FRONTEND_SCRIPT,
    SCHEDULE_FRONTEND_SCRIPT,
    FRONTEND_URL_BASE,
    OPERATING_STATES,
    PARAM_NUMBER_METADATA,
    PARAM_SELECT_METADATA,
    PARAM_TRANSLATION_KEYS,
)
from custom_components.htha.sensor import (
    HtHATemperatureSpreadSensor,
    HtHAScheduleValidationSensor,
    build_param_sensor_description,
    compute_operating_state,
)

COMPONENT = Path(__file__).parent / "custom_components" / "htha"
PLATFORM_FILES = [
    "sensor", "binary_sensor", "number", "select", "switch", "datetime", "button",
]


def _load(name: str) -> dict:
    return json.loads((COMPONENT / name).read_text(encoding="utf-8"))


def _used_keys() -> dict[str, set[str]]:
    """translation_keys per platform: mapped params + literal keys in code."""
    used: dict[str, set[str]] = {p: set() for p in PLATFORM_FILES}
    from htheatpump import HtParams
    from htheatpump.htparams import HtDataTypes

    for param, key in PARAM_TRANSLATION_KEYS.items():
        if param in PARAM_NUMBER_METADATA:
            used["number"].add(key)
        if param in PARAM_SELECT_METADATA:
            used["select"].add(key)
        if param in HtParams and HtParams[param].data_type == HtDataTypes.BOOL:
            used["binary_sensor"].add(key)
        elif param in HtParams:
            used["sensor"].add(key)
    used["sensor"] |= {"time_programs", "operating_state",
                       "heating_circuit_spread", "heat_source_spread"}
    for platform in ("switch", "datetime", "button"):
        src = (COMPONENT / f"{platform}.py").read_text(encoding="utf-8")
        used[platform] |= set(re.findall(r'translation_key="([a-z0-9_]+)"', src))
    return used


@pytest.mark.parametrize("lang", ["en", "de"])
def test_every_translation_key_has_a_name(lang):
    entity = _load(f"translations/{lang}.json")["entity"]
    for platform, keys in _used_keys().items():
        for key in keys:
            assert key in entity.get(platform, {}), f"{lang}: {platform}.{key} missing"
            assert entity[platform][key]["name"], f"{lang}: {platform}.{key} empty"


def test_translations_keep_config_and_options():
    for lang in ("en", "de"):
        data = _load(f"translations/{lang}.json")
        assert "config" in data and "options" in data


def test_names_are_unique_per_platform():
    entity = _load("translations/en.json")["entity"]
    for platform, items in entity.items():
        names = [v["name"] for v in items.values()]
        assert len(names) == len(set(names)), platform


def test_icons_cover_translation_keys():
    icons = _load("icons.json")["entity"]
    for platform, keys in _used_keys().items():
        for key in keys:
            assert "default" in icons.get(platform, {}).get(key, {}), f"{platform}.{key}"


def test_operating_state_translations():
    for lang in ("en", "de"):
        states = _load(f"translations/{lang}.json")["entity"]["sensor"][
            "operating_state"]["state"]
        assert set(states) == set(OPERATING_STATES)


def test_mirror_sensor_is_diagnostic_disabled_with_unit():
    desc = build_param_sensor_description("HKR Soll_Raum")
    assert desc.translation_key == "hkr_soll_raum"
    assert desc.entity_category == EntityCategory.DIAGNOSTIC
    assert desc.entity_registry_enabled_default is False
    assert desc.native_unit_of_measurement == "°C"
    assert desc.device_class == SensorDeviceClass.TEMPERATURE


def test_regular_sensor_description():
    desc = build_param_sensor_description("Temp. Vorlauf")
    assert desc.entity_registry_enabled_default is True
    assert desc.entity_category is None
    assert desc.state_class == SensorStateClass.MEASUREMENT
    assert desc.suggested_display_precision == 1
    assert desc.icon is None


def test_counter_sensor_is_diagnostic():
    desc = build_param_sensor_description("BSZ Verdichter Schaltungen")
    assert desc.entity_category == EntityCategory.DIAGNOSTIC
    assert desc.entity_registry_enabled_default is True


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (None, None),
        ({}, None),
        ({"Verdichter": False, "Stoerung": True}, "fault"),
        ({"Verdichter": False, "Hauptschalter": False}, "off"),
        ({"Verdichter": False, "Betriebsart": 0}, "off"),
        ({"Verdichter": True, "Warmwasservorrang": True, "Betriebsart": 1}, "hot_water"),
        ({"Verdichter": True, "Betriebsart": 2}, "cooling"),
        ({"Verdichter": True, "Betriebsart": 1}, "heating"),
        ({"Verdichter": False, "Betriebsart": 1, "Hauptschalter": True}, "standby"),
    ],
)
def test_compute_operating_state(data, expected):
    result = compute_operating_state(data)
    assert result == expected
    assert result is None or result in OPERATING_STATES


def test_spread_sensor_value():
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {"Temp. Vorlauf": 35.4, "Temp. Ruecklauf": 30.1}
    entry = MagicMock(entry_id="abc")
    sensor = HtHATemperatureSpreadSensor(
        coordinator, entry, MagicMock(key="heating_circuit_spread"),
        "Temp. Vorlauf", "Temp. Ruecklauf",
    )
    assert sensor.unique_id == "abc_heating_circuit_spread"
    assert sensor.available
    assert sensor.native_value == pytest.approx(5.3)
    coordinator.data = {"Temp. Vorlauf": 35.4}
    assert not sensor.available
    assert sensor.native_value is None


async def test_frontend_registration_is_idempotent():
    hass = MagicMock()
    hass.data = {}
    hass.config.components = {"frontend", "http"}
    hass.http.async_register_static_paths = AsyncMock()
    integration = MagicMock(version="9.9.9")
    with patch(
        "homeassistant.loader.async_get_integration",
        AsyncMock(return_value=integration),
    ), patch("homeassistant.components.frontend.add_extra_js_url") as add_js, patch(
        "custom_components.htha.async_ensure_resource", new_callable=AsyncMock,
    ) as ensure_resource:
        await async_register_frontend(hass)
        await async_register_frontend(hass)
        assert ensure_resource.await_count == 2
        for script in (FRONTEND_SCRIPT, SCHEDULE_FRONTEND_SCRIPT):
            ensure_resource.assert_any_await(hass, "9.9.9", script)
    hass.http.async_register_static_paths.assert_awaited_once()
    (config,) = hass.http.async_register_static_paths.await_args.args[0]
    assert config.url_path == FRONTEND_URL_BASE
    assert Path(config.path, FRONTEND_SCRIPT).is_file()
    assert add_js.call_count == 2
    for script in (FRONTEND_SCRIPT, SCHEDULE_FRONTEND_SCRIPT):
        add_js.assert_any_call(hass, f"{FRONTEND_URL_BASE}/{script}?v=9.9.9")
        assert Path(config.path, script).is_file()
    assert hass.data[DATA_FRONTEND_REGISTERED] is True


async def test_frontend_registration_without_http():
    hass = MagicMock()
    hass.data = {}
    hass.http = None
    await async_register_frontend(hass)
    assert DATA_FRONTEND_REGISTERED not in hass.data


async def test_frontend_registration_without_frontend():
    hass = MagicMock()
    hass.data = {}
    hass.config.components = {"http"}
    hass.http.async_register_static_paths = AsyncMock()
    await async_register_frontend(hass)
    hass.http.async_register_static_paths.assert_not_awaited()


def test_strategy_roles_exist_in_translations():
    js = (COMPONENT / "frontend" / FRONTEND_SCRIPT).read_text(encoding="utf-8")
    entity = _load("translations/en.json")["entity"]
    roles = re.findall(
        r'"((?:sensor|binary_sensor|number|select|switch|datetime|button)\.[a-z0-9_]+)"', js)
    assert roles
    for role in roles:
        platform, key = role.split(".")
        assert key in entity[platform], role


class _FakeResources:
    """Minimal stand-in for lovelace's ResourceStorageCollection."""

    def __init__(self, items=None):
        self.loaded = False
        self.items = list(items or [])
        self.async_load = AsyncMock(side_effect=self._load)
        self._n = 0

    async def _load(self):
        self.loaded = True

    def async_items(self):
        return [dict(i) for i in self.items]

    async def async_create_item(self, data):
        self._n += 1
        item = {"id": f"new{self._n}", "type": data["res_type"], "url": data["url"]}
        self.items.append(item)
        return item

    async def async_update_item(self, item_id, updates):
        for item in self.items:
            if item["id"] == item_id:
                item.update(type=updates["res_type"], url=updates["url"])
                return item
        raise KeyError(item_id)

    async def async_delete_item(self, item_id):
        self.items = [i for i in self.items if i["id"] != item_id]


def _resource_hass(resources):
    hass = MagicMock()
    hass.config.components = {"frontend", "http", "lovelace"}
    hass.data = {"lovelace": MagicMock(resources=resources)}
    return hass


def _fake_store(data=None):
    store = MagicMock()
    store.async_load = AsyncMock(return_value=data)
    store.async_save = AsyncMock()
    store.async_remove = AsyncMock()
    return store


@pytest.mark.parametrize("script", [FRONTEND_SCRIPT, SCHEDULE_FRONTEND_SCRIPT])
async def test_lovelace_resource_created_once_and_versioned(script):
    other = {"id": "x", "type": "module", "url": "/hacsfiles/iconset.js"}
    resources = _FakeResources([other])
    hass = _resource_hass(resources)
    store = _fake_store()
    with patch.object(lovelace_resource, "_store", return_value=store):
        await lovelace_resource.async_ensure_resource(hass, "1.0.13", script)
        await lovelace_resource.async_ensure_resource(hass, "1.0.13", script)
    ours = [i for i in resources.items if i["id"] != "x"]
    assert ours == [{"id": "new1", "type": "module", "url": f"{FRONTEND_URL_BASE}/{script}?v=1.0.13"}]
    assert other in resources.items
    store.async_save.assert_awaited_once_with({"resource_id": "new1"})
    resources.async_load.assert_awaited_once()


@pytest.mark.parametrize("script", [FRONTEND_SCRIPT, SCHEDULE_FRONTEND_SCRIPT])
async def test_lovelace_resource_version_is_updated_not_duplicated(script):
    old = {"id": "r1", "type": "module", "url": f"{FRONTEND_URL_BASE}/{script}?v=1.0.12"}
    resources = _FakeResources([old])
    store = _fake_store()
    with patch.object(lovelace_resource, "_store", return_value=store):
        await lovelace_resource.async_ensure_resource(_resource_hass(resources), "1.0.13", script)
    assert resources.items == [{"id": "r1", "type": "module", "url": f"{FRONTEND_URL_BASE}/{script}?v=1.0.13"}]
    store.async_save.assert_not_awaited()


@pytest.mark.parametrize("script", [FRONTEND_SCRIPT, SCHEDULE_FRONTEND_SCRIPT])
async def test_lovelace_resource_skipped_in_yaml_mode(script):
    hass = _resource_hass(None)
    hass.data["lovelace"].resources = object()  # read-only YAML collection
    with patch.object(lovelace_resource, "_store") as store:
        await lovelace_resource.async_ensure_resource(hass, "1.0.13", script)
    store.assert_not_called()


@pytest.mark.parametrize("script", [FRONTEND_SCRIPT, SCHEDULE_FRONTEND_SCRIPT])
async def test_lovelace_resource_removed_only_if_ours(script):
    ours = {"id": "new1", "type": "module", "url": f"{FRONTEND_URL_BASE}/{script}?v=1.0.13"}
    resources = _FakeResources([ours])
    with patch.object(lovelace_resource, "_store", return_value=_fake_store(None)):
        await lovelace_resource.async_remove_resource(_resource_hass(resources), script)
    assert resources.items == [ours]  # not created by us -> kept
    store = _fake_store({"resource_id": "new1"})
    with patch.object(lovelace_resource, "_store", return_value=store):
        await lovelace_resource.async_remove_resource(_resource_hass(resources), script)
    assert resources.items == []
    store.async_remove.assert_awaited_once()


def test_strategy_registers_into_current_registry():
    js = (COMPONENT / "frontend" / FRONTEND_SCRIPT).read_text(encoding="utf-8")
    assert "window.customElements" in js and "setInterval" in js
    manifest = _load("manifest.json")
    assert f'HTHA_VERSION = "{manifest["version"]}"' in js


async def test_frontend_resources_have_independent_ownership_and_legacy_store():
    resources = _FakeResources()
    hass = _resource_hass(resources)
    stores = {}

    def store_factory(_hass, _version, key):
        if key not in stores:
            stores[key] = _fake_store()
            async def save(data):
                stores[key].async_load.return_value = data
            stores[key].async_save.side_effect = save
        return stores[key]

    with patch.object(lovelace_resource, "Store", side_effect=store_factory):
        for script in (FRONTEND_SCRIPT, SCHEDULE_FRONTEND_SCRIPT):
            await lovelace_resource.async_ensure_resource(hass, "1.3.0", script)
        assert len(resources.items) == 2
        assert lovelace_resource.STORE_KEY in stores  # preserve pre-upgrade ownership
        assert len(stores) == 2
        await lovelace_resource.async_remove_resource(hass)
        assert len(resources.items) == 1
        assert SCHEDULE_FRONTEND_SCRIPT in resources.items[0]["url"]
        await lovelace_resource.async_remove_resource(hass, SCHEDULE_FRONTEND_SCRIPT)
        assert resources.items == []


@pytest.mark.parametrize("script", [FRONTEND_SCRIPT, SCHEDULE_FRONTEND_SCRIPT])
async def test_resource_cleanup_keeps_repurposed_user_resource(script):
    other = {"id": "new1", "type": "module", "url": "/user-card.js"}
    resources = _FakeResources([other])
    with patch.object(lovelace_resource, "_store", return_value=_fake_store({"resource_id": "new1"})):
        await lovelace_resource.async_remove_resource(_resource_hass(resources), script)
    assert resources.items == [other]


@pytest.mark.parametrize("script", [FRONTEND_SCRIPT, SCHEDULE_FRONTEND_SCRIPT])
async def test_resource_registration_deferred_until_start(script):
    hass = _resource_hass(_FakeResources())
    hass.config.components = {"frontend", "http"}
    hass.is_running = False
    await lovelace_resource.async_ensure_resource(hass, "1.3.0", script)
    callback = hass.bus.async_listen_once.call_args.args[1]
    hass.config.components.add("lovelace")
    with patch.object(lovelace_resource, "_store", return_value=_fake_store()):
        await callback(MagicMock())
    assert hass.data["lovelace"].resources.items[0]["url"] == lovelace_resource.resource_url("1.3.0", script)


def test_schedule_validation_exposes_own_entry_for_frontend_discovery():
    coordinator = MagicMock()
    entry = MagicMock(entry_id="pump-entry")
    sensor = HtHAScheduleValidationSensor(coordinator, entry, MagicMock(key="schedule_validation"))
    with patch("custom_components.htha.schedule_services.snapshot", return_value={"status": "ready"}):
        assert sensor.extra_state_attributes == {"status": "ready", "config_entry_id": "pump-entry"}


@pytest.mark.parametrize("has_remaining", [False, True])
async def test_frontend_resources_removed_only_with_last_entry(has_remaining):
    hass = MagicMock()
    hass.data = {}
    entry = MagicMock(entry_id="removed")
    hass.config_entries.async_entries.return_value = (
        [entry, MagicMock(entry_id="remaining")] if has_remaining else [entry]
    )
    with patch("homeassistant.helpers.storage.Store", return_value=_fake_store()), patch(
        "custom_components.htha.async_remove_resource", new_callable=AsyncMock,
    ) as remove_resource:
        await async_remove_entry(hass, entry)
    if has_remaining:
        remove_resource.assert_not_awaited()
    else:
        assert remove_resource.await_count == 2
        for script in (FRONTEND_SCRIPT, SCHEDULE_FRONTEND_SCRIPT):
            remove_resource.assert_any_await(hass, script)
