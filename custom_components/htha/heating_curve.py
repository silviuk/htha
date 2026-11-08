"""Read-only heating curve analysis; no transport or Home Assistant dependencies."""

from math import isfinite

POINTS = (
    ("upper", "HKR RLT Soll_oHG (Heizkurve)", 18, 22.0),
    ("zero", "HKR RLT Soll_0 (Heizkurve)", 0, 27.0),
    ("lower", "HKR RLT Soll_uHG (Heizkurve)", -15, 30.0),
)
STATES = ["factory", "differs_from_factory", "check_recommended"]


def finite_number(value):
    """Reject unavailable, invalid and non-finite values instead of assuming zero."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return result if isfinite(result) else None


def interpolate(values, outdoor):
    """Linear return setpoint through +18/0/-15 outdoor, clamped at both ends."""
    if outdoor >= 18:
        return values[0]
    if outdoor <= -15:
        return values[2]
    if outdoor >= 0:
        return values[1] + (values[0] - values[1]) * outdoor / 18
    return values[1] + (values[2] - values[1]) * -outdoor / 15


def evaluate_curve(data, options=None):
    """Return state and attributes, or None until all three inputs are valid.

    Warnings are htha floor-heating heuristics, not manufacturer limits.
    Reference overrides change comparison only, never these fixed heuristics.
    """
    data, options = data or {}, options or {}
    values = [finite_number(data.get(param)) for _, param, _, _ in POINTS]
    if any(value is None for value in values):
        return None
    factory = [point[3] for point in POINTS]
    reference = [finite_number(options.get(f"curve_reference_{key}", default))
                 for key, _, _, default in POINTS]
    if any(value is None for value in reference):
        reference = factory
    monotonic = values[0] <= values[1] <= values[2]
    reasons = []
    if not monotonic:
        reasons.append("Return setpoints do not increase as outdoor temperature falls.")
    if any(value > default + 5 for value, default in zip(values, factory)):
        reasons.append("A point is more than 5 K above the factory floor-heating curve.")
    if values[2] > 35:
        reasons.append("The -15 °C outdoor point exceeds 35 °C return.")
    differs = values != reference
    state = "check_recommended" if reasons else "differs_from_factory" if differs else "factory"
    attrs = {"monotonic": monotonic, "reference_is_factory": reference == factory,
             "reasons": reasons}
    for (key, _, outdoor, default), value, ref in zip(POINTS, values, reference):
        attrs[f"{key}_point"] = {
            "outdoor_c": outdoor, "value": value, "factory_value": default,
            "delta_k": round(value - default, 3), "reference_value": ref,
            "reference_delta_k": round(value - ref, 3),
        }
    attrs["explanation"] = " ".join(reasons) if reasons else (
        "Differs from the reference curve; this alone is informational."
        if differs else "Matches the reference curve."
    )
    outdoor = finite_number(data.get("Temp. Aussen"))
    if outdoor is not None:
        current = interpolate(values, outdoor)
        baseline = interpolate(factory, outdoor)
        ref = interpolate(reference, outdoor)
        attrs.update(outdoor_temperature=outdoor,
                     interpolated_return_setpoint=round(current, 3),
                     factory_return_setpoint=round(baseline, 3),
                     interpolated_delta_k=round(current - baseline, 3),
                     reference_return_setpoint=round(ref, 3),
                     reference_delta_k=round(current - ref, 3))
    return state, attrs
