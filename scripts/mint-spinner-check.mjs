// mint-spinner-check.mjs — #286 AC5 (mint pending spinner) + AC6 (regression guard: success/error
// copy + the #281 copy-to-clipboard control, which already ships). account.html 404s
// /auth/session and never renders its mint UI on the plain local tier (#224 no-auth-plane), so
// this needs a REAL hosted+login session — same magic-link login() flow account-page-check.mjs
// already uses, and the SAME Fetch-domain hold technique loading-states-check.mjs uses for the
// other four "held open" ACs.
//
//   node scripts/mint-spinner-check.mjs <hosted-origin> <server-log-path>
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BASE = process.argv[2], LOG = process.argv[3];
if (!BASE || !LOG) { console.error('usage: node scripts/mint-spinner-check.mjs <hosted-origin> <server-log-path>'); process.exit(2); }

const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }

let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c && d === undefined ? '' : `  (${JSON.stringify(d)})`)); if (!c) failed++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const toMs = s => { const m = /^([\d.eE+-]+)(m?s)$/.exec(s || ''); if (!m) return NaN;
  const n = parseFloat(m[1]); return m[2] === 'ms' ? n : n * 1000; };

async function login(email) {
  await fetch(BASE + '/auth/magic-link', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) });
  let tok;
  for (let i = 0; i < 60; i++) {
    const text = readFileSync(LOG, 'utf8');
    const m = [...text.matchAll(/auth\/redeem\?token=([A-Za-z0-9._~-]+)/g)];
    if (m.length) { tok = m[m.length - 1][1]; break; }
    await sleep(200);
  }
  if (!tok) throw new Error('no redeem token appeared in the server log for ' + email);
  const res = await fetch(BASE + '/auth/redeem', { method: 'POST', redirect: 'manual',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: 'token=' + encodeURIComponent(tok) });
  const cookie = (res.headers.get('set-cookie') || '').split(';')[0];
  if (!cookie.startsWith('mdr_session=')) throw new Error('login did not yield a session cookie: ' + JSON.stringify([res.status, cookie]));
  return cookie;
}

