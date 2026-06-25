const {spawn}=require('child_process');const http=require('http');const https=require('https');
const CHROME=process.argv[2], BASE=process.argv[3].replace(/\/$/,'');const PORT=9000+Math.floor(Math.random()*900);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const gj=p=>new Promise((res,rej)=>{http.get('http://localhost:'+PORT+p,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>res(JSON.parse(d)));}).on('error',rej);});
function req(method,path,body){return new Promise((res,rej)=>{const u=new URL(BASE+path);const lib=u.protocol==='https:'?https:http;const data=body!=null?JSON.stringify(body):null;const r=lib.request(u,{method,headers:data?{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}:{}},rr=>{let d='';rr.on('data',c=>d+=c);rr.on('end',()=>res({code:rr.statusCode,body:d}));});r.on('error',rej);if(data)r.write(data);r.end();});}
(async()=>{
  const cr=await req('POST','/api/reviews',{title:'xss',markdown:'# X\n\nbody\n'});const rid=JSON.parse(cr.body).id;const URL=BASE+'/review/'+rid;
  const c=spawn(CHROME,['--headless=new','--disable-gpu','--no-sandbox','--remote-debugging-port='+PORT,URL],{stdio:'ignore'});
  let t;for(let i=0;i<60;i++){try{t=await gj('/json');if(t.find(x=>x.type==='page'))break;}catch(e){}await sleep(150);}
  const pg=(t||[]).find(x=>x.type==='page');const ws=new WebSocket(pg.webSocketDebuggerUrl);let id=0;const pend=new Map();
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id);}});
  await new Promise(r=>ws.addEventListener('open',r));
  const send=(meth,par={})=>new Promise(res=>{const i=++id;pend.set(i,res);ws.send(JSON.stringify({id:i,method:meth,params:par}));});
  const ev=async x=>(await send('Runtime.evaluate',{expression:x,returnByValue:true,awaitPromise:true})).result.result.value;
  await send('Runtime.enable');
  for(let i=0;i<40;i++){if(await ev('!!document.querySelector("#turnbanner")'))break;await sleep(200);}
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'agent'});
  await req('POST','/api/reviews/'+rid+'/handoff',{state:'working',owner:'x'});
  await req('POST','/api/reviews/'+rid+'/handoff',{to:'reviewer',state:'done',message:'<img src=x onerror=window.__XSS=1><b>bold</b>'});
  await sleep(2600);
  const injected=await ev('!!window.__XSS');
  const imgInBanner=await ev(`document.querySelector('#turnbanner').querySelectorAll('img,b').length`);
  const txt=await ev(`document.querySelector('#turntext').textContent`);
  console.log('  XSS executed: '+injected+'  (expect false)');
  console.log('  injected <img>/<b> elements in banner: '+imgInBanner+'  (expect 0)');
  console.log('  banner text (literal): '+JSON.stringify(txt));
  ws.close();c.kill();process.exit(injected||imgInBanner>0?1:0);
})().catch(e=>{console.error('ERR',String(e));process.exit(2);});
