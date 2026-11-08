/* Offline 412px curve layout regression via stdio CDP; no screenshots or network.
   Run: node tests/check-curve-layout.cjs
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
  await cdp('Network.enable',{},s);
  await cdp('Network.setBlockedURLs',{urls:['http://*','https://*','ws://*','wss://*']},s);
  await cdp('Emulation.setDeviceMetricsOverride',{width:412,height:915,deviceScaleFactor:1,mobile:true},s);
  const source=fs.readFileSync(path.join(root,'custom_components/htha/frontend/htha-heatpump-strategy.js'),'utf8');
  const html=`<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'"><style>body{margin:0;font-family:Arial}ha-card{display:block;border:1px solid #aaa;border-radius:12px}</style><script>${source}</script><htha-heating-curve-card></htha-heating-curve-card>`;
  const {frameTree}=await cdp('Page.getFrameTree',{},s);
  await cdp('Page.setDocumentContent',{frameId:frameTree.frame.id,html},s);
  const evaluate=async expression=>{const r=await cdp('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},s);if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
  for(const language of ['en','de'])for(const state of ['factory','differs_from_factory','check_recommended','unavailable']) {
   const result=await evaluate(`(()=>{
     const c=document.querySelector('htha-heating-curve-card');
     c.setConfig({entity:'sensor.curve'});
     c.hass={language:${JSON.stringify(language)},states:{'sensor.curve':{state:${JSON.stringify(state)},attributes:{upper_point:{outdoor_c:18,delta_k:2},zero_point:{outdoor_c:0,delta_k:3},lower_point:{outdoor_c:-15,delta_k:4}}}}};
     const r=c.shadowRoot;
     const hidden=r.querySelector('.help').hidden;
     r.querySelector('button').click();
     const opened=!r.querySelector('.help').hidden;
     c.hass={...c._hass};
     return {width:document.documentElement.scrollWidth,hidden,opened,preserved:!r.querySelector('.help').hidden,expanded:r.querySelector('button').getAttribute('aria-expanded'),help:r.querySelector('.help').textContent,status:r.querySelector('.status').textContent};
   })()`);
   assert.ok(result.width<=412,JSON.stringify({language,state,result}));
   assert.ok(result.hidden && result.opened && result.preserved);
   assert.equal(result.expanded,'true');
   assert.match(result.help,/1–2 K/);
   assert.match(result.help,language==='de'?/keine Herstellergrenzen/:/not manufacturer limits/);
   if(state==='differs_from_factory')assert.match(result.status,/\+18 °C .*\+2 K/);
  }
  assert.equal(errors.length,0,JSON.stringify(errors));
  console.log('Curve card: 8 offline 412px EN/DE states passed; help collapsed initially, toggle and updates verified.');
 } finally {
  try{await cdp('Browser.close');}catch{}
  child.kill();
 }
})().catch(err=>{console.error(err);process.exitCode=1;});
