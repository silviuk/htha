/* Optional native Chrome rendering via stdio CDP; no server or network sockets.
   Run: node tests/capture-schedule-editor.cjs
   CHROME_PATH may point to an already-installed browser. No dependency download. */
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const factory=process.argv.includes('--factory');
const dest=process.argv.find(a=>a.startsWith('--out='));
const out=dest?path.resolve(root,dest.slice(6)):path.join(root,'docs','schedule-editor-evidence',...(factory?['factory-preset']:[]));fs.mkdirSync(out,{recursive:true});
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
  const results=[];
  const variants=[];
  for(const width of [1100,360,412])for(const language of ['en','de'])for(const theme of ['light','dark'])variants.push({width,language,theme,category:'heating'});
  variants.push({width:1100,language:'en',theme:'light',category:'hot_water'},{width:360,language:'de',theme:'dark',category:'hot_water'});
  for(const {width,language,theme,category} of variants) {
   await cdp('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<=412},s);
   await evaluate(`renderFixture(${JSON.stringify({language,theme,category,factory})}) && true`);
   const layout=await evaluate(`(()=>{const c=document.querySelector('htha-schedule-scratchpad-card'),r=c.shadowRoot;return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,grids:r.querySelectorAll('.week-grid').length,cells:r.querySelectorAll('[role=gridcell]').length,sendDisabled:r.getElementById('save').disabled,unknownCurrent:c._model.current_state,headline:r.querySelector('h2').textContent};})()`);
   assert.ok(layout.documentWidth<=width,'No page overflow');assert.equal(layout.grids,2);assert.equal(layout.sendDisabled,true);
   const help=await evaluate(`(()=>{const r=document.querySelector('htha-schedule-scratchpad-card').shadowRoot,d=r.getElementById('advice'),b=d.querySelector('summary').getBoundingClientRect();return {closed:!d.open,width:b.width,height:b.height,noCheckbox:!r.getElementById('normal-confirm'),hasInfo:d.textContent.includes('OFFLINE INFO')};})()`);
   assert.deepEqual(help,{closed:true,width:28,height:28,noCheckbox:true,hasInfo:true});
   if(factory)assert.equal(await evaluate(`(()=>{const r=document.querySelector('htha-schedule-scratchpad-card').shadowRoot;return ['rename','delete','update-profile'].every(id=>r.getElementById(id).disabled) && !r.getElementById('save-profile').disabled;})()`),true,'Factory mutations disabled; Save as enabled');
   const {cssContentSize}=await cdp('Page.getLayoutMetrics',{},s);
   const {data}=await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width,height:Math.ceil(cssContentSize.height),scale:1}},s);
   const file=`${width}-${language}-${theme}${category==='hot_water'?'-hot-water':''}.png`;fs.writeFileSync(path.join(out,file),Buffer.from(data,'base64'));results.push({file,category,...layout});
  }
  // Real DOM checks beyond stubs: focus, scroll, dirty state, pointer cancellation.
  const dom=await evaluate(`(()=>{
   const c=document.querySelector('htha-schedule-scratchpad-card');c._dirty=true;
   const r=c.shadowRoot;r.getElementById('day-detail').open=true;const scroll=r.querySelector('[data-scroll]');scroll.scrollLeft=500;
   const button=r.querySelector('.day-scroll [data-cell="0:24"]');button.focus();const before=c._draft.entries[0][0].state;
   c.hass={...c._hass,states:{'sensor.offline_validation':{attributes:{...c._model,revision:8,draft:{entries:[]}}}}};
   const result={focusPreserved:r.activeElement===button,scrollPreserved:scroll.scrollLeft===500,draftPreserved:c._draft.entries[0][0].state===before};
   c._selection.clear();button.scrollIntoView({block:'center'});const rect=button.getBoundingClientRect();result.pointer={x:rect.x+rect.width/2,y:rect.y+rect.height/2};return result;
  })()`);
  const point=dom.pointer;delete dom.pointer;
  await cdp('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1},s);
  dom.cancelSafe=await evaluate(`(()=>{const c=document.querySelector('htha-schedule-scratchpad-card'),g=c._gesture;if(!g)return false;c.shadowRoot.activeElement.dispatchEvent(new PointerEvent('pointercancel',{pointerId:g.pointerId,bubbles:true}));return !c._gesture && c._selection.cells.size===0;})()`);
  await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1},s);
  for(const [key,value]of Object.entries(dom))assert.equal(value,true,key);assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'layout-checks.json'),JSON.stringify({fixturesOnly:true,results,domChecks:dom,runtimeErrors:errors},null,2)+'\n');
  console.log(`Captured ${results.length} offline screenshots; no page overflow at 1100px/360px/412px; compact help and focus/scroll/draft/cancel checks passed.`);
 }finally{await cdp('Browser.close').catch(()=>child.kill());}
})().catch(err=>{console.error(err);process.exitCode=1;});
