const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const plain=x=>JSON.parse(JSON.stringify(x));
const draft=(state=1)=>({entries:Array.from({length:7},()=>[{start:'00:00',end:'24:00',state}])});
const meta={index:2,name:'Heating',ead:7,nos:3,ste:15,nod:7};
function fixture({confirm=true,prompt='My profile',language='en'}={}) {
  const nodes=new Map(),calls=[],timers=new Set();let Card;
  class Element {
    attachShadow(){this.shadowRoot={innerHTML:'',querySelectorAll:()=>[],querySelector:()=>null,getElementById:id=>{
      if(!nodes.has(id))nodes.set(id,{id,value:'',checked:false,dataset:{},style:{},focus(){this.focused=true;}});
      return nodes.get(id);
    }};}
  }
  const window={confirm:()=>confirm,prompt:()=>prompt};
  vm.runInNewContext(fs.readFileSync('custom_components/htha/frontend/htha-schedule-scratchpad-card.js','utf8'),{
    HTMLElement:Element,customElements:{get:()=>undefined,define:(_,c)=>{Card=c;}},window,
    setInterval:fn=>{timers.add(fn);return fn;},clearInterval:fn=>timers.delete(fn),
  });
  const card=new Card();card.setConfig({entity:'sensor.validation',config_entry_id:'entry'});
  card._hass={language,locale:{language},config:{time_zone:'Europe/Berlin'},states:{},callWS:async request=>{calls.push(plain(request));return {response:plain(card._model)};}};
  card._model={metadata:meta,revision:1,session_id:'s',mode_catalog:[],mapping_revision:0,current_program:{...meta,...draft()},current_state:'read',baseline_read_at:'2026-11-07T10:00:00Z',writes_enabled:false};
  card.adoptDraft(draft());
  return {card,api:window.HthaScheduleEditor,nodes,calls,timers,window};
}

function factory(category='heating') {
  return {id:'factory_default_'+category,name:'Factory default (Heliotherm)',revision:1,category,read_only:true,mode_name:category==='heating'?'Normal':'On'};
}

for(const category of ['heating','hot_water'])for(const language of ['en','de'])test('factory picker/localized explanation/read-only actions '+category+' '+language,async()=>{
  const {card,calls}=fixture({language}),p=factory(category);card._category=category;
  card._hass.callWS=async request=>{calls.push(request);return {response:{profiles:[{id:'user',name:'User profile',revision:2}],builtin_profiles:[p]}};};
  await card.listProfiles();assert.deepEqual(plain(card._profiles),[p,{id:'user',name:'User profile',revision:2}]);
  card._profileId=p.id;card._profile=p;card._profileDraft=draft();card.render();
  const html=card.shadowRoot.innerHTML;
  for(const id of ['rename','delete','update-profile'])assert.match(html,new RegExp('id="'+id+'"[^>]*disabled'));
  for(const id of ['profile-load','profile-apply','save-profile'])assert.doesNotMatch(html,new RegExp('id="'+id+'"[^>]*disabled'));
  assert.match(html,language==='de'?/Werkseinstellung \(Heliotherm\)/:/Factory default \(Heliotherm\)/);
  assert.match(html,category==='heating'?(language==='de'?/Nicht belegte Heizzeiten bleiben Normalbetrieb/:/Unspecified heating periods remain Normal/):/WW_min, \+5 K/);
  assert.equal(card.draftName(),language==='de'?'Werkseinstellung (Heliotherm)':'Factory default (Heliotherm)');
  const before=calls.length;await card.renameProfile();await card.deleteProfile();await card.saveProfile(true);assert.equal(calls.length,before);
});

test('factory Save as creates a user copy without sending or updating builtin',async()=>{
  const {card,calls}=fixture(),p=factory();card._profile=p;card._profileDraft=draft();card.render=()=>{};
  card._hass.callWS=async request=>{calls.push(plain(request));return {response:{...card._model,saved_profile:{id:'copy',name:'My profile',revision:1,draft:draft()},profiles:[{id:'copy',name:'My profile',revision:1}],builtin_profiles:[p]}};};
  await card.saveProfile();assert.equal(calls.length,1);assert.equal(calls[0].service,'save_time_program_profile');
  assert.equal(calls[0].service_data.profile_id,undefined);assert.equal(calls[0].service_data.expected_profile_revision,undefined);
  assert.equal(card._profile.id,'copy');assert.equal(card._profile.read_only,undefined);assert.equal(card._profiles[0].id,p.id);
});

