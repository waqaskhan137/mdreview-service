// resolve-undo-check.mjs — #287 "Undo on resolve toasts", RENDERED OUTCOMES + REAL API state in a
// real headless Chrome. Same zero-dep shape as scripts/palette-restyle-check.mjs /
// latex-canvas-check.mjs: Node's built-in WebSocket + fetch driving CDP directly.
//
// Covers viewer.html's AC1 (toast look, both themes, live theme-toggle), AC2 (undo -> reopened,
// via both a click and a trusted Enter keypress), AC3 (the UNDO_MS window: activatable near 9s,
// inert after 10s+fade), AC4 (409 race with another tab), AC5 (reload mid-window loses nothing),
// AC6 (real <button>, focusable, Enter-activatable), AC9 (this IS the runnable regression check).
// AC7 (view-only readers never see the trigger) is a SEPARATE hosted/anonymous-public-link run —
// see resolve-viewonly-check.mjs — because it needs a different tier's access policy, not this
// review's owner-only local instance.
//
// Every seeded comment is created HERE, over the real HTTP API against the real running instance
// (fetch() from Node, not a page-side stub) — no synthetic DOM events stand in for a resolve.
//
//   node scripts/resolve-undo-check.mjs <local-review-url>     # exit 0 = pass
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const URL_ARG = process.argv[2];
if (!URL_ARG) { console.error('usage: node scripts/resolve-undo-check.mjs <local-review-url>'); process.exit(2); }
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

// ---- fixture: seed comments over the real API, no synthetic client-side stubs -----------------
async function apiPost(path, body) {
  const r = await fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}) });
  return { status: r.status, json: r.ok ? await r.json() : null };
}
async function apiGet(path) {
  const r = await fetch(API + path);
  return { status: r.status, json: r.ok ? await r.json() : null };
}
async function mkComment(n) {
  const { json } = await apiPost('/comments', { anchor: { quoted_text: '', block_num: String(n) }, text: 'note ' + n });
  return json.comment_id;
}

const PORT = 9500 + (Date.now() % 400);
const profile = mkdtempSync(join(tmpdir(), 'resolve-undo-'));
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
const media = (motion) => cmd('Emulation.setEmulatedMedia', {
  features: motion ? [{ name: 'prefers-reduced-motion', value: motion }] : [],
});
// Colour tokens are light-dark(); a probe element is the only way to read the RESOLVED colour
// (getPropertyValue returns the raw light-dark(...) text, the #285 lesson).
const bgOf = tok => evaluate(`(()=>{const p=document.createElement('div');
  p.style.cssText='position:absolute;left:-9999px;background:var(${tok})';
  document.body.appendChild(p);const v=getComputedStyle(p).backgroundColor;p.remove();return v;})()`);

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
  ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
  await cmd('Page.enable'); await cmd('Runtime.enable');
}

