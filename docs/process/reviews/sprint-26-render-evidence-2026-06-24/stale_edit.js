const {spawn}=require('child_process');const http=require('http');const https=require('https');
const CHROME=process.argv[2], BASE=process.argv[3].replace(/\/$/,'');const PORT=9000+Math.floor(Math.random()*900);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const gj=p=>new Promise((res,rej)=>{http.get('http://localhost:'+PORT+p,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>res(JSON.parse(d)));}).on('error',rej);});
function req(method,path,body){return new Promise((res,rej)=>{const u=new URL(BASE+path);const lib=u.protocol==='https:'?https:http;const data=body!=null?JSON.stringify(body):null;const r=lib.request(u,{method,headers:data?{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}:{}},rr=>{let d='';rr.on('data',c=>d+=c);rr.on('end',()=>res({code:rr.statusCode,body:d}));});r.on('error',rej);if(data)r.write(data);r.end();});}
(async()=>{
  const cr=await req('POST','/api/reviews',{title:'se',markdown:'# SE\n\nbody\n'});const rid=JSON.parse(cr.body).id;const URL=BASE+'/review/'+rid;
  const c=spawn(CHROME,['--headless=new','--disable-gpu','--no-sandbox','--remote-debugging-port='+PORT,URL],{stdio:'ignore'});
  let t;for(let i=0;i<60;i++){try{t=await gj('/json');if(t.find(x=>x.type==='page'))break;}catch(e){}await sleep(150);}
  const pg=(t||[]).find(x=>x.type==='page');const ws=new WebSocket(pg.webSocketDebuggerUrl);let id=0;const pend=new Map();
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id);}});
  await new Promise(r=>ws.addEventListener('open',r));
  const send=(meth,par={})=>new Promise(res=>{const i=++id;pend.set(i,res);ws.send(JSON.stringify({id:i,method:meth,params:par}));});
  const ev=async x=>(await send('Runtime.evaluate',{expression:x,returnByValue:true,awaitPromise:true})).result.result.value;
  await send('Runtime.enable');
  for(let i=0;i<40;i++){if(await ev('!!document.querySelector("#turnbanner")'))break;await sleep(200);}
  const stepCls=async()=>JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('#turnsteps li')].map(li=>li.className))`));
  // ROUND 1: claim, edit (source_updated bumps high), comment+resolve, done
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'agent'});
  await req('POST','/api/reviews/'+rid+'/handoff',{state:'working',owner:'r1'});
  await req('PUT','/api/reviews/'+rid+'/source',{markdown:'# SE\n\nround1 edit\n'});
  await sleep(2600);
  console.log('  round1 after edit:', JSON.stringify(await stepCls()), '(expect [active/done, active/done, ...])');
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'reviewer',state:'done',message:'r1 done'});
  await sleep(2600);
  // ROUND 2: NEW turn. The stale (round1) source_updated is now < new turn_updated. "Editing" must be PENDING.
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'agent'});
  await req('POST','/api/reviews/'+rid+'/handoff',{state:'working',owner:'r2'});
  await sleep(2600);
  const cls=await stepCls();
  console.log('  round2 fresh claim:', JSON.stringify(cls));
  const editPending = cls[1]==='';
  const cmtPending = cls[2]==='';
  console.log('  '+(editPending?'ok':'FAIL')+' stale source_updated does NOT light Editing on new turn');
  console.log('  '+(cmtPending?'ok':'FAIL')+' stale comments_updated does NOT light Updating on new turn');
  ws.close();c.kill();process.exit(editPending&&cmtPending?0:1);
})().catch(e=>{console.error('ERR',String(e));process.exit(2);});
