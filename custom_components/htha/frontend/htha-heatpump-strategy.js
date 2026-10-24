/*
 * Ht HA - dashboard strategies for Heliotherm heat pumps.
 *
 * Served by the htha integration and loaded automatically. Registers:
 *   - dashboard strategy  custom:htha-heatpump  (one view per heat pump)
 *   - view strategy       custom:htha-heatpump  (sections view)
 *   - section strategy    custom:htha-heatpump  (one section, see SECTIONS)
 *
 * Entities are discovered from the entity registry (platform "htha",
 * matched by domain + translation_key), so it works with any entity_ids and
 * with several heat pumps. Only built-in Home Assistant cards are used.
 */
const HTHA_VERSION = "1.0.13";

const ROLES = {
  operating_state: "sensor.operating_state",
  outdoor: "sensor.temp_aussen",
  outdoor_damped: "sensor.temp_aussen_verzoegert",
  hot_water: "sensor.temp_brauchwasser",
  fresh_water: "sensor.temp_frischwasser_istwert",
  flow: "sensor.temp_vorlauf",
  return: "sensor.temp_ruecklauf",
  heating_spread: "sensor.heating_circuit_spread",
  heating_target: "sensor.hkr_sollwert",
  source_in: "sensor.temp_eq_eintritt",
  source_out: "sensor.temp_eq_austritt",
  source_spread: "sensor.heat_source_spread",
  suction_gas: "sensor.temp_sauggas",
  evaporation: "sensor.temp_verdampfung",
  condensation: "sensor.temp_kondensation",
  hot_gas: "sensor.temp_heissgas",
  low_pressure: "sensor.niederdruck",
  high_pressure: "sensor.hochdruck",
  compressor_starts: "sensor.bsz_verdichter_schaltungen",
  compressor_hours: "sensor.bsz_verdichter_betriebsst_ges",
  heating_pump_hours: "sensor.bsz_hkp_betriebsstunden",
  source_pump_hours: "sensor.bsz_eq_betriebsstunden",
  hot_water_hours: "sensor.bsz_wwv_betriebsstunden",
  time_programs: "sensor.time_programs",
  mode_code: "sensor.betriebsart",
  fault: "binary_sensor.stoerung",
  compressor: "binary_sensor.verdichter",
  hot_water_mode: "binary_sensor.warmwasservorrang",
  heating_pump: "binary_sensor.heizkreispumpe",
  source_pump: "binary_sensor.eq_pumpe_ventilator",
  circulation_pump: "binary_sensor.zirkulationspumpe_ww",
  main_switch: "binary_sensor.hauptschalter",
  flow_switch: "binary_sensor.fws_stroemungsschalter",
  mode: "select.betriebsart",
  room_setpoint: "number.hkr_soll_raum",
  hw_normal: "number.ww_normaltemp",
  hw_minimum: "number.ww_minimaltemp",
  curve_upper: "number.hkr_rlt_soll_ohg",
  curve_zero: "number.hkr_rlt_soll_0",
  curve_lower: "number.hkr_rlt_soll_uhg",
  heat_up: "number.hkr_aufheiztemp",
  setback: "number.hkr_absenktemp",
  heating_limit: "number.hkr_heizgrenze",
  hw_hyst_normal: "number.ww_hysterese_normaltemp",
  hw_hyst_minimum: "number.ww_hysterese_minimaltemp",
  writes: "switch.write_protection",
  clock: "datetime.ht_datetime",
  clock_sync: "button.ht_datetime_sync",
};

// Sensors that only mirror a number/select; never shown when the control exists.
const MIRRORS = new Set([
  "sensor.hkr_soll_raum", "sensor.ww_normaltemp", "sensor.ww_minimaltemp",
  "sensor.hkr_rlt_soll_ohg", "sensor.hkr_rlt_soll_0", "sensor.hkr_rlt_soll_uhg",
  "sensor.hkr_aufheiztemp", "sensor.hkr_absenktemp", "sensor.hkr_heizgrenze",
  "sensor.ww_hysterese_normaltemp", "sensor.ww_hysterese_minimaltemp", "sensor.betriebsart",
]);