const PORT = 9900 + (Date.now() % 300);
const profile = mkdtempSync(join(tmpdir(), 'mint-spinner-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { rmSync(profile, { recursive: true, force: true }); } catch {} };
const overall = setTimeout(() => { console.error('mint-spinner-check: overall timeout'); cleanup(); process.exit(2); }, 120000);
overall.unref();

let ws, id = 0; const pending = new Map();
let holdFilter = () => false, heldQueue = [];
const cmd = (method, params = {}) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async expr => {
  const r = await cmd('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error('page eval threw: ' + (r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text));
  return r.result?.result?.value;
};
const media = motion => cmd('Emulation.setEmulatedMedia', { features: motion ? [{ name: 'prefers-reduced-motion', value: motion }] : [] });

async function main() {
  const cookie = await login('mint-spinner@example.com');

  let target;
  for (let i = 0; i < 60 && !target; i++) {
    try {
      const tabs = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      target = (tabs || []).find(t => t.type === 'page' && !String(t.url).startsWith('chrome-extension://'));
    } catch {}
    await sleep(250);
  }
  if (!target) { console.error('no page target found'); process.exit(2); }
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r, { once: true }));
  ws.addEventListener('message', e => {
    const m = JSON.parse(e.data);
    if (m.id !== undefined && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === 'Fetch.requestPaused') {
      const p = m.params;
      if (holdFilter(p)) heldQueue.push(p);
      else cmd('Fetch.continueRequest', { requestId: p.requestId });
    }
  });
  await cmd('Page.enable'); await cmd('Runtime.enable');
  await cmd('Network.enable');
  const origin = new URL(BASE).origin;
  const [name, value] = cookie.split('=');
  await cmd('Network.setCookie', { name, value, url: origin, path: '/', httpOnly: true, secure: origin.startsWith('https') });
  await cmd('Fetch.enable', { patterns: [{ urlPattern: '*/account/tokens*', requestStage: 'Request' }] });
  await cmd('Emulation.setDeviceMetricsOverride', { width: 1400, height: 900, deviceScaleFactor: 1, mobile: false });

  await cmd('Page.navigate', { url: BASE + '/account' });
  let ready = false;
  for (let i = 0; i < 80; i++) {
    const st = await evaluate(`document.readyState + '|' + !!document.querySelector('#acct-nav .acct-navrow')`);
    if (st === 'complete|true') { ready = true; break; }
    await sleep(250);
  }
  ok('setup: account.html loaded, authenticated (nav rendered)', ready);
  if (!ready) { cleanup(); process.exit(1); }

  await evaluate(`document.querySelector('.acct-navrow[data-section="security"]').click(); true`);
  await sleep(150);
  await evaluate(`document.querySelector('.acct-row[data-row="tokens"]').click(); true`);
  await sleep(150);

  // ============================================================================================
  // AC5: hold POST /account/tokens open — disabled, spinner + "Minting…".
  // ============================================================================================
  holdFilter = p => p.request.method === 'POST' && /\/account\/tokens$/.test(new URL(p.request.url).pathname);
  heldQueue = [];
  await evaluate(`(()=>{const i=document.getElementById('tok-label');if(i)i.value='mint-spinner-check';return true;})()`);
  await evaluate(`document.getElementById('tok-mint').click(); true`);
  let held;
  for (let i = 0; i < 40 && !held; i++) { if (heldQueue.length) held = heldQueue.shift(); else await sleep(100); }
  ok('AC5 setup: the mint POST is held open', !!held);
  await sleep(200);
  const pendingState = await evaluate(`(()=>{const b=document.getElementById('tok-mint');
    return JSON.stringify({disabled:b.disabled, text:b.textContent, hasSpinner:!!b.querySelector('.spin')});})()`);
  const p = JSON.parse(pendingState);
  ok('AC5: mint control is disabled', p.disabled, p);
  ok('AC5: mint control reads "Minting…"', /Minting…/.test(p.text), p.text);
  ok('AC5: mint control shows a spinner', p.hasSpinner, p);

  // motion, both media states, WHILE held (so the element stays present for the whole assertion).
  await media(null);
  const before = await evaluate(`(()=>{const el=document.querySelector('#tok-mint .spin');if(!el)return null;
    const cs=getComputedStyle(el);const a=el.getAnimations?el.getAnimations():[];
    return JSON.stringify({name:cs.animationName,dur:cs.animationDuration,iter:cs.animationIterationCount,t:a[0]?a[0].currentTime:null});})()`);
  ok('AC10 (mint spinner): element present for motion sampling', !!before);
  if (before) {
    const b = JSON.parse(before);
    ok('AC10 (mint spinner): computed animation-name is spin', b.name === 'spin', b.name);
    ok('AC10 (mint spinner): computed animation-duration is 900ms', Math.abs(toMs(b.dur) - 900) < 1, b.dur);
    ok('AC10 (mint spinner): computed animation-iteration-count is infinite', b.iter === 'infinite', b.iter);
    await sleep(120);
    const afterT = await evaluate(`(()=>{const el=document.querySelector('#tok-mint .spin');const a=el&&el.getAnimations?el.getAnimations():[];return a[0]?a[0].currentTime:null;})()`);
    ok('AC10 (mint spinner): currentTime advances ~100ms apart', typeof afterT === 'number' && typeof b.t === 'number' && afterT > b.t, { before: b.t, after: afterT });

    await media('reduce');
    await sleep(50);
    const rmBefore = await evaluate(`(()=>{const el=document.querySelector('#tok-mint .spin');const cs=getComputedStyle(el);const a=el.getAnimations?el.getAnimations():[];
      return JSON.stringify({dur:cs.animationDuration,iter:cs.animationIterationCount,t:a[0]?a[0].currentTime:null,n:a.length});})()`);
    const rb = JSON.parse(rmBefore);
    ok('AC10 (mint spinner, reduced motion): animation-duration collapses to ~0.01ms', toMs(rb.dur) < 0.02, rb.dur);
    ok('AC10 (mint spinner, reduced motion): animation-iteration-count collapses to 1', rb.iter === '1', rb.iter);
    await sleep(120);
    const rmAfter = await evaluate(`(()=>{const el=document.querySelector('#tok-mint .spin');if(!el)return null;const a=el.getAnimations?el.getAnimations():[];return a[0]?a[0].currentTime:null;})()`);
    const advanced = (typeof rmAfter === 'number' && typeof rb.t === 'number') ? rmAfter > rb.t : false;
    ok('AC10 (mint spinner, reduced motion): currentTime does NOT advance', !advanced, { before: rb.t, after: rmAfter, n: rb.n });
    await media(null);
  }

  // release: 2xx -> AC6 regression guard (already ships, per #281): #minted block + copy control.
  await cmd('Fetch.continueRequest', { requestId: held.requestId });
  let minted = false;
  for (let i = 0; i < 40; i++) { if (await evaluate(`!!document.getElementById('tok-plain')`)) { minted = true; break; } await sleep(150); }
  ok('AC5->AC6: on 2xx the pending state resolves to the #minted success block', minted);
  if (minted) {
    const after = await evaluate(`(()=>{const b=document.getElementById('tok-mint');
      return JSON.stringify({mintBtnGone: !b, heading:(document.querySelector('.acct-minted-h')||{}).textContent, hasCopyBtn:!!document.getElementById('tok-copy')});})()`);
    const a = JSON.parse(after);
    ok('AC6 regression guard: mint button replaced by the success block', a.mintBtnGone, a);
    ok('AC6 regression guard: success heading "Copy it now — it is shown only once"', a.heading === '1. Copy it now — it is shown only once', a.heading);
    ok('AC6 regression guard: the copy control exists (already shipped by #281)', a.hasCopyBtn, a);
    // clicking it should place the token on the clipboard OR degrade visibly (documented escape
    // hatch when headless Chrome without focus refuses the write) — same contract account-page-
    // check.mjs already asserts; not re-derived here, just confirmed it still resolves either way.
    await evaluate(`document.getElementById('tok-copy').click(); true`);
    await sleep(150);
    const label = await evaluate(`document.getElementById('tok-copy').textContent`);
    ok('AC6 regression guard: clicking copy changes its label (copied, or a visible degrade)',
      label === 'copied' || label === 'select to copy', label);
  }

  // ============================================================================================
  // AC5/AC6 error path: forced non-2xx (a real 4xx, bad CSRF) -> spinner clears, exact error copy,
  // button restored (a retry click sees the plain button again, not a stuck "Minting…").
  // ============================================================================================
  await evaluate(`document.getElementById('tok-done')?.click(); true`);
  await sleep(100);
  await evaluate(`window.__realCSRF = CSRF; CSRF = 'not-the-real-token'; true`);
  holdFilter = () => false; heldQueue = [];
  await evaluate(`(()=>{const i=document.getElementById('tok-label');if(i)i.value='should-fail';return true;})()`);
  await evaluate(`document.getElementById('tok-mint').click(); true`);
  await sleep(500);
  const errState = await evaluate(`(()=>{const f=document.getElementById('flash');const b=document.getElementById('tok-mint');
    return JSON.stringify({flash:f.textContent, flashClass:f.className, btnText:b?b.textContent:null, btnDisabled:b?b.disabled:null, btnHasSpinner:b?!!b.querySelector('.spin'):null});})()`);
  const es = JSON.parse(errState);
  ok('AC6 regression guard: a real 4xx reads "Could not mint the token (<status>). Nothing was created."',
    /^Could not mint the token \(\d+\)\. Nothing was created\.$/.test(es.flash), es.flash);
  ok('AC5: on failure the button is restored (not stuck disabled/spinning)', es.btnDisabled === false && !es.btnHasSpinner, es);
  ok('AC5: on failure the label reads "Mint token" again (not stuck "Minting…")', es.btnText === 'Mint token', es.btnText);
  await evaluate(`CSRF = window.__realCSRF; true`);

  console.log(failed ? `\n${failed} case(s) failed` : '\nall mint-spinner cases pass');
  cleanup();
  process.exit(failed ? 1 : 0);
}

main().catch(e => { console.error('FATAL:', e); cleanup(); process.exit(2); });
