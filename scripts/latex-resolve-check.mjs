// scripts/latex-resolve-check.mjs — #342 "LaTeX viewer has no Resolved surface, so it cannot
// safely take the Resolve action". Rendered-outcome checks for the ported #resolved/.rcard panel
// and the resolve/undo action on top of it, in latex-viewer.html. Zero-dep: raw CDP over Node's
// built-in WebSocket + fetch, self-contained like scripts/latex-threeway-check.mjs (boots its own
// throwaway local instance rather than taking a URL an .sh wrapper must supply).
//
// WHAT THIS PINS (ticket ACs):
//   AC1 the Resolved N toggle count is REAL (0 with nothing resolved, an explicit empty state
//       rather than a blank box, then N after N resolves) and the panel lists one card per
//       resolved thread carrying its quoted anchor + thread body.
//   AC2 Reopen from the panel calls the EXISTING reopenComment(cid,text) — real API state flips
//       resolved -> reopened, the card leaves the panel and reappears in the active rail, no
//       navigation.
//   AC3 the Resolve trigger + its undo toast match viewer.html's #287 behaviour: resolve, a
//       "Comment resolved / undo" action-toast, undo restores the thread (click path).
//   AC4 permission parity: setCommentVisible(false) (the exact function /status's can_comment
//       gate drives) hides the Resolve trigger and every reopen box, while the resolved panel
//       itself and its read content stay visible (#320 "keep every READ surface" class).
//   AC5 THE ticket's namesake: after the undo window fully expires with no click, the resolved
//       thread is STILL reachable and reopenable from the panel, and nothing auto-reverted
//       server-side in the meantime. This is what #287 refused to ship here without.
//
// Every seeded comment is created HERE, over the real HTTP API against the real running instance
// (fetch() from Node) — no synthetic DOM events stand in for a resolve or a reopen; every outcome
// is checked BOTH in the DOM and against a follow-up GET of real server state.
//
// Needs: a Chrome/Chromium binary. Runs against a THROWAWAY local instance; no host, no staging.
//   export PATH=".../node/bin:$PATH"; node scripts/latex-resolve-check.mjs
import { spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = join(HERE, '..');
const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }

let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c ? '' : `  (${JSON.stringify(d)})`)); if (!c) failed++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

function freePort() {
  const py = spawnSync('python3', ['-c', 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()']);
  return py.stdout.toString().trim();
}

const port = freePort();
const dataDir = join(ROOT, '.scratch', 'latex_resolve_data_' + Date.now());
spawnSync('mkdir', ['-p', dataDir]);
const srv = spawn('python3', ['-m', 'mdreview'], {
  cwd: ROOT,
  env: { ...process.env, MDREVIEW_DATA: dataDir, PORT: port, MDREVIEW_WEB_DIR: join(ROOT, 'web', 'app'),
    MDREVIEW_ENABLE_LATEX: '1', PYTHONPATH: join(ROOT, 'src') },
  stdio: ['ignore', 'ignore', 'ignore'],
});
async function waitUp() {
  for (let i = 0; i < 60; i++) {
    try { const r = await fetch(`http://127.0.0.1:${port}/healthz`); if (r.ok) return true; } catch {}
    await sleep(250);
  }
  return false;
}

let chrome, ws;
async function cleanup() {
  try { ws?.close(); } catch {}
  try { chrome?.kill(); } catch {}
  try { srv.kill(); } catch {}
  try { rmSync(dataDir, { recursive: true, force: true }); } catch {}
}
process.on('exit', () => { try { chrome?.kill(); } catch {} try { srv.kill(); } catch {} });

if (!(await waitUp())) { console.error('server never came up'); await cleanup(); process.exit(1); }

const API_BASE = `http://127.0.0.1:${port}`;
async function apiPost(rid, path, body) {
  const r = await fetch(`${API_BASE}/api/reviews/${rid}${path}`, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  return { status: r.status, json: r.ok ? await r.json() : null };
}
async function apiGet(rid, path) {
  const r = await fetch(`${API_BASE}/api/reviews/${rid}${path}`);
  return { status: r.status, json: r.ok ? await r.json() : null };
}

const TEX = ['\\documentclass{article}', '\\begin{document}', '\\section{Intro}',
  'line four content', 'line five content', 'line six content', 'line seven content',
  'line eight content', 'line nine content', '\\end{document}'].join('\n');
const createRes = await fetch(`${API_BASE}/api/reviews`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ title: 'resolve-fixture', kind: 'latex', markdown: TEX }),
});
const rid = (await createRes.json()).id;
async function mkComment(n, snippet) {
  const { json } = await apiPost(rid, '/comments', { anchor: { quoted_text: snippet, block_num: String(n) }, text: 'note on line ' + n });
  return json.comment_id;
}
// c1 AC2 (panel reopen), c2 AC3 (toast-click undo), c3 AC5 (post-expiry recovery — the ticket's
// point), c4 AC4/theme (resolved via the UI, then probed for permission + theme), c5 stays OPEN
// throughout so AC4 has an active .gres to probe hiding on.
const c1 = await mkComment(4, 'line four content');
const c2 = await mkComment(5, 'line five content');
const c3 = await mkComment(6, 'line six content');
const c4 = await mkComment(7, 'line seven content');
const c5 = await mkComment(8, 'line eight content');
ok('fixture: 5 independent open comments seeded over the real API', [c1, c2, c3, c4, c5].every(Boolean));