const TEXT = {
  en: {
    overview: "Heat pump", heating: "Heating circuit", heating_curve: "Heating curve (return setpoints)",
    hot_water: "Hot water", source: "Heat source & refrigerant", statistics: "Statistics",
    controls: "Controls", schedule: "Time programs", diagnostics: "Diagnostics",
    state: "State", mode: "Operating mode", compressor: "Compressor", hot_water_mode: "Hot water mode",
    heating_pump: "Heating pump", source_pump: "Source pump/fan", fault: "Fault", outdoor: "Outdoor",
    flow: "Flow", return: "Return", spread: "Spread", room_setpoint: "Room setpoint",
    target: "Target", curve_upper: "At upper heating limit", curve_zero: "At 0 °C outdoor",
    curve_lower: "At lower heating limit", hw_temp: "Hot water", hw_normal: "Setpoint (normal)",
    hw_minimum: "Setpoint (minimum)", circulation: "Circulation pump", inlet: "Inlet", outlet: "Outlet",
    suction_gas: "Suction gas", evaporation: "Evaporation", condensation: "Condensation", hot_gas: "Hot gas",
    low_pressure: "Low pressure", high_pressure: "High pressure", activity: "Activity (24 h)",
    temps_48h: "Flow, return & outdoor (48 h)", hw_72h: "Hot water vs. setpoints (72 h)",
    source_48h: "Heat source & suction gas (48 h)", starts_per_day: "Compressor starts per day",
    hours_per_day: "Runtime per day (h)", compressor_starts: "Compressor starts (total)",
    heating_pump_hours: "Heating pump", source_pump_hours: "Source pump/fan", hot_water_hours: "Hot water mode",
    compressor_hours: "Compressor", writes: "Allow writes",
    writes_off: "**Read-only.** Settings can't be changed while *Allow writes* is off. Turn it on (confirm by switching it on again within 10 s) to show the controls.",
    writes_on: "**Writes enabled.** Changes are sent to the heat pump immediately. Turn *Allow writes* off again when you are done.",
    fault_alert: "The heat pump reports a **fault**. Check the unit's display.",
    clock_sync: "Sync clock", no_heat_pump: "No Ht HA heat pump found. Is the integration set up?",
    unknown_section: "Unknown htha section", setpoint_room: "Room setpoint", hw_setpoints: "Hot water setpoints",
    curve_settings: "Heating curve", other_settings: "Other settings",
  },
  de: {
    overview: "Wärmepumpe", heating: "Heizkreis", heating_curve: "Heizkurve (Rücklaufsollwerte)",
    hot_water: "Warmwasser", source: "Wärmequelle & Kältekreis", statistics: "Statistik",
    controls: "Einstellungen", schedule: "Zeitprogramme", diagnostics: "Diagnose",
    state: "Zustand", mode: "Betriebsart", compressor: "Verdichter", hot_water_mode: "Warmwasserbetrieb",
    heating_pump: "Heizkreispumpe", source_pump: "Quellenpumpe/Ventilator", fault: "Störung", outdoor: "Außen",
    flow: "Vorlauf", return: "Rücklauf", spread: "Spreizung", room_setpoint: "Raum-Sollwert",
    target: "Sollwert", curve_upper: "An oberer Heizgrenze", curve_zero: "Bei 0 °C außen",
    curve_lower: "An unterer Heizgrenze", hw_temp: "Warmwasser", hw_normal: "Sollwert (normal)",
    hw_minimum: "Sollwert (minimal)", circulation: "Zirkulationspumpe", inlet: "Eintritt", outlet: "Austritt",
    suction_gas: "Sauggas", evaporation: "Verdampfung", condensation: "Kondensation", hot_gas: "Heißgas",
    low_pressure: "Niederdruck", high_pressure: "Hochdruck", activity: "Aktivität (24 h)",
    temps_48h: "Vorlauf, Rücklauf & Außen (48 h)", hw_72h: "Warmwasser und Sollwerte (72 h)",
    source_48h: "Wärmequelle & Sauggas (48 h)", starts_per_day: "Verdichterstarts pro Tag",
    hours_per_day: "Laufzeit pro Tag (h)", compressor_starts: "Verdichterstarts (gesamt)",
    heating_pump_hours: "Heizkreispumpe", source_pump_hours: "Quellenpumpe/Ventilator", hot_water_hours: "Warmwasserbetrieb",
    compressor_hours: "Verdichter", writes: "Schreibzugriff",
    writes_off: "**Nur Anzeige.** Einstellungen können nicht geändert werden, solange *Schreibzugriff* aus ist. Einschalten (innerhalb von 10 s erneut einschalten zum Bestätigen), um die Regler anzuzeigen.",
    writes_on: "**Schreibzugriff aktiv.** Änderungen werden sofort an die Wärmepumpe gesendet. Danach *Schreibzugriff* wieder ausschalten.",
    fault_alert: "Die Wärmepumpe meldet eine **Störung**. Bitte das Display der Anlage prüfen.",
    clock_sync: "Uhr synchronisieren", no_heat_pump: "Keine Ht HA Wärmepumpe gefunden. Ist die Integration eingerichtet?",
    unknown_section: "Unbekannter htha-Abschnitt", setpoint_room: "Raum-Sollwert", hw_setpoints: "Warmwasser-Sollwerte",
    curve_settings: "Heizkurve", other_settings: "Weitere Einstellungen",
  },
};

