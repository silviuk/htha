// Pure generated configuration checks. No HA, browser or hardware transport.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function fixture(language='en',count=1) {
  const registry=new Map();
  const context={HTMLElement:class{},window:{customElements:{get:k=>registry.get(k),define:(k,v)=>registry.set(k,v)}},console:{info(){}},setInterval(){}};
  registry.set('home-assistant',class{});
  vm.runInNewContext(fs.readFileSync('custom_components/htha/frontend/htha-heatpump-strategy.js','utf8'),context);
  const api=context.window.hthaHeatpumpStrategy,hass={language,entities:{},states:{},devices:{}};
  for(let n=0;n<count;n++)for(const key of Object.values(api.ROLES)) {
    const [domain,translation_key]=key.split('.'),entity_id=`${domain}.pump_${n}_${translation_key}`;
    hass.entities[entity_id]={entity_id,translation_key,platform:'htha',device_id:`pump${n}`,config_entry_id:`entry${n}`};
    hass.states[entity_id]={state:'off'};
  }
  return {api,hass,registry};
}
function activeLiveEntities(node,on,result=[]) {
  if(!node || typeof node!=='object')return result;
  if(Array.isArray(node)){node.forEach(n=>activeLiveEntities(n,on,result));return result;}
  const conditions=node.type==='conditional'?node.conditions:node.visibility;
  if(conditions?.some(c=>c.entity.includes('write_protection') && (c.state==='on'?!on:on)))return result;
  // A history/statistics series conveys a different quantity from a live value.
  if(node.type==='history-graph' || node.type==='statistics-graph')return result;
  if(['tile','gauge','entity'].includes(node.type) && node.entity)result.push(node.entity);
  for(const k of ['cards','card','sections','badges'])activeLiveEntities(node[k],on,result);
  return result;
}
for(const language of ['en','de'])for(const on of [false,true])test(`unique live fields, gated features, no comfort view: ${language}, writes ${on}`,async()=>{
  const {api,hass,registry}=fixture(language,2),view=api.buildView(hass,{});
  const ids=activeLiveEntities(view,on);
  assert.equal(new Set(ids).size,ids.length,JSON.stringify(ids));
  assert.equal(view.max_columns,3);
  assert.ok(ids.some(id=>id.endsWith('hkr_soll_raum')),'Room setpoint remains visible with writes off');
  for(const pump of api.findHeatPumps(hass))for(const [role,id] of Object.entries(pump.e))if(!['mode_code','time_programs'].includes(role))assert.ok(ids.includes(id) || JSON.stringify(view).includes(id),id);
  const dashboard=await registry.get('ll-strategy-dashboard-htha-heatpump').generate({},hass);
  assert.equal(dashboard.views.length,2);
  assert.ok(!JSON.stringify(dashboard).toLowerCase().includes('comfort'));
  assert.ok(!api.SECTIONS.includes('comfort'));
  const controls=api.buildSection(hass,{section:'controls'});
  for(const stack of controls.cards.filter(c=>c.type==='vertical-stack')) {
    assert.equal(stack.cards.length,2);
    assert.ok(!stack.cards[0].card.features);
    assert.ok(stack.cards[1].card.features.length);
    assert.equal(stack.cards[0].card.entity,stack.cards[1].card.entity);
    assert.equal(stack.cards[0].conditions[0].state_not,'on');
    assert.equal(stack.cards[1].conditions[0].state,'on');
  }
  const schedule=api.buildSection(hass,{section:'schedule',schedule_editor:false}).cards[1].content;
  assert.match(schedule,language==='de'?/0 Absenken, 1 Normalbetrieb, 2 Aufheizen/:/0 Setback, 1 Normal, 2 Boost/);
});
test('sparse registry does not create empty cards or require controls',()=>{
  const {api,hass}=fixture();
  for(const id of Object.keys(hass.entities))if(!id.endsWith('operating_state'))delete hass.entities[id];
  const ids=activeLiveEntities(api.buildView(hass,{}),false);
  assert.equal(ids.length,1);
});
test('explicit YAML keeps live fields in one section and pairs gated control alternatives',()=>{
  const yaml=fs.readFileSync('dashboards/heliotherm_heatpump.yaml','utf8');
  const locations=new Map();
  for(const [section,body] of yaml.split('  - type: grid').entries()) {
    for(const block of body.split(/(?=^    - type: )/m)) {
      const ids=[...block.matchAll(/type: (?:tile|gauge)\r?\n\s+entity: (\S+)/g)].map(m=>m[1]);
      if(!ids.length)continue;
      for(const id of new Set(ids)) {
        assert.ok(!locations.has(id),`Repeated ${id} in sections ${locations.get(id)}, ${section}`);
        locations.set(id,section);
      }
      if(ids.length===2) {
        assert.equal(ids[0],ids[1]);assert.match(block,/type: vertical-stack/);
        assert.match(block,/state_not: 'on'/);assert.match(block,/state: 'on'/);
      } else assert.equal(ids.length,1);
    }
  }
  assert.ok(locations.size>20);
  assert.doesNotMatch(yaml,/columns: [46]\b|Comfort/);
});

test('schedule editor follows each validation sensor and config entry, with a read-only opt-out',async()=>{
  const {api,hass,registry}=fixture('en',2);
  for(const n of [0,1]) {
    const config={section:'schedule',device_id:`pump${n}`};
    const card=api.buildSection(hass,config).cards[1];
    assert.equal(card.type,'custom:htha-schedule-scratchpad-card');
    assert.equal(card.entity,`sensor.pump_${n}_schedule_validation`);
    assert.equal(card.config_entry_id,`entry${n}`);
    assert.equal(api.buildSection(hass,{...config,schedule_editor:false}).cards[1].type,'markdown');
  }
  const view=await registry.get('ll-strategy-view-htha-heatpump').generate({sections:['schedule']},hass);
  assert.equal(view.sections.length,2);
  assert.equal(view.sections[1].cards[1].config_entry_id,'entry1');
});
test('schedule falls back safely when validation sensor or entry ID is missing',()=>{
  for(const missing of ['sensor','entry']) {
    const {api,hass}=fixture();
    const id='sensor.pump_0_schedule_validation';
    if(missing==='sensor')delete hass.entities[id];
    else delete hass.entities[id].config_entry_id;
    assert.equal(api.buildSection(hass,{section:'schedule'}).cards[1].type,'markdown');
  }
});
test('editor works without read-only time-program sensor and respects disabled sections',()=>{
  const {api,hass}=fixture();
  delete hass.entities['sensor.pump_0_time_programs'];
  assert.equal(api.buildSection(hass,{section:'schedule'}).cards[1].type,'custom:htha-schedule-scratchpad-card');
  assert.ok(!JSON.stringify(api.buildView(hass,{sections:['overview']})).includes('custom:htha-schedule'));
});
test('frontend version matches the manifest',()=>{
  const manifest=JSON.parse(fs.readFileSync('custom_components/htha/manifest.json','utf8'));
  const strategy=fs.readFileSync('custom_components/htha/frontend/htha-heatpump-strategy.js','utf8');
  assert.match(strategy,new RegExp('HTHA_VERSION = "'+manifest.version.replaceAll('.','\\.')+'"'));
  assert.equal(manifest.version,'1.3.3');
});

test('schedule discovers entry from validation state when registry omits it',()=>{
  const {api,hass}=fixture();
  const id='sensor.pump_0_schedule_validation';
  delete hass.entities[id].config_entry_id;
  hass.states[id].attributes={config_entry_id:'state-entry'};
  assert.equal(api.buildSection(hass,{section:'schedule'}).cards[1].config_entry_id,'state-entry');
});
