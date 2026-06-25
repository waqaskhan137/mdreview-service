const {spawn}=require('child_process');const http=require('http');const https=require('https');
const CHROME=process.argv[2], BASE=process.argv[3].replace(/\/$/,'');
const PORT=9000+Math.floor(Math.random()*900);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const gj=p=>new Promise((res,rej)=>{http.get('http://localhost:'+PORT+p,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>res(JSON.parse(d)));}).on('error',rej);});
function req(method,path,body){return new Promise((res,rej)=>{const u=new URL(BASE+path);const lib=u.protocol==='https:'?https:http;const data=body!=null?JSON.stringify(body):null;const r=lib.request(u,{method,headers:data?{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}:{}},rr=>{let d='';rr.on('data',c=>d+=c);rr.on('end',()=>res({code:rr.statusCode,body:d}));});r.on('error',rej);if(data)r.write(data);r.end();});}
const RESULTS=[];
function check(label,cond,extra){RESULTS.push({label,pass:!!cond,extra:extra||''});console.log((cond?'  ok  ':'  FAIL')+' '+label+(extra?'   ['+extra+']':''));}

async function openPage(rid){
  const URL=BASE+'/review/'+rid;
  const c=spawn(CHROME,['--headless=new','--disable-gpu','--no-sandbox','--remote-debugging-port='+PORT,URL],{stdio:'ignore'});
  let t;for(let i=0;i<60;i++){try{t=await gj('/json');if(t.find(x=>x.type==='page'))break;}catch(e){}await sleep(150);}
  const pg=(t||[]).find(x=>x.type==='page');
  const ws=new WebSocket(pg.webSocketDebuggerUrl);let id=0;const pend=new Map();
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id);}});
  await new Promise(r=>ws.addEventListener('open',r));
  const send=(meth,par={})=>new Promise(res=>{const i=++id;pend.set(i,res);ws.send(JSON.stringify({id:i,method:meth,params:par}));});
  const ev=async x=>(await send('Runtime.evaluate',{expression:x,returnByValue:true,awaitPromise:true})).result.result.value;
  await send('Runtime.enable');
  for(let i=0;i<40;i++){if(await ev('!!document.querySelector("#turnbanner")'))break;await sleep(200);}
  return {c,ws,ev};
}
const snapEv=`JSON.stringify((function(){const b=document.querySelector('#turnbanner');const steps=[...document.querySelectorAll('#turnsteps li')].map(li=>({t:li.textContent,cls:li.className}));return {cls:b.className,text:document.querySelector('#turntext').textContent,timer:document.querySelector('#turntimer').textContent,steps,allText:b.textContent};})())`;

