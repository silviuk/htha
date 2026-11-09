/* Current schedule auto-load is read-only; drafts require an explicit choice. */
const clone = value => JSON.parse(JSON.stringify(value));
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const time = i => `${String(Math.floor(i / 4)).padStart(2,'0')}:${String(i % 4 * 15).padStart(2,'0')}`;
const slot = s => /^([01]\d|2[0-3]):(00|15|30|45)$/.test(s) ? Number(s.slice(0,2))*4+Number(s.slice(3))/15 : s === '24:00' ? 96 : NaN;
function toCells(draft, nos=256) {
  const week = Array.from({length:7},()=>Array(96).fill(null));
  if (!Array.isArray(draft?.entries) || draft.entries.length !== 7) return week;
  draft.entries.forEach((day,d) => {
    const used = new Set();
    if (!Array.isArray(day)) return;
    for (const e of day) {
      if (e?.start === '24:00' && e.end === '24:00') continue;
      const a=slot(e?.start || ''), b=slot(e?.end || '');
      if (!Number.isInteger(a) || !Number.isInteger(b) || a>=b || !Number.isInteger(e?.state) || e.state<0 || e.state>=nos) {
        week[d].fill(null); return;
      }
      for (let i=a;i<b;i++) {week[d][i]=used.has(i)?null:e.state;used.add(i);}
    }
  });
  return week;
}
function toDraft(week) {
  return {entries:week.map(day => {
    const result=[];
    day.forEach((state,i)=>{
      if (result.length && result.at(-1).state === state) result.at(-1).end=time(i+1);
      else result.push({start:time(i),end:time(i+1),state});
    });
    return result;
  })};
}
class Selection {
  constructor() {this.clear();}
  clear() {this.cells=new Set();this.anchor=null;}
  range(day,a,b,add=false) {
    if (!add) this.cells.clear();
    for(let i=Math.min(a,b);i<=Math.max(a,b);i++) this.cells.add(`${day}:${i}`);
  }
  choose(day,i,{shiftKey=false,ctrlKey=false,metaKey=false}={}) {
    const add=ctrlKey || metaKey;
    if (shiftKey && this.anchor?.day===day) this.range(day,this.anchor.i,i,add);
    else {
      if (!add) this.cells.clear();
      const key=`${day}:${i}`;
      if (add && this.cells.has(key)) this.cells.delete(key); else this.cells.add(key);
      this.anchor={day,i};
    }
  }
  ranges() {
    const result=[];
    for(let d=0;d<7;d++) for(let i=0;i<96;i++) if(this.cells.has(`${d}:${i}`)) {
      const last=result.at(-1);
      if(last?.day===d && last.end===i) last.end=i+1; else result.push({day:d,start:i,end:i+1});
    }
    return result;
  }
}
class LocalWeek {
  constructor(draft) {this.week=toCells(draft);this.undo=[];this.redo=[];}
  change(edit) {
    const before=clone(this.week); edit(this.week);
    if(JSON.stringify(before)===JSON.stringify(this.week)) return false;
    this.undo.push(before);if(this.undo.length>100)this.undo.shift();this.redo=[];return true;
  }
  paint(selection,mode) {return this.change(week=>{for(const key of selection.cells){const [d,i]=key.split(':').map(Number);week[d][i]=mode;}});}
  copy(day,targets) {return this.change(week=>{for(const d of targets)week[d]=clone(week[day]);});}
  history(redo=false) {
    const source=redo?this.redo:this.undo,target=redo?this.undo:this.redo;
    if(!source.length)return false;target.push(clone(this.week));this.week=source.pop();return true;
  }
}
const DE = {
  'Changed (old value shown lighter with ×)':'Geändert (alter Wert heller mit ×)',
  'was':'war','now':'jetzt',
  'Schedule editor':'Zeitprogramm-Editor','Heating':'Heizung','Hot water':'Warmwasser','Profiles':'Profile',
  'Unsaved draft':'Ungespeicherter Entwurf','Custom / no matching saved profile':'Individuell / kein passendes Profil',
  'Load from pump':'Von Wärmepumpe laden','Refresh baseline':'Vergleichsbasis aktualisieren','Current heat-pump schedule':'Aktuelles Wärmepumpenprogramm',
  'Draft schedule':'Zeitprogramm-Entwurf','Validate':'Prüfen','Save profile':'Profil speichern','Save as':'Speichern unter',
  'Update profile':'Profil überschreiben','Rename':'Umbenennen','Delete':'Löschen','Use as starting point':'Als Vorlage verwenden',
  'Apply profile…':'Profil anwenden…','Saved in HA':'In HA gespeichert','Sent to heat pump':'An Wärmepumpe gesendet',
  'Send to heat pump':'An Wärmepumpe senden','Send schedule':'Zeitprogramm senden','Cancel':'Abbrechen',
  'Set mode for selection':'Modus für Auswahl setzen','Clear selection':'Auswahl aufheben','Selected cells':'Ausgewählte Viertelstunden',
  'Select':'Auswählen','Multi-select':'Mehrfachauswahl','Select day':'Tag auswählen',
  'Select mode: drag slots to select. Turn off to scroll; taps still select. Multi-select adds or removes tapped slots.':'Auswahlmodus: Viertelstunden durch Ziehen auswählen. Zum Scrollen ausschalten; Antippen wählt weiterhin aus. Mehrfachauswahl fügt angetippte Viertelstunden hinzu oder entfernt sie.',
  'Select range':'Zeitraum auswählen','Add selection':'Zur Auswahl hinzufügen','Start':'Beginn','End':'Ende','Day':'Tag',
  'Copy this day to…':'Diesen Tag kopieren auf…','All days':'Alle Tage','Weekdays':'Werktage','Weekend':'Wochenende',
  'Selected days':'Ausgewählte Tage','Copy day':'Tag kopieren','Undo':'Rückgängig','Redo':'Wiederholen',
  'Setback':'Absenken','Normal':'Normalbetrieb','Boost':'Aufheizen','Minimum maintenance':'Mindesttemperatur halten',
  'Off':'Aus','On':'Ein','Help and recommendations':'Hilfe und Empfehlungen','Optional mode mapping override':'Optionale Moduszuordnung',
  'Verified default for firmware 2.03N; override only after checking your controller. Labels never translate numeric payloads.':'Geprüfte Standardzuordnung für Firmware 2.03N; nur nach Prüfung am Regler ändern. Namen ändern niemals die gesendeten Zahlencodes.',
  'Normal charging':'Normal laden','Unknown':'Unbekannt','Unverified':'Nicht bestätigt','Mode':'Modus',
  'Confirm mode mapping':'Moduszuordnung bestätigen','Unverified mode mapping':'Nicht bestätigte Moduszuordnung',
  'Verify each numeric code on this controller before assigning a name. Labels never translate numeric payloads.':'Jeden Zahlencode am Regler prüfen, bevor ein Name zugeordnet wird. Namen ändern niemals die gesendeten Zahlencodes.',
  'Normal code':'Normal-Code','Floor heating':'Fußbodenheizung','Advice / Why':'Hinweise / Warum',
  'Click selects; Ctrl/Cmd toggles; Shift extends within one day. Drag selects only. Arrows move, Shift+arrows extend, Space toggles, Escape clears. On phones enable Select to drag; disable it to scroll. Multi-select toggles tapped slots. Select day selects the focused day.':'Klick wählt; Strg/Cmd schaltet um; Umschalt erweitert im selben Tag. Ziehen wählt nur aus. Pfeile bewegen, Umschalt+Pfeile erweitern, Leertaste schaltet um, Escape hebt auf. Am Handy Auswählen zum Ziehen einschalten, zum Scrollen ausschalten. Mehrfachauswahl schaltet angetippte Viertelstunden um. Tag auswählen wählt den fokussierten Tag.',
  'Selection alone makes no changes. Choose a mode, then Set mode.':'Die Auswahl allein ändert nichts. Modus wählen und danach setzen.',
  'Load discards local edits. Continue?':'Laden verwirft lokale Änderungen. Fortfahren?',
  'Overwrite the local draft on these days?':'Lokalen Entwurf an diesen Tagen überschreiben?',
  'Delete this saved profile? The pump schedule is unchanged.':'Dieses gespeicherte Profil löschen? Das Pumpenprogramm bleibt unverändert.',
  'Profile name':'Profilname','New profile name':'Neuer Profilname','Confirm overwriting saved profile?':'Gespeichertes Profil überschreiben?',
  'Changes compared with pump':'Änderungen gegenüber Wärmepumpe','No changes':'Keine Änderungen','Entries':'Einträge',
  'Compared with pump read at':'Verglichen mit Pumpenstand vom','Last successful read':'Letzter erfolgreicher Abruf',
  'Current state unavailable':'Aktueller Zustand nicht verfügbar','Needs validation / not sendable':'Prüfung erforderlich / nicht sendebereit',
  'Validate the current draft':'Aktuellen Entwurf prüfen','Fix critical findings':'Kritische Befunde beheben',
  'Acknowledge every warning':'Jede Warnung bestätigen','Allow writes is OFF':'Schreibzugriff ist AUS',
  'Confirm all used mode mappings':'Alle verwendeten Moduszuordnungen bestätigen','Baseline unavailable':'Vergleichsbasis nicht verfügbar',
  'Review again after another session changed the editor':'Nach Änderung in einer anderen Sitzung erneut prüfen',
  'Acknowledge selected warnings':'Ausgewählte Warnungen bestätigen','I have reviewed this warning':'Ich habe diese Warnung gelesen',
  'Multiple slot writes can partially fail. No automatic retry or rollback.':'Mehrere Schreibvorgänge können teilweise fehlschlagen. Kein automatischer Wiederholungsversuch und kein automatisches Zurücksetzen.',
  'Current time; not compressor activity. Global mode and overrides can supersede the time program.':'Aktuelle Zeit, keine Kompressoraktivität. Globale Betriebsart und Übersteuerungen können das Zeitprogramm überlagern.',
  'Full 00:00–24:00 draft coverage is integration policy, stricter than manual fallback. DHW Minimum maintains the minimum target; it is not hard-Off. Heating Normal follows the existing curve, not continuous compressor operation.':'Vollständige Entwurfsabdeckung von 00:00–24:00 ist eine strengere Integrationsregel als der Rückfallbetrieb im Handbuch. Warmwasser-Minimum hält die Mindesttemperatur; es schaltet nicht vollständig ab. Heizung Normal folgt der vorhandenen Heizkurve und bedeutet keinen Kompressordauerlauf.',
  'For slow floor heating, review comfort and recovery after setback. For a buffer-fed fresh-water station, plan charging before demand and verify plumbing separately. No temperature, curve, hysteresis or global mode is changed here.':'Bei träger Fußbodenheizung Komfort und Erholung nach Absenkung prüfen. Bei pufferbetriebener Frischwasserstation vor dem Bedarf laden und Hydraulik separat prüfen. Hier werden keine Temperaturen, Heizkurven, Hysteresen oder globalen Betriebsarten geändert.',
  'Use previous program as draft':'Vorheriges Programm als Entwurf verwenden','Restore previous program':'Vorheriges Programm wiederherstellen',
  'Recovery evidence':'Wiederherstellungsdaten','Read-only preview':'Schreibgeschützte Vorschau','Keep edits and refresh':'Entwurf behalten und aktualisieren',
  'This library is damaged or has an unsupported version. Repair the HA Store from a backup; no approval was restored.':'Profilbibliothek beschädigt oder Version nicht unterstützt. HA Store aus Sicherung reparieren; keine Freigabe wurde wiederhergestellt.',
  'Resolve unknown cells explicitly before saving or sending.':'Unbekannte Viertelstunden vor Speichern oder Senden ausdrücklich setzen.',
  'No service response':'Keine Dienstantwort','Sending…':'Wird gesendet…','minutes':'Minuten','cells':'Viertelstunden',
  'Controller':'Regler','Category':'Kategorie','Profile':'Profil','Changed days':'Geänderte Tage','Numeric modes':'Zahlencodes',
  'Allow writes':'Schreibzugriff','ON':'EIN','OFF':'AUS',
  'Confirm the Normal-code attestation':'Normal-Code ausdrücklich bestätigen',
  'Normal code conflicts with the semantic mapping':'Normal-Code widerspricht der Moduszuordnung',
  'Profile compatibility must be reviewed':'Profilkompatibilität prüfen',
  'Previous comparison — validate again':'Vorheriger Vergleich — erneut prüfen',
  'Native protocol':'Natives Protokoll',
};
const SEMANTIC_LABELS={setback:'Setback',normal:'Normal',boost:'Boost',minimum:'Off',charging:'On'};
const GATES={writes_off:'Allow writes is OFF',baseline_unavailable:'Baseline unavailable',validation_required:'Validate the current draft',critical_findings:'Fix critical findings',complete_mapping:'Confirm all used mode mappings',warnings_required:'Acknowledge every warning',mode_mapping:'Confirm the Normal-code attestation',normal_mapping_conflict:'Normal code conflicts with the semantic mapping',profile_incompatible:'Profile compatibility must be reviewed'};
Object.assign(DE, {
  'Current schedule (on pump)':'Aktuelles Zeitprogramm (auf der Wärmepumpe)', 'read at':'Gelesen um',
  'Reload from pump':'Erneut von Wärmepumpe laden', 'Retry':'Erneut versuchen',
  'Edit a copy of current schedule':'Kopie des aktuellen Zeitprogramms bearbeiten',
  'Start from profile…':'Mit Profil beginnen…', 'New schedule':'Neues Zeitprogramm',
  'Discard draft / Close editor':'Entwurf verwerfen / Editor schließen',
  'Resume draft':'Entwurf fortsetzen', 'Discard draft':'Entwurf verwerfen',
  'An existing server draft is available.':'Ein vorhandener Server-Entwurf ist verfügbar.',
  'Replace the existing server draft?':'Vorhandenen Server-Entwurf ersetzen?',
  'Factory default (Heliotherm)':'Werkseinstellung (Heliotherm)',
  'Built-in, read-only':'Integriert, schreibgeschützt',
  'Saved':'Gespeichert','version':'Version','copy':'Kopie',
  'Factory preset mapping must be verified; reload after confirmation':'Zuordnung der Werkseinstellung prüfen; nach Bestätigung erneut laden',
  'Factory default: Monday–Sunday 00:00–24:00 Normal. Unspecified heating periods remain Normal.':'Werkseinstellung: Montag–Sonntag 00:00–24:00 Normalbetrieb. Nicht belegte Heizzeiten bleiben Normalbetrieb.',
  'Factory default: Monday–Sunday 00:00–24:00 On. Unspecified hot-water periods are Off (minimum maintenance at WW_min, +5 K).':'Werkseinstellung: Montag–Sonntag 00:00–24:00 Ein. Nicht belegte Warmwasserzeiten zählen als Aus (Mindesttemperaturhaltung bei WW_min, +5 K).',
  'web control 321 manual, pp.10–11. Save as creates an editable copy.':'Handbuch web control 321, S.10–11. Speichern unter erstellt eine bearbeitbare Kopie.',
});
GATES.factory_mapping='Factory preset mapping must be verified; reload after confirmation';
const FINDINGS_DE={
  metadata:'Zuerst gültige Programmdaten dieses Reglers laden.',unsupported_controller:'Nicht unterstütztes Reglerformat. Verhalten neuerer RCG-Regler darf nicht vorausgesetzt werden.',
  program_kind:'Heizung oder Warmwasser ausdrücklich passend zum Programm wählen.',program_name:'Der Programmname identifiziert kein unterstütztes Heizungs-/Warmwasserprogramm.',
  mode_mapping:'Normal-Code an diesem Regler und dieser Firmware prüfen. Modbus-Betriebsarten sind keine Zeitprogramm-Codes.',
  normal_mapping_conflict:'Der bestätigte Normal-Code muss zur gespeicherten Moduszuordnung Normalbetrieb bzw. Normal laden passen.',
  complete_mapping:'Alle im Entwurf verwendeten Zahlencodes am Regler prüfen und die Moduszuordnung bestätigen.',profile_incompatible:'Profil, Metadaten, Regler/Firmware oder Zuordnung passen nicht zusammen. Nach Prüfung ausdrücklich neu speichern oder aktuellen Pumpenstand laden.',
  slots:'Ein Tag benötigt 1 bis 96 begrenzte Intervalle.',format:'Ungültiges Intervall: Zahlencodes, Viertelstunden, Reihenfolge und lückenlose Abdeckung prüfen.',coverage:'Tag muss bei 24:00 enden. Impliziter Rückfallbetrieb wird im Entwurf nicht akzeptiert.',
  short_window:'Ein Normal-Zeitfenster ist kürzer als 30 Minuten. Komfort und Erholung prüfen. Dies ist keine Mindestlaufzeit des Kompressors.',
  many_windows:'Mehr als zwei Normal-Zeitfenster pro Tag: wiederholtes Nachladen prüfen. Zeitfenster sind keine Kompressorstarts.',
  floor_non_normal:'Nicht-Normal-Zeiten bei Fußbodenheizung: Absenkung/Aufheizen sowie Erholung und Komfort prüfen. Keine allgemeine Absenkdauer ist belegt.',
  precharge:'Bei pufferbetriebener Frischwasserstation vor dem Bedarf normal laden. Keine festen Haushaltszeiten werden erzwungen.',
  non_atomic:'Mehrere unabhängige Schreibvorgänge können teilweise fehlschlagen. Wiederherstellungsdaten prüfen und Vergleichsbasis mit erhaltenem Entwurf aktualisieren. Kein automatischer Wiederholungsversuch oder Rücksetzen.',
  pv:'Optionale PV-Ausrichtung betrifft Eigenverbrauch, nicht wärmere Außenluft bei Grundwasseranlagen. Keine feste PV-Zeit wird erzwungen.',
  hygiene:'Die Zeitprogrammprüfung bewertet keine Trinkwasserhygiene. Puffer, Frischwasserstation, Verteilung und Zirkulation separat prüfen.',
  cycling:'Keine belegten exakten Starts/Stunde/Tag oder Mindest-Ein-/Auszeiten für dieses Modell: keine erfundenen Gerätegrenzen.',
};
class HthaScheduleScratchpadCard extends HTMLElement {
  setConfig(config) {
    if(!config.entity || !config.config_entry_id)throw new Error('entity and config_entry_id required');
    const changed=this.config && (this.config.entity!==config.entity || this.config.config_entry_id!==config.config_entry_id);
    this.config={...config};
    if(!this.shadowRoot)this.attachShadow({mode:'open'});
    this.shadowRoot.onfocusout=()=>Promise.resolve().then(()=>{if(this._deferredRender && !this.shadowRoot.activeElement && !this._gesture){this._deferredRender=false;this.render();}});
    if(!this._selection || changed) {
      this._selection=new Selection();this._dirty=true;this._category='heating';this._day=0;
      this._policy={kind:'heating',normal_state:1,mapping_confirmed:true,floor_heating:true};
      this._profiles=[];this._warningChecks=new Set();this._mode=0;this._add=false;this._selectMode=false;this._multiSelect=false;
      this._draft=null;this._local=null;this._model=null;this._validatedHash=undefined;
      this._profileId='';this._catalogLoaded=false;this._catalogLast=0;
      this._currentViews={};this._currentRequests={};this._autoLoaded=new Set();this._readErrors={};
    }
  }
  connectedCallback() {
    if(!this._timer && typeof setInterval==='function')this._timer=setInterval(()=>this.updateNow(),60000);
    if(typeof document!=='undefined' && !this._visibilityListener) {
      this._visibilityListener=()=>{if(document.visibilityState==='visible')void this.listProfiles(true);};
      document.addEventListener('visibilitychange',this._visibilityListener);
    }
    if(this._hass && this.config)void this.listProfiles(true);
  }
  disconnectedCallback() {
    if(this._timer)clearInterval(this._timer);this._timer=null;this._gesture=null;
    if(this._visibilityListener)document.removeEventListener('visibilitychange',this._visibilityListener);
    this._visibilityListener=null;
  }
  set hass(hass) {
    this._hass=hass;
    if(!this.config)return;
    if(!this._catalogLoaded){this._catalogLoaded=true;void this.listProfiles();}
    const attr=hass.states[this.config.entity]?.attributes;
    if(attr) {
      const previous=this._model;
      if(previous && (attr.session_id!==previous.session_id || attr.revision<previous.revision || (this._validatedHash && attr.draft_hash!==this._validatedHash)))this.invalidate(false);
      this._model={...previous,...clone(attr)};
      const changed=!previous || previous.revision!==attr.revision || previous.session_id!==attr.session_id || previous.writes_enabled!==attr.writes_enabled;
      if(changed && !this._gesture && !this.shadowRoot.activeElement)this.render();else {if(changed)this._deferredRender=true;this.updateGates();}
    } else if(!this.shadowRoot.innerHTML)this.render();
    if(hass.callWS)void this.loadCurrent();
  }
  get index(){return this._category==='hot_water'?0:2;}
  get days(){return this._hass?.language?.startsWith('de')?['Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag','Sonntag']:['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];}
  t(s){return this._hass?.language?.startsWith('de')?(DE[s]||s):s;}
  getCardSize(){return 18;}
  adoptDraft(draft) {
    this._local=new LocalWeek(draft);this._draft=toDraft(this._local.week);this._selection.clear();
    this._restoring=false;this.invalidate(false);
  }
  invalidate(render=true) {this._dirty=true;this._validatedHash=undefined;this._warningChecks?.clear();if(render)this.render();}
  edit() {if(this._local)this._draft=toDraft(this._local.week);this._restoring=false;this.invalidate();}
  draftName(){return this._profile && this._profileDraft && JSON.stringify(this._profileDraft)===JSON.stringify(this._draft)?(this._profile.read_only?this.t(this._profile.name):this._profile.name):this.t('Unsaved draft');}
  revisionData(){return {expected_draft_revision:this._model?.revision,session_id:this._model?.session_id};}
  label(mode) {
    if(mode===null || mode===undefined)return this.t('Unknown');
    const c=(this._draft?this._model?.mode_catalog:this._currentViews[this._category]?.mode_catalog)?.find(x=>x.state===mode);
    return c?.confirmed && SEMANTIC_LABELS[c.semantic]?`${this.t(SEMANTIC_LABELS[c.semantic])} [${mode}]`:`${this.t('Mode')} ${mode} (${this.t('Unverified').toLowerCase()})`;
  }
  styleMode(mode) {
    const c=(this._draft?this._model?.mode_catalog:this._currentViews[this._category]?.mode_catalog)?.find(x=>x.state===mode);
    return c?.confirmed && SEMANTIC_LABELS[c.semantic]?c.semantic:'unknown';
  }
  stamp(value) {
    if(!value)return this.t('Unknown');
    try{return new Intl.DateTimeFormat(this._hass?.locale?.language || this._hass?.language || 'en',{dateStyle:'medium',timeStyle:'short',timeZone:this._hass?.config?.time_zone || 'Europe/Berlin'}).format(new Date(value));}catch{return this.t('Unknown');}
  }
  now() {
    try {
      const p=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:this._hass?.config?.time_zone || 'Europe/Berlin',weekday:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date()).map(x=>[x.type,x.value]));
      return {day:['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].indexOf(p.weekday),percent:(Number(p.hour)*60+Number(p.minute))/1440*100};
    }catch{return {day:-1,percent:0};}
  }
  updateNow(){const n=this.now();this.shadowRoot?.querySelectorAll('[data-now]').forEach(e=>{e.hidden=Number(e.dataset.now)!==n.day;e.style.left=`${n.percent}%`;});}
  missing() {
    const model=this._model||{},reasons=new Set((model.missing_gates||[]).map(s=>this.t(GATES[s]||s)));
    if(this._dirty || this._validatedHash!==model.draft_hash)reasons.add(this.t('Validate the current draft'));
    if(!model.writes_enabled)reasons.add(this.t('Allow writes is OFF'));
    if(model.critical_count)reasons.add(this.t('Fix critical findings'));
    if(!model.mapping_valid || model.metadata?.index!==this.index)reasons.add(this.t('Confirm all used mode mappings'));
    if(model.warning_ids?.length && !model.warnings_acknowledged)reasons.add(this.t('Acknowledge every warning'));
    if(model.current_state!=='read' || model.metadata?.index!==this.index)reasons.add(this.t('Baseline unavailable'));
    return [...reasons];
  }
  updateGates() {
    const root=this.shadowRoot,send=root?.getElementById?.('save');
    if(send)send.disabled=!!this._busy || this.missing().length>0 || !this._model?.can_apply;
    const reasons=root?.getElementById?.('gate-reasons');if(reasons)reasons.textContent=this.missing().join(' · ');
  }
  async call(service,data={}) {
    if(this._busy)return null;
    this._busy=true;this._error='';this.render();
    try {
      const result=await this._hass.callWS({type:'call_service',domain:'htha',service,service_data:{config_entry_id:this.config.config_entry_id,...data},return_response:true});
      const model=result.response;if(!model)throw new Error(this.t('No service response'));
      if(model.session_id){if(service!=='validate_time_program' && this._validatedHash && model.draft_hash!==this._validatedHash)this.invalidate(false);this._model=model;}
      if(model.current_state==='read' && model.metadata?.index===this.index)this._currentViews[this._category]={current_program:clone(model.current_program),metadata:clone(model.metadata),read_at:model.baseline_read_at,mode_catalog:clone(model.mode_catalog||[]),current_profile_names:clone(model.current_profile_names||[])};
      if(model.profiles)this._profiles=clone([...(model.builtin_profiles||[]),...model.profiles]);
      if(['load_time_program_draft','load_time_program_profile','start_time_program_draft'].includes(service)) {
        this.adoptDraft(model.draft);this._profile=model.profile_context||null;this._profileDraft=this._profile?clone(model.draft):null;
        this._mappingEdits=null;
        this._policy={kind:this._category,normal_state:1,mapping_confirmed:true,floor_heating:true};
      } else if(service==='validate_time_program') {
        this._dirty=false;this._validatedHash=model.draft_hash;this._warningChecks.clear();
      } else if(['apply_time_program','restore_previous_time_program','refresh_time_program_baseline','set_time_program_mode_mapping'].includes(service))this.invalidate(false);
      if(service==='set_time_program_mode_mapping')this._mappingEdits=null;
      if(model.saved_profile){if(service!=='rename_time_program_profile' || this._profile?.id===model.saved_profile.id){this._profile=clone(model.saved_profile);this._profileDraft=clone(model.saved_profile.draft||this._profileDraft);}this._notice=this.t('Saved in HA');}
      if(['apply_time_program','restore_previous_time_program'].includes(service))this._notice=this.t('Sent to heat pump');
      return model;
    }catch(e) {
      this._error=e.message||String(e);this.invalidate(false);
      // Fresh-read failure and interrupted sends must not show stale verified truth.
      if(service==='validate_time_program' || ['apply_time_program','restore_previous_time_program','refresh_time_program_baseline'].includes(service)) {
        this._model={...this._model,current_program:null,current_state:'unavailable',can_apply:false};
      }
      return null;
    }finally{this._busy=false;this.render();
      if(['save_time_program_profile','rename_time_program_profile','delete_time_program_profile','apply_time_program','restore_previous_time_program'].includes(service))await this.listProfiles();
    }
  }
  discardOK(){return !this._draft || !this._dirty || window.confirm(this.t('Load discards local edits. Continue?'));}
  async loadCurrent(force=false) {
    if(!this._hass?.callWS)return null;
    const category=this._category,index=this.index,entry=this.config.config_entry_id;
    if(this._currentRequests[category])return this._currentRequests[category];
    if(!force && this._autoLoaded.has(category))return this._currentViews[category]||null;
    this._autoLoaded.add(category);delete this._readErrors[category];
    const request=(async()=>{
      try {
        const result=await this._hass.callWS({type:'call_service',domain:'htha',service:'get_current_time_program',
          service_data:{config_entry_id:entry,program_index:index,force},return_response:true});
        if(!result.response?.current_view)throw new Error(this.t('No service response'));
        if(entry!==this.config.config_entry_id)return null;
        this._currentViews[category]=clone(result.response.current_view);
        // Never adopt a server draft just because a snapshot arrived.
        if(!this._draft)this._model=clone(result.response);
        return this._currentViews[category];
      }catch(e){if(entry===this.config.config_entry_id){delete this._currentViews[category];this._readErrors[category]=e.message||String(e);}return null;}
      finally{if(entry===this.config.config_entry_id){delete this._currentRequests[category];if(!this._gesture && !this.shadowRoot.activeElement)this.render();else this._deferredRender=true;}}
    })();
    this._currentRequests[category]=request;
    return request;
  }
  async loadPump(){if(this._draft)return this.call('refresh_time_program_baseline',this.revisionData());return this.loadCurrent(true);}
  async openDraft(profileId=null) {
    if(!this.discardOK())return null;
    if(!this._draft && this._model?.draft && !window.confirm(this.t('Replace the existing server draft?')))return null;
    const response=await this.call('start_time_program_draft',{program_index:this.index,...this.revisionData(),...(profileId?{profile_id:profileId}:{})});
    return response;
  }
  async resumeDraft() {
    const model=await this.call('get_time_program_editor',{program_index:this._model?.metadata?.index??this.index});
    if(model?.draft && [0,2].includes(model.metadata?.index)){this._category=model.metadata.index===2?'heating':'hot_water';this._policy={kind:this._category,normal_state:1,mapping_confirmed:true,floor_heating:true};this.adoptDraft(model.draft);this._profile=model.profile_context||null;this._profileDraft=this._profile?clone(model.draft):null;this.render();await this.listProfiles();}
  }
  async closeDraft() {
    if(!this.discardOK())return;
    const model=await this.call('discard_time_program_draft',this.revisionData());
    if(!model)return;
    this._draft=null;this._local=null;this._profile=null;this._profileDraft=null;this._selection.clear();this._sendDialog=false;this.invalidate();
  }
  async listProfiles(debounced=false) {
    if(!this._hass?.callWS || !this.config)return null;
    if(debounced && (this._catalogRequest || Date.now()-(this._catalogLast||0)<2000))return this._catalogRequest||null;
    // Explicit refreshes queue behind the current request, including a refresh
    // requested after a mutation or category switch. Catalog requests never overlap.
    const previous=this._catalogRequest;
    const category=this._category,entry=this.config.config_entry_id;
    const request=(async()=>{
      if(previous)await previous;
      this._catalogLast=Date.now();
      try {
        const result=await this._hass.callWS({type:'call_service',domain:'htha',service:'list_time_program_profiles',service_data:{config_entry_id:entry,category},return_response:true});
        const model=result.response;if(!model)throw new Error(this.t('No service response'));
        if(category!==this._category || entry!==this.config.config_entry_id)return null;
        this._profiles=clone([...(model.builtin_profiles||[]),...(model.profiles||[])]);
        if(!this._profiles.some(p=>p.id===this._profileId))this._profileId='';
        this._model={...this._model,library_error:model.library_error};
        // Keep the native picker open; apply its updated options on blur.
        if(this.shadowRoot.activeElement || this._gesture)this._deferredRender=true;
        else this.render();
        return model;
      }catch(e){if(category===this._category && entry===this.config.config_entry_id){this._error=e.message||String(e);if(this.shadowRoot.activeElement || this._gesture)this._deferredRender=true;else this.render();}return null;}
    })();
    this._catalogRequest=request;
    try{return await request;}finally{if(this._catalogRequest===request)this._catalogRequest=null;}
  }
  async changeCategory(category) {
    if(category===this._category || !this.discardOK())return;
    this._category=category;this._draft=null;this._local=null;this._profile=null;this._profileId='';this._mappingEdits=null;
    this._selection.clear();this._policy={kind:category,normal_state:1,mapping_confirmed:true,floor_heating:true};this.invalidate(false);
    this.render();
    await this.loadCurrent();
    await this.listProfiles();
    this.render();
  }
  async loadProfile(shortcut=false) {
    if(!this._profileId || !this.discardOK())return null;
    const response=await this.openDraft(this._profileId);
    if(response && shortcut) {
      // Always stops at the review: no automatic acknowledgement or apply.
      await this.validate();
    }
    return response;
  }
  uniqueProfileName(name,excludeId=null) {
    const names=new Set(['Factory default (Heliotherm)',DE['Factory default (Heliotherm)']].map(n=>n.toLowerCase()));
    for(const p of this._profiles)if(p.id!==excludeId && (!p.category || p.category===this._category))names.add(p.name.trim().toLowerCase());
    const base=name.trim();let candidate=base;
    for(let n=2;names.has(candidate.toLowerCase());n++) {
      const suffix=` (${n})`;
      candidate=Array.from(base).slice(0,80-suffix.length).join('').trimEnd()+suffix;
    }
    return candidate;
  }
  async saveProfile(update=false) {
    if(!this._draft)return;
    if(update && this._profile?.read_only)return;
    if(this._local?.week.some(day=>day.includes(null))){this._error=this.t('Resolve unknown cells explicitly before saving or sending.');this.render();return;}
    const source=this._profile;
    const base=source?.read_only?`${this.t(source.name)} (${this.t('copy')})`:source?.name||'';
    const name=window.prompt(this.t('Profile name'),update?source?.name:this.uniqueProfileName(base));if(name===null)return;
    if(update && (!this._profile || !window.confirm(this.t('Confirm overwriting saved profile?'))))return;
    return this.call('save_time_program_profile',{category:this._category,name,draft:clone(this._draft),...this.revisionData(),...(update?{profile_id:this._profile.id,expected_profile_revision:this._profile.revision}:{})});
  }
  async renameProfile() {
    const profile=this._profiles.find(p=>p.id===this._profileId);if(!profile || profile.read_only)return;
    const name=window.prompt(this.t('New profile name'),this.uniqueProfileName(profile.name,profile.id));if(name===null)return;
    return this.call('rename_time_program_profile',{profile_id:profile.id,name,expected_profile_revision:profile.revision});
  }
  async deleteProfile() {
    const profile=this._profiles.find(p=>p.id===this._profileId);if(!profile || profile.read_only || !window.confirm(`${this.t('Delete this saved profile? The pump schedule is unchanged.')}\n\n${profile.name}`))return;
    return this.call('delete_time_program_profile',{profile_id:profile.id,expected_profile_revision:profile.revision,confirm:true});
  }
  async validate() {
    if(!this._draft)return;
    const normal=this._model?.mode_catalog?.find(c=>c.confirmed && c.semantic===(this.index===2?'normal':'charging'));
    this._policy={...this._policy,normal_state:normal?.state??1,mapping_confirmed:!!this._model?.mapping_valid};
    return this.call('validate_time_program',{draft:clone(this._draft),policy:clone(this._policy),fresh_read:true,expected_mapping_revision:this._model?.mapping_revision||0,...this.revisionData()});
  }
  async acknowledge() {
    const model=this._model;
    if(this._dirty || !model?.warning_ids?.every(id=>this._warningChecks.has(id)))return;
    return this.call('acknowledge_time_program_warnings',{draft_hash:this._validatedHash,warning_ids:[...this._warningChecks],...this.revisionData()});
  }
  requestSend() {
    if(this._busy || this.missing().length || !this._model?.can_apply)return;
    this._sendDialog=true;this.render();
  }
  async confirmSend(confirm) {
    if(!this._sendDialog)return;this._sendDialog=false;
    if(!confirm){this.render();return;}
    if(this._busy || this.missing().length || !this._model?.can_apply)return;
    return this.call(this._restoring?'restore_previous_time_program':'apply_time_program',{...(this._restoring?{}:{draft:clone(this._draft)}),draft_hash:this._validatedHash,confirm:true,...this.revisionData()});
  }
  paint() {
    if(!this._local || !Number.isInteger(this._mode) || this._mode<0 || this._mode>=(this._model?.metadata?.nos||0))return;
    if(this._local.paint(this._selection,this._mode))this.edit();
  }
  copyDay(targets) {
    if(!this._local || !targets.length)return;
    if(!window.confirm(`${this.t('Overwrite the local draft on these days?')}\n${targets.map(d=>this.days[d]).join(', ')}`))return;
    if(this._local.copy(this._day,targets))this.edit();
  }
  selectRange(day,start,end,add=this._add) {
    if(!Number.isInteger(start) || !Number.isInteger(end) || start<0 || end>96 || start>=end)return;
    this._selection.range(day,start,end-1,add);this._selection.anchor={day,i:start};this.updateSelection();
  }
  key(day,i,event) {
    let d=day,n=i;
    if(event.key==='Escape'){event.preventDefault();this._selection.clear();this.updateSelection();return;}
    if(event.key===' '){event.preventDefault();this._selection.choose(day,i,{ctrlKey:true});this.updateSelection();return;}
    if(event.key==='ArrowLeft')n=Math.max(0,i-1);else if(event.key==='ArrowRight')n=Math.min(95,i+1);
    else if(event.key==='ArrowUp')d=Math.max(0,day-1);else if(event.key==='ArrowDown')d=Math.min(6,day+1);else return;
    event.preventDefault();
    if(event.shiftKey){if(!this._selection.anchor)this._selection.anchor={day,i};this._selection.choose(d,n,event);this.updateSelection();}
    this._focus={day:d,i:n};
    const scope=event.currentTarget?.closest('.day-scroll') || this.shadowRoot;
    scope.querySelector(`[data-cell="${d}:${n}"]`)?.focus();
  }
  pointerDown(day,i,event) {
    if(event.button!==0 || event.isPrimary===false || this._gesture)return;
    this._ignoreClick=false;this._day=day;this._focus={day,i};
    const touch=event.pointerType==='touch';
    this._gesture={day,start:i,end:i,add:event.ctrlKey||event.metaKey||this._multiSelect,
      shift:event.shiftKey,touch,drag:!touch||this._selectMode,moved:false,
      x:event.clientX,y:event.clientY,before:new Set(this._selection.cells),
      pointerId:event.pointerId,target:event.currentTarget};
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }
  pointerMove(event) {
    const g=this._gesture;
    if(!g || (event.pointerId!==undefined && event.pointerId!==g.pointerId))return;
    if(Math.hypot(event.clientX-g.x,event.clientY-g.y)>8)g.moved=true;
    if(!g.drag)return; // Allow native scrolling and pointer cancellation.
    if(g.touch)event.preventDefault?.();
    const hit=this.shadowRoot.elementFromPoint?.(event.clientX,event.clientY)?.closest?.('[data-cell]')
      || document.elementFromPoint?.(event.clientX,event.clientY)?.closest?.('[data-cell]');
    let i;
    if(hit) {
      const [day,index]=hit.dataset.cell.split(':').map(Number);
      if(day!==g.day)return;
      i=index;
    } else if(!g.touch) {
      // Preserve mouse dragging beyond the row edges.
      const row=event.currentTarget.closest('[data-row]');if(!row)return;
      const rect=row.getBoundingClientRect();
      i=Math.max(0,Math.min(95,Math.floor((event.clientX-rect.left)/rect.width*96)));
    } else return;
    g.end=i;
    this._selection.cells=new Set(g.before);
    this._selection.range(g.day,g.shift && this._selection.anchor?.day===g.day?this._selection.anchor.i:g.start,i,g.add);
    this.updateSelection();
  }
  pointerEnd(cancel=false,event) {
    const g=this._gesture;
    if(!g || (event?.pointerId!==undefined && event.pointerId!==g.pointerId))return;
    this._selection.cells=new Set(g.before);
    if(!cancel && (g.drag || !g.moved)) {
      if(g.start===g.end) {
        const toggle=g.touch && !g.add && g.before.size===1 && g.before.has(`${g.day}:${g.end}`);
        if(toggle)this._selection.clear();
        else this._selection.choose(g.day,g.end,{shiftKey:g.shift,ctrlKey:g.add});
      }
      else {this._selection.range(g.day,g.shift && this._selection.anchor?.day===g.day?this._selection.anchor.i:g.start,g.end,g.add);if(!g.shift)this._selection.anchor={day:g.day,i:g.start};}
    }
    this._ignoreClick=true;this._gesture=null;
    if(g.target?.hasPointerCapture?.(g.pointerId))g.target.releasePointerCapture?.(g.pointerId);
    this.updateSelection();
    if(this._deferredRender)Promise.resolve().then(()=>{if(!this._gesture){this._deferredRender=false;this.render();}});
  }
  clickCell(day,i,event) {
    if(this._ignoreClick && event.detail!==0){this._ignoreClick=false;return;}
    this._ignoreClick=false;this._day=day;this._focus={day,i};
    this._selection.choose(day,i,{shiftKey:event.shiftKey,ctrlKey:event.ctrlKey||this._multiSelect,metaKey:event.metaKey});this.updateSelection();
  }
  selectionText(){return `${this.t('Selected cells')}: ${this._selection.cells.size} · `+this._selection.ranges().map(r=>`${this.days[r.day]} ${time(r.start)}–${time(r.end)}`).join(' · ');}
  updateSelection() {
    this.shadowRoot?.querySelectorAll('[data-cell]').forEach(e=>{const selected=this._selection.cells.has(e.dataset.cell);e.classList.toggle('selected',selected);e.setAttribute('aria-selected',String(selected));});
    const text=this.shadowRoot?.getElementById?.('selection-status');if(text)text.textContent=this.selectionText();
    const paint=this.shadowRoot?.getElementById?.('paint');if(paint)paint.disabled=!this._selection.cells.size || !!this._busy || !this._local;
  }
  grid(week,editable=false,detail=false,baseline=null) {
    const n=this.now(),days=detail?[this._day]:[0,1,2,3,4,5,6];
    const ruler=`<div class="ruler"><span class="day-label"></span><div>${Array.from({length:25},(_,h)=>`<span class="hour ${h%6?'minor':''}" style="left:${h/24*100}%">${h===24?'24':String(h).padStart(2,'0')}</span>`).join('')}</div></div>`;
    return `<div class="${detail?'day-scroll':'week-grid'}${editable?' editable-grid':''}${editable && this._selectMode?' select-mode':''}" ${editable?'role="grid" aria-label="'+esc(this.t('Draft schedule'))+'"':''}>${ruler}${days.map(d=>{
      const row=week[d],bars=toDraft([row]).entries[0];
      const replaced=i=>editable && baseline?.[d]?.[i]!=null && baseline[d][i]!==row[i];
      const description=i=>replaced(i)?`${this.t('was')} ${this.label(baseline[d][i])}, ${this.t('now')} ${this.label(row[i])}`:this.label(row[i]);
      return `<div class="week-row" role="row"><button class="day-label" data-day="${d}" title="${esc(this.days[d])}" ${this._busy?'disabled':''}>${esc(this.days[d].slice(0,3))}</button><div class="timeline" data-row="${d}">
      ${bars.map(e=>`<span class="bar ${this.styleMode(e.state)}" style="left:${slot(e.start)/96*100}%;width:${(slot(e.end)-slot(e.start))/96*100}%" title="${esc(`${this.days[d]} ${e.start}–${e.end}: ${this.label(e.state)}`)}"></span>`).join('')}
      ${row.map((mode,i)=>replaced(i)?`<span aria-hidden="true" class="replaced old-${this.styleMode(baseline[d][i])}" style="left:${i/96*100}%;width:${100/96}%">${this.replacedMark()}</span>`:'').join('')}
      ${editable?row.map((mode,i)=>`<button role="gridcell" tabindex="${(this._focus?.day??this._day)===d && (this._focus?.i??0)===i?'0':'-1'}" class="cell ${replaced(i)?'changed':''} ${this._selection.cells.has(`${d}:${i}`)?'selected':''}" data-cell="${d}:${i}" aria-selected="${this._selection.cells.has(`${d}:${i}`)}" aria-label="${esc(`${this.days[d]} ${time(i)}–${time(i+1)} ${description(i)}`)}" title="${esc(`${time(i)}–${time(i+1)} ${description(i)}`)}" ${this._busy?'disabled':''}></button>`).join(''):''}
      <div class="ticks"></div><span class="now" data-now="${d}" style="left:${n.percent}%" ${n.day!==d?'hidden':''} title="${esc(this.t('Current time; not compressor activity. Global mode and overrides can supersede the time program.'))}"></span></div></div>`;
    }).join('')}</div>`;
  }
  replacedMark() {
    // Stretch the cross to each slot, including the narrow phone overview.
    return '<svg aria-hidden="true" viewBox="0 0 10 20" preserveAspectRatio="none"><path d="M1 2L9 18M9 2L1 18" vector-effect="non-scaling-stroke"/></svg>';
  }
  legendHTML(nos=0,{changed=false}={}) {
    return `<div class="legend">${Array.from({length:nos},(_,i)=>`<span><i class="swatch ${this.styleMode(i)}"></i>${esc(this.label(i))}</span>`).join('')}<span><i class="swatch unknown"></i>${esc(this.t('Unknown'))}</span>${changed?`<span><i class="swatch changed-key" aria-hidden="true">${this.replacedMark()}</i>${esc(this.t('Changed (old value shown lighter with ×)'))}</span>`:''}</div>`;
  }
  diffHTML() {
    const diff=this._model?.diff;if(!diff)return '';
    return `<section class="diff"><h3>${esc(this.t('Changes compared with pump'))}</h3>${this._dirty?`<p>${esc(this.t('Previous comparison — validate again'))}</p>`:''}<p>${esc(this.t('Compared with pump read at'))} ${esc(this.stamp(diff.baseline_read_at||this._model.baseline_read_at))} · ${diff.changed_minutes} ${esc(this.t('minutes'))}</p>${diff.days.map(day=>`<details ${day.ranges.length?'open':''}><summary>${esc(this.days[day.day])}: ${day.changed_minutes} ${esc(this.t('minutes'))} · ${esc(this.t('Entries'))} ${day.old_entries??'?'} → ${day.new_entries??'?'} / ${day.capacity}</summary>${day.baseline_unknown?`<p>${esc(this.t('Baseline unavailable'))}</p>`:''}${day.ranges.length?`<ul>${day.ranges.map(r=>`<li>${esc(r.start)}–${esc(r.end)}: ${esc(this.label(r.from_state))} → ${esc(this.label(r.to_state))}</li>`).join('')}</ul>`:`<p>${esc(this.t('No changes'))}</p>`}</details>`).join('')}</section>`;
  }
  finding(f) {
    const code=f.id.split(':')[0];
    if(code==='complete_mapping')return this.t('Confirm all used mode mappings');
    if(this._hass?.language?.startsWith('de')) {
      if(f.message_de)return f.message_de;
      if(code==='capacity') {const day=this._model?.diff?.days?.[f.day];return `${this.days[f.day]} benötigt ${day?.new_entries??'?'} Einträge; Regler unterstützt ${day?.capacity??7}. Einen Wechsel zusammenführen oder entfernen.`;}
      return FINDINGS_DE[code]||f.message;
    }
    if(code==='profile_incompatible')return 'Profile metadata, controller/firmware or mapping differs. Review and explicitly update the profile, or load the current pump program.';
    if(code==='normal_mapping_conflict')return this.t('Normal code conflicts with the semantic mapping');
    return f.message;
  }
  findingList(findings) {
    return (findings||[]).map(f=>`<li class="${esc(f.severity)}">${f.day!=null?'<b>'+esc(this.days[f.day])+': </b>':''}${esc(this.finding(f))}${f.severity==='warning'?`<label><input type="checkbox" data-warning="${esc(f.id)}" ${this._warningChecks.has(f.id)?'checked':''} ${this._dirty || this._busy?'disabled':''}>${esc(this.t('I have reviewed this warning'))}</label>`:''}<small>${esc(this._hass?.language?.startsWith('de')?(f.source_de||this.t(f.source)):f.source)}</small></li>`).join('');
  }
  render() {
    if(!this.shadowRoot || !this.config || !this.shadowRoot.getElementById)return;
    const root=this.shadowRoot,active=root.activeElement,focusId=active?.id,focusCell=active?.dataset?.cell;
    const scrolls=[...root.querySelectorAll('[data-scroll]')].map(e=>[e.dataset.scroll,e.scrollLeft,e.scrollTop]);
    const opens=new Set([...root.querySelectorAll('details[id][open]')].map(e=>e.id));
    const view=this._currentViews[this._category];
    const t=s=>esc(this.t(s)),m=this._draft?(this._model||{}):{...this._model,...(view?{metadata:view.metadata,current_program:view.current_program,current_state:'read',baseline_read_at:view.read_at,mode_catalog:view.mode_catalog,current_profile_names:view.current_profile_names||[]}:{metadata:null,current_program:null,current_state:'unknown'})},busy=this._busy?'disabled':'',loaded=m.metadata?.index===this.index;
    const metadata=loaded?m.metadata:null,nos=metadata?.nos||0,current=loaded && m.current_state==='read'?toCells(m.current_program,nos):toCells(null);
    const draft=this._local?.week||toCells(this._draft,nos),unknown=draft.some(day=>day.includes(null));
    const options=(end=false,value=0)=>Array.from({length:end?97:96},(_,i)=>`<option value="${i}" ${i===value?'selected':''}>${time(i)}</option>`).join('');
    const mapping=this._mappingEdits||(m.mapping_valid?m.mode_mapping?.mapping:{});
    const semanticChoices=this.index===2?['setback','normal','boost']:['minimum','charging'];
    const chosen=this._profiles.find(p=>p.id===this._profileId);
    root.innerHTML=`<style>
      :host{display:block;color:var(--primary-text-color,#202937);font:14px/1.5 system-ui,sans-serif}*{box-sizing:border-box}ha-card{display:block;background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#dce1e7);border-radius:16px;padding:20px;overflow:hidden}h2{font-size:1.35rem;margin:0}h3{font-size:1rem;margin:8px 0}p{margin:8px 0}.muted,small{color:var(--secondary-text-color,#657080)}small{display:block}button,select,input{font:inherit;color:inherit;background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#b6c0cc);border-radius:7px;min-height:38px;padding:7px 10px;max-width:100%}button{cursor:pointer}button:disabled{opacity:.5;cursor:default}button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid var(--primary-color,#007f91);outline-offset:2px}button.primary{background:var(--primary-color,#087f8c);color:white;border-color:transparent}.controls,.tabs,.legend{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}.tabs button[aria-selected=true]{border-color:var(--primary-color,#087f8c);box-shadow:inset 0 -3px var(--primary-color,#087f8c)}.tabs{justify-content:space-between}.status{font-size:.8rem;border:1px solid var(--divider-color,#dce1e7);padding:5px 9px;border-radius:20px}.controls label{display:flex;gap:6px;align-items:center}.controls select{max-width:280px}section{margin:18px 0}.schedule{padding:12px;border:1px solid var(--divider-color,#dce1e7);border-radius:10px}.week-row,.ruler{display:grid;grid-template-columns:42px minmax(0,1fr);align-items:center;margin:5px 0;gap:8px}.day-label{font-weight:600;font-size:.75rem;padding:0;border:0;background:transparent}.ruler{height:20px;margin-top:22px;font-size:.68rem;color:var(--secondary-text-color,#657080)}.ruler>div{position:relative;height:100%}.hour{position:absolute;transform:translateX(-50%)}.hour.minor:nth-child(even){visibility:hidden}.timeline{height:30px;position:relative;display:grid;grid-template-columns:repeat(96,minmax(0,1fr));border:1px solid var(--divider-color,#b6c0cc);border-radius:3px}.bar{position:absolute;top:0;bottom:0;pointer-events:none}.setback,.swatch.setback{background:#1689c6}.normal,.swatch.normal{background:#9465c9}.boost,.swatch.boost{background:#db4a46}.minimum,.swatch.minimum{background:#91999f}.charging,.swatch.charging{background:#37965c}.unknown,.swatch.unknown{background:repeating-linear-gradient(135deg,#858c9340 0 3px,#858c9380 3px 5px)}.cell{z-index:2;position:relative;min-width:0;min-height:0;width:100%;height:100%;padding:0;border:0;border-radius:0;background:transparent;touch-action:auto;user-select:none;-webkit-user-select:none}.cell.selected{outline:2px solid var(--primary-text-color,#152331);outline-offset:-2px;background:repeating-linear-gradient(45deg,transparent 0 3px,#ffffff80 3px 5px);z-index:3}.cell:focus{outline:3px solid #ffce31;outline-offset:0;z-index:4}.ticks{position:absolute;inset:0;pointer-events:none;z-index:1;background-image:linear-gradient(to right,#20293655 1px,transparent 1px),linear-gradient(to right,#20293625 1px,transparent 1px);background-size:calc(100% / 24) 100%,calc(100% / 96) 100%}.now{position:absolute;top:-3px;bottom:-3px;width:3px;background:var(--primary-text-color,#111);box-shadow:0 0 0 1px var(--card-background-color,#fff);pointer-events:none;z-index:5}.legend{font-size:.8rem}.legend span{display:inline-flex;gap:5px;align-items:center}.swatch{display:inline-block;width:16px;height:13px;border-radius:2px;border:1px solid #20293660}.selection-status{font-size:.85rem;overflow-wrap:anywhere}details{border-top:1px solid var(--divider-color,#dce1e7);padding:10px 0}summary{cursor:pointer}ul{padding-left:20px}.critical,.error{color:var(--error-color,#ba2533)}.warning{border-left:3px solid #ce8b19;padding-left:9px}.findings li{margin:10px 0}.findings label{display:flex;align-items:center;gap:8px}input[type=checkbox]{min-height:24px;min-width:24px}button[aria-pressed=true]{background:var(--primary-color,#087f8c);color:white}.select-mode .cell{touch-action:none}.day-scroll{min-width:4276px}.day-scroll .timeline{height:44px}.scroll{overflow:auto}.toolbar{border-radius:9px;background:var(--secondary-background-color,#f2f5f7);padding:12px}.profile-name{overflow-wrap:anywhere}.send-review{position:fixed;inset:8vh max(16px,calc((100vw - 600px)/2));max-height:84vh;overflow:auto;z-index:9999;background:var(--card-background-color,#fff);color:inherit;border:2px solid var(--primary-color,#087f8c);border-radius:14px;padding:20px;box-shadow:0 0 0 100vmax #0008}.send-review dl{display:grid;grid-template-columns:1fr 2fr;gap:8px}.send-review dd{margin:0;overflow-wrap:anywhere}.diff{font-size:.9rem}.mapping-grid label{display:flex;justify-content:space-between;gap:8px;margin:7px 0}.actions{border-top:1px solid var(--divider-color,#dce1e7);padding-top:12px}.phone-hint{display:none}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:280px;overflow:auto;font-size:.75rem}
      @media(max-width:600px){ha-card{padding:12px;border-radius:12px}h2{font-size:1.1rem}.minor{display:none!important}.week-row,.ruler{grid-template-columns:28px minmax(0,1fr);gap:4px}.schedule{padding:8px}.week-grid:not(.editable-grid) .timeline{height:25px}.editable-grid{min-width:4276px}.editable-grid .timeline{height:46px}.editable-grid .day-label{position:sticky;left:0;z-index:6;background:var(--card-background-color,#fff)}.phone-hint{display:block}.controls label{flex-wrap:wrap}.controls select{max-width:100%}button,select,input{min-height:44px}.controls button{flex:0 1 auto}.day-label{min-height:30px}.send-review{inset:12px;max-height:calc(100vh - 24px)}.legend{gap:5px}.tabs .status{width:100%}.toolbar{padding:8px}.mapping-grid label{flex-wrap:wrap}}
      :host{min-width:0}small{font-size:.875rem;overflow-wrap:anywhere}.controls>*{min-width:0}.controls label{max-width:100%}.controls select{min-width:0}section{margin:12px 0}.controls,.tabs,.legend{margin:8px 0;gap:6px}.help{border:0;padding:4px 0}.help>summary{display:flex;align-items:center;justify-content:center;width:28px;height:28px;min-height:28px;border:1px solid var(--divider-color);border-radius:50%;font-weight:600;list-style:none}.help>summary::-webkit-details-marker{display:none}.help[open]>summary{background:var(--secondary-background-color)}.day-label{font-size:.875rem}.ruler{font-size:.75rem}.legend{font-size:.875rem}
      @media(max-width:600px){ha-card{padding:10px}.controls label{flex:1 1 140px}.controls label select{flex:1;min-width:0}section{margin:10px 0}.schedule{padding:6px}.send-review dl{grid-template-columns:1fr}.status{font-size:.875rem}.ruler{margin-top:14px}}
      /* New color remains above; the lower 60% shows the replaced pump mode. */
      .old-setback{--old-color:#1689c6}.old-normal{--old-color:#9465c9}.old-boost{--old-color:#db4a46}.old-minimum{--old-color:#91999f}.old-charging{--old-color:#37965c}.old-unknown{--old-color:var(--secondary-text-color,#657080)}
      .replaced{position:absolute;top:40%;bottom:0;z-index:1;background:color-mix(in srgb,var(--old-color) 42%,var(--card-background-color,#fff));border-top:1px solid var(--card-background-color,#fff)}
      .replaced,.replaced *,.changed-key,.changed-key *{pointer-events:none}
      .replaced svg,.changed-key svg{display:block;width:100%;height:100%;fill:none;stroke:var(--primary-text-color,#202937);stroke-width:.8}
      .changed-key{background:color-mix(in srgb,var(--primary-text-color,#202937) 25%,var(--card-background-color,#fff))}
      @media(prefers-contrast:more){.replaced{background:color-mix(in srgb,var(--old-color) 60%,var(--card-background-color,#fff))}.replaced svg,.changed-key svg{stroke-width:1.4}.bar{border:1px solid currentColor}.cell.selected{outline-width:3px}}
    </style><ha-card><h2>${t('Schedule editor')}</h2><div class="tabs" role="tablist"><div>${['heating','hot_water'].map(c=>`<button role="tab" data-category="${c}" aria-selected="${c===this._category}" ${busy}>${t(c==='heating'?'Heating':'Hot water')}</button>`).join('')}</div><span class="status">${t('Allow writes')}: <b>${t(m.writes_enabled?'ON':'OFF')}</b></span></div>
      <div class="controls"><button id="load" ${busy}>${t('Reload from pump')}</button>${this._draft?`<button id="refresh" ${busy} ${!metadata?'disabled':''}>${t('Refresh baseline')}</button><button id="close-draft" ${busy}>${t('Discard draft / Close editor')}</button>`:`<button id="edit-current" ${busy} ${!view?'disabled':''}>${t('Edit a copy of current schedule')}</button><button id="new-schedule" ${busy} ${!view?'disabled':''}>${t('New schedule')}</button>${this._model?.draft?`<button id="resume-draft" ${busy} >${t('Resume draft')}</button><button id="close-draft" ${busy}>${t('Discard draft')}</button><small>${t('An existing server draft is available.')}</small>`:''}`}</div>
      <div class="controls"><select id="profiles" aria-label="${t('Profiles')}" ${busy}><option value="">${t('Start from profile…')}</option>${this._profiles.map(p=>`<option value="${esc(p.id)}" ${p.id===this._profileId?'selected':''}>${p.read_only?t(p.name):esc(p.name)} · ${p.read_only?t('Built-in, read-only'):`${t('Saved')} · ${t('version')} ${esc(p.revision)}`}</option>`).join('')}</select><button id="profile-load" ${busy} ${!chosen?'disabled':''}>${t('Use as starting point')}</button><button id="profile-apply" ${busy} ${!chosen?'disabled':''}>${t('Apply profile…')}</button><button id="rename" ${busy} ${!chosen || chosen.read_only?'disabled':''}>${t('Rename')}</button><button id="delete" ${busy} ${!chosen || chosen.read_only?'disabled':''}>${t('Delete')}</button></div>
      ${chosen?.read_only || this._profile?.read_only?`<small>${t(this.index===2?'Factory default: Monday–Sunday 00:00–24:00 Normal. Unspecified heating periods remain Normal.':'Factory default: Monday–Sunday 00:00–24:00 On. Unspecified hot-water periods are Off (minimum maintenance at WW_min, +5 K).')} ${t('web control 321 manual, pp.10–11. Save as creates an editable copy.')}</small>`:''}
      ${m.library_error?`<p class="error">${t('This library is damaged or has an unsupported version. Repair the HA Store from a backup; no approval was restored.')}</p>`:''}
      <section class="schedule"><h3>${t('Current schedule (on pump)')}</h3><small class="profile-name">${esc(loaded && m.current_state==='read'?(m.current_profile_names?.join(', ')||this.t('Custom / no matching saved profile')):this.t('Current state unavailable'))}</small>${this.grid(current)}${this.legendHTML(nos)}<small>${t('read at')}: ${esc(this.stamp(loaded?m.baseline_read_at:null))} · ${esc(metadata?`#${metadata.index} ${metadata.name} · ead=${metadata.ead}, nos=${metadata.nos}, ste=${metadata.ste}, nod=${metadata.nod}`:this.t('Unknown'))}</small></section>
      ${this._draft?`<section class="schedule"><h3>${t('Draft schedule')} <small class="profile-name">${esc(this.draftName())}</small></h3><div class="controls"><button id="select-mode" aria-pressed="${!!this._selectMode}">${t('Select')}</button><button id="multi-select" aria-pressed="${!!this._multiSelect}">${t('Multi-select')}</button><button id="select-day">${t('Select day')}</button></div><small>${t('Select mode: drag slots to select. Turn off to scroll; taps still select. Multi-select adds or removes tapped slots.')}</small><div class="scroll" data-scroll="week">${this.grid(draft,true,false,current)}</div>${this.legendHTML(nos,{changed:true})}<small>${t('Current time; not compressor activity. Global mode and overrides can supersede the time program.')}</small></section>
      <div class="toolbar"><p id="selection-status" class="selection-status" aria-live="polite">${esc(this.selectionText())}</p><div class="controls"><select id="mode" aria-label="${t('Mode')}" ${busy}>${Array.from({length:nos},(_,i)=>`<option value="${i}" ${this._mode===i?'selected':''}>${esc(this.label(i))}</option>`).join('')}</select><button id="paint" ${busy} ${!this._selection.cells.size || !this._local?'disabled':''}>${t('Set mode for selection')}</button><button id="clear">${t('Clear selection')}</button><button id="undo" ${busy} ${!this._local?.undo.length?'disabled':''}>${t('Undo')}</button><button id="redo" ${busy} ${!this._local?.redo.length?'disabled':''}>${t('Redo')}</button></div>
      <p class="phone-hint muted">${t('Selection alone makes no changes. Choose a mode, then Set mode.')}</p><div class="controls"><label>${t('Day')} <select id="day">${this.days.map((day,d)=>`<option value="${d}" ${d===this._day?'selected':''}>${esc(day)}</option>`).join('')}</select></label><label>${t('Start')} <select id="range-start">${options(false,this._rangeStart??24)}</select></label><label>${t('End')} <select id="range-end">${options(true,this._rangeEnd??32)}</select></label><label><input type="checkbox" id="add-selection" ${this._add?'checked':''}>${t('Add selection')}</label><button id="select-range">${t('Select range')}</button></div>
      <details id="day-detail" ${opens.has('day-detail')?'open':''}><summary>${esc(this.days[this._day])} · 00:00–24:00</summary><div class="scroll" data-scroll="detail">${this.grid(draft,true,true,current)}</div><ul>${toDraft(draft).entries[this._day].map(e=>`<li>${esc(e.start)}–${esc(e.end)}: ${esc(this.label(e.state))}</li>`).join('')}</ul></details>
      <div class="controls"><label>${t('Copy this day to…')} <select id="copy-target"><option value="all">${t('All days')}</option><option value="weekdays">${t('Weekdays')}</option><option value="weekend">${t('Weekend')}</option><option value="custom">${t('Selected days')}</option></select></label><button id="copy" data-copy="${this._day}" ${busy} ${!this._local?'disabled':''}>${t('Copy day')}</button></div><div id="copy-days" hidden>${this.days.map((day,d)=>`<label><input type="checkbox" data-copy-day="${d}">${esc(day)}</label>`).join('')}</div></div>
      ${this._draft?`<small>${this._draft.entries.map((day,d)=>`${this.days[d].slice(0,3)}: ${day.length}/${Math.min(metadata?.ead||7,7)}`).join(' · ')} ${unknown?' · '+t('Resolve unknown cells explicitly before saving or sending.'):''}</small>`:''}
      <details id="mapping-detail" ${opens.has('mapping-detail')?'open':''}><summary>${t(m.mapping_valid?'Optional mode mapping override':'Unverified mode mapping')}</summary><p>${t('Verified default for firmware 2.03N; override only after checking your controller. Labels never translate numeric payloads.')}</p><div class="mapping-grid">${Array.from({length:nos},(_,i)=>`<label>${t('Mode')} ${i}<select data-map="${i}" ${busy}><option value="">${t('Unverified')}</option>${semanticChoices.map(s=>`<option value="${s}" ${mapping?.[String(i)]===s?'selected':''}>${t(SEMANTIC_LABELS[s])}</option>`).join('')}</select></label>`).join('')}</div><button id="mapping-save" ${busy} ${!metadata?'disabled':''}>${t('Confirm mode mapping')}</button></details>
      <div class="controls">${this.index===2?`<label><input type="checkbox" id="floor" ${this._policy.floor_heating?'checked':''} ${busy}>${t('Floor heating')}</label>`:''}</div>
      <details class="help" id="advice" ${opens.has('advice')?'open':''}><summary aria-label="${t('Help and recommendations')}" title="${t('Help and recommendations')}">?</summary><p>${t('Click selects; Ctrl/Cmd toggles; Shift extends within one day. Drag selects only. Arrows move, Shift+arrows extend, Space toggles, Escape clears. On phones enable Select to drag; disable it to scroll. Multi-select toggles tapped slots. Select day selects the focused day.')}</p><p>${t('Full 00:00–24:00 draft coverage is integration policy, stricter than manual fallback. DHW Minimum maintains the minimum target; it is not hard-Off. Heating Normal follows the existing curve, not continuous compressor operation.')}</p><p>${t('For slow floor heating, review comfort and recovery after setback. For a buffer-fed fresh-water station, plan charging before demand and verify plumbing separately. No temperature, curve, hysteresis or global mode is changed here.')}</p><ul>${this.findingList((m.findings||[]).filter(f=>f.severity==='info'))}</ul></details>
      <div class="controls actions"><button class="primary" id="check" ${busy} ${!this._draft?'disabled':''}>${t('Validate')}</button><button id="save-profile" ${busy} ${!this._draft?'disabled':''}>${t('Save profile')} / ${t('Save as')}</button><button id="update-profile" ${busy} ${!this._profile || this._profile.read_only?'disabled':''}>${t('Update profile')}</button><button class="primary" id="save" ${busy} ${this.missing().length || !m.can_apply?'disabled':''}>${t('Send to heat pump')}</button></div>
      <small id="gate-reasons">${esc(this.missing().join(' · '))}</small><p id="draft-status" aria-live="polite">${this._dirty?t('Needs validation / not sendable'):esc(m.status==='applied'?this.t('Sent to heat pump'):m.status==='warnings'?this.t('Acknowledge every warning'):m.status==='critical'?this.t('Fix critical findings'):this.t('Validate'))}</p><p class="error" role="alert">${esc(this._error)}</p><p role="status">${esc(this._notice)}</p>
      <ul class="findings">${this.findingList((m.findings||[]).filter(f=>f.severity!=='info'))}</ul><button id="ack" ${busy} ${this._dirty || m.critical_count || !m.warning_ids?.length || !m.warning_ids?.every(id=>this._warningChecks.has(id))?'disabled':''}>${t('Acknowledge selected warnings')}</button>
      ${this.diffHTML()}<details id="recovery" ${opens.has('recovery')?'open':''}><summary>${t('Recovery evidence')}</summary><p class="error">${esc(m.apply_error||'')} ${esc(m.recovery_read_error||'')}</p><div class="controls"><button id="previous" ${busy} ${!m.previous_program?'disabled':''}>${t('Use previous program as draft')}</button><button id="restore" ${busy} ${!this._restoring || this.missing().length || !m.can_apply?'disabled':''}>${t('Restore previous program')}</button></div><pre>${esc(JSON.stringify({previous_program:m.previous_program,actual_program:m.actual_program,possible_partial_write:m.possible_partial_write,recovery_storage_error:m.recovery_storage_error},null,2))}</pre></details>
      ${this._sendDialog?`<div class="send-review" role="dialog" aria-modal="true" aria-label="${t('Send schedule')}"><h3>${t(this._restoring?'Restore previous program':'Send schedule')}</h3><dl><dt>${t('Controller')}</dt><dd>${esc(m.controller?.serial||m.metadata?.name||this.config.config_entry_id)} ${esc(m.controller?.firmware||'')}</dd><dt>${t('Category')}</dt><dd>${t(this.index===2?'Heating':'Hot water')}</dd><dt>${t('Profile')}</dt><dd>${esc(this.draftName())}</dd><dt>${t('Changed days')}</dt><dd>${esc(m.diff?.days?.filter(d=>d.changed_cells).map(d=>this.days[d.day]).join(', ')||this.t('No changes'))}</dd><dt>${t('Numeric modes')}</dt><dd>${esc([...new Set(this._draft?.entries.flat().map(e=>e.state))].map(n=>this.label(n)).join(', '))}</dd><dt>${t('Compared with pump read at')}</dt><dd>${esc(this.stamp(m.baseline_read_at))}</dd></dl>${this.diffHTML()}<p>${t('Multiple slot writes can partially fail. No automatic retry or rollback.')}</p><div class="controls"><button id="send-cancel">${t('Cancel')}</button><button class="primary" id="send-confirm">${t('Send schedule')}</button></div></div>`:''}
      `:''}
      <p class="error" role="alert">${esc(this._readErrors[this._category]||(!this._draft?this._error:''))}</p>${this._readErrors[this._category]?`<button id="retry">${t('Retry')}</button>`:''}
    </ha-card>`;
    const by=id=>root.getElementById(id),bind=(id,event,fn)=>{const e=by(id);if(e)e[event]=fn;};
    root.querySelectorAll('[data-category]').forEach(e=>e.onclick=()=>this.changeCategory(e.dataset.category));
    bind('retry','onclick',()=>this.loadCurrent(true));bind('edit-current','onclick',()=>this.openDraft());bind('new-schedule','onclick',()=>this.openDraft('factory_default_'+this._category));bind('resume-draft','onclick',()=>this.resumeDraft());bind('close-draft','onclick',()=>this.closeDraft());
    bind('load','onclick',()=>this.loadPump());bind('refresh','onclick',()=>this.call('refresh_time_program_baseline',this.revisionData()));
    for(const event of ['onfocus','onpointerdown','onkeydown'])bind('profiles',event,()=>{void this.listProfiles(true);});
    bind('profiles','onchange',e=>{this._profileId=e.target.value;this.render();});bind('profile-load','onclick',()=>this.loadProfile());bind('profile-apply','onclick',()=>this.loadProfile(true));bind('rename','onclick',()=>this.renameProfile());bind('delete','onclick',()=>this.deleteProfile());
    bind('save-profile','onclick',()=>this.saveProfile());bind('update-profile','onclick',()=>this.saveProfile(true));bind('check','onclick',()=>this.validate());bind('ack','onclick',()=>this.acknowledge());
    bind('save','onclick',()=>this.requestSend());bind('restore','onclick',()=>this.requestSend());bind('send-cancel','onclick',()=>this.confirmSend(false));bind('send-confirm','onclick',()=>this.confirmSend(true));
    bind('select-mode','onclick',()=>{this._selectMode=!this._selectMode;this.render();});
    bind('multi-select','onclick',()=>{this._multiSelect=!this._multiSelect;this.render();});
    bind('select-day','onclick',()=>this.selectRange(this._day,0,96,this._multiSelect));
    bind('mode','onchange',e=>{this._mode=Number(e.target.value);});bind('paint','onclick',()=>this.paint());bind('clear','onclick',()=>{this._selection.clear();this.updateSelection();});
    bind('undo','onclick',()=>{if(this._local?.history())this.edit();});bind('redo','onclick',()=>{if(this._local?.history(true))this.edit();});
    bind('day','onchange',e=>{this._day=Number(e.target.value);this._focus={day:this._day,i:0};this.render();});
    root.querySelectorAll('[data-day]').forEach(e=>e.onclick=()=>{this._day=Number(e.dataset.day);this.render();if(by('day-detail'))by('day-detail').open=true;});
    bind('range-start','onchange',e=>{this._rangeStart=Number(e.target.value);});bind('range-end','onchange',e=>{this._rangeEnd=Number(e.target.value);});bind('add-selection','onchange',e=>{this._add=e.target.checked;});
    bind('select-range','onclick',()=>this.selectRange(this._day,Number(by('range-start').value),Number(by('range-end').value)));
    bind('copy-target','onchange',e=>{by('copy-days').hidden=e.target.value!=='custom';});
    bind('copy','onclick',()=>{const target=by('copy-target').value;this.copyDay(target==='all'?[0,1,2,3,4,5,6]:target==='weekdays'?[0,1,2,3,4]:target==='weekend'?[5,6]:[...root.querySelectorAll('[data-copy-day]:checked')].map(e=>Number(e.dataset.copyDay)));});
    bind('floor','onchange',e=>{this._policy.floor_heating=e.target.checked;this.invalidate();});
    root.querySelectorAll('[data-map]').forEach(e=>e.onchange=()=>{this._mappingEdits=Object.fromEntries([...root.querySelectorAll('[data-map]')].map(x=>[x.dataset.map,x.value||null]));this.invalidate(false);this.updateGates();});
    bind('mapping-save','onclick',()=>{const map=Object.fromEntries([...root.querySelectorAll('[data-map]')].map(e=>[e.dataset.map,e.value||null]));if(window.confirm(this.t('Verify each numeric code on this controller before assigning a name. Labels never translate numeric payloads.')))this.call('set_time_program_mode_mapping',{program_index:this.index,mapping:map,expected_mapping_revision:m.mapping_revision||0,confirmed:true,...this.revisionData()});});
    root.querySelectorAll('[data-warning]').forEach(e=>e.onchange=()=>{if(e.checked)this._warningChecks.add(e.dataset.warning);else this._warningChecks.delete(e.dataset.warning);by('ack').disabled=this._dirty || !!m.critical_count || !m.warning_ids?.every(id=>this._warningChecks.has(id));});
    bind('previous','onclick',()=>{if(!this.discardOK())return;this.adoptDraft(m.previous_program);this._profile=null;this._restoring=true;this.render();});
    root.querySelectorAll('[data-cell]').forEach(e=>{
      const [d,i]=e.dataset.cell.split(':').map(Number);
      e.onclick=event=>this.clickCell(d,i,event);e.onkeydown=event=>this.key(d,i,event);
      e.onpointerdown=event=>this.pointerDown(d,i,event);e.onpointermove=event=>this.pointerMove(event);e.onpointerup=event=>this.pointerEnd(false,event);e.onpointercancel=event=>this.pointerEnd(true,event);e.onlostpointercapture=event=>this.pointerEnd(true,event);
      e.onfocus=()=>{this._focus={day:d,i};this._day=d;if(by('day'))by('day').value=String(d);};
    });
    for(const [key,left,top] of scrolls){const e=root.querySelector(`[data-scroll="${key}"]`);if(e){e.scrollLeft=left;e.scrollTop=top;}}
    if(focusId)by(focusId)?.focus();else if(focusCell)root.querySelector(`[data-cell="${focusCell}"]`)?.focus();
    if(this._sendDialog) {
      const dialog=root.querySelector('.send-review');by('send-cancel')?.focus();
      if(dialog)dialog.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();this.confirmSend(false);}if(e.key==='Tab'){const buttons=[by('send-cancel'),by('send-confirm')];if(e.shiftKey && root.activeElement===buttons[0]){e.preventDefault();buttons[1].focus();}else if(!e.shiftKey && root.activeElement===buttons[1]){e.preventDefault();buttons[0].focus();}}};
    }
  }
}
if(!customElements.get('htha-schedule-scratchpad-card'))customElements.define('htha-schedule-scratchpad-card',HthaScheduleScratchpadCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(c=>c.type==='htha-schedule-scratchpad-card'))window.customCards.push({type:'htha-schedule-scratchpad-card',name:'HTHA schedule editor',description:'Local selection, persistent HA profiles and guarded weekly schedule review.'});
// Pure logic is exposed for the Node built-in runner and offline fixture only.
window.HthaScheduleEditor={Selection,LocalWeek,toCells,toDraft,time,slot,esc};
