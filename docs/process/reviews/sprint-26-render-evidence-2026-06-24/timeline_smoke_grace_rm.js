const {spawn}=require('child_process');const http=require('http');const https=require('https');
const CHROME=process.argv[2], BASE=process.argv[3].replace(/\/$/,'');const REDUCED=process.argv[4]==='1';const SCHEME=process.argv[5]||'1';
const PORT=9000+Math.floor(Math.random()*900);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const gj=p=>new Promise((res,rej)=>{http.get('http://localhost:'+PORT+p,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>res(JSON.parse(d)));}).on('error',rej);});
function req(method,path,body){return new Promise((res,rej)=>{const u=new URL(BASE+path);const lib=u.protocol==='https:'?https:http;const data=body!=null?JSON.stringify(body):null;const r=lib.request(u,{method,headers:data?{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}:{}},rr=>{let d='';rr.on('data',c=>d+=c);rr.on('end',()=>res({code:rr.statusCode,body:d}));});r.on('error',rej);if(data)r.write(data);r.end();});}
const RESULTS=[];function check(label,cond,extra){RESULTS.push({label,pass:!!cond,extra:extra||''});console.log((cond?'  ok  ':'  FAIL')+' '+label+(extra?'   ['+extra+']':''));}
(async()=>{
  const cr=await req('POST','/api/reviews',{title:'g',markdown:'# G\n\nbody G\n'});
  const rid=JSON.parse(cr.body).id;const URL=BASE+'/review/'+rid;
  const c=spawn(CHROME,['--headless=new','--disable-gpu','--no-sandbox','--remote-debugging-port='+PORT,'--blink-settings=preferredColorScheme='+SCHEME,URL],{stdio:'ignore'});
  let t;for(let i=0;i<60;i++){try{t=await gj('/json');if(t.find(x=>x.type==='page'))break;}catch(e){}await sleep(150);}
  const pg=(t||[]).find(x=>x.type==='page');const ws=new WebSocket(pg.webSocketDebuggerUrl);let id=0;const pend=new Map();
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id);}});
  await new Promise(r=>ws.addEventListener('open',r));
  const send=(meth,par={})=>new Promise(res=>{const i=++id;pend.set(i,res);ws.send(JSON.stringify({id:i,method:meth,params:par}));});
  const ev=async x=>(await send('Runtime.evaluate',{expression:x,returnByValue:true,awaitPromise:true})).result.result.value;
  await send('Runtime.enable');
  if(REDUCED)await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  for(let i=0;i<40;i++){if(await ev('typeof renderBanner==="function"'))break;await sleep(200);}

  // --- pickup-timeout >grace: call renderBanner with a status whose turn_updated is 999s ago ---
  console.log('--- pickup-timeout >grace branch (synthetic stale turn_updated) ---');
  const past=`renderBanner({turn:'agent',turn_updated:(Date.now()/1000-999),agent_status:null});`;
  await ev(past);
  let s=JSON.parse(await ev(`JSON.stringify({cls:document.querySelector('#turnbanner').className,text:document.querySelector('#turntext').textContent})`));
  check('grace>: "No agent has picked this up"',/No agent has picked this up/.test(s.text),s.text);
  check('grace>: uses .warn (non-spinning)',/\bwarn\b/.test(s.cls)&&!/\bloading\b/.test(s.cls),s.cls);

  // --- stale-lease "may have stopped" (MR-066) ---
  console.log('--- stale-lease (as.at far past STALE_S) ---');
  await ev(`renderBanner({turn:'agent',turn_updated:(Date.now()/1000-10),agent_status:{state:'working',owner:'x',at:(Date.now()/1000-999)}});`);
  s=JSON.parse(await ev(`JSON.stringify({cls:document.querySelector('#turnbanner').className,text:document.querySelector('#turntext').textContent})`));
  check('stale-lease: "Agent may have stopped"',/Agent may have stopped/.test(s.text),s.text);
  check('stale-lease: .warn, not steps',/\bwarn\b/.test(s.cls)&&!/\bsteps\b/.test(s.cls),s.cls);

  // --- reduced-motion: active step animationName === none ---
  console.log('--- working state + reduced-motion='+REDUCED+' ---');
  await ev(`renderBanner({turn:'agent',turn_updated:(Date.now()/1000-5),source_updated:0,comments_updated:0,agent_status:{state:'working',owner:'x',at:(Date.now()/1000)}});`);
  await sleep(200);
  const anim=await ev(`(function(){const li=document.querySelector('#turnsteps li.active');if(!li)return 'NO-ACTIVE';return getComputedStyle(li,'::before').animationName;})()`);
  if(REDUCED) check('reduced-motion: active ::before animationName === none',anim==='none',anim);
  else check('motion-on: active ::before animationName === turnspin (liveness)',anim==='turnspin',anim);

  // --- legibility: timer + step text color resolves (non-transparent) in this scheme ---
  const colors=JSON.parse(await ev(`JSON.stringify({bg:getComputedStyle(document.querySelector('#turnbanner')).backgroundColor,timer:getComputedStyle(document.querySelector('#turntimer')).color,step:getComputedStyle(document.querySelector('#turnsteps li.active')||document.querySelector('#turnsteps li')).color})`));
  check('scheme'+SCHEME+': timer + step colors resolve (rendered)',!!colors.timer&&!!colors.step&&colors.timer!=='rgba(0, 0, 0, 0)',JSON.stringify(colors));

  ws.close();c.kill();
  console.log('\nSUMMARY '+JSON.stringify(RESULTS));
  process.exit(RESULTS.some(r=>!r.pass)?1:0);
})().catch(e=>{console.error('DRIVER ERROR',String(e),e&&e.stack);process.exit(2);});
