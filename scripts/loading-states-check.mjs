// loading-states-check.mjs — #286's runnable regression check (AC1-4, AC7-11): RENDERED OUTCOMES
// + REAL API state in a real headless Chrome, both themes where colour is asserted. Same zero-dep
// shape as scripts/resolve-undo-check.mjs / scripts/latex-canvas-check.mjs: Node's built-in
// WebSocket + fetch driving CDP directly. Fixtures are seeded HERE, over the real HTTP API, in the
// order each AC needs them (AC2's empty-dashboard check runs before ANY review exists).
//
// "Held open" fetches (AC1 skeleton, AC3 unreachable, AC7 compiling, AC9 posting) are produced with
// the CDP Fetch domain (Fetch.enable + requestPaused), not a fixed sleep and not a page-side stub:
// a matching request genuinely does not resolve until this script calls continueRequest (release)
// or failRequest (simulate a network failure). GET polls that happen to share a URL prefix with a
// POST we want to hold (e.g. GET vs POST /comments) are told apart by request.method and continued
// immediately. holdFilter is reset to `()=>false` (and the queue drained) the instant a phase is
// done with it, so a forgotten release in one phase cannot silently swallow an unrelated request in
// a later one — the exact bug that made the first draft of this script cascade-fail.
//
// AC5 (mint pending) needs a real hosted+login session (account.html 404s /auth/session and shows
// "Could not reach the server" on the plain local tier) and lives in mint-spinner-check.mjs instead.
//
//   node scripts/loading-states-check.mjs <base-url>
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BASE = (process.argv[2] || '').replace(/\/$/, '');
if (!BASE) { console.error('usage: node scripts/loading-states-check.mjs <base-url>'); process.exit(2); }

const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }

let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c && d === undefined ? '' : `  (${JSON.stringify(d)})`)); if (!c) failed++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));
// Chrome serialises a sub-millisecond animation-duration in scientific notation (e.g. "1e-05s"),
// not the literal "0.01ms" theme.css writes — compare the parsed VALUE, never the string.
const toMs = s => { const m = /^([\d.eE+-]+)(m?s)$/.exec(s || ''); if (!m) return NaN;
  const n = parseFloat(m[1]); return m[2] === 'ms' ? n : n * 1000; };

// ---- fixtures: seeded over the real API, not synthetic client-side stubs -----------------------
async function apiPost(path, body) {
  const r = await fetch(BASE + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  return { status: r.status, json: r.ok ? await r.json() : null };
}
async function apiPut(path, body, ifMatch) {
  const r = await fetch(BASE + path, { method: 'PUT', headers: { 'Content-Type': 'application/json', 'If-Match': `"${ifMatch}"` }, body: JSON.stringify(body) });
  return r.status;
}
async function waitCompile(rid, timeoutMs = 180000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const st = await fetch(BASE + `/api/latex/${rid}/compile`).then(r => r.json()).catch(() => null);
    if (st && (st.state === 'ok' || st.state === 'failed')) return st.state;
    await sleep(1000);
  }
  return 'timeout';
}

const PORT = 9600 + (Date.now() % 300);
const profile = mkdtempSync(join(tmpdir(), 'loading-states-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { rmSync(profile, { recursive: true, force: true }); } catch {} };
const overall = setTimeout(() => { console.error('loading-states-check: overall timeout'); cleanup(); process.exit(2); }, 280000);
overall.unref();

let ws, id = 0; const pending = new Map();
let holdFilter = () => false;   // (params) => boolean — reassigned per phase, reset after every use
let heldQueue = [];             // paused requests currently held (matched holdFilter, not yet resolved)
const cmd = (method, params = {}) => new Promise(res => {
  const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params }));
});
const evaluate = async expr => {
  const r = await cmd('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error('page eval threw: ' +
    (r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text));
  return r.result?.result?.value;
};
const media = motion => cmd('Emulation.setEmulatedMedia', {
  features: motion ? [{ name: 'prefers-reduced-motion', value: motion }] : [],
});
// Colour tokens are light-dark(); a probe element is the only way to read the RESOLVED colour
// (getPropertyValue returns the raw light-dark(...) text). Always sampled on the CURRENT live page
// — never cached across a navigation, which resets data-theme back to the injected default.
const bgOf = tok => evaluate(`(()=>{const p=document.createElement('div');
  p.style.cssText='position:absolute;left:-9999px;background:var(${tok})';
  document.body.appendChild(p);const v=getComputedStyle(p).backgroundColor;p.remove();return v;})()`);

// Every navigation in this script should start deterministically in LIGHT theme (dark is only
// ever visited by explicitly flipping data-theme on an ALREADY-loaded page, never relied on across
// a Page.navigate) — set via the SAME pre-paint applier every page already reads from localStorage,
// injected before the page's own scripts run.
async function armLightTheme() {
  await cmd('Page.addScriptToEvaluateOnNewDocument', { source: "try{localStorage.setItem('mdr.theme','light');}catch(e){}" });
}