const SECTIONS = [
  "overview", "heating", "hot_water", "source", "statistics", "controls", "schedule", "diagnostics",
];

function texts(hass) {
  const lang = ((hass.locale && hass.locale.language) || hass.language || "en").split("-")[0];
  return TEXT[lang] || TEXT.en;
}

/** Find all htha heat pumps: [{deviceId, name, e: {role: entity_id}, all: [entity_id]}]. */
function findHeatPumps(hass) {
  const byKey = {};
  for (const [role, key] of Object.entries(ROLES)) byKey[key] = role;
  const pumps = new Map();
  for (const ent of Object.values(hass.entities || {})) {
    if (ent.platform !== "htha" || !hass.states[ent.entity_id]) continue;
    const devId = ent.device_id || "_none";
    if (!pumps.has(devId)) {
      const dev = (hass.devices || {})[devId] || {};
      pumps.set(devId, {
        deviceId: devId, name: dev.name_by_user || dev.name || "Heat pump", e: {}, all: [],
      });
    }
    const pump = pumps.get(devId);
    pump.all.push(ent.entity_id);
    const key = `${ent.entity_id.split(".")[0]}.${ent.translation_key}`;
    const role = byKey[key];
    if (role && !pump.e[role]) pump.e[role] = ent.entity_id;
    pump.keys = pump.keys || {};
    pump.keys[ent.entity_id] = key;
  }
  return [...pumps.values()].sort((a, b) => a.name.localeCompare(b.name));
}

function pickPump(hass, config) {
  const pumps = findHeatPumps(hass);
  if (config && config.device_id) return pumps.find((p) => p.deviceId === config.device_id);
  return pumps[0];
}

const HALF = { grid_options: { columns: 6 } };
const THIRD = { grid_options: { columns: 4 } };

function tile(entity, name, extra = {}) {
  if (!entity) return null;
  const card = { type: "tile", entity, ...HALF, ...extra };
  if (name) card.name = name;
  return card;
}

function heading(text, icon, badges = [], style = "title") {
  const card = { type: "heading", heading: text, heading_style: style };
  if (icon) card.icon = icon;
  const b = badges.filter(Boolean);
  if (b.length) card.badges = b;
  return card;
}

