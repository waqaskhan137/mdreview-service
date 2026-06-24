// MR-073 G7 timeline smoke. Node built-in WebSocket over CDP. Drives the agent-turn lifecycle by
// POSTing the real /handoff, /source, /comments endpoints between DOM reads, asserting the live DOM.
// Usage: node timeline_smoke.js <chrome> <base> [scheme 0|1] [reduced 0|1]
const {spawn}=require('child_process');const http=require('http');const https=require('https');
const CHROME=process.argv[2], BASE=process.argv[3].replace(/\/$/,'');
const SCHEME=process.argv[4]||'1'; // 1=light 0=dark (preferredColorScheme)
const REDUCED=process.argv[5]==='1';
const PORT=9000+Math.floor(Math.random()*900);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const gj=p=>new Promise((res,rej)=>{http.get('http://localhost:'+PORT+p,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>res(JSON.parse(d)));}).on('error',rej);});
// minimal HTTP helper against BASE
function req(method,path,body){return new Promise((res,rej)=>{
  const u=new URL(BASE+path);const lib=u.protocol==='https:'?https:http;
  const data=body!=null?JSON.stringify(body):null;
  const r=lib.request(u,{method,headers:data?{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}:{}},rr=>{let d='';rr.on('data',c=>d+=c);rr.on('end',()=>res({code:rr.statusCode,body:d}));});
  r.on('error',rej);if(data)r.write(data);r.end();
});}

const RESULTS=[];
function check(label,cond,extra){RESULTS.push({label,pass:!!cond,extra:extra||''});console.log((cond?'  ok  ':'  FAIL')+' '+label+(extra?'   ['+extra+']':''));}