const profile = mkdtempSync(join(tmpdir(), 'latex-resolve-'));
const cdpPort = 9700 + (Date.now() % 400);
chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
let target;
for (let i = 0; i < 60; i++) {
  try {
    const tabs = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
    target = (tabs || []).find(t => t.type === 'page' && !String(t.url).startsWith('chrome-extension://'));
    if (target) break;
  } catch {}
  await sleep(250);
}
if (!target) { console.error('no page target'); await cleanup(); process.exit(2); }
ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r, { once: true }));
let id = 0; const pending = new Map();
ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async expr => {
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error('page eval threw: ' +
    (r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text));
  return r.result?.result?.value;
};
// evalJson: expr must itself evaluate (client-side) to a JSON STRING (via JSON.stringify) — this
// wrapper is the ONE place that parses it back into an object, so every call site below just
// writes one JSON.stringify({...}) and never juggles nested quote-balancing itself.
const evalJson = async expr => JSON.parse(await evaluate(expr));
const bgOf = tok => evaluate(`(()=>{const p=document.createElement('div');
  p.style.cssText='position:absolute;left:-9999px;background:var(${tok})';
  document.body.appendChild(p);const v=getComputedStyle(p).backgroundColor;p.remove();return v;})()`);

await send('Page.enable'); await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1500, height: 900, deviceScaleFactor: 1, mobile: false });

async function gotoAndWait(url, marker) {
  await send('Page.navigate', { url });
  for (let i = 0; i < 80; i++) {
    const st = await evaluate(`document.readyState + '|' + !!document.querySelector('${marker}')`);
    if (typeof st === 'string' && st === 'complete|true') return true;
    await sleep(250);
  }
  return false;
}

const url = `${API_BASE}/review/${rid}`;
const ready = await gotoAndWait(url, '#resbtn');
ok('the latex viewer actually loaded with the fixture (probe is not vacuous)', ready,
  await evaluate(`document.readyState + ' gcards=' + document.querySelectorAll('.gcard').length`));
if (!ready) { console.log('\naborting: nothing to sample'); await cleanup(); process.exit(1); }
await sleep(400);

// #railcol is the live rail; renderComments() also mirrors each card into #cmtdock (the narrow
// floating dock) via cloneNode, so counting '.gcard' unscoped double-counts every card. Scope to
// the rail for a true count.
const gcardCount = await evaluate(`document.querySelectorAll('#railcol .gcard').length`);
ok('fixture: all 5 seeded comments render as active .gcard cards', gcardCount === 5, gcardCount);

// The click handler TOGGLES #resolved — driving it by blind clicks means each call site has to
// know the panel's current state to predict the result. This drives the real #resbtn click
// handler (not a hand-rolled class write) but only clicks when the state actually needs to
// change, so every call site below can just say what it wants.
async function setResolvedPanel(open) {
  const showing = await evaluate(`document.getElementById('resolved').classList.contains('show')`);
  if (showing !== open) { await evaluate(`(document.querySelector('#resbtn').click(),true)`); await sleep(150); }
}

// ================= AC1: empty state before anything is resolved ================================
await setResolvedPanel(true);
const emptyState = await evalJson(`JSON.stringify({
  btn: document.querySelector('#resbtn').textContent.trim(),
  count: document.querySelector('.resolved-count').textContent.trim(),
  itemsChildren: document.querySelector('#resitems').children.length,
  emptyVisible: getComputedStyle(document.querySelector('#resempty')).display !== 'none',
  panelVisible: getComputedStyle(document.querySelector('#resolved')).display !== 'none',
})`);
ok('AC1: with nothing resolved, #resbtn reads "Resolved 0"', emptyState.btn === 'Resolved 0', emptyState);
ok('AC1: the panel opens and shows the EXPLICIT empty state, not a blank box',
  emptyState.panelVisible && emptyState.emptyVisible && emptyState.itemsChildren === 0, emptyState);
await setResolvedPanel(false);