function badge(entity, extra = {}) {
  if (!entity) return null;
  return { type: "entity", entity, show_state: true, show_icon: true, ...extra };
}

function history(title, hours, entries) {
  const entities = entries.filter((x) => x && x.entity);
  if (!entities.length) return null;
  return { type: "history-graph", title, hours_to_show: hours, entities };
}

function alert(type, content, visibility) {
  const card = {
    type: "markdown", text_only: true,
    content: `<ha-alert alert-type="${type}">${content}</ha-alert>`,
  };
  if (visibility) card.visibility = visibility;
  return card;
}

const isOn = (entity) => [{ condition: "state", entity, state: "on" }];
const isOff = (entity) => [{ condition: "state", entity, state_not: "on" }];

function num(hass, entity, fallback) {
  const st = entity && hass.states[entity];
  const v = st ? parseFloat(st.state) : NaN;
  return Number.isFinite(v) ? v : fallback;
}

function section(cards) {
  const list = cards.filter(Boolean);
  // A heading alone is not worth a section.
  if (list.filter((c) => c.type !== "heading").length === 0) return null;
  return { type: "grid", cards: list };
}

const BUILDERS = {
  overview(hass, p, t) {
    const e = p.e;
    return section([
      heading(p.name, "mdi:heat-pump", [badge(e.outdoor), badge(e.operating_state)]),
      e.fault ? alert("error", t.fault_alert, isOn(e.fault)) : null,
      tile(e.operating_state, t.state),
      tile(e.mode, t.mode),
      tile(e.compressor, t.compressor, { color: "orange" }),
      tile(e.hot_water_mode, t.hot_water_mode, { color: "red" }),
      tile(e.heating_pump, t.heating_pump, { color: "deep-orange" }),
      tile(e.source_pump, t.source_pump, { color: "cyan" }),
      tile(e.fault, t.fault),
      tile(e.outdoor, t.outdoor),
      history(t.activity, 24, [
        { entity: e.operating_state, name: t.state },
        { entity: e.compressor, name: t.compressor },
        { entity: e.hot_water_mode, name: t.hot_water_mode },
        { entity: e.heating_pump, name: t.heating_pump },
      ]),
    ]);
  },

  heating(hass, p, t) {
    const e = p.e;
    const curve = [e.curve_upper, e.curve_zero, e.curve_lower].some(Boolean);
    return section([
      heading(t.heating, "mdi:radiator", [badge(e.heating_pump, { show_state: false })]),
      tile(e.flow, t.flow, { color: "red" }),
      tile(e.return, t.return, { color: "blue" }),
      tile(e.heating_spread, t.spread),
      tile(e.room_setpoint, t.room_setpoint),
      tile(e.heating_target, t.target),
      history(t.temps_48h, 48, [
        { entity: e.flow, name: t.flow },
        { entity: e.return, name: t.return },
        { entity: e.outdoor, name: t.outdoor },
      ]),
      curve ? heading(t.heating_curve, "mdi:chart-bell-curve-cumulative", [], "subtitle") : null,
      tile(e.curve_upper, t.curve_upper, THIRD),
      tile(e.curve_zero, t.curve_zero, THIRD),
      tile(e.curve_lower, t.curve_lower, THIRD),
    ]);
  },

  hot_water(hass, p, t) {
    const e = p.e;
    const min = num(hass, e.hw_minimum, 40);
    const normal = num(hass, e.hw_normal, Math.max(min, 45));
    return section([
      heading(t.hot_water, "mdi:water-boiler", [badge(e.hot_water_mode, { show_state: false })]),
      e.hot_water ? {
        type: "gauge", entity: e.hot_water, name: t.hw_temp, min: 10, max: 65, needle: true,
        segments: [
          { from: 0, color: "var(--info-color)" },
          { from: min, color: "var(--warning-color)" },
          { from: normal, color: "var(--success-color)" },
        ],
      } : null,
      tile(e.hw_normal, t.hw_normal),
      tile(e.hw_minimum, t.hw_minimum),
      tile(e.hot_water_mode, t.hot_water_mode, { color: "red" }),
      tile(e.circulation_pump, t.circulation),
      tile(e.fresh_water, null),
      history(t.hw_72h, 72, [
        { entity: e.hot_water, name: t.hw_temp },
        { entity: e.hw_normal, name: t.hw_normal },
        { entity: e.hw_minimum, name: t.hw_minimum },
      ]),
    ]);
  },

  source(hass, p, t) {
    const e = p.e;
    return section([
      heading(t.source, "mdi:heat-pump-outline", [badge(e.source_pump, { show_state: false })]),
      tile(e.source_in, t.inlet, { color: "teal" }),
      tile(e.source_out, t.outlet, { color: "cyan" }),
      tile(e.source_spread, t.spread),
      tile(e.source_pump, t.source_pump, { color: "cyan" }),
      tile(e.suction_gas, t.suction_gas),
      tile(e.evaporation, t.evaporation),
      tile(e.condensation, t.condensation),
      tile(e.hot_gas, t.hot_gas),
      tile(e.low_pressure, t.low_pressure),
      tile(e.high_pressure, t.high_pressure),
      history(t.source_48h, 48, [
        { entity: e.source_in, name: t.inlet },
        { entity: e.source_out, name: t.outlet },
        { entity: e.suction_gas, name: t.suction_gas },
      ]),
    ]);
  },

  statistics(hass, p, t) {
    const e = p.e;
    const hours = [
      e.heating_pump_hours && { entity: e.heating_pump_hours, name: t.heating_pump_hours },
      e.source_pump_hours && { entity: e.source_pump_hours, name: t.source_pump_hours },
      e.hot_water_hours && { entity: e.hot_water_hours, name: t.hot_water_hours },
      e.compressor_hours && { entity: e.compressor_hours, name: t.compressor_hours },
    ].filter(Boolean);
    return section([
      heading(t.statistics, "mdi:chart-bar"),
      e.compressor_starts ? {
        type: "statistics-graph", title: t.starts_per_day, chart_type: "bar", period: "day",
        days_to_show: 30, stat_types: ["change"], entities: [{ entity: e.compressor_starts, name: t.compressor }],
      } : null,
      hours.length ? {
        type: "statistics-graph", title: t.hours_per_day, chart_type: "bar", period: "day",
        days_to_show: 30, stat_types: ["change"], entities: hours,
      } : null,
      tile(e.compressor_starts, t.compressor_starts),
      ...hours.map((h) => tile(h.entity, h.name)),
    ]);
  },

  controls(hass, p, t) {
    const e = p.e;
    if (!e.writes) return null;
    const on = isOn(e.writes);
    const ctl = (entity, name, feature, extra = {}) =>
      tile(entity, name, { features: [feature], visibility: on, ...extra });
    const numIn = { type: "numeric-input", style: "buttons" };
    const others = [e.heat_up, e.setback, e.heating_limit, e.hw_hyst_normal, e.hw_hyst_minimum].filter(Boolean);
    return section([
      heading(t.controls, "mdi:tune-variant", [badge(e.writes, { color: "red" })]),
      alert("info", t.writes_off, isOff(e.writes)),
      alert("warning", t.writes_on, on),
      tile(e.writes, t.writes, { color: "red", grid_options: { columns: 12 } }),
      ctl(e.mode, t.mode, { type: "select-options" }, { grid_options: { columns: 12 } }),
      ctl(e.room_setpoint, t.room_setpoint, numIn),
      e.hw_normal || e.hw_minimum ? { ...heading(t.hw_setpoints, "mdi:water-boiler", [], "subtitle"), visibility: on } : null,
      ctl(e.hw_normal, t.hw_normal, numIn),
      ctl(e.hw_minimum, t.hw_minimum, numIn),
      e.curve_upper ? { ...heading(t.curve_settings, "mdi:chart-bell-curve-cumulative", [], "subtitle"), visibility: on } : null,
      ctl(e.curve_upper, t.curve_upper, numIn, THIRD),
      ctl(e.curve_zero, t.curve_zero, numIn, THIRD),
      ctl(e.curve_lower, t.curve_lower, numIn, THIRD),
      others.length ? { ...heading(t.other_settings, "mdi:cog", [], "subtitle"), visibility: on } : null,
      ...others.map((x) => ctl(x, null, numIn)),
      e.clock_sync ? tile(e.clock_sync, t.clock_sync, { visibility: on }) : null,
    ]);
  },

  schedule(hass, p, t) {
    const sensor = p.e.time_programs;
    if (!sensor) return null;
    return section([
      heading(t.schedule, "mdi:calendar-clock"),
      { type: "markdown", content: scheduleTemplate(sensor) },
    ]);
  },

  diagnostics(hass, p, t) {
    const e = p.e;
    const shown = new Set();
    for (const name of ["overview", "heating", "hot_water", "source", "statistics", "controls"]) {
      const s = BUILDERS[name](hass, p, t);
      if (s) collectEntities(s, shown);
    }
    const rest = p.all
      .filter((id) => !shown.has(id) && !MIRRORS.has(p.keys[id]))
      .filter((id) => id !== e.time_programs && id !== e.clock_sync)
      .sort();
    return section([
      heading(t.diagnostics, "mdi:stethoscope"),
      ...rest.map((id) => tile(id, null)),
    ]);
  },
};