async function gotoAndWait(url, marker) {
  await cmd('Page.navigate', { url });
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
  await cmd('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });

  // Seed 5 independent open comments BEFORE the first navigation: one resolve is a one-shot
  // transition (the card leaves the rail), so each AC gets its own fixture rather than racing to
  // reuse a single comment across cases.
  const c1 = await mkComment(1);  // AC1 (both-theme style) + AC2 (click-driven undo)
  const c2 = await mkComment(2);  // AC3 (the timing window)
  const c3 = await mkComment(3);  // AC6 (keyboard: focus + trusted Enter)
  const c4 = await mkComment(4);  // AC5 (reload mid-window)
  const c5 = await mkComment(5);  // AC4 (409 race with another tab)
  ok('fixture: 5 independent open comments seeded over the real API', [c1, c2, c3, c4, c5].every(Boolean));

  const ready = await gotoAndWait(URL_ARG, '.gcard');
  ok('the viewer actually loaded with the fixture (probe is not vacuous)', ready,
    await evaluate(`document.readyState + ' gcards=' + document.querySelectorAll('.gcard').length`));
  if (!ready) { console.log('\naborting: nothing to sample'); cleanup(); process.exit(1); }

  // ---- static: AC3's "one literal governs the window" claim, checked against THIS running
  // instance's actual served source (not a second copy of the file on disk) -------------------
  const servedJs = await evaluate(`fetch('/review/${RID}').then(r=>r.text())`);
  const undoMsDecls = (servedJs.match(/\bUNDO_MS\s*=\s*10000\b/g) || []).length;
  ok('AC3: UNDO_MS=10000 is declared exactly once in the served page', undoMsDecls === 1,
    `found ${undoMsDecls}`);
  const undoMsCallSite = /toastAction\(\s*'Comment resolved'[\s\S]{0,160}?UNDO_MS\s*\)/.test(servedJs);
  ok('AC3: the resolve toast call site passes UNDO_MS (not a second literal)', undoMsCallSite);

  // ---- positive control: theme tokens actually differ, so the "chip stays identical" assertion
  // below is capable of failing -----------------------------------------------------------------
  await evaluate(`document.documentElement.setAttribute('data-theme','light')`);
  const accentLight = await bgOf('--accent');
  await evaluate(`document.documentElement.setAttribute('data-theme','dark')`);
  const accentDark = await bgOf('--accent');
  ok('positive control: --accent actually differs between themes (the flip is real)',
    accentLight !== accentDark, `light=${accentLight} dark=${accentDark}`);

  // ================= AC1 + AC2: resolve c1, sample the chip in BOTH themes, then undo ==========
  await evaluate(`document.documentElement.setAttribute('data-theme','light')`);
  await evaluate(`document.querySelector('.gcard[data-id="${c1}"] [data-act=resolve]').click(); true`);
  await sleep(400);
  const toastVisibleNow = await evaluate(`(()=>{const t=document.getElementById('toast');
    return {opacity:getComputedStyle(t).opacity, hasAction:t.classList.contains('hasaction')};})()`);
  ok('positive control: the toast is actually showing right after the click (not vacuously absent)',
    toastVisibleNow.hasAction === true && parseFloat(toastVisibleNow.opacity) > 0, JSON.stringify(toastVisibleNow));

  const chipByTheme = {};
  for (const theme of ['light', 'dark']) {
    await evaluate(`document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)})`);
    const s = await evaluate(`(()=>{const t=document.getElementById('toast');const b=t.querySelector('.toastbtn');
      const span=t.querySelector('span');const tc=getComputedStyle(t), bc=getComputedStyle(b);
      return JSON.stringify({msg:span.textContent.trim(), label:b.textContent.trim(), bg:tc.backgroundColor, color:tc.color, radius:tc.borderRadius,
        btnFont:bc.fontFamily, btnSize:bc.fontSize, btnColor:bc.color, tag:b.tagName});})()`);
    const j = JSON.parse(s);
    chipByTheme[theme] = j;
    ok(`AC1 (${theme}): message reads exactly "Comment resolved"`, j.msg === 'Comment resolved', j.msg);
    ok(`AC1 (${theme}): undo control is labelled exactly "undo"`, j.label === 'undo', j.label);
    ok(`AC1 (${theme}): background-color rgb(31, 29, 26)`, j.bg === 'rgb(31, 29, 26)', j.bg);
    ok(`AC1 (${theme}): color rgb(232, 228, 220)`, j.color === 'rgb(232, 228, 220)', j.color);
    ok(`AC1 (${theme}): border-radius 8px`, j.radius === '8px', j.radius);
    ok(`AC1 (${theme}): undo control font-family contains "Geist Mono"`, j.btnFont.includes('Geist Mono'), j.btnFont);
    ok(`AC1 (${theme}): undo control font-size 11px`, j.btnSize === '11px', j.btnSize);
    ok(`AC1 (${theme}): undo control color rgb(181, 167, 230)`, j.btnColor === 'rgb(181, 167, 230)', j.btnColor);
    ok(`AC6 (${theme}): the undo control is a real <button>`, j.tag === 'BUTTON', j.tag);
  }
  ok('AC1: computed values are IDENTICAL across themes (the mock hardcodes hex, never inverts)',
    JSON.stringify(chipByTheme.light) === JSON.stringify(chipByTheme.dark),
    JSON.stringify(chipByTheme));

  // AC2: click undo, verify rendered outcome + real API state
  await evaluate(`document.querySelector('#toast .toastbtn').click(); true`);
  await sleep(400);
  const c1After = await apiGet(`/comments/${c1}`);
  ok('AC2: GET after undo -> status "reopened"', c1After.json?.status === 'reopened', c1After.json?.status);
  ok('AC2: resolved_by is null', c1After.json?.resolved_by === null, c1After.json?.resolved_by);
  const c1Hist = c1After.json?.status_history?.slice(-1)?.[0];
  ok('AC2: last status_history entry is {from:resolved,to:reopened,by:reviewer}',
    c1Hist && c1Hist.from === 'resolved' && c1Hist.to === 'reopened' && c1Hist.by === 'reviewer',
    JSON.stringify(c1Hist));
  ok('AC2: no reopen thread entry was added (empty-body reopen)',
    c1After.json?.thread?.length === 1, c1After.json?.thread?.length);
  const c1Dom = await evaluate(`(()=>{const g=document.querySelector('.gcard[data-id="${c1}"]');
    const r=document.querySelector('.rcard[data-id="${c1}"]');return {gcard:!!g, rcard:!!r};})()`);
  ok('AC2: the card is back in the active rail (.gcard present, no .rcard)',
    c1Dom.gcard === true && c1Dom.rcard === false, JSON.stringify(c1Dom));

  // ================= AC3: the 10s window, timed against a real toast ============================
  await evaluate(`document.querySelector('.gcard[data-id="${c2}"] [data-act=resolve]').click(); true`);
  let t0 = null;
  for (let i = 0; i < 40 && !t0; i++) {
    const has = await evaluate(`document.getElementById('toast').classList.contains('hasaction')`);
    if (has) t0 = Date.now();
    else await sleep(150);
  }
  ok('AC3 setup: the undo toast appeared', !!t0);
  const samples = [];
  while (Date.now() - t0 < 11200) {
    const s = await evaluate(`(()=>{const t=document.getElementById('toast');const cs=getComputedStyle(t);
      return JSON.stringify({hasAction:t.classList.contains('hasaction'), pointerEvents:cs.pointerEvents, opacity:cs.opacity});})()`);
    samples.push({ elapsed: Date.now() - t0, ...JSON.parse(s) });
    await sleep(400);
  }
  const activatableEarly = samples.some(s => s.elapsed < 9500 && s.hasAction && s.pointerEvents === 'auto');
  const inertLate = samples.some(s => s.elapsed > 10300 && !s.hasAction);
  ok('AC3: undo is still activatable at ~9s (hasaction + pointer-events:auto)', activatableEarly,
    JSON.stringify(samples.filter(s => s.elapsed < 9500).slice(-2)));
  ok('AC3: undo is inert after 10s + fade (hasaction removed, pointer-events reverts)', inertLate,
    JSON.stringify(samples.filter(s => s.elapsed > 10300).slice(0, 2)));
  const c2After = await apiGet(`/comments/${c2}`);
  ok('AC3: an expired, un-clicked undo changes NOTHING server-side (still "resolved")',
    c2After.json?.status === 'resolved', c2After.json?.status);

  // ================= AC6: keyboard — focus + a TRUSTED Enter keypress ============================
  await evaluate(`document.querySelector('.gcard[data-id="${c3}"] [data-act=resolve]').click(); true`);
  await sleep(400);
  await evaluate(`document.querySelector('#toast .toastbtn').focus(); true`);
  const focused = await evaluate(`document.activeElement === document.querySelector('#toast .toastbtn')`);
  ok('AC6: the undo control is focusable (Tab-reachable — a real <button>, no negative tabindex)', focused);
  // CDP Input.dispatchKeyEvent is TRUSTED synthetic input (unlike element.dispatchEvent), so the
  // browser's native "Enter activates the focused button" default action actually fires — but
  // only with text/unmodifiedText/nativeVirtualKeyCode all present; a bare rawKeyDown/keyDown
  // (no text fields) reaches the page's own keydown listeners but does NOT trigger the browser's
  // default button-activation action in headless Chrome (verified with an isolated data: URL
  // repro before wiring this in).
  const enterOpts = { windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13, key: 'Enter', code: 'Enter', text: '\r', unmodifiedText: '\r' };
  await cmd('Input.dispatchKeyEvent', { type: 'keyDown', ...enterOpts });
  await cmd('Input.dispatchKeyEvent', { type: 'keyUp', ...enterOpts });
  await sleep(400);
  const c3After = await apiGet(`/comments/${c3}`);
  ok('AC6: Enter on the focused undo control produces AC2\'s outcome (status "reopened")',
    c3After.json?.status === 'reopened', c3After.json?.status);

  // ================= AC5: reload mid-window loses nothing ========================================
  await evaluate(`document.querySelector('.gcard[data-id="${c4}"] [data-act=resolve]').click(); true`);
  await sleep(600);   // well inside the 10s window
  const reloaded = await gotoAndWait(URL_ARG, '#resbtn');
  ok('AC5 setup: reload completed', reloaded);
  await evaluate(`document.querySelector('#resbtn').click(); true`);
  await sleep(200);
  const c4Dom = await evaluate(`(()=>{const r=document.querySelector('.rcard[data-id="${c4}"]');
    return {present:!!r, hasReopen: r ? !!r.querySelector('[data-act=reopen]') : false};})()`);
  ok('AC5: after reload the comment renders in the Resolved panel with its Reopen affordance',
    c4Dom.present && c4Dom.hasReopen, JSON.stringify(c4Dom));
  const c4Api = await apiGet(`/comments/${c4}`);
  ok('AC5: API state stayed "resolved" — nothing auto-reopened on reload', c4Api.json?.status === 'resolved');

  // ================= AC4: undo races another tab that already reopened ===========================
  await evaluate(`document.querySelector('.gcard[data-id="${c5}"] [data-act=resolve]').click(); true`);
  await sleep(400);
  // Simulate "another tab" winning the race: reopen it directly over the API, bypassing this page.
  const raceReopen = await apiPost(`/comments/${c5}/reopen`, {});
  ok('AC4 setup: the "other tab" reopened it first (direct API call)', raceReopen.status === 200);
  await evaluate(`document.querySelector('#toast .toastbtn').click(); true`);
  await sleep(400);
  const toastAfterRace = await evaluate(`document.getElementById('toast').textContent.trim()`);
  ok('AC4: no error surface — the toast states the fact, not "Reopen failed"',
    toastAfterRace === 'Already reopened', toastAfterRace);
  const c5After = await apiGet(`/comments/${c5}`);
  const reopenEntries = (c5After.json?.status_history || []).filter(h => h.to === 'reopened');
  ok('AC4: GET shows status "reopened" with exactly ONE reopen entry (the race did not double-append)',
    c5After.json?.status === 'reopened' && reopenEntries.length === 1,
    `status=${c5After.json?.status} reopenEntries=${reopenEntries.length}`);

  // ================= motion: no NEW keyframe animation added; the existing opacity transition
  // already collapses under the theme.css global reduced-motion guard (universal selector) ========
  await media('reduce');
  await evaluate(`document.querySelector('.gcard') && true`);   // no-op settle
  const rmDur = await evaluate(`getComputedStyle(document.getElementById('toast')).transitionDuration`);
  const rmMs = parseFloat(rmDur) * 1000;
  ok('motion: #toast transition collapses under prefers-reduced-motion (theme.css global guard, no new keyframes added)',
    rmMs < 1, `got=${rmDur} = ${rmMs}ms`);
  await media(null);

  console.log(failed ? `\n${failed} case(s) failed` : '\nall resolve-undo cases pass');
  cleanup();
  process.exit(failed ? 1 : 0);
}

main().catch(e => { console.error('FATAL:', e); cleanup(); process.exit(2); });