// ================= AC1 + AC2: resolve c1, verify panel + reopen from the panel =================
await evaluate(`document.querySelector('.gcard[data-id="${c1}"] [data-act=resolve]').click(); true`);
await sleep(400);
const afterResolve1 = await evalJson(`JSON.stringify({
  btn: document.querySelector('#resbtn').textContent.trim(),
  gcardGone: !document.querySelector('.gcard[data-id="${c1}"]'),
})`);
ok('AC1: #resbtn count updates to 1 IMMEDIATELY on resolve (reachable before any undo window matters)',
  afterResolve1.btn === 'Resolved 1', afterResolve1);
ok('AC2 setup: the resolved card leaves the active rail', afterResolve1.gcardGone, afterResolve1);

await setResolvedPanel(true);
const rcard1 = await evalJson(`(()=>{
  const r=document.querySelector('.rcard[data-id="${c1}"]');
  if(!r) return JSON.stringify({present:false});
  return JSON.stringify({present:true,
    hasQuote: r.textContent.includes('line four content'),
    hasThread: r.textContent.includes('note on line 4'),
    hasReopen: !!r.querySelector('[data-act=reopen]'),
    hasTextarea: !!r.querySelector('.reopenbox textarea')});
})()`);
ok('AC1: the resolved card carries its quoted anchor and thread body (real content, not a stub)',
  rcard1.present && rcard1.hasQuote && rcard1.hasThread, rcard1);
ok('AC2 setup: the resolved card has a Reopen control with a reply textarea', rcard1.hasReopen && rcard1.hasTextarea, rcard1);

const c1BeforeReopen = await apiGet(rid, `/comments/${c1}`);
ok('AC2: server state is "resolved" before the panel Reopen is clicked', c1BeforeReopen.json?.status === 'resolved', c1BeforeReopen.json?.status);
await evaluate(`(()=>{
  const r=document.querySelector('.rcard[data-id="${c1}"]');
  r.querySelector('.reopenbox textarea').value='reopening via the panel';
  r.querySelector('[data-act=reopen]').click();
})();true`);
await sleep(400);
const c1After = await apiGet(rid, `/comments/${c1}`);
ok('AC2: reopening from the PANEL (not the undo toast) flips real server state to "reopened"',
  c1After.json?.status === 'reopened', c1After.json?.status);
ok('AC2: the optional reply text was actually sent through the existing reopenComment(cid,text)',
  (c1After.json?.thread || []).some(e => e.text === 'reopening via the panel'), c1After.json?.thread);
const c1Dom = await evalJson(`JSON.stringify({
  gcard: !!document.querySelector('.gcard[data-id="${c1}"]'),
  rcard: !!document.querySelector('.rcard[data-id="${c1}"]'),
  btn: document.querySelector('#resbtn').textContent.trim(),
})`);
ok('AC2: the card is back in the active rail with NO page reload (.gcard present, .rcard gone, count back to 0)',
  c1Dom.gcard === true && c1Dom.rcard === false && c1Dom.btn === 'Resolved 0', c1Dom);

// ================= AC3: resolve c2, undo via the TOAST (viewer.html's #287 accelerator path) ===
await evaluate(`document.querySelector('.gcard[data-id="${c2}"] [data-act=resolve]').click(); true`);
await sleep(400);
const toastNow = await evalJson(`(()=>{
  const t=document.getElementById('toast');
  return JSON.stringify({msg:t.querySelector('span').textContent.trim(),
    label:t.querySelector('.toastbtn').textContent.trim(),
    hasAction:t.classList.contains('hasaction'), opacity:getComputedStyle(t).opacity});
})()`);
ok('AC3: resolve shows a "Comment resolved / undo" action-toast, matching viewer.html\'s #287 copy',
  toastNow.msg === 'Comment resolved' && toastNow.label === 'undo' && toastNow.hasAction && parseFloat(toastNow.opacity) > 0,
  toastNow);
await evaluate(`document.querySelector('#toast .toastbtn').click(); true`);
await sleep(400);
const c2After = await apiGet(rid, `/comments/${c2}`);
ok('AC3: clicking undo restores the thread — real server state back to "reopened"',
  c2After.json?.status === 'reopened', c2After.json?.status);
const c2Dom = await evalJson(`JSON.stringify({gcard: !!document.querySelector('.gcard[data-id="${c2}"]'), rcard: !!document.querySelector('.rcard[data-id="${c2}"]')})`);
ok('AC3: the card is back in the active rail after undo', c2Dom.gcard === true && c2Dom.rcard === false, c2Dom);

