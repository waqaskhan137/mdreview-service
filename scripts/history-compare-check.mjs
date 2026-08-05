// history-compare-check.mjs: #310 "Viewer history: Compare button calls undefined renderCompare
// (dead control)", RENDERED OUTCOMES in a real headless Chrome, same zero-dep shape as
// resolve-undo-check.mjs / latex-canvas-check.mjs: Node's built-in WebSocket + fetch driving CDP
// directly.
//
// The bug this guards: `7fcd840` (#208) deleted renderCompare() but left its call site, so
// clicking #histcmp flipped HISTMODE to 'compare' and the button label to 'Browse' BEFORE
// throwing a ReferenceError, leaving the modal labelled Browse while still showing the browse
// list. A source-text grep for the function name would go green the moment ANY function with
// that name exists, even an empty one, so every assertion below is a DOM/state outcome: the
// pickers actually render, are populated from the real /history API (not placeholders), the diff
// they show is the real content of the two selected revisions, and the mode/label pair is
// consistent in both directions. AC1-AC3, AC5 (this run itself IS the browser evidence with the
// console captured), AC6 (a mutation that removes the restored definition fails HERE, not on a
// grep; see the ticket's mutation-test requirement).
//
// AC4 (the #208 shared renderer, mdDiff.renderInto via paintDiff, is not regressed / not
// reintroduced as a second copy) is a structural property of the fix (renderCompare calls the
// existing renderDiff, unchanged) rather than something this script re-derives; tests/diff_selfcheck.js
// covers linediff.js directly and the neighbouring viewer suites cover the shared inline toggle.
//
// AC7 (typography untouched) is NOT this script's job. tests/reading_font_selfcheck.sh and
// tests/viewer_polish_selfcheck.sh own that contract and must stay green; this script only checks
// that the new pickers don't diverge in COMPUTED font metrics from an existing modal control,
// as a cheap tripwire, not a replacement for those suites.
//
//   node scripts/history-compare-check.mjs <local-review-url>     # exit 0 = pass
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const URL_ARG = process.argv[2];
if (!URL_ARG) { console.error('usage: node scripts/history-compare-check.mjs <local-review-url>'); process.exit(2); }
const u = new URL(URL_ARG);
const ORIGIN = u.origin;
const RID = u.pathname.replace(/^\/review\//, '');
const API = `${ORIGIN}/api/reviews/${RID}`;

const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }

let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c && !d ? '' : d ? `  (${d})` : '')); if (!c) failed++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function apiPut(path, body) {
  const r = await fetch(API + path, { method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}) });
  return { status: r.status, json: r.ok ? await r.json() : null };
}
async function apiGet(path) {
  const r = await fetch(API + path);
  return { status: r.status, json: r.ok ? await r.json() : null };
}

const PORT = 9600 + (Date.now() % 400);
const profile = mkdtempSync(join(tmpdir(), 'history-compare-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { rmSync(profile, { recursive: true, force: true }); } catch {} };

let ws, id = 0; const pending = new Map();
const cmd = (method, params = {}) => new Promise(res => {
  const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params }));
});
const evaluate = async expr => {
  const r = await cmd('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error('page eval threw: ' +
    (r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text));
  return r.result?.result?.value;
};

async function connect() {
  let target;
  for (let i = 0; i < 60 && !target; i++) {
    try {
      const tabs = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      // /json/list also returns Chrome EXTENSION background pages; filter to a real page target.
      target = (tabs || []).find(t => t.type === 'page' && !String(t.url).startsWith('chrome-extension://'));
    } catch {}
    await sleep(250);
  }
  if (!target) { console.error('no page target found'); process.exit(2); }
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r, { once: true }));
  ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
  await cmd('Page.enable'); await cmd('Runtime.enable');
}

async function gotoAndWait(url, marker) {
  await cmd('Page.navigate', { url });
  // Poll for real readiness: a fixed sleep after Page.navigate can sample about:blank.
  let ready = false;
  for (let i = 0; i < 80; i++) {
    const st = await evaluate(`document.readyState + '|' + !!document.querySelector('${marker}')`);
    if (typeof st === 'string' && st === 'complete|true') { ready = true; break; }
    await sleep(250);
  }
  return ready;
}