test('factory shortcut fresh-validates then stops for critical mapping without ack/apply',async()=>{
  const {card,calls}=fixture(),p=factory();card._dirty=false;card._profileId=p.id;card.render=()=>{};
  card._hass.callWS=async request=>{calls.push(plain(request));return {response:{...card._model,draft:draft(null),profile_context:p,
    critical_count:1,findings:[{id:'factory_mapping',severity:'critical',message:'Factory mapping unverified'}],missing_gates:['factory_mapping'],can_apply:false}};};
  await card.loadProfile(true);
  assert.deepEqual(calls.map(c=>c.service),['load_time_program_profile','validate_time_program']);
  assert.equal(calls[1].service_data.fresh_read,true);assert.ok(card._local.week.every(day=>day.every(x=>x===null)));
  assert.ok(card.missing().some(s=>s.includes('Factory preset mapping')));assert.equal(card._warningChecks.size,0);
  await card.saveProfile();assert.equal(calls.length,2); // unknown cells cannot become a numeric saved copy
});

test('factory dirty replacement cancellation preserves draft and does not call services',async()=>{
  const {card,calls}=fixture({confirm:false});card._profileId=factory().id;
  await card.loadProfile();await card.loadProfile(true);assert.equal(calls.length,0);assert.deepEqual(plain(card._draft),draft());
});
test('96 recurring cells round trip all-day and midnight endpoints',()=>{
  const {api}=fixture();const week=api.toCells(draft());assert.equal(week.length,7);assert.equal(week[0].length,96);
  assert.deepEqual(plain(api.toDraft(week)),draft());assert.equal(api.time(96),'24:00');assert.ok(Number.isNaN(api.slot('24:15')));
});
test('unknown native gaps, overlaps, bad codes and padding are visible',()=>{
  const {api}=fixture();const raw=draft();raw.entries[0]=[{start:'00:00',end:'01:00',state:1},{start:'00:45',end:'02:00',state:0}];
  const cells=api.toCells(raw,3);assert.equal(cells[0][3],null);assert.equal(cells[0][8],null);
  const padded=draft();padded.entries[0].push({start:'24:00',end:'24:00',state:2});assert.deepEqual(plain(api.toDraft(api.toCells(padded))),draft());
  padded.entries[1][0].state=true;assert.ok(api.toCells(padded,3)[1].every(x=>x===null));
});
test('click, Ctrl/Cmd toggle, inclusive Shift and additive Shift stay row-local',()=>{
  const {api}=fixture(),s=new api.Selection();
  s.choose(0,2);s.choose(0,4,{ctrlKey:true});s.choose(0,2,{metaKey:true});assert.deepEqual([...s.cells],['0:4']);
  s.choose(0,8,{shiftKey:true});assert.equal(s.cells.size,7); // anchor remained 2 after toggle
  s.choose(0,10,{ctrlKey:true,shiftKey:true});assert.equal(s.cells.size,9);
  s.choose(1,4,{shiftKey:true});assert.deepEqual([...s.cells],['1:4']);
  s.choose(2,7,{ctrlKey:true,shiftKey:true});assert.deepEqual([...s.cells],['1:4','2:7']);
});
test('selection and dropdown never edit, invalidate or call services; explicit Set does',()=>{
  const {card,calls,nodes}=fixture();card.render();card._dirty=false;card._validatedHash='hash';
  card.clickCell(0,24,{detail:0});nodes.get('mode').onchange({target:{value:'2'}});
  assert.equal(card._dirty,false);assert.equal(card._validatedHash,'hash');assert.equal(card._draft.entries[0][0].state,1);assert.equal(calls.length,0);
  card.paint();assert.equal(card._dirty,true);assert.equal(card._validatedHash,undefined);assert.equal(card._local.week[0][24],2);assert.equal(calls.length,0);
});
test('pointer drag selects only, captures pointer and cancellation is safe',()=>{
  const {card,calls}=fixture();card.render=()=>{};let capture;
  card._selection.choose(2,8);const before=[...card._selection.cells];
  card.pointerDown(0,4,{button:0,pointerType:'mouse',pointerId:7,currentTarget:{setPointerCapture:id=>capture=id}});
  card.pointerMove({clientX:120,currentTarget:{closest:()=>({getBoundingClientRect:()=>({left:0,width:960})})}});
  assert.equal(capture,7);assert.equal(card._gesture.end,12);card.pointerEnd(true);assert.deepEqual([...card._selection.cells],before);
  card.pointerDown(0,4,{button:0,pointerType:'mouse',pointerId:7,currentTarget:{}});card._gesture.end=9;card.pointerEnd();
  assert.equal(card._selection.cells.size,6);assert.deepEqual(plain(card._draft),draft());assert.equal(calls.length,0);
});
test('touch range/add controls preserve scroll and last endpoint is 24:00',()=>{
  const {card}=fixture();card.render=()=>{};
  card.pointerDown(0,3,{button:0,pointerType:'touch'});assert.equal(card._gesture,undefined);
  card.selectRange(0,94,96);card.selectRange(0,2,4,true);assert.equal(card._selection.cells.size,4);
  assert.match(card.selectionText(),/23:30–24:00/);card.selectRange(0,95,97);assert.equal(card._selection.cells.size,4);
});
test('keyboard arrows, Shift, Space and Escape have independent selection semantics',()=>{
  const {card}=fixture();card.render=()=>{};let prevented=0;
  const key=(d,i,key,shiftKey=false)=>card.key(d,i,{key,shiftKey,preventDefault:()=>prevented++});
  key(0,4,'ArrowRight',true);assert.equal(card._selection.cells.size,2);assert.equal(card._dirty,true);
  key(0,5,' ',false);assert.equal(card._selection.cells.size,1);key(0,5,'Escape');assert.equal(card._selection.cells.size,0);assert.equal(prevented,3);
});
for(const targets of [[0,1,2,3,4,5,6],[0,1,2,3,4],[5,6],[1,3]])test('copy/deep isolation/one-step undo '+targets,()=>{
  const {card,calls}=fixture();card.render=()=>{};card._local.week[0][0]=2;
  const before=plain(card._local.week);card.copyDay(targets);const after=plain(card._local.week);
  for(const d of targets)assert.equal(after[d][0],2);
  card._local.history();assert.deepEqual(plain(card._local.week),before);card._local.history(true);assert.deepEqual(plain(card._local.week),after);
  if(targets.includes(1)){card._local.week[0][0]=0;assert.equal(card._local.week[1][0],2);}assert.equal(calls.length,0);
});
test('copy confirmation cancellation changes nothing',()=>{const {card,calls}=fixture({confirm:false});card.copyDay([1]);assert.equal(card._local.undo.length,0);assert.equal(calls.length,0);});
test('8-run editing is retained, compression is numeric and does not smooth',()=>{
  const {api}=fixture(),week=api.toCells(draft());for(let i=0;i<7;i++)week[0][i]=i%2;
  const encoded=api.toDraft(week);assert.equal(encoded.entries[0].length,8);assert.deepEqual(plain(api.toCells(encoded)),plain(week));
});
test('dirty replacement cancel prevents category/profile/pump calls',async()=>{
  const {card,calls}=fixture({confirm:false});card._profileId='p';await card.changeCategory('hot_water');await card.loadProfile();await card.loadPump();assert.equal(card._category,'heating');assert.equal(calls.length,0);
});
test('profile Save/create and explicit overwrite use immutable local copy and revision',async()=>{
  const {card,calls}=fixture();card.render=()=>{};await card.saveProfile();assert.equal(calls[0].service,'save_time_program_profile');assert.equal(calls[0].service_data.profile_id,undefined);
  card._profile={id:'p',name:'N',revision:4};await card.saveProfile(true);assert.equal(calls[1].service_data.expected_profile_revision,4);
  card._local.week[0][0]=2;assert.equal(calls[0].service_data.draft.entries[0][0].state,1);
});
test('profile rename/delete use selected UUID and exact profile revision',async()=>{
  const {card,calls}=fixture();card.render=()=>{};card._profiles=[{id:'p',name:'P',revision:3}];card._profileId='p';await card.renameProfile();await card.deleteProfile();
  assert.deepEqual(calls.map(c=>c.service),['rename_time_program_profile','delete_time_program_profile']);assert.equal(calls[1].service_data.confirm,true);assert.equal(calls[0].service_data.expected_profile_revision,3);
});
test('Apply profile shortcut stops at fresh validation and never trusts saved approvals',async()=>{
  const {card,calls}=fixture();card.render=()=>{};card._dirty=false;card._profileId='p';
  card._hass.callWS=async request=>{calls.push(request);return {response:{...card._model,draft:draft(2),draft_hash:'new',warning_ids:['non_atomic'],can_apply:false}};};
  await card.loadProfile(true);assert.deepEqual(calls.map(c=>c.service),['load_time_program_profile','validate_time_program']);assert.equal(calls[1].service_data.fresh_read,true);assert.equal(card._warningChecks.size,0);
});
test('profile conflict preserves draft and invalidates local approval',async()=>{
  const {card}=fixture();card.render=()=>{};card._hass.callWS=async()=>{throw new Error('Profile revision conflict');};await card.saveProfile();assert.match(card._error,/conflict/);assert.deepEqual(plain(card._draft),draft());assert.equal(card._dirty,true);
});
test('validate shows findings AND server diff and uses baseline/mapping/session revisions',async()=>{
  const {card,calls}=fixture();card._model={...card._model,draft_hash:'checked',critical_count:1,findings:[{id:'coverage:0',severity:'critical',day:0,message:'Missing coverage'}],diff:{changed_minutes:15,days:[{day:0,changed_minutes:15,old_entries:1,new_entries:3,capacity:7,ranges:[{start:'06:00',end:'06:15',from_state:1,to_state:2}]}]}};
  await card.validate();assert.equal(calls[0].service_data.fresh_read,true);assert.equal(calls[0].service_data.expected_draft_revision,1);assert.equal(calls[0].service_data.session_id,'s');
  assert.match(card.shadowRoot.innerHTML,/Missing coverage/);assert.match(card.shadowRoot.innerHTML,/Changes compared with pump/);assert.match(card.shadowRoot.innerHTML,/06:00–06:15/);
});
function sendReady(card){card._dirty=false;card._validatedHash='checked';Object.assign(card._model,{draft_hash:'checked',can_apply:true,current_state:'read',mapping_valid:true,writes_enabled:true,warning_ids:['warning'],warnings_acknowledged:true,missing_gates:[]});}
test('send review cancel and duplicate-send prevention yield zero/one apply calls',async()=>{
  const {card,calls}=fixture();card.render=()=>{};sendReady(card);card.requestSend();await card.confirmSend(false);assert.equal(calls.length,0);
  card.requestSend();await Promise.all([card.confirmSend(true),card.confirmSend(true)]);assert.equal(calls.length,1);assert.equal(calls[0].service,'apply_time_program');assert.equal(calls[0].service_data.confirm,true);
});
test('per-warning explicit acknowledgement required, never auto-acknowledged',async()=>{
  const {card,calls}=fixture();card.render=()=>{};card._dirty=false;card._validatedHash='h';card._model.warning_ids=['a','b'];card._warningChecks.add('a');await card.acknowledge();assert.equal(calls.length,0);
  card._warningChecks.add('b');await card.acknowledge();assert.deepEqual(calls[0].service_data.warning_ids,['a','b']);
});
test('every missing gate including writes OFF remains visible and send disabled',()=>{
  const {card}=fixture();Object.assign(card._model,{critical_count:2,warning_ids:['w'],current_state:'unknown',missing_gates:['complete_mapping']});card.render();
  const reasons=card.missing().join('|');for(const text of ['Allow writes is OFF','Validate the current draft','Fix critical findings','Acknowledge every warning','Confirm all used mode mappings','Baseline unavailable'])assert.ok(reasons.includes(text),text);
  assert.match(card.shadowRoot.innerHTML,/id="save"[^>]*disabled/);
});
test('read failure and failed apply show unknown current, retain draft, never retry',async()=>{
  const {card,calls}=fixture();card.render=()=>{};card._hass.callWS=async r=>{calls.push(r);throw new Error('Read unavailable');};
  await card.validate();assert.equal(card._model.current_program,null);assert.equal(card._model.current_state,'unavailable');assert.deepEqual(plain(card._draft),draft());assert.equal(calls.length,1);
});
test('hass updates preserve dirty draft, selection, focus and active gesture',()=>{
  const {card}=fixture();card.render=()=>{throw new Error('Must not replace focused DOM');};card._gesture={day:0};card._local.week[0][0]=2;card._draft=card._local?card._draft:null;card._selection.choose(0,2);
  card.hass={states:{'sensor.validation':{attributes:{revision:2,session_id:'s',draft:draft(0),can_apply:false}}}};
  assert.equal(card._local.week[0][0],2);assert.equal(card._selection.cells.size,1);assert.ok(card._gesture);
});
test('idempotent config keeps local state and timer cleans up',()=>{
  const {card,timers}=fixture();card._selection.choose(1,5);const local=card._local;card.setConfig(card.config);assert.equal(card._local,local);assert.equal(card._selection.cells.size,1);
  card.connectedCallback();card.connectedCallback();assert.equal(timers.size,1);card.disconnectedCallback();assert.equal(timers.size,0);
});
for(const language of ['en','de'])test('localized safe rendering, semantic colors, phone/dark CSS '+language,()=>{
  const {card}=fixture({language});card._profiles=[{id:'p',name:'<img src=x onerror=evil()>',revision:1}];card._model.mode_catalog=[{state:0,semantic:'setback',confirmed:true},{state:1,semantic:'normal',confirmed:true},{state:2,semantic:'boost',confirmed:false}];card.render();
  const html=card.shadowRoot.innerHTML;assert.ok(html.includes('&lt;img'));assert.ok(!html.includes('<img'));assert.ok(html.includes('max-width:600px'));assert.ok(html.includes('var(--card-background-color'));
  assert.equal(card.styleMode(2),'unknown');assert.equal(card.styleMode(0),'setback');assert.match(html,/00:00–24:00/);assert.match(html,language==='de'?/Zeitprogramm-Entwurf/:/Draft schedule/);
});
test('timestamps use HA time zone, not browser zone',()=>{const {card}=fixture();assert.match(card.stamp('2026-11-07T10:00:00Z'),/11:00/);});

