/* Explicit draft -> check -> acknowledgement -> confirmed apply. No write on edit. */
const clone = value => JSON.parse(JSON.stringify(value));
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const DE = {
  'Schedule scratchpad':'Zeitprogramm-Entwurf', 'Load from pump':'Von Wärmepumpe laden',
  'Check':'Prüfen', 'Acknowledge warnings':'Warnungen bestätigen', 'Save to heat pump':'An Wärmepumpe senden',
  'Heating':'Heizung', 'Hot water':'Warmwasser', 'Normal code':'Normal-Code',
  'I verified this numeric Normal code on my controller':'Ich habe diesen numerischen Normal-Code an meinem Regler geprüft',
  'Floor heating':'Fußbodenheizung', 'Unsaved local edits — check again':'Lokale Änderungen — erneut prüfen',
  'Draft only; no pump change until confirmed Save. Allow writes must be ON separately.':'Nur Entwurf; keine Änderung an der Wärmepumpe vor bestätigtem Speichern. Schreibzugriff muss separat eingeschaltet sein.',
  'Load discards this draft. Continue?':'Laden verwirft diesen Entwurf. Fortfahren?',
  'Send the checked weekly schedule to the heat pump? Multiple writes can partially fail.':'Geprüftes Wochenprogramm an die Wärmepumpe senden? Mehrere Schreibvorgänge können teilweise fehlschlagen.',
  'Add interval':'Intervall hinzufügen', 'Remove':'Entfernen', 'Apply unavailable: validate, acknowledge, and separately enable Allow writes.':'Speichern gesperrt: prüfen, bestätigen und Schreibzugriff separat aktivieren.',
};
class HthaScheduleScratchpadCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity || !config.config_entry_id) throw new Error('entity and config_entry_id required');
    this.config = config;
    this.attachShadow({mode:'open'});
    this._dirty = true;
    this._policy = {kind:'heating', normal_state:1, mapping_confirmed:false, floor_heating:true};
  }
  set hass(hass) {
    this._hass = hass;
    const attributes = hass.states[this.config.entity]?.attributes;
    if (attributes && (!this._model || (attributes.revision > this._model.revision || (attributes.revision === this._model.revision && attributes.can_apply !== this._model.can_apply)))) {
      if (this._validatedHash && attributes.draft_hash !== this._validatedHash) this._dirty = true;
      this._model = clone(attributes);
      if (!this._draft && attributes.draft) this._draft = clone(attributes.draft);
      this.render();
    } else if (!this.shadowRoot.innerHTML) this.render();
  }
  t(text) { return this._hass?.language?.startsWith('de') ? (DE[text] || text) : text; }
  getCardSize() { return 10; }
  edit() { this._dirty = true; this._validatedHash = undefined; this.render(); }
  async call(service, data) {
    this._busy = true; this._error = ''; this.render();
    try {
      const result = await this._hass.callWS({type:'call_service', domain:'htha', service,
        service_data:{config_entry_id:this.config.config_entry_id, ...data}, return_response:true});
      const model = result.response;
      if (!model) throw new Error('No service response; refresh and check integration version');
      this._model = model;
      if (service === 'load_time_program_draft') {
        this._draft = clone(model.draft); this._dirty = true; this._validatedHash = undefined;
        this._policy.mapping_confirmed = false;
      } else if (service === 'validate_time_program') {
        this._dirty = false; this._validatedHash = model.draft_hash;
      } else if (service === 'apply_time_program') {
        this._dirty = true; this._validatedHash = undefined;
      }
    } catch(error) { this._error = error.message || String(error); this._dirty = true; }
    finally { this._busy = false; this.render(); }
  }
  render() {
    if (!this.shadowRoot || !this.config) return;
    const openDays = new Set(Array.from(this.shadowRoot.querySelectorAll('details[open]')).map(x => Number(x.dataset.day)));
    const t = text => esc(this.t(text));
    const model = this._model || {};
    const canApply = !this._dirty && model.can_apply && this._validatedHash === model.draft_hash;
    const busy = this._busy ? 'disabled' : '';
    const names = this._hass?.language?.startsWith('de') ? ['Mo','Di','Mi','Do','Fr','Sa','So'] : ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
    const rows = (this._draft?.entries || []).map((day, d) => `<details data-day="${d}" ${openDays.has(d)?'open':''}><summary><b>${names[d]}</b> <small>${esc(day.map(e => `${e.start}–${e.end} [${e.state}]`).join(' · '))}</small></summary><div>${day.map((entry, n) => `<div class="interval">
      <input aria-label="${names[d]} start" data-day="${d}" data-row="${n}" data-field="start" value="${esc(entry.start)}" pattern="[0-9]{2}:[0-9]{2}" ${busy}>
      <span>–</span><input aria-label="${names[d]} end" data-day="${d}" data-row="${n}" data-field="end" value="${esc(entry.end)}" ${busy}>
      <select aria-label="${names[d]} mode" data-day="${d}" data-row="${n}" data-field="state" ${busy}>${Array.from({length:model.metadata?.nos || 3}, (_, mode) => `<option value="${mode}" ${entry.state===mode?'selected':''}>${mode}${this._policy.mapping_confirmed && mode===this._policy.normal_state ? ' — Normal' : ''}</option>`).join('')}</select>
      <button data-remove="${d}:${n}" title="${t('Remove')}" ${busy}>×</button></div>`).join('')}
      <button data-add="${d}" ${busy} ${day.length >= (model.metadata?.ead || 7) ? 'disabled' : ''}>+ ${t('Add interval')}</button></div></details>`).join('');
    this.shadowRoot.innerHTML = `<style>
      ha-card{padding:16px}h2{font-size:1.15em;margin:0 0 10px}p{font-size:.9em;color:var(--secondary-text-color)}
      .controls{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}button,input,select{font:inherit;border:1px solid var(--divider-color);border-radius:6px;padding:7px;background:var(--card-background-color);color:var(--primary-text-color)}button{cursor:pointer}button:disabled{opacity:.45;cursor:default}input:not([type=checkbox]){width:5ch}input[type=number]{width:3ch}label{display:block;margin:8px 0;font-size:.9em}details{border-top:1px solid var(--divider-color);padding:8px 0}summary{cursor:pointer}summary small{display:inline}details[open] summary{margin-bottom:10px}.interval{display:flex;align-items:center;gap:4px;margin-bottom:4px;flex-wrap:wrap}.critical,.error{color:var(--error-color)}.warning{color:var(--warning-color)}.ready{color:var(--success-color)}li{margin:6px 0}small{display:block;color:var(--secondary-text-color)}
    </style><ha-card><h2>${t('Schedule scratchpad')}</h2><p>${t('Draft only; no pump change until confirmed Save. Allow writes must be ON separately.')}</p>
    <div class="controls"><select id="program" ${busy}><option value="2" ${this._policy.kind==='heating'?'selected':''}>${t('Heating')}</option><option value="0" ${this._policy.kind==='hot_water'?'selected':''}>${t('Hot water')}</option></select><button id="load" ${busy}>${t('Load from pump')}</button></div>
    <label>${t('Normal code')} <input id="normal" type="number" min="0" max="${(model.metadata?.nos || 3)-1}" value="${this._policy.normal_state}" ${busy}></label>
    <label><input id="mapping" type="checkbox" ${this._policy.mapping_confirmed?'checked':''} ${busy}>${t('I verified this numeric Normal code on my controller')}</label>
    <label><input id="floor" type="checkbox" ${this._policy.floor_heating?'checked':''} ${busy}>${t('Floor heating')}</label>
    ${rows}<p id="draft-status">${this._dirty ? t('Unsaved local edits — check again') : esc(model.status)}</p>
    <div class="controls"><button id="check" ${busy} ${!this._draft?'disabled':''}>${t('Check')}</button>
    <button id="ack" ${busy} ${this._dirty || model.critical_count || !model.warning_ids?.length ? 'disabled':''}>${t('Acknowledge warnings')}</button>
    ${canApply ? `<button id="save" ${busy}>${t('Save to heat pump')}</button>` : ''}</div>
    ${!canApply ? `<small>${t('Apply unavailable: validate, acknowledge, and separately enable Allow writes.')}</small>` : ''}
    <p class="error">${esc(this._error)}</p><ul>${(model.findings || []).map(f => `<li class="${esc(f.severity)}"><b>${esc(f.severity.toUpperCase())}</b>${f.day!==null && f.day!==undefined ? ' '+names[f.day] : ''}: ${esc(f.message)}<small>${esc(f.source)}</small></li>`).join('')}</ul></ha-card>`;
    const byId = id => this.shadowRoot.getElementById(id);
    byId('program').onchange = event => {
      if (this._draft && !window.confirm(this.t('Load discards this draft. Continue?'))) { this.render(); return; }
      this._policy.kind = event.target.value==='0' ? 'hot_water' : 'heating';
      this._policy.mapping_confirmed = false; this._draft = null; this.edit();
    };
    byId('normal').onchange = event => {this._policy.normal_state=Number(event.target.value);this._policy.mapping_confirmed=false;this.edit();};
    byId('mapping').onchange = event => {this._policy.mapping_confirmed=event.target.checked;this.edit();};
    byId('floor').onchange = event => {this._policy.floor_heating=event.target.checked;this.edit();};
    byId('load').onclick = () => {
      if (this._draft && !window.confirm(this.t('Load discards this draft. Continue?'))) return;
      this.call('load_time_program_draft', {program_index:this._policy.kind==='hot_water'?0:2});
    };
    this.shadowRoot.querySelectorAll('[data-field]').forEach(input => { input.oninput = event => {
      const x = event.target, day = this._draft.entries[Number(x.dataset.day)];
      day[Number(x.dataset.row)][x.dataset.field] = x.dataset.field==='state' ? Number(x.value) : x.value;
      // Invalidate immediately while typing, without replacing the focused input.
      this._dirty = true; this._validatedHash = undefined;
      byId('save')?.remove(); byId('ack').disabled = true;
      byId('draft-status').textContent = this.t('Unsaved local edits — check again');
      x.closest('details').querySelector('summary small').textContent = day.map(e => `${e.start}–${e.end} [${e.state}]`).join(' · ');
    }; });
    this.shadowRoot.querySelectorAll('[data-remove]').forEach(button => { button.onclick = () => {const [d,n]=button.dataset.remove.split(':').map(Number);this._draft.entries[d].splice(n,1);this.edit();}; });
    this.shadowRoot.querySelectorAll('[data-add]').forEach(button => { button.onclick = () => {
      const day=this._draft.entries[Number(button.dataset.add)];
      day.push({start:day.at(-1)?.end || '00:00', end:'24:00', state:this._policy.normal_state});this.edit();
    }; });
    byId('check').onclick = () => this.call('validate_time_program', {draft:clone(this._draft),policy:clone(this._policy)});
    byId('ack').onclick = () => this.call('acknowledge_time_program_warnings', {draft_hash:model.draft_hash,warning_ids:model.warning_ids});
    if (byId('save')) byId('save').onclick = () => {
      if (window.confirm(this.t('Send the checked weekly schedule to the heat pump? Multiple writes can partially fail.'))) this.call('apply_time_program', {draft:clone(this._draft),draft_hash:model.draft_hash,confirm:true});
    };
  }
}
if (!customElements.get('htha-schedule-scratchpad-card')) customElements.define('htha-schedule-scratchpad-card', HthaScheduleScratchpadCard);
window.customCards = window.customCards || [];
window.customCards.push({type:'htha-schedule-scratchpad-card',name:'HTHA schedule scratchpad',description:'Checked, explicitly applied weekly drafts. No writes on edit.'});