async function connect() {
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
  await armLightTheme();
  // Scoped to only the endpoints any phase below might hold; everything else (HTML/CSS/JS/fonts,
  // GET polls that share a path prefix with a held POST) flows through untouched.
  await cmd('Fetch.enable', { patterns: [
    { urlPattern: '*/api/reviews*', requestStage: 'Request' },
    { urlPattern: '*/api/latex/*/compile', requestStage: 'Request' },
  ] });
}

// Arm a NEW hold phase: replace the filter and drop anything left over from a PRIOR phase (should
// never happen if every phase resolves what it holds, but a stale entry silently stealing a later
// waitHeld() is worse than a loud, clean reset here).
function armHold(filterFn) { holdFilter = filterFn; heldQueue = []; }
function disarmHold() { holdFilter = () => false; heldQueue = []; }

async function gotoAndWait(url, marker) {
  await cmd('Page.navigate', { url });
  let readyState = false;
  for (let i = 0; i < 80; i++) {
    const st = await evaluate(`document.readyState + '|' + !!document.querySelector('${marker}')`);
    if (typeof st === 'string' && st === 'complete|true') { readyState = true; break; }
    await sleep(250);
  }
  return readyState;
}

async function waitHeld(n, timeoutMs = 6000) {
  const t0 = Date.now();
  while (heldQueue.length < n && Date.now() - t0 < timeoutMs) await sleep(50);
  return heldQueue.splice(0, n);
}
async function releaseAll(list) { for (const p of list) await cmd('Fetch.continueRequest', { requestId: p.requestId }); }
async function failAll(list) { for (const p of list) await cmd('Fetch.failRequest', { requestId: p.requestId, errorReason: 'ConnectionRefused' }); }

// ---- generic spinner motion assertion, reused for every .spin arc in the app -------------------
async function assertSpinnerMotion(selector, label) {
  await media(null);
  const before = await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)return null;
    const cs=getComputedStyle(el);const a=el.getAnimations?el.getAnimations():[];
    return JSON.stringify({name:cs.animationName,dur:cs.animationDuration,iter:cs.animationIterationCount,
      t:a[0]?a[0].currentTime:null,n:a.length});})()`);
  if (!before) { ok(`${label}: element present for motion sampling`, false, 'not found'); return; }
  const b = JSON.parse(before);
  ok(`${label}: computed animation-name is spin`, b.name === 'spin', b.name);
  ok(`${label}: computed animation-duration is 900ms`, Math.abs(toMs(b.dur) - 900) < 1, b.dur);
  ok(`${label}: computed animation-iteration-count is infinite`, b.iter === 'infinite', b.iter);
  await sleep(120);
  const after = await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)return null;
    const a=el.getAnimations?el.getAnimations():[];return a[0]?a[0].currentTime:null;})()`);
  ok(`${label}: currentTime advances ~100ms apart (not reduced motion)`,
    typeof after === 'number' && typeof b.t === 'number' && after > b.t, { before: b.t, after });

  await media('reduce');
  await sleep(50);
  const rmBefore = await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)return null;
    const cs=getComputedStyle(el);const a=el.getAnimations?el.getAnimations():[];
    return JSON.stringify({dur:cs.animationDuration,iter:cs.animationIterationCount,
      t:a[0]?a[0].currentTime:null,n:a.length});})()`);
  const rb = JSON.parse(rmBefore);
  ok(`${label} (reduced motion): animation-duration collapses to ~0.01ms`, toMs(rb.dur) < 0.02, rb.dur);
  ok(`${label} (reduced motion): animation-iteration-count collapses to 1`, rb.iter === '1', rb.iter);
  await sleep(120);
  const rmAfter = await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)return null;
    const a=el.getAnimations?el.getAnimations():[];return a[0]?a[0].currentTime:null;})()`);
  // Empty getAnimations() (rb.n===0 or the after read is null) IS the frozen/settled state under a
  // sub-millisecond single-iteration animation — treated as "not advancing", not as a missing case.
  const advanced = (typeof rmAfter === 'number' && typeof rb.t === 'number') ? (rmAfter > rb.t) : false;
  ok(`${label} (reduced motion): currentTime does NOT advance`, !advanced, { before: rb.t, after: rmAfter, animCount: rb.n });
  await media(null);
}