(async()=>{
  // create a review
  const cr=await req('POST','/api/reviews',{title:'tl',markdown:'# TL\n\norig body\n'});
  const rid=JSON.parse(cr.body).id;
  const URL=BASE+'/review/'+rid;
  const args=['--headless=new','--disable-gpu','--no-sandbox','--hide-scrollbars','--remote-debugging-port='+PORT,
    '--blink-settings=preferredColorScheme='+SCHEME, URL];
  const c=spawn(CHROME,args,{stdio:'ignore'});
  let t;for(let i=0;i<60;i++){try{t=await gj('/json');if(t.find(x=>x.type==='page'))break;}catch(e){}await sleep(150);}
  const pg=(t||[]).find(x=>x.type==='page'); if(!pg){console.error('no page');c.kill();process.exit(2);}
  const ws=new WebSocket(pg.webSocketDebuggerUrl);let id=0;const pend=new Map();
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id);}});
  await new Promise(r=>ws.addEventListener('open',r));
  const send=(meth,par={})=>new Promise(res=>{const i=++id;pend.set(i,res);ws.send(JSON.stringify({id:i,method:meth,params:par}));});
  const ev=async x=>(await send('Runtime.evaluate',{expression:x,returnByValue:true,awaitPromise:true})).result.result.value;
  await send('Runtime.enable');await send('Page.enable');
  if(REDUCED)await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  // wait for app boot
  for(let i=0;i<40;i++){if(await ev('!!document.querySelector("#turnbanner")'))break;await sleep(200);}

  // helper to read banner state
  const snap=async()=>JSON.parse(await ev(`JSON.stringify((function(){
    const b=document.querySelector('#turnbanner');
    const steps=[...document.querySelectorAll('#turnsteps li')].map(li=>({t:li.textContent,cls:li.className}));
    const stepsVisible=getComputedStyle(document.querySelector('#turnsteps')).display;
    return {cls:b.className, text:document.querySelector('#turntext').textContent,
            timer:document.querySelector('#turntimer').textContent, steps, stepsDisplay:stepsVisible};
  })())`));

  // === SCENARIO A: full lifecycle on this review ===
  console.log('\n--- A: claim ---');
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'agent'});
  await req('POST','/api/reviews/'+rid+'/handoff',{state:'working',owner:'gate-x'});
  await sleep(2300); // let a poll tick land
  let s=await snap();
  check('A1 banner has class steps',/\bsteps\b/.test(s.cls),s.cls);
  check('A1 turntext "Agent is working"',/Agent is working/.test(s.text),s.text);
  check('A1 timer M:SS format',/^\d+:\d\d$/.test(s.timer),s.timer);
  check('A1 step0 Connected active',s.steps[0]&&/Connected/.test(s.steps[0].t)&&s.steps[0].cls==='active',JSON.stringify(s.steps[0]));
  check('A1 step1 Editing pending(no class)',s.steps[1]&&/Editing/.test(s.steps[1].t)&&s.steps[1].cls==='',JSON.stringify(s.steps[1]));
  check('A1 step2 Updating pending(no class)',s.steps[2]&&/Updating/.test(s.steps[2].t)&&s.steps[2].cls==='',JSON.stringify(s.steps[2]));
  check('A1 Editing label ABSENT-as-reached (baseline guard: no done/active on step1)',s.steps[1]&&s.steps[1].cls==='');

  console.log('\n--- A2: timer ticks fetch-free (no POST, wait) ---');
  const t1=(await snap()).timer;
  await sleep(2200); // do NOT post anything
  const t2=(await snap()).timer;
  const toS=x=>{const[m,sec]=x.split(':').map(Number);return m*60+sec;};
  check('A2 timer advanced without a new /status',toS(t2)>toS(t1),t1+' -> '+t2);

  console.log('\n--- A3: edit (PUT /source) -> Editing reached ---');
  await req('PUT','/api/reviews/'+rid+'/source',{markdown:'# TL\n\nedited body by agent\n'});
  await sleep(2600);
  s=await snap();
  const ed=s.steps[1];
  check('A3 Editing reached (done|active)',ed&&(ed.cls==='done'||ed.cls==='active'),JSON.stringify(ed));
  check('A3 still in steps mode',/\bsteps\b/.test(s.cls),s.cls);

  console.log('\n--- A4: create+resolve a comment -> Updating comments reached ---');
  const cc=await req('POST','/api/reviews/'+rid+'/comments',{quoted_text:'edited body',text:'note',role:'agent'});
  const cid=JSON.parse(cc.body).comment_id||JSON.parse(cc.body).id||(JSON.parse(cc.body).comment&&JSON.parse(cc.body).comment.comment_id);
  await req('POST','/api/reviews/'+rid+'/comments/'+cid+'/resolve',{justification:'done'});
  await sleep(2600);
  s=await snap();
  const up=s.steps[2];
  check('A4 Updating comments reached',up&&(up.cls==='done'||up.cls==='active'),JSON.stringify(up));

  console.log('\n--- A5: hand back done ---');
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'reviewer',state:'done',message:'tightened intro'});
  await sleep(2600);
  s=await snap();
  check('A5 text "Agent updated the draft ... Your turn"',/Agent updated the draft.*Your turn/.test(s.text),s.text);
  check('A5 final timer "Agent revised in M:SS"',/Agent revised in \d+:\d\d/.test(s.timer),s.timer);
  check('A5 comment step relabelled "Resolved comments"',s.steps[2]&&/Resolved comments/.test(s.steps[2].t),JSON.stringify(s.steps[2]));
  check('A5 no active spinner on done (no li.active)',!s.steps.some(x=>x.cls==='active'),JSON.stringify(s.steps.map(x=>x.cls)));

  console.log('\nA_RESULT '+JSON.stringify({rid}));
  ws.close();c.kill();
  // emit machine summary
  console.log('SUMMARY '+JSON.stringify(RESULTS));
  process.exit(RESULTS.some(r=>!r.pass)?1:0);
})().catch(e=>{console.error('DRIVER ERROR',String(e),e&&e.stack);process.exit(2);});
