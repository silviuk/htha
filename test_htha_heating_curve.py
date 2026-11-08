"""Offline curve analysis, availability, platform registration and localization."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntityDescription

from custom_components.htha.heating_curve import POINTS, evaluate_curve, interpolate
from custom_components.htha.sensor import HtHAHeatingCurveSensor, async_setup_entry as setup_sensor
from custom_components.htha.binary_sensor import HtHAHeatingCurveProblem, async_setup_entry as setup_binary
from custom_components.htha.config_flow import HtHAOptionsFlow


def data(values=(22, 27, 30), outdoor=9):
    return {**{point[1]: value for point, value in zip(POINTS, values)}, "Temp. Aussen": outdoor}


@pytest.mark.parametrize("values,state", [
    ((22, 27, 30), "factory"), ((24, 27, 30), "differs_from_factory"),
    ((20, 25, 28), "differs_from_factory"), ((27, 32, 35), "differs_from_factory"),
    ((27.01, 32, 35), "check_recommended"), ((22, 32.01, 35), "check_recommended"),
    ((22, 27, 35.01), "check_recommended"), ((28, 27, 30), "check_recommended"),
    ((22, 31, 30), "check_recommended"), ((27, 27, 30), "differs_from_factory"),
])
def test_states_and_strict_thresholds(values, state):
    result, attrs = evaluate_curve(data(values))
    assert result == state
    assert attrs["monotonic"] == (values[0] <= values[1] <= values[2])
    assert bool(attrs["reasons"]) == (state == "check_recommended")
    assert attrs["explanation"]
    for point, value in zip(POINTS, values):
        assert attrs[f"{point[0]}_point"]["delta_k"] == pytest.approx(value - point[3])


@pytest.mark.parametrize("missing", [None, "unknown", "unavailable", "", "bad", float('nan'), float('inf'), True])
@pytest.mark.parametrize("point", range(3))
def test_any_invalid_point_is_unavailable(point, missing):
    values = [22, 27, 30]
    values[point] = missing
    assert evaluate_curve(data(values)) is None


@pytest.mark.parametrize("outdoor,expected", [(40,22), (18,22), (9,24.5), (0,27), (-7.5,28.5), (-15,30), (-40,30)])
def test_linear_interpolation_and_clamping(outdoor, expected):
    assert interpolate([22,27,30], outdoor) == expected
    _, attrs = evaluate_curve(data((24,29,32), outdoor))
    assert attrs["factory_return_setpoint"] == expected
    assert attrs["interpolated_return_setpoint"] == expected + 2
    assert attrs["interpolated_delta_k"] == 2


@pytest.mark.parametrize("outdoor", [None, "unknown", "unavailable", float('nan')])
def test_outdoor_optional(outdoor):
    state, attrs = evaluate_curve(data(outdoor=outdoor))
    assert state == "factory"
    assert "outdoor_temperature" not in attrs
    assert "interpolated_return_setpoint" not in attrs


def test_restart_missing_keys_and_reference_override():
    assert evaluate_curve(None) is None
    assert evaluate_curve({}) is None
    assert evaluate_curve({POINTS[0][1]: 22}) is None
    options = dict(curve_reference_upper=24, curve_reference_zero=29, curve_reference_lower=32)
    state, attrs = evaluate_curve(data((24,29,32)), options)
    assert state == "factory"
    assert not attrs["reference_is_factory"]
    assert attrs["upper_point"]["reference_delta_k"] == 0
    assert attrs["upper_point"]["delta_k"] == 2
    assert evaluate_curve(data((22,27,30)), options)[0] == "differs_from_factory"
    assert evaluate_curve(data((28,33,36)), dict(curve_reference_upper=28,
        curve_reference_zero=33, curve_reference_lower=36))[0] == "check_recommended"


def entities():
    coordinator = MagicMock(data=None, last_update_success=True, serial_number=None, sw_version=None,
                            host="offline.invalid", port=9999)
    entry = SimpleNamespace(entry_id="offline", options={}, runtime_data=coordinator)
    sensor = HtHAHeatingCurveSensor(coordinator, entry, SensorEntityDescription(key="heating_curve_check"))
    binary = HtHAHeatingCurveProblem(coordinator, entry, BinarySensorEntityDescription(key="heating_curve_problem"))
    return coordinator, entry, sensor, binary


def test_entities_never_report_ok_before_first_complete_data():
    coordinator, _, sensor, binary = entities()
    assert not sensor.available and not binary.available
    assert sensor.native_value is None and binary.is_on is None
    for readings, available, problem in [(data(), True, False), (data((28,27,30)), True, True),
                                          (data((None,27,30)), False, None), (data(), True, False)]:
        coordinator.data = readings
        assert sensor.available is available and binary.available is available
        assert binary.is_on is problem
    coordinator.last_update_success = False
    assert not sensor.available and not binary.available


@pytest.mark.asyncio
async def test_platforms_register_translated_enum_and_problem():
    _, entry, _, _ = entities()
    added = []
    # Empty selection intentionally leaves checks unavailable, without I/O.
    await setup_sensor(None, entry, added.extend)
    await setup_binary(None, entry, added.extend)
    sensor = next(e for e in added if isinstance(e, HtHAHeatingCurveSensor))
    binary = next(e for e in added if isinstance(e, HtHAHeatingCurveProblem))
    assert sensor.entity_description.device_class == SensorDeviceClass.ENUM
    assert sensor.entity_description.options == ["factory", "differs_from_factory", "check_recommended"]
    assert binary.entity_description.device_class == BinarySensorDeviceClass.PROBLEM
    assert sensor.unique_id == "offline_heating_curve_check"
    assert binary.unique_id == "offline_heating_curve_problem"


@pytest.mark.parametrize("language", ["en", "de"])
def test_translations(language):
    root = Path(__file__).parent / "custom_components/htha"
    translated = json.loads((root / f"translations/{language}.json").read_text(encoding="utf-8"))
    entity = translated["entity"]
    assert set(entity["sensor"]["heating_curve_check"]["state"]) == {
        "factory", "differs_from_factory", "check_recommended"}
    assert entity["binary_sensor"]["heating_curve_problem"]["name"]
    for key, temperature in zip(("hkr_rlt_soll_ohg", "hkr_rlt_soll_0", "hkr_rlt_soll_uhg"), ("+18", "0", "-15")):
        for platform in ("sensor", "number"):
            name = entity[platform][key]["name"]
            assert temperature in name
            assert ("Rücklauf" if language == "de" else "Return") in name
    for key in ("upper", "zero", "lower"):
        assert translated["options"]["step"]["init"]["data"][f"curve_reference_{key}"]


@pytest.mark.asyncio
async def test_reference_options_defaults_ranges_and_save():
    import voluptuous as vol

    entry = SimpleNamespace(options={}, data={})
    flow = HtHAOptionsFlow(entry)
    flow.async_show_form = MagicMock(side_effect=lambda **kwargs: kwargs)
    form = await flow.async_step_init()
    schema = form["data_schema"]
    defaults = schema({"scan_interval": 600})
    assert [defaults[f"curve_reference_{key}"] for key in ("upper", "zero", "lower")] == [22, 27, 30]
    for key, minimum, maximum in (("upper",15,40), ("zero",20,50), ("lower",25,60)):
        assert schema({"scan_interval":600, f"curve_reference_{key}":maximum})[f"curve_reference_{key}"] == maximum
        for invalid in (minimum - 1, maximum + 1, "unavailable"):
            with pytest.raises(vol.Invalid):
                schema({"scan_interval":600, f"curve_reference_{key}":invalid})
    flow.async_create_entry = MagicMock(side_effect=lambda **kwargs: kwargs)
    saved = await flow.async_step_init(schema({"scan_interval":600,
        "curve_reference_upper":25, "curve_reference_zero":32, "curve_reference_lower":40}))
    assert [saved["data"][f"curve_reference_{key}"] for key in ("upper", "zero", "lower")] == [25, 32, 40]