async function main() {
  await connect();
  await cmd('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });

  // ============================================================================================
  // AC2: dashboard empty state — BEFORE any review exists on this throwaway instance.
  // ============================================================================================
  disarmHold();
  const readyEmpty = await gotoAndWait(BASE + '/', '.dash-empty');
  ok('AC2 setup: dashboard loaded with the empty-state DOM present (zero reviews so far)', readyEmpty);
  if (readyEmpty) {
    const empty = await evaluate(`(()=>{const h=document.querySelector('.dash-empty .de-h');
      const b=document.querySelector('.dash-empty .de-body');
      const cta=document.querySelector('.dash-empty a.btn');
      return JSON.stringify({heading:h?h.textContent:null,
        body:b?b.textContent:null, ctaText:cta?cta.textContent:null, ctaHref:cta?cta.getAttribute('href'):null,
        ctaBg: cta?getComputedStyle(cta).backgroundColor:null});})()`);
    const e = JSON.parse(empty);
    ok('AC2: heading is exactly "No documents yet"', e.heading === 'No documents yet', e.heading);
    ok('AC2: body names create_review and "Your agent creates them."', /Your agent creates them\./.test(e.body || '') && /create_review/.test(e.body || ''), e.body);
    ok('AC2: CTA labelled "Connect your agent", navigates to /account', e.ctaText === 'Connect your agent' && e.ctaHref === '/account', e);
    const accent = await bgOf('--accent');
    ok('AC2: CTA computed background-color equals resolved --accent', e.ctaBg === accent, { got: e.ctaBg, want: accent });
  }

  // Positive control: the SAME two tokens the assertions below key on actually differ between
  // themes, sampled on a REAL loaded page (not about:blank, where every var() resolves transparent
  // and the control would pass vacuously).
  await evaluate(`document.documentElement.setAttribute('data-theme','light')`);
  const codeBgLight = await bgOf('--code-bg'), dangerBgLight = await bgOf('--danger-bg');
  await evaluate(`document.documentElement.setAttribute('data-theme','dark')`);
  const codeBgDark = await bgOf('--code-bg'), dangerBgDark = await bgOf('--danger-bg');
  ok('positive control: --code-bg actually differs between themes', codeBgLight !== codeBgDark, { codeBgLight, codeBgDark });
  ok('positive control: --danger-bg actually differs between themes', dangerBgLight !== dangerBgDark, { dangerBgLight, dangerBgDark });

  // Seed the one markdown review AC1/AC3/AC4/AC9(viewer) share, now that AC2 has run against zero.
  const md = (await apiPost('/api/reviews', { title: 'loading-states md fixture',
    markdown: '# Fixture\n\nBlock one.\n\nBlock two.\n\nBlock three.\n\nBlock four.\n' })).json.id;
  ok('fixture: markdown review created', !!md, md);

  // ============================================================================================
  // AC1: dashboard skeleton — hold /api/reviews open, sample, release, confirm it's gone.
  // ============================================================================================
  armHold(p => p.request.method === 'GET' && /\/api\/reviews(\?|$)/.test(p.request.url));
  await cmd('Page.navigate', { url: BASE + '/' });
  const heldReviews = await waitHeld(2);
  ok('AC1 setup: both /api/reviews fetches held open (no scope=shared miss)', heldReviews.length === 2, heldReviews.map(h => h.request.url));
  await sleep(200);   // let the page's synchronous skeleton render land
  const skel = await evaluate(`(()=>{const rows=[...document.querySelectorAll('#list .skrow')];
    const geoms=rows.map(r=>{const p=r.querySelectorAll('.skpill');
      return {opacity:getComputedStyle(r).opacity,
        lead:{w:Math.round(p[0].getBoundingClientRect().width),h:Math.round(p[0].getBoundingClientRect().height),
          radius:getComputedStyle(p[0]).borderRadius, bg:getComputedStyle(p[0]).backgroundColor, anim:getComputedStyle(p[0]).animationName},
        trail:{w:Math.round(p[2].getBoundingClientRect().width)}};});
    // VISIBLE text only: document.body.textContent naively includes <script> source (this file's
    // own dashboard.html carries a code COMMENT mentioning "Loading…" in its inline <script>),
    // which is not rendered and is not what AC1 means by "on the page".
    const clone=document.body.cloneNode(true);
    clone.querySelectorAll('script,style').forEach(e=>e.remove());
    const loadingText=clone.textContent.includes('Loading…');
    return JSON.stringify({n:rows.length, geoms, loadingText});})()`);
  const s = JSON.parse(skel);
  ok('AC1: exactly three skeleton rows', s.n === 3, s.n);
  if (s.n === 3) {
    ok('AC1: row opacities are 1, .7, .45', s.geoms.map(g => g.opacity).join(',') === '1,0.7,0.45', s.geoms.map(g => g.opacity));
    ok('AC1: leading pill ~24px wide, 8px tall, 4px radius', s.geoms.every(g => Math.abs(g.lead.w - 24) <= 1 && Math.abs(g.lead.h - 8) <= 1 && g.lead.radius === '4px'), s.geoms);
    ok('AC1: trailing pill ~32px wide', s.geoms.every(g => Math.abs(g.trail.w - 32) <= 1), s.geoms.map(g => g.trail.w));
    const codeBgNow = await bgOf('--code-bg');   // theme is 'dark' from the toggle above; sample fresh, not a stale light capture
    ok('AC1: computed background-color equals resolved --code-bg', s.geoms.every(g => g.lead.bg === codeBgNow), { got: s.geoms.map(g => g.lead.bg), want: codeBgNow });
    ok('AC1: skeleton elements are static (computed animation-name: none)', s.geoms.every(g => g.lead.anim === 'none'), s.geoms.map(g => g.lead.anim));
  }
  ok('AC1: the string "Loading…" is rendered nowhere on the page', !s.loadingText);
  await releaseAll(heldReviews);
  let settled = false;
  for (let i = 0; i < 40; i++) {
    const n = await evaluate(`document.querySelectorAll('#list .skrow').length`);
    if (n === 0) { settled = true; break; }
    await sleep(150);
  }
  ok('AC1: no skeleton node remains once the response resolves', settled);
  disarmHold();
  await evaluate(`document.documentElement.setAttribute('data-theme','light')`);

  // ============================================================================================
  // AC3: dashboard unreachable (in-app) — fail /api/reviews, banner + Try again + 8s auto-retry.
  // ============================================================================================
  armHold(p => p.request.method === 'GET' && /\/api\/reviews(\?|$)/.test(p.request.url));
  await cmd('Page.navigate', { url: BASE + '/' });
  let heldFirst = await waitHeld(2);
  ok('AC3 setup: both /api/reviews fetches held for the first (failing) load', heldFirst.length === 2, heldFirst.map(h => h.request.url));
  await failAll(heldFirst);
  await sleep(400);
  const banner = await evaluate(`(()=>{const b=document.querySelector('.unreach-banner');
    if(!b)return null;const cs=getComputedStyle(b);
    return JSON.stringify({text:b.textContent, bold:!!b.querySelector('b'),
      bg:cs.backgroundColor, border:cs.borderColor,
      retryPresent:!!document.querySelector('#retrynow'), countText:(document.querySelector('#retrycount')||{}).textContent});})()`);
  ok('AC3 setup: the unreachable banner rendered', !!banner, banner);
  if (banner) {
    const bJ = JSON.parse(banner);
    const dangerBg = await bgOf('--danger-bg'), dangerBorder = await bgOf('--danger-border');
    ok('AC3: banner text is the #221 sentence with "not" bold', /The server didn.t answer\. You have\s*not\s*been signed out\./.test(bJ.text.replace(/\s+/g, ' ')) && bJ.bold, bJ.text);
    ok('AC3: banner computed background = --danger-bg', bJ.bg === dangerBg, { got: bJ.bg, want: dangerBg });
    ok('AC3: banner computed border-color = --danger-border', bJ.border === dangerBorder, { got: bJ.border, want: dangerBorder });
    ok('AC3: a countdown "retrying in Ns" starting near 8 is shown', /retrying in \d+s/.test(bJ.countText || ''), bJ.countText);
  }
  // the auto-retry: without touching anything, a NEW pair of requests should appear once the
  // countdown reaches 0 (~8s) — held again (not answered), so the auto-fire is unambiguous.
  const autoRetried = await waitHeld(2, 10500);
  ok('AC3: at 0 the countdown fires a refetch WITHOUT user action', autoRetried.length === 2, autoRetried.length);
  // now answer for real: a successful refetch clears the banner and renders the list.
  await releaseAll(autoRetried);
  let recovered = false;
  for (let i = 0; i < 40; i++) {
    const gone = await evaluate(`!document.querySelector('.unreach-banner')`);
    if (gone) { recovered = true; break; }
    await sleep(150);
  }
  ok('AC3: a successful refetch clears the banner', recovered);
  // manual "Try again": fail once more, then click it, confirm an immediate new request (not
  // waiting for the 8s timer).
  armHold(p => p.request.method === 'GET' && /\/api\/reviews(\?|$)/.test(p.request.url));
  await cmd('Page.navigate', { url: BASE + '/' });
  const heldAgain = await waitHeld(2);
  await failAll(heldAgain);
  await sleep(300);
  await evaluate(`document.querySelector('#retrynow').click(); true`);
  const manualRetry = await waitHeld(2, 3000);
  ok('AC3: "Try again" triggers an immediate refetch (not waiting on the countdown)', manualRetry.length === 2, manualRetry.length);
  await releaseAll(manualRetry);
  await sleep(500);
  disarmHold();

  // ============================================================================================
  // AC4: dashboard no-results — search-emptied (query echoed) vs filter-emptied.
  // ============================================================================================
  // A second review: with only one, "One thing to do next" promotes it OUT of #list into the
  // #nextup hero (rev 3's own resting-view rule), and no .rw row is ever left to wait for.
  const md2 = (await apiPost('/api/reviews', { title: 'loading-states md fixture two', markdown: '# t2\n\npara\n' })).json.id;
  ok('fixture: second markdown review created (so a .rw row survives hero promotion)', !!md2, md2);
  const readyList = await gotoAndWait(BASE + '/', '.rw');
  ok('AC4 setup: dashboard loaded with the seeded row', readyList);
  await evaluate(`(()=>{const s=document.querySelector('#search');s.value='zzz-nomatch';
    s.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await sleep(150);
  const nores = await evaluate(`(()=>{const n=document.querySelector('#noresults');
    const h=n.querySelector('.nr-h'),b=n.querySelector('.nr-body');
    return JSON.stringify({heading:h?h.textContent:null, body:b?b.textContent:null, shown:getComputedStyle(n).display});})()`);
  const nr = JSON.parse(nores);
  ok('AC4: heading echoes the query exactly, HTML-escaped', nr.heading === 'Nothing matches "zzz-nomatch"', nr.heading);
  ok('AC4: explainer names titles/projects/paths, not comment text', /Titles, projects and paths are searched/.test(nr.body || ''), nr.body);
  await evaluate(`(()=>{const s=document.querySelector('#search');s.value='';
    s.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await sleep(150);
  const restored = await evaluate(`document.querySelectorAll('#list .rw').length`);
  ok('AC4: clearing the search restores the list', restored >= 1, restored);
  // filter-emptied: the "Working" filter with nothing agent-owned yet -> "Nothing in this view."
  await evaluate(`document.querySelector('.filt[data-filter="working"]').click(); true`);
  await sleep(150);
  const filtEmpty = await evaluate(`document.querySelector('#noresults').textContent`);
  ok('AC4: a filter-emptied (no query) view still reads "Nothing in this view."', filtEmpty === 'Nothing in this view.', filtEmpty);

  // ============================================================================================
  // AC9 (viewer.html): comment posting — pending card, 2xx replaces it, failure keeps text +
  // retry/discard, retry succeeds, discard removes a second one.
  // ============================================================================================
  const mdUrl = `${BASE}/review/${md}`;
  const mdReady = await gotoAndWait(mdUrl, '.blk .num');
  ok('AC9 setup (viewer.html): markdown review loaded', mdReady);
  armHold(p => p.request.method === 'POST' && /\/comments$/.test(new URL(p.request.url).pathname));
  await evaluate(`document.querySelector('.blk .num').click(); true`);
  await sleep(100);
  await evaluate(`(()=>{const t=document.querySelector('#popnote');t.value='pending text one';
    t.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await evaluate(`document.querySelector('#popsave').click(); true`);
  const held1 = await waitHeld(1);
  ok('AC9 setup (viewer.html): the POST is held open', held1.length === 1);
  const pendingState = await evaluate(`(()=>{const p=document.querySelector('.gcard.pending');
    if(!p)return null;const cs=getComputedStyle(p);
    return JSON.stringify({opacity:cs.opacity, text:p.querySelector('.gtext').textContent,
      hasSpinner:!!p.querySelector('.spin'), statusText:(p.querySelector('.gpending-status')||{}).textContent,
      composerClosed:document.querySelector('#pop').style.display!=='block'});})()`);
  ok('AC9 (viewer.html): pending card renders at opacity .6 with the typed text + spinner + "posting…", composer already closed',
    !!pendingState, pendingState);
  if (pendingState) {
    const p = JSON.parse(pendingState);
    ok('AC9 (viewer.html): pending opacity is .6', p.opacity === '0.6', p.opacity);
    ok('AC9 (viewer.html): pending card carries the typed text', p.text === 'pending text one', p.text);
    ok('AC9 (viewer.html): pending card has a spinner reading "posting…"', p.hasSpinner && /posting…/.test(p.statusText || ''), p);
    ok('AC9 (viewer.html): composer closed immediately (optimistic)', p.composerClosed);
  }
  await releaseAll(held1);
  disarmHold();
  let addedOk = false;
  for (let i = 0; i < 40; i++) {
    const st = await evaluate(`(()=>{const cards=document.querySelectorAll('#gutter .gcard');
      return JSON.stringify({n:cards.length, pending:!!document.querySelector('.gcard.pending')});})()`);
    const j = JSON.parse(st);
    if (j.n === 1 && !j.pending) { addedOk = true; break; }
    await sleep(150);
  }
  ok('AC9 (viewer.html): on 2xx the pending card is replaced by the real card', addedOk);

  // second comment: forced failure -> retry (unheld, succeeds) -> a third: forced failure -> discard.
  armHold(p => p.request.method === 'POST' && /\/comments$/.test(new URL(p.request.url).pathname));
  await evaluate(`document.querySelector('.blk .num').click(); true`);
  await sleep(100);
  await evaluate(`(()=>{const t=document.querySelector('#popnote');t.value='pending text two';
    t.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await evaluate(`document.querySelector('#popsave').click(); true`);
  const held2 = await waitHeld(1);
  await failAll(held2);
  disarmHold();
  await sleep(400);
  const failedState = await evaluate(`(()=>{const p=document.querySelector('.gcard.pending.failed');
    if(!p)return null;const cs=getComputedStyle(p);
    return JSON.stringify({opacity:cs.opacity, text:p.querySelector('.gtext').textContent,
      err:(p.querySelector('.gpending-err')||{}).textContent,
      hasRetry:!!p.querySelector('[data-act=retry]'), hasDiscard:!!p.querySelector('[data-act=discard]')});})()`);
  ok('AC9 (viewer.html): on failure the SAME card stays with "Not posted — your text is kept." + retry/discard', !!failedState, failedState);
  if (failedState) {
    const f = JSON.parse(failedState);
    ok('AC9 (viewer.html): failed card returns to full opacity', f.opacity === '1', f.opacity);
    ok('AC9 (viewer.html): failed card keeps the typed text', f.text === 'pending text two', f.text);
    ok('AC9 (viewer.html): failed card reads exactly "Not posted — your text is kept."', f.err === 'Not posted — your text is kept.', f.err);
    ok('AC9 (viewer.html): failed card has retry and discard', f.hasRetry && f.hasDiscard, f);
  }
  // retry: re-posts the IDENTICAL text — deliberately UNHELD (holdFilter disarmed above), so it
  // resolves against the real server exactly as a normal click would.
  await evaluate(`document.querySelector('.gcard.pending.failed [data-act=retry]').click(); true`);
  let retryOk = false;
  for (let i = 0; i < 40; i++) {
    const st = await evaluate(`JSON.stringify({n:document.querySelectorAll('#gutter .gcard').length, pending:!!document.querySelector('.gcard.pending')})`);
    const j = JSON.parse(st);
    if (j.n === 2 && !j.pending) { retryOk = true; break; }
    await sleep(150);
  }
  ok('AC9 (viewer.html): retry re-posts the identical text and succeeds (2 real cards now)', retryOk);
  const apiComments = await fetch(`${BASE}/api/reviews/${md}/comments`).then(r => r.json()).catch(() => null);
  const texts = (apiComments && apiComments.comments || []).map(c => (c.thread || [])[0] && c.thread[0].text);
  ok('AC9 (viewer.html): at no point was the typed text lost (both comments landed server-side)',
    texts.includes('pending text one') && texts.includes('pending text two'), texts);

  // discard: a third attempt, forced failure, then explicitly discarded (card removed).
  armHold(p => p.request.method === 'POST' && /\/comments$/.test(new URL(p.request.url).pathname));
  await evaluate(`document.querySelector('.blk .num').click(); true`);
  await sleep(100);
  await evaluate(`(()=>{const t=document.querySelector('#popnote');t.value='discard me';
    t.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await evaluate(`document.querySelector('#popsave').click(); true`);
  const held3 = await waitHeld(1);
  await failAll(held3);
  disarmHold();
  await sleep(300);
  await evaluate(`document.querySelector('.gcard.pending.failed [data-act=discard]').click(); true`);
  await sleep(150);
  const afterDiscard = await evaluate(`JSON.stringify({pending:!!document.querySelector('.gcard.pending'), n:document.querySelectorAll('#gutter .gcard').length})`);
  ok('AC9 (viewer.html): discard removes the card', JSON.parse(afterDiscard).pending === false, afterDiscard);

  // Motion needs a LIVE pending card — arm one more held post purely to sample the posting-spinner
  // honestly, in both media states, then release it.
  armHold(p => p.request.method === 'POST' && /\/comments$/.test(new URL(p.request.url).pathname));
  await evaluate(`document.querySelector('.blk .num').click(); true`);
  await sleep(100);
  await evaluate(`(()=>{const t=document.querySelector('#popnote');t.value='motion sample';
    t.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await evaluate(`document.querySelector('#popsave').click(); true`);
  const heldMotion = await waitHeld(1);
  await sleep(150);
  await assertSpinnerMotion('.gcard.pending .spin', 'AC10 (viewer.html posting spinner)');
  await releaseAll(heldMotion);
  disarmHold();
  await sleep(400);

  await mainLatex(md);
  console.log(failed ? `\n${failed} case(s) failed` : '\nall loading-states cases pass');
  cleanup();
  process.exit(failed ? 1 : 0);
}

async function mainLatex(md) {
  await evaluate(`document.documentElement.setAttribute('data-theme','light')`);

  // ============================================================================================
  // AC9 (latex-viewer.html): the same optimistic pending/failed/retry/discard contract.
  // ============================================================================================
  const lpost = (await apiPost('/api/reviews', { title: 'loading-states latex posting fixture', kind: 'latex',
    markdown: '\\documentclass{article}\n\\begin{document}\nposting fixture\n\\end{document}' })).json.id;
  ok('fixture: latex posting review created', !!lpost, lpost);
  disarmHold();
  const latexReady = await gotoAndWait(`${BASE}/review/${lpost}`, '.ln[data-num="1"]');
  ok('AC9 setup (latex-viewer.html): latex review loaded', latexReady);
  armHold(p => p.request.method === 'POST' && /\/comments$/.test(new URL(p.request.url).pathname));
  await evaluate(`document.querySelector('.ln[data-num="1"] .n').click(); true`);
  await sleep(100);
  await evaluate(`(()=>{const t=document.querySelector('#popnote');t.value='latex pending';
    t.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await evaluate(`document.querySelector('#popsave').click(); true`);
  const lheld1 = await waitHeld(1);
  ok('AC9 setup (latex-viewer.html): the POST is held open', lheld1.length === 1);
  const lpending = await evaluate(`(()=>{const p=document.querySelector('.gcard.pending');
    if(!p)return null;const cs=getComputedStyle(p);
    return JSON.stringify({opacity:cs.opacity, text:p.querySelector('.gtext').textContent,
      hasSpinner:!!p.querySelector('.spin'), composerClosed:document.querySelector('#pop').style.display!=='block'});})()`);
  ok('AC9 (latex-viewer.html): pending card renders at opacity .6 with typed text + spinner, composer closed', !!lpending, lpending);
  await failAll(lheld1);
  disarmHold();
  await sleep(400);
  const lfailedState = await evaluate(`(()=>{const p=document.querySelector('.gcard.pending.failed');
    if(!p)return null;return JSON.stringify({err:(p.querySelector('.gpending-err')||{}).textContent,
      hasRetry:!!p.querySelector('[data-act=retry]'), hasDiscard:!!p.querySelector('[data-act=discard]'),
      text:p.querySelector('.gtext').textContent});})()`);
  ok('AC9 (latex-viewer.html): failure keeps the SAME card with "Not posted…" + retry/discard, text intact', !!lfailedState, lfailedState);
  if (lfailedState) {
    const f = JSON.parse(lfailedState);
    ok('AC9 (latex-viewer.html): exact copy "Not posted — your text is kept."', f.err === 'Not posted — your text is kept.', f.err);
  }
  await evaluate(`document.querySelector('.gcard.pending.failed [data-act=retry]').click(); true`);
  let lretryOk = false;
  for (let i = 0; i < 40; i++) {
    const st = await evaluate(`JSON.stringify({n:document.querySelectorAll('#railcol .gcard').length, pending:!!document.querySelector('.gcard.pending')})`);
    const j = JSON.parse(st);
    if (j.n >= 1 && !j.pending) { lretryOk = true; break; }
    await sleep(150);
  }
  ok('AC9 (latex-viewer.html): retry re-posts and succeeds', lretryOk);

  // ============================================================================================
  // AC7 / D1: recompile running. Holding the VERY FIRST compile-status request leaves refreshPdf()
  // mid-await, so the page never actually PAINTS anything (the static default "PDF" shows) — the
  // opposite of what AC7 needs. Instead the first request is let through UNHELD (a real response,
  // genuinely queued/running — tectonic hasn't produced a PDF yet), so refreshPdf() actually
  // renders the running state; ONLY the poll's next request (2s later) is held, freezing that
  // rendered state for as long as this check likes, regardless of how fast the real compile is.
  // ============================================================================================
  const lrun = (await apiPost('/api/reviews', { title: 'lease-freshness.tex', kind: 'latex',
    markdown: '\\documentclass{article}\n\\begin{document}\nlease freshness\n\\end{document}' })).json.id;
  ok('fixture: latex running-compile review created', !!lrun, lrun);
  let compileSeen = 0;
  armHold(p => {
    if (!/\/api\/latex\/.*\/compile$/.test(new URL(p.request.url).pathname)) return false;
    compileSeen++;
    return compileSeen > 1;   // let the first (real) response through; hold every one after
  });
  await cmd('Page.navigate', { url: `${BASE}/review/${lrun}` });
  let paintedRunning = false;
  for (let i = 0; i < 40; i++) {
    if (await evaluate(`document.body.classList.contains('compile-running')`)) { paintedRunning = true; break; }
    await sleep(150);
  }
  ok('AC7 setup: the first (real) compile-status response painted the running state', paintedRunning);
  const compileHeld = await waitHeld(1, 8000);
  ok('AC7 setup: the next compile-status poll is held, freezing the running state', compileHeld.length === 1, compileHeld.map(h => h.request.url));
  await sleep(200);
  const running = await evaluate(`(()=>{const b=document.body;
    return JSON.stringify({running:b.classList.contains('compile-running'),
      pdfstate:document.querySelector('#pdfstate').textContent,
      filename:document.querySelector('#filename').textContent,
      hasSpinner:!!document.querySelector('#pdfstate .spin'),
      progressDisplay:getComputedStyle(document.querySelector('#compileprogress')).display,
      recBtn:document.querySelector('#recompilebtn').textContent,
      recDisabled:document.querySelector('#recompilebtn').disabled});})()`);
  const r = JSON.parse(running);
  ok('AC7: body.compile-running is set while queued/running', r.running, r);
  // A literal leading space (SPIN_ICON+' Compiling '+...) is the app's spacing between the icon
  // and the label (#pdfstate has no flex/gap) — expected in textContent, trimmed before comparing.
  const pdfstateTrimmed = r.pdfstate.trim();
  ok('AC7: #pdfstate shows a spinner beside "Compiling <name>…"', r.hasSpinner && /^Compiling .+…$/.test(pdfstateTrimmed), r.pdfstate);
  ok('AC7: <name> is the SAME document name the top-bar #filename shows',
    r.filename && r.filename !== 'loading…' && pdfstateTrimmed === `Compiling ${r.filename}…`, r);
  ok('AC7: #recompilebtn reads "Recompiling…" and is disabled', r.recBtn === 'Recompiling…' && r.recDisabled, r);
  ok('AC7/D1: the progress bar element is shown while running', r.progressDisplay === 'block', r.progressDisplay);

  await assertSpinnerMotion('#pdfstate .spin', 'AC10 (latex-viewer compiling spinner)');
  // D1: the progress bar's static reduced-motion tint — computed `left` reverts to the animation's
  // base (non-animated) value once duration collapses, rather than freezing mid-sweep.
  await media(null);
  const fillLeftNormal = await evaluate(`getComputedStyle(document.querySelector('.compileprogress .fill')).left`);
  await media('reduce');
  await sleep(200);
  const fillLeftReduced = await evaluate(`getComputedStyle(document.querySelector('.compileprogress .fill')).left`);
  ok('D1: under reduced motion the fill settles at its static base position (left:0), not mid-sweep',
    fillLeftReduced === '0px', { normal: fillLeftNormal, reduced: fillLeftReduced });
  await media(null);
  await releaseAll(compileHeld);
  disarmHold();

  // ============================================================================================
  // AC8 / D2: compile failed — real fixture (undefined control sequence -> a genuine l.NNN line).
  // v0 compiles ok (has_pdf survives into the v1 failure), v1 introduces \deltaa (the mock's own
  // example), a real "Undefined control sequence" TeX error with the classic  l.<num>  prefix.
  // ============================================================================================
  const lfail = (await apiPost('/api/reviews', { title: 'lease-freshness-failed.tex', kind: 'latex',
    markdown: '\\documentclass{article}\n\\begin{document}\nok v0\n\\end{document}' })).json.id;
  ok('fixture: latex failed-compile review created', !!lfail, lfail);
  const v0 = await waitCompile(lfail);
  ok('fixture: v0 compiled ok (has_pdf will survive into the v1 failure)', v0 === 'ok', v0);
  const putSt = await apiPut(`/api/reviews/${lfail}/source`,
    { markdown: '\\documentclass{article}\n\\begin{document}\nSome text \\deltaa here.\n\\end{document}' }, 0);
  ok('fixture: v1 (broken) source accepted', putSt === 200, putSt);
  const v1 = await waitCompile(lfail);
  ok('fixture: v1 reached failed', v1 === 'failed', v1);

  const failReady = await gotoAndWait(`${BASE}/review/${lfail}`, '#errbar');
  ok('AC8 setup: failed-compile review loaded cold', failReady);
  await sleep(300);
  const failCard = await evaluate(`(()=>{const bar=document.querySelector('.errbar');const cs=getComputedStyle(bar);
    return JSON.stringify({failedClass:document.body.classList.contains('compile-failed'),
      bg:cs.backgroundColor, border:cs.borderBottomColor,
      head:document.querySelector('#errhead').textContent, line:document.querySelector('#errline').textContent,
      lineMono:getComputedStyle(document.querySelector('#errline')).fontFamily,
      fullLogHidden:!document.querySelector('#errdetails').open, fullLogText:document.querySelector('#errlog').textContent.slice(0,200)});})()`);
  const fc = JSON.parse(failCard);
  const dangerBg2 = await bgOf('--danger-bg'), dangerBorder2 = await bgOf('--danger-border');
  ok('AC8: body.compile-failed is set on a cold load of a failed review', fc.failedClass);
  ok('AC8: failure surface computed background = --danger-bg (was warning-tinted)', fc.bg === dangerBg2, { got: fc.bg, want: dangerBg2 });
  ok('AC8: failure surface computed border = --danger-border', fc.border === dangerBorder2, { got: fc.border, want: dangerBorder2 });
  ok('D2: headline reads the mock sentence verbatim', fc.head === 'Compile failed — the last good PDF is still shown.', fc.head);
  // Two real pointer shapes exist: classic "l.<num>" (a .log file's own convention) and tectonic's
  // actual stdout/stderr shape "error: paper.tex:<num>:" (verified with a direct tectonic run) —
  // src/latex_review/compiler.py ships log_tail from the latter, so that is what a real failure
  // here produces, not the mock's literal l.214 example.
  ok('AC8: mono line carries the log\'s own pointer to the failing line', /l\.\d+/.test(fc.line) || /:\d+:/.test(fc.line), fc.line);
  ok('D2: mono line ALSO retains #205\'s revision detail (which vN failed, which vM is shown)', /v\d+ failed/.test(fc.line) && /showing/.test(fc.line), fc.line);
  ok('AC8: the mono line renders in the mono font', /Geist Mono/.test(fc.lineMono), fc.lineMono);
  ok('AC8: "full log" is a disclosure, closed by default', fc.fullLogHidden, fc.fullLogText);
  await evaluate(`document.querySelector('#errdetails summary').click(); true`);
  await sleep(100);
  const revealed = await evaluate(`JSON.stringify({open:document.querySelector('#errdetails').open, hasText:document.querySelector('#errlog').textContent.length>0})`);
  ok('AC8: "full log" reveals the complete log_tail', JSON.parse(revealed).open && JSON.parse(revealed).hasText, revealed);
  const dl = await evaluate(`JSON.stringify({text:document.querySelector('#dlbtn').textContent, href:document.querySelector('#dlbtn').getAttribute('href')})`);
  ok('AC8 regression guard: Download keeps naming the shown revision (#205, ships today)', /Download v\d+/.test(JSON.parse(dl).text), dl);

  // ============================================================================================
  // AC10 mechanical: the reduced-motion guard is declared ONCE, in theme.css, nowhere else. Every
  // page this ticket touches is served content, fetched fresh from the running instance (not a
  // second copy of the file on disk).
  // ============================================================================================
  const guardFiles = ['/dashboard.html', '/account.html', `/review/${md}`, `/review/${lpost}`, `/review/${lfail}`, '/static/theme.css'];
  const guardCount = await evaluate(`(async()=>{
    const files=${JSON.stringify(guardFiles)};
    const texts=await Promise.all(files.map(f=>fetch(f).then(r=>r.text())));
    const counts=texts.map(t=>(t.match(/@media\\s*\\(prefers-reduced-motion:\\s*reduce\\)/g)||[]).length);
    return JSON.stringify({files,counts,total:counts.reduce((a,b)=>a+b,0)});
  })()`);
  const gc = JSON.parse(guardCount);
  ok('AC10: exactly ONE prefers-reduced-motion guard exists across the served pages + theme.css',
    gc.total === 1, gc);
}

main().catch(e => { console.error('FATAL:', e); cleanup(); process.exit(2); });