function collectEntities(obj, set) {
  if (Array.isArray(obj)) { obj.forEach((x) => collectEntities(x, set)); return; }
  if (obj && typeof obj === "object") {
    if (typeof obj.entity === "string" && obj.type !== "heading") set.add(obj.entity);
    for (const [k, v] of Object.entries(obj)) if (k !== "visibility") collectEntities(v, set);
  }
}

function scheduleTemplate(sensor) {
  return `{% set sensor = '${sensor}' %}
{% set current_day = now().weekday() %}
{% set current_hour = now().hour %}
{% if state_attr(sensor, 'time_programs') is not none %}
{% for program in state_attr(sensor, 'time_programs') %}
### <ha-icon icon="mdi:calendar-clock"></ha-icon> {{ program.name }}

| Day | 00:00 - 06:00 - 12:00 - 18:00 - 24:00 |
| :--- | :--- |
{% set days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] -%}
{% for day_num in range(program.entries|length) -%}
{% set is_today = (day_num == current_day) -%}
{% set day_entries = program.entries[day_num] | reject('none') | list -%}
| {% if is_today %} **{{ days[day_num] }}**{% else %}{{ days[day_num] }}{% endif %} | {% for h in range(24) -%}
{%- set ns = namespace(state=0) -%}
{%- for entry in day_entries -%}
  {%- set start_h = entry.start.split(':')[0] | int -%}
  {%- set end_h = entry.end.split(':')[0] | int -%}
  {%- if start_h <= h and h < end_h -%}
    {%- set ns.state = entry.state -%}
  {%- endif -%}
{%- endfor -%}
{%- if is_today and h == current_hour -%}
  {%- set color = '#f44336' -%}
{%- else -%}
  {%- set color = '#4caf50' if ns.state == 1 else '#2196f3' if ns.state == 2 else '#757575' -%}
{%- endif -%}
<font color="{{ color }}">█</font>
{%- endfor %} |
{% endfor %}
{% endfor %}

**Legend:** <font color="#4caf50">█</font> Comfort | <font color="#2196f3">█</font> Setback | <font color="#757575">█</font> Off | <font color="#f44336">▶</font> Now
{% else %}
No time programs loaded from the heat pump yet.
{% endif %}
`;
}