// ================= AC5: THE ticket's point — post-expiry recovery, no click on the toast ========
await evaluate(`document.querySelector('.gcard[data-id="${c3}"] [data-act=resolve]').click(); true`);
let t0 = null;
for (let i = 0; i < 40 && !t0; i++) {
  const has = await evaluate(`document.getElementById('toast').classList.contains('hasaction')`);
  if (has) t0 = Date.now(); else await sleep(150);
}
ok('AC5 setup: the undo toast appeared for c3', !!t0);
while (Date.now() - t0 < 10600) await sleep(300);   // past UNDO_MS (10000) + the opacity fade
const toastExpired = await evaluate(`document.getElementById('toast').classList.contains('hasaction')`);
ok('AC5: the undo toast is inert after the window expires (no click happened)', toastExpired === false, toastExpired);
const c3Untouched = await apiGet(rid, `/comments/${c3}`);
ok('AC5: an expired, un-clicked undo changed NOTHING server-side (still "resolved")',
  c3Untouched.json?.status === 'resolved', c3Untouched.json?.status);
// the panel — NOT the dead toast — is the only path back now
await setResolvedPanel(true);
const c3Panel = await evalJson(`(()=>{
  const r=document.querySelector('.rcard[data-id="${c3}"]');
  return JSON.stringify({present:!!r, hasReopen: r?!!r.querySelector('[data-act=reopen]'):false});
})()`);
ok('AC5: PAST the undo window, the resolved thread is still reachable in the panel with a working Reopen',
  c3Panel.present && c3Panel.hasReopen, c3Panel);
await evaluate(`document.querySelector('.rcard[data-id="${c3}"] [data-act=reopen]').click(); true`);
await sleep(400);
const c3Reopened = await apiGet(rid, `/comments/${c3}`);
ok('AC5: the panel Reopen (the ONLY path back once undo is dead) actually works — server state "reopened"',
  c3Reopened.json?.status === 'reopened', c3Reopened.json?.status);

// ================= AC4 / #320: permission parity ================================================
// c4: resolve it through the real UI so a genuine .rcard exists to probe.
await evaluate(`document.querySelector('.gcard[data-id="${c4}"] [data-act=resolve]').click(); true`);
await sleep(400);
await setResolvedPanel(true);

// ---- both-theme rendered check on the panel itself (before flipping to viewonly) --------------
const panelByTheme = {};
for (const theme of ['light', 'dark']) {
  await evaluate(`document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)})`);
  panelByTheme[theme] = await evalJson(`(()=>{
    const p=document.getElementById('resolved');
    const cs=getComputedStyle(p);
    return JSON.stringify({bg:cs.backgroundColor,border:cs.borderColor,visible:cs.display!=='none'});
  })()`);
}
ok('theme: the resolved panel is visible in both themes', panelByTheme.light.visible && panelByTheme.dark.visible, panelByTheme);
ok('theme: panel background actually differs light vs dark (not a hardcoded literal)',
  panelByTheme.light.bg !== panelByTheme.dark.bg, panelByTheme);
await evaluate(`document.documentElement.setAttribute('data-theme','light')`);
const accentLight = await bgOf('--accent');
await evaluate(`document.documentElement.setAttribute('data-theme','dark')`);
const accentDark = await bgOf('--accent');
ok('positive control: --accent actually differs between themes (the flip is real, not a no-op)',
  accentLight !== accentDark, { accentLight, accentDark });

// ---- viewonly: the exact function the /status poll calls, not a hand-rolled class toggle -------
await evaluate(`setCommentVisible(false); renderComments(); true`);
await sleep(150);
const vo = await evalJson(`(()=>{
  const gres=document.querySelector('.gcard[data-id="${c5}"] [data-act=resolve]');
  const rbox=document.querySelector('.rcard[data-id="${c4}"] .reopenbox');
  const rcard=document.querySelector('.rcard[data-id="${c4}"]');
  const panel=document.getElementById('resolved');
  return JSON.stringify({
    gresHidden: !!gres && getComputedStyle(gres).display==='none',
    reopenboxHidden: !!rbox && getComputedStyle(rbox).display==='none',
    rcardStillReadable: !!rcard && getComputedStyle(rcard).display!=='none' && rcard.textContent.includes('line seven content'),
    panelStillVisible: getComputedStyle(panel).display!=='none',
  });
})()`);
ok('AC4: the Resolve trigger is hidden under viewonly (an active card\'s .gres)', vo.gresHidden === true, vo);
ok('AC4: the Reopen box is hidden under viewonly (a resolved card\'s .reopenbox)', vo.reopenboxHidden === true, vo);
ok('#320: the resolved surface stays a READ surface under viewonly — the card and its quote/thread are still shown',
  vo.rcardStillReadable === true, vo);
ok('#320: the panel itself is never hidden by viewonly (only the author controls are)', vo.panelStillVisible === true, vo);
await evaluate(`setCommentVisible(true); renderComments(); true`);

console.log(failed ? `\n${failed} case(s) failed` : '\nall #342 latex-resolve cases pass');
await cleanup();
process.exit(failed ? 1 : 0);