async function main() {
  await connect();
  await cmd('Emulation.setDeviceMetricsOverride', { width: 1400, height: 900, deviceScaleFactor: 1, mobile: false });

  // ---- fixture: build three DISTINGUISHABLE revisions over the real API (PUT /source snapshots
  // the outgoing round each time), so the pickers have real history to be populated from, and
  // each diff pair has unique text that proves a re-render used the NEWLY selected pair rather
  // than a stale cached one. ----------------------------------------------------------------------
  const put1 = await apiPut('/source', { markdown: '# Doc\n\nBRAVO-v1 marker line.\n\nShared unchanged line.\n' });
  const put2 = await apiPut('/source', { markdown: '# Doc\n\nCHARLIE-v2 marker line.\n\nShared unchanged line.\n' });
  ok('fixture: two revisions pushed over PUT /source', put1.status === 200 && put2.status === 200,
    `put1=${put1.status} put2=${put2.status}`);
  const hist = await apiGet('/history');
  const rounds = hist.json?.rounds || [];
  ok('positive control: /history actually recorded 2 archived rounds (not a vacuous 0/1-version fixture)',
    rounds.length === 2, `rounds=${JSON.stringify(rounds.map(r => r.round))}`);

  const ready = await gotoAndWait(URL_ARG, '#histbtn');
  ok('the viewer actually loaded (probe is not vacuous)', ready,
    await evaluate(`document.readyState + ' ' + location.href`));
  if (!ready) { console.log('\naborting: nothing to sample'); cleanup(); process.exit(1); }

  // Catch exceptions from INSIDE event handlers too, not just from this script's own --eval
  // expressions: this is exactly how the pre-fix bug manifested (mode+label flipped, then a
  // ReferenceError from the onclick handler, silent to anything that only checks eval() throws).
  await evaluate(`(()=>{window.__errs=[];
    window.addEventListener('error', e => window.__errs.push(String((e.error&&e.error.message)||e.message)));
    return true;})()`);

  // ================= baseline: History open in Browse mode ========================================
  await evaluate(`document.querySelector('#histbtn').click(); true`);
  let histReady = false;
  for (let i = 0; i < 40; i++) { if (await evaluate(`!!document.querySelector('.histitem')`)) { histReady = true; break; } await sleep(150); }
  ok('setup: History modal opened to the browse list', histReady);
  const base = JSON.parse(await evaluate(`JSON.stringify({mode:HISTMODE,
    label:document.querySelector('#histcmp').textContent,
    histlist:!!document.querySelector('.histlist'), cmpbar:!!document.querySelector('.cmpbar')})`));
  ok('baseline: mode=browse, label=Compare, browse list showing, no cmpbar yet',
    base.mode === 'browse' && base.label === 'Compare' && base.histlist === true && base.cmpbar === false,
    JSON.stringify(base));

  // ================= AC1 + AC2 (forward): click Compare ===========================================
  await evaluate(`document.querySelector('#histcmp').click(); true`);
  await sleep(500);
  // Optional-chained throughout: if the compare view never rendered (the exact pre-fix bug),
  // these must degrade into named FAIL assertions below, not an uncaught eval exception that
  // aborts the whole run before naming which case broke.
  const cmp1 = JSON.parse(await evaluate(`JSON.stringify({mode:HISTMODE,
    label:document.querySelector('#histcmp').textContent,
    cmpbar:!!document.querySelector('.cmpbar'), histlist:!!document.querySelector('.histlist'),
    optsA:[...document.querySelectorAll('#cmpA option')].map(o=>o.value),
    optsB:[...document.querySelectorAll('#cmpB option')].map(o=>o.value),
    valA:document.querySelector('#cmpA')?.value ?? null, valB:document.querySelector('#cmpB')?.value ?? null,
    diffhead:!!document.querySelector('#diffview .diffhead'),
    diffbody:(document.querySelector('#diffview .diffbody')||{textContent:''}).textContent})`));

  ok('AC2: clicking Compare flips mode to compare AND label to Browse together (no lying state)',
    cmp1.mode === 'compare' && cmp1.label === 'Browse', JSON.stringify({ mode: cmp1.mode, label: cmp1.label }));
  ok('AC1: the browse list is replaced by the compare view (no stale list left showing)',
    cmp1.histlist === false, JSON.stringify(cmp1.histlist));
  ok('AC1: two pickers render (.cmpbar #cmpA and #cmpB both present)',
    cmp1.cmpbar === true && cmp1.optsA.length > 0 && cmp1.optsB.length > 0, JSON.stringify(cmp1));
  ok('AC1: pickers are populated from the REAL /history revisions, not placeholders (3 options each: current + 2 rounds)',
    JSON.stringify(cmp1.optsA) === JSON.stringify(['current', '1', '0']) &&
    JSON.stringify(cmp1.optsB) === JSON.stringify(['current', '1', '0']),
    JSON.stringify({ optsA: cmp1.optsA, optsB: cmp1.optsB }));
  ok('AC1: default pair is (previous round -> current), the "what just changed" default',
    cmp1.valA === '1' && cmp1.valB === 'current', `valA=${cmp1.valA} valB=${cmp1.valB}`);
  ok('AC1: Compare actually renders a comparison (a real diff head, not "Loading..." or empty)',
    cmp1.diffhead === true, JSON.stringify(cmp1.diffhead));
  ok('AC1: the diff shows the REAL content of the two selected revisions (BRAVO-v1 removed, CHARLIE-v2 added)',
    cmp1.diffbody.includes('BRAVO-v1') && cmp1.diffbody.includes('CHARLIE-v2'),
    JSON.stringify(cmp1.diffbody));
  const errsAfterOpen = await evaluate(`JSON.stringify(window.__errs)`);
  ok('AC5: no console error after opening Compare (this is the ReferenceError the bug threw)',
    JSON.parse(errsAfterOpen).length === 0, errsAfterOpen);

  // ================= AC3: selecting a different pair re-renders the diff =========================
  await evaluate(`(()=>{const el=document.querySelector('#cmpA');if(!el)return false;el.value='0';
    el.dispatchEvent(new Event('change',{bubbles:true}));return true;})()`);
  await sleep(500);
  const cmp2 = JSON.parse(await evaluate(`JSON.stringify({valA:document.querySelector('#cmpA')?.value ?? null,
    diffbody:(document.querySelector('#diffview .diffbody')||{textContent:''}).textContent})`));
  ok('AC3: changing picker A re-renders against the NEW pair (v0 removed, v2 still added)',
    cmp2.diffbody.includes('BRAVO-v1 marker line.') === false && cmp2.diffbody.includes('CHARLIE-v2 marker line.'),
    JSON.stringify(cmp2.diffbody));
  ok('positive control: the re-render actually used fresh data, not a stale cached diff (the OLD pair\'s text is gone)',
    cmp1.diffbody.includes('BRAVO-v1 marker line.') && !cmp2.diffbody.includes('BRAVO-v1 marker line.'),
    `before=${JSON.stringify(cmp1.diffbody)} after=${JSON.stringify(cmp2.diffbody)}`);

  // ================= AC2 (reverse): toggle back to Browse =========================================
  await evaluate(`document.querySelector('#histcmp').click(); true`);
  await sleep(400);
  const back = JSON.parse(await evaluate(`JSON.stringify({mode:HISTMODE,
    label:document.querySelector('#histcmp').textContent,
    histlist:!!document.querySelector('.histlist'), cmpbar:!!document.querySelector('.cmpbar')})`));
  ok('AC2: toggling back restores mode=browse, label=Compare, the version list, and drops the cmpbar',
    back.mode === 'browse' && back.label === 'Compare' && back.histlist === true && back.cmpbar === false,
    JSON.stringify(back));

  // ================= AC7 tripwire: the new pickers inherit type, they don't declare their own ====
  // Not a substitute for reading_font_selfcheck.sh / viewer_polish_selfcheck.sh (owned by AGENTS.md
  // rule 6); just a cheap same-run check that #cmpA didn't quietly pick up a divergent computed
  // font from the modal's other controls.
  await evaluate(`document.querySelector('#histcmp').click(); true`);
  await sleep(400);
  const fonts = JSON.parse(await evaluate(`JSON.stringify({
    cmpA:(()=>{const el=document.querySelector('#cmpA');if(!el)return null;const s=getComputedStyle(el);return s.fontFamily+'|'+s.fontSize;})(),
    histclose:(()=>{const el=document.querySelector('#histclose');if(!el)return null;const s=getComputedStyle(el);return s.fontFamily+'|'+s.fontSize;})()})`));
  ok('AC7 tripwire: #cmpA computed font-family matches the modal\'s other controls (no new declaration)',
    !!fonts.cmpA && fonts.cmpA.split('|')[0] === fonts.histclose.split('|')[0], JSON.stringify(fonts));

  const errsFinal = await evaluate(`JSON.stringify(window.__errs)`);
  ok('AC5: no console error across the whole open/switch/toggle-back flow', JSON.parse(errsFinal).length === 0, errsFinal);

  console.log(failed ? `\n${failed} case(s) failed` : '\nall history-compare cases pass');
  cleanup();
  process.exit(failed ? 1 : 0);
}

main().catch(e => { console.error('FATAL:', e); cleanup(); process.exit(2); });