function errorSection(message) {
  return { type: "grid", cards: [{ type: "markdown", content: `<ha-alert alert-type="warning">${message}</ha-alert>` }] };
}

function buildSection(hass, config) {
  const t = texts(hass);
  const name = (config && config.section) || "overview";
  if (!BUILDERS[name]) return errorSection(`${t.unknown_section}: ${name}`);
  const pump = pickPump(hass, config);
  if (!pump) return errorSection(t.no_heat_pump);
  return BUILDERS[name](hass, pump, t) || { type: "grid", cards: [] };
}

function buildView(hass, config) {
  const t = texts(hass);
  const pumps = config && config.device_id
    ? findHeatPumps(hass).filter((p) => p.deviceId === config.device_id)
    : findHeatPumps(hass);
  if (!pumps.length) return { type: "sections", sections: [errorSection(t.no_heat_pump)] };
  const wanted = (config && config.sections) || SECTIONS;
  const sections = [];
  for (const pump of pumps) {
    for (const name of wanted) {
      const s = BUILDERS[name] && BUILDERS[name](hass, pump, t);
      if (s) sections.push(s);
    }
  }
  return { type: "sections", max_columns: (config && config.max_columns) || 4, sections };
}

class HthaSectionStrategy extends HTMLElement {
  static registryDependencies = ["entities", "devices"];
  static async generate(config, hass) { return buildSection(hass, config); }
}