(async()=>{
  // === B: signal-honesty reply-then-blocked ===
  console.log('--- B: reply-then-blocked (Resolved must NEVER appear) ---');
  let cr=await req('POST','/api/reviews',{title:'b',markdown:'# B\n\nbody for B scenario\n'});
  let rid=JSON.parse(cr.body).id;
  let P=await openPage(rid);
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'agent'});
  await req('POST','/api/reviews/'+rid+'/handoff',{state:'working',owner:'gate-b'});
  // create a comment + REPLY (no resolve) -> comments_updated bumps
  let cc=await req('POST','/api/reviews/'+rid+'/comments',{quoted_text:'body for B',text:'q',role:'reviewer'});
  let cid=JSON.parse(cc.body).comment_id||JSON.parse(cc.body).id;
  await req('POST','/api/reviews/'+rid+'/comments/'+cid+'/reply',{text:'thinking',role:'agent'});
  await sleep(2600);
  let s=JSON.parse(await P.ev(snapEv));
  check('B Updating comments may show (reached)',s.steps[2]&&s.steps[2].cls!=='',JSON.stringify(s.steps[2]));
  check('B "Resolved" NOT present while working',!/Resolved/.test(s.allText),s.allText.replace(/\s+/g,' ').slice(0,120));
  // now hand back blocked
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'reviewer',state:'blocked',message:'need a decision'});
  await sleep(2600);
  s=JSON.parse(await P.ev(snapEv));
  check('B blocked banner "Agent needs you"',/Agent needs you/.test(s.text),s.text);
  check('B NOT a crash banner (.warn absent)',!/\bwarn\b/.test(s.cls),s.cls);
  check('B "Resolved" NEVER appears this turn',!/Resolved/.test(s.allText),s.allText.replace(/\s+/g,' ').slice(0,140));
  P.ws.close();P.c.kill();

  // === C: reopen-after-done guard (fresh page load AFTER done) ===
  console.log('\n--- C: fresh page load after a done (no bogus duration) ---');
  cr=await req('POST','/api/reviews',{title:'c',markdown:'# C\n\nbody C\n'});
  rid=JSON.parse(cr.body).id;
  // drive the whole turn WITHOUT any page open
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'agent'});
  await req('POST','/api/reviews/'+rid+'/handoff',{state:'working',owner:'gate-c'});
  await req('PUT','/api/reviews/'+rid+'/source',{markdown:'# C\n\nedited C\n'});
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'reviewer',state:'done',message:'done C'});
  // NOW open a fresh page that never saw turn==agent
  P=await openPage(rid);
  await sleep(2600);
  s=JSON.parse(await P.ev(snapEv));
  check('C done banner shows',/Agent updated the draft/.test(s.text),s.text);
  check('C NO bogus "revised in" duration',!/revised in/.test(s.allText),s.timer+' | '+s.allText.replace(/\s+/g,' ').slice(0,100));
  P.ws.close();P.c.kill();

  // === D1: crash path (MR-068) ===
  console.log('\n--- D1: crash signal (MR-068 intact) ---');
  cr=await req('POST','/api/reviews',{title:'d1',markdown:'# D1\n\nbody\n'});
  rid=JSON.parse(cr.body).id;
  P=await openPage(rid);
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'agent'});
  await req('POST','/api/reviews/'+rid+'/handoff',{state:'working',owner:'gate-d'});
  await sleep(1500);
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'reviewer',state:'blocked',message:'agent process exited 1 without finishing'});
  await sleep(2600);
  s=JSON.parse(await P.ev(snapEv));
  check('D1 crash text "Agent run stopped"',/Agent run stopped/.test(s.text),s.text);
  check('D1 crash uses .warn',/\bwarn\b/.test(s.cls),s.cls);
  check('D1 crash not in steps mode',!/\bsteps\b/.test(s.cls),s.cls);
  P.ws.close();P.c.kill();

  // === D2: pickup-timeout (MR-066) ===
  console.log('\n--- D2: pickup-timeout (MR-066 intact) ---');
  // PICKUP_GRACE_S=60. We cannot wait 60s of wall easily; instead flip to agent and check the
  // pre-grace spinner, then verify the warn arm by NOT claiming and checking the grace logic via clock.
  // To exercise the >grace branch deterministically we backdate is impossible (server sets turn_updated=now).
  // So: assert pre-grace state = "waiting for an agent" + loading (spinner), no steps, no timer leak.
  cr=await req('POST','/api/reviews',{title:'d2',markdown:'# D2\n\nbody\n'});
  rid=JSON.parse(cr.body).id;
  P=await openPage(rid);
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'agent'});  // parked, never claimed
  await sleep(2600);
  s=JSON.parse(await P.ev(snapEv));
  check('D2 pre-grace "waiting for an agent"',/waiting for an agent/.test(s.text),s.text);
  check('D2 pre-grace uses loading spinner',/\bloading\b/.test(s.cls),s.cls);
  check('D2 parked NOT in steps mode',!/\bsteps\b/.test(s.cls),s.cls);
  check('D2 timer cleared when parked',s.timer==='',JSON.stringify(s.timer));
  check('D2 steps cleared when parked',s.steps.length===0,JSON.stringify(s.steps));
  P.ws.close();P.c.kill();

  console.log('\nSUMMARY '+JSON.stringify(RESULTS));
  process.exit(RESULTS.some(r=>!r.pass)?1:0);
})().catch(e=>{console.error('DRIVER ERROR',String(e),e&&e.stack);process.exit(2);});
