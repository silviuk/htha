// Offline card lifecycle regression checks. No browser, server or transport.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function cardClass() {
  let Card;
  class Element {
    attachShadow() {
      if (this.shadowRoot) throw new Error('NotSupportedError');
      this.shadowRoot = {innerHTML:'', querySelectorAll:()=>[]};
    }
  }
  vm.runInNewContext(fs.readFileSync('custom_components/htha/frontend/htha-schedule-scratchpad-card.js','utf8'), {
    HTMLElement:Element, customElements:{get:()=>undefined,define:(_name,value)=>{Card=value;}}, window:{},
  });
  return Card;
}

test('repeated setConfig creates one shadow root', () => {
  const Card=cardClass(), card=new Card();
  const config={entity:'sensor.validation',config_entry_id:'mock'};
  card.setConfig(config);
  const root=card.shadowRoot;
  card.setConfig(config);
  assert.equal(card.shadowRoot,root);
});

for (const next of [{session_id:'new',revision:0},{session_id:'old',revision:1}]) {
  test('session/revision reset consumes local validation '+JSON.stringify(next), () => {
    const Card=cardClass(), card=new Card();
    card.setConfig({entity:'sensor.validation',config_entry_id:'mock'});
    card.render=()=>{};
    card._model={session_id:'old',revision:10};
    card._validatedHash='same'; card._dirty=false;
    card.hass={states:{'sensor.validation':{attributes:{...next,draft_hash:'same',can_apply:true}}}};
    assert.equal(card._dirty,true);
    assert.equal(card._validatedHash,undefined);
    assert.equal(card._model.revision,next.revision);
  });
}

test('render exposes required controls and named, unverified modes', () => {
  const Card=cardClass(), card=new Card();
  card.setConfig({entity:'sensor.validation',config_entry_id:'mock'});
  card._draft={entries:[[{start:'00:00',end:'24:00',state:1}]]};
  card._model={metadata:{index:2,nos:3,ead:7}};
  card.shadowRoot.getElementById=()=>({});
  card.render();
  assert.match(card.shadowRoot.innerHTML,/data-copy/);
  assert.match(card.shadowRoot.innerHTML,/Mode 0 \(unverified\)/);
  assert.match(card.shadowRoot.innerHTML,/24:00/);
  assert.match(card.shadowRoot.innerHTML,/id="save"[^>]*disabled/);
  assert.match(card.shadowRoot.innerHTML,/Validate the current draft/);
  assert.match(card.shadowRoot.innerHTML,/Labels never translate numeric payloads/);
});