class HthaViewStrategy extends HTMLElement {
  static registryDependencies = ["entities", "devices"];
  static async generate(config, hass) { return buildView(hass, config); }
}

class HthaDashboardStrategy extends HTMLElement {
  static registryDependencies = ["entities", "devices"];
  static async generate(config, hass) {
    const pumps = findHeatPumps(hass);
    if (!pumps.length) return { views: [{ title: "Heat pump", ...buildView(hass, config) }] };
    return {
      title: pumps.length === 1 ? pumps[0].name : "Heat pumps",
      views: pumps.map((p, i) => ({
        title: p.name, path: i ? `heat-pump-${i + 1}` : "heat-pump", icon: "mdi:heat-pump",
        strategy: { type: "custom:htha-heatpump", device_id: p.deviceId },
      })),
    };
  }
}

// Registration.
//
// Home Assistant's core bundle installs a scoped custom element registry
// polyfill that replaces window.customElements. Modules loaded via
// extra_module_url can run before that (always with the legacy/es5 build,
// which e.g. older Android WebViews get, and as a race on a cold cache with
// the modern build). Elements defined into the native registry are then
// invisible to Home Assistant, which waits 5 s and fails with "Timeout waiting
// for strategy element ...". So register synchronously into whatever registry
// is current now, and keep checking until Home Assistant's own registry is in
// place and holds our elements.
const ELEMENTS = [
  ["ll-strategy-section-htha-heatpump", HthaSectionStrategy],
  ["ll-strategy-view-htha-heatpump", HthaViewStrategy],
  ["ll-strategy-dashboard-htha-heatpump", HthaDashboardStrategy],
];
const registerAll = () => {
  const registry = window.customElements;
  let ok = true;
  for (const [tag, cls] of ELEMENTS) {
    if (registry.get(tag)) continue;
    try {
      // A fresh subclass per registry: a constructor may only be defined once per registry.
      registry.define(tag, class extends cls {});
    } catch (err) {
      ok = false;
      console.warn(`htha: could not register ${tag}`, err);
    }
  }
  return ok && !!registry.get("home-assistant");
};
if (!registerAll()) {
  let tries = 0;
  const timer = setInterval(() => {
    if (registerAll() || ++tries >= 240) clearInterval(timer);
  }, 250);
  if (timer && typeof timer.unref === "function") timer.unref();
}

// Exposed for tests / tooling.
window.hthaHeatpumpStrategy = { version: HTHA_VERSION, buildSection, buildView, findHeatPumps, SECTIONS, ROLES };
console.info(`%c HTHA-HEATPUMP-STRATEGY %c ${HTHA_VERSION} `, "background:#e65100;color:#fff", "");
