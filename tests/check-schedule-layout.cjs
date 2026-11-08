/* Offline 412px layout regression via stdio CDP; no screenshots or network.
   Run: node tests/check-schedule-layout.cjs
   CHROME_PATH may point to an already-installed browser. No dependency download. */
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const profile=path.join(root,'.schedule-chrome');
const chrome=process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const child=spawn(chrome,['--headless=new','--no-sandbox','--disable-gpu','--remote-debugging-pipe',`--user-data-dir=${profile}`,'--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps','--no-proxy-server','--host-resolver-rules=MAP * ~NOTFOUND','--metrics-recording-only','--disable-features=MediaRouter,OptimizationHints','about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe','pipe','pipe']});
let seq=0,pending=new Map(),buffer='';const errors=[];
child.stderr.on('data',()=>{});
child.stdio[4].on('data',chunk=>{buffer+=chunk.toString();let pos;while((pos=buffer.indexOf('\0'))>=0){const raw=buffer.slice(0,pos);buffer=buffer.slice(pos+1);if(!raw)continue;const m=JSON.parse(raw);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}}else if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);}});
child.on('error',err=>{for(const p of pending.values())p.reject(err);});
function cdp(method,params={},sessionId){return new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>reject(new Error('CDP timeout: '+method)),20000);pending.set(id,{resolve,reject,timer});child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');});}
(async()=>{
 try {
  const {targetId}=await cdp('Target.createTarget',{url:'about:blank'});
  const {sessionId:s}=await cdp('Target.attachToTarget',{targetId,flatten:true});
  await cdp('Runtime.enable',{},s);await cdp('Page.enable',{},s);
  // Block every HTTP request independently of the fixture CSP and DNS block.
  await cdp('Network.enable',{},s);await cdp('Network.setBlockedURLs',{urls:['http://*','https://*','ws://*','wss://*']},s);
  let html=fs.readFileSync(path.join(__dirname,'fixtures','schedule-editor.html'),'utf8');
  html=html.replace('<script src="../../custom_components/htha/frontend/htha-schedule-scratchpad-card.js"></script>',()=>'<script>'+fs.readFileSync(path.join(root,'custom_components/htha/frontend/htha-schedule-scratchpad-card.js'),'utf8')+'</script>');
  const {frameTree}=await cdp('Page.getFrameTree',{},s);await cdp('Page.setDocumentContent',{frameId:frameTree.frame.id,html},s);
  const evaluate=async expression=>{const r=await cdp('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},s);if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;};

  for(const category of ['heating','hot_water'])for(const language of ['en','de'])for(const theme of ['light','dark'])for(const editor of [false,true]){
    await cdp('Emulation.setDeviceMetricsOverride',{width:412,height:915,deviceScaleFactor:1,mobile:true},s);
    await evaluate('renderFixture('+JSON.stringify({category,language,theme})+') && true');
    if(!editor)await evaluate("(()=>{const c=document.querySelector('htha-schedule-scratchpad-card'),m=c._model;c._currentViews[c._category]={metadata:m.metadata,current_program:m.current_program,read_at:m.baseline_read_at,mode_catalog:m.mode_catalog};c._draft=null;c._local=null;c.render();return true;})()");
    const layout=await evaluate("(()=>{const c=document.querySelector('htha-schedule-scratchpad-card'),r=c.shadowRoot;return {width:document.documentElement.scrollWidth,grids:r.querySelectorAll('.week-grid').length,editor:!!r.getElementById('mode'),send:r.getElementById('save')?.disabled??null};})()");
    assert.ok(layout.width<=412,JSON.stringify({category,language,theme,editor,layout}));
    assert.equal(layout.grids,editor?2:1);assert.equal(layout.editor,editor);assert.equal(layout.send,editor?true:null);
    if(editor) {
      const targets=await evaluate(`(()=>{const r=document.querySelector('htha-schedule-scratchpad-card').shadowRoot;
        const cell=r.querySelector('.week-grid [data-cell]'),rect=cell.getBoundingClientRect();
        const before=getComputedStyle(cell).touchAction;r.getElementById('select-mode').click();
        const after=getComputedStyle(r.querySelector('.week-grid [data-cell]')).touchAction;
        r.getElementById('select-mode').click();
        return {width:rect.width,height:rect.height,before,after,outside:getComputedStyle(r.querySelector('ha-card')).touchAction};})()`);
      assert.ok(targets.width>=44 && targets.height>=44,JSON.stringify(targets));
      assert.equal(targets.before,'auto');assert.equal(targets.after,'none');assert.equal(targets.outside,'auto');
    }
  }
  await cdp('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:1},s);
  await evaluate(`(()=>{const c=renderFixture({language:'en'});c._selection.clear();
    window.selectionBefore=JSON.stringify(c._draft);window.selectionCalls=0;
    c._hass.callWS=async()=>{window.selectionCalls++;throw Error('Selection must not call services');};
    window.touchLog=[];c.shadowRoot.addEventListener('pointerdown',e=>{if(e.target.dataset.cell)window.touchLog.push(e.pointerType);});
    return true;})()`);
  const point=async i=>evaluate(`(()=>{const c=document.querySelector('htha-schedule-scratchpad-card'),r=c.shadowRoot,
    cell=r.querySelector('.week-grid [data-cell="0:${i}"]');cell.scrollIntoView({block:'center',inline:'nearest'});
    const b=cell.getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2};})()`);
  const touch=async(type,p)=>cdp('Input.dispatchTouchEvent',{type,touchPoints:p?[{...p,id:1}]:[]},s);
  const selected=()=>evaluate("[...document.querySelector('htha-schedule-scratchpad-card')._selection.cells]");
  const tap=async i=>{const p=await point(i);await touch('touchStart',p);await touch('touchEnd');};
  await tap(1);assert.deepEqual(await selected(),['0:1']);
  await evaluate("document.querySelector('htha-schedule-scratchpad-card').shadowRoot.getElementById('multi-select').click()");
  await tap(3);assert.deepEqual(await selected(),['0:1','0:3']);
  await evaluate(`(()=>{const r=document.querySelector('htha-schedule-scratchpad-card').shadowRoot;
    r.getElementById('multi-select').click();r.getElementById('select-mode').click();return true;})()`);
  const start=await point(1),end=await point(4);await touch('touchStart',start);
  assert.equal(await evaluate("(()=>{const c=document.querySelector('htha-schedule-scratchpad-card'),g=c._gesture;return !!g && g.target.hasPointerCapture(g.pointerId);})()"),true);
  await touch('touchMove',end);await touch('touchEnd');
  assert.deepEqual(await selected(),['0:1','0:2','0:3','0:4']);
  await touch('touchStart',start);await touch('touchMove',end);await touch('touchCancel');
  assert.deepEqual(await selected(),['0:1','0:2','0:3','0:4']);
  const unchanged=await evaluate(`(()=>{const c=document.querySelector('htha-schedule-scratchpad-card');
    return {draft:JSON.stringify(c._draft)===window.selectionBefore,calls:window.selectionCalls,
      gesture:c._gesture,dirty:c._dirty,hash:c._validatedHash,touch:window.touchLog};})()`);
  assert.equal(unchanged.draft,true);assert.equal(unchanged.calls,0);assert.equal(unchanged.gesture,null);
  assert.equal(unchanged.dirty,false);assert.equal(unchanged.hash,'offline-hash');
  assert.ok(unchanged.touch.length>=4 && unchanged.touch.every(t=>t==='touch'));
  assert.deepEqual(errors,[]);console.log('16 offline 412px layout checks, 44px targets, touch-action isolation and native touch tap/multi-select/drag/cancel checks passed; no screenshots or network access.');
 }finally{await cdp('Browser.close').catch(()=>child.kill());}
})().catch(err=>{console.error(err);process.exitCode=1;});