test('edited profile is labelled Unsaved draft and ordinary edits exit restore workflow',()=>{
  const {card}=fixture();card.render=()=>{};card._profile={id:'p',name:'Saved'};card._profileDraft=draft();assert.equal(card.draftName(),'Saved');
  card._restoring=true;card._local.week[0][0]=2;card.edit();assert.equal(card.draftName(),'Unsaved draft');assert.equal(card._restoring,false);
});
test('renaming another saved profile does not relabel active draft',async()=>{
  const {card}=fixture();card.render=()=>{};card._profile={id:'active',name:'Active'};card._profileDraft=draft();
  card._hass.callWS=async()=>({response:{...card._model,saved_profile:{id:'other',name:'Renamed',draft:draft(2)}}});
  await card.call('rename_time_program_profile',{});assert.equal(card.draftName(),'Active');
});
test('changing policy invalidates the check, but numeric dropdown alone does not',()=>{
  const {card,nodes}=fixture();card.render();sendReady(card);nodes.get('normal').onchange({target:{value:'2'}});
  assert.equal(card._dirty,true);assert.equal(card._validatedHash,undefined);assert.equal(card._policy.mapping_confirmed,false);
});
test('stale comparison is explicitly labelled after editing',()=>{
  const {card}=fixture();card._model.diff={changed_minutes:0,days:[]};card._dirty=true;card.render();assert.match(card.shadowRoot.innerHTML,/Previous comparison — validate again/);
});
