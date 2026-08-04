// share-visibility-check.mjs — #284, asserted as RENDERED OUTCOMES in a real headless Chrome.
//
// dashboard.html's data comes from fetch() calls (/auth/session, /api/reviews,
// /api/reviews?scope=shared) that this ticket owns end to end, so — same shape as
// scripts/admin-reskin-check.mjs — a window.fetch stub installed via
// Page.addScriptToEvaluateOnNewDocument runs BEFORE any page script (including the pre-paint
// theme applier), so dashboard.html's own boot()/load()/render() code runs for real against a
// known fixture. Real subresources (theme.css, basecoat, session.js, account.js) still load from
// a real (LOCAL-tier) server: only the page's OWN data calls are intercepted. This sidesteps
// reproducing the magic-link login + cookie flow here — that flow, and the server-side share
// membership/authorization it fronts, is asserted for real (real accounts, real grants) by
// tests/share_scope_selfcheck.py. This script asserts only what a server-side test cannot: that
// the badges and the "Shared with you" group actually PAINT, with the right computed colour, in
// both themes (#265's lesson: a CSS-text assertion can stay green over a layout that never
// rendered).
//
//   node scripts/share-visibility-check.mjs http://127.0.0.1:PORT
// (PORT serves a LOCAL-tier `python -m mdreview` instance; tests/share_visibility_ui_selfcheck.sh
// provisions it — the local tier is enough because every datum comes from the fetch stub, not
// from a real hosted boot.)
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BASE = process.argv[2];
if (!BASE) { console.error('usage: share-visibility-check.mjs <origin>'); process.exit(2); }
const DASH_URL = BASE.replace(/\/$/, '') + '/';

const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }

let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c ? '' : `  (${d})`)); if (!c) failed++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

const port = 9700 + (Date.now() % 500);
const profile = mkdtempSync(join(tmpdir(), 'share-vis-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
const done = () => { try { chrome.kill(); } catch {} try { rmSync(profile, { recursive: true, force: true }); } catch {} };
const overall = setTimeout(() => { console.error('share-visibility-check: overall timeout (120s)'); done(); process.exit(2); }, 120000);
overall.unref();

// ---- the fixture + window.fetch stub, injected before every navigation on this tab -----------
// Fixture timestamps are deliberately staggered so the THIRD owned doc (no badge, "Lease
// freshness...") is the most recently active — it is the one the dashboard's own "next up"
// promotion (unrelated to #284, out of scope) shifts into the hero block, which does not render
// badges. That keeps both badge-bearing rows in the plain list this check samples, independent of
// that orthogonal behaviour.
const FIXTURE_SCRIPT = `
(function(){
  var T0 = 1700000000;
  var boot = (location.hash.match(/boot=([a-z0-9]+)/) || [])[1] || 'main';
  var owned = [
    // The highest-activity "yours" row: the dashboard's OWN "next up" hero promotion (unrelated
    // to #284, out of scope here) shifts whichever "yours" row is most recently active OUT of the
    // plain list and into a hero block that renders no badges at all. Giving THIS row the max
    // timestamp, and none of the badge-relevant rows below it, keeps pub1/shr1/plain1 all in the
    // plain list this check samples — otherwise which row gets promoted (and silently vanishes
    // from every '.rw' query here) would depend on wall-clock T0 arithmetic alone.
    {id:'hero1', title:'Zzz newest doc (promotion bait, not asserted)', project:'misc', kind:'markdown',
     created:T0, source_updated:T0+99999, feedback_updated:0, revision:0, turn:'reviewer',
     notes_total:1, notes_addressed:0, status:'feedback'},
    {id:'pub1', title:'Magic-link rate limiting', project:'auth-service', kind:'markdown',
     created:T0, source_updated:T0+300, feedback_updated:0, revision:0, turn:'reviewer',
     notes_total:3, notes_addressed:0, status:'feedback',
     share_public: boot==='main' ? 'view' : undefined},
    {id:'shr1', title:'Retry semantics for the MCP bridge', project:'agent-bridge', kind:'markdown',
     created:T0, source_updated:T0+200, feedback_updated:0, revision:0, turn:'reviewer',
     notes_total:2, notes_addressed:0, status:'feedback',
     share_count: boot==='main' ? 2 : undefined},
    {id:'plain1', title:'Lease freshness under partition', project:'papers', kind:'latex',
     created:T0, source_updated:T0+9000, feedback_updated:0, revision:0, turn:'reviewer',
     notes_total:6, notes_addressed:0, status:'feedback'},
    // Populates "With the agent" so the AC1/AC6 group-ORDER assertion below is a real check
    // (Shared with you after a group that actually rendered), not a vacuous one.
    {id:'agent1', title:'Session revocation, take two', project:'auth-service', kind:'markdown',
     created:T0, source_updated:T0+100, feedback_updated:0, revision:0, turn:'agent',
     notes_total:4, notes_addressed:2, status:'feedback'}
  ];
  // JSON.stringify drops keys whose value is undefined — the SAME additive-default-safe shape the
  // real server sends (key absent, never a falsy 0/None), so this fixture cannot pass by
  // accident on a shape the real server would never produce.
  var sharedIn = boot==='main' ? [
    {id:'inb1', title:'Quorum loss and the read path', kind:'latex', right:'comment',
     from_email:'j.reyes', created:T0, source_updated:T0+14400, feedback_updated:0},
    {id:'inb2', title:'Onboarding runbook, draft 2', kind:'markdown', right:'view',
     from_email:'t.okafor', created:T0, source_updated:T0+600, feedback_updated:0}
  ] : [];
  var jsonRes = function(obj, status){ return new Response(JSON.stringify(obj), {status: status||200, headers:{'Content-Type':'application/json'}}); };
  var orig = window.fetch.bind(window);
  window.fetch = function(input, init){
    var url = typeof input === 'string' ? input : (input && input.url) || '';
    var path = url.replace(/^https?:\\/\\/[^/]+/, '');
    if (path === '/auth/session') return Promise.resolve(jsonRes({authenticated:true, uid:'u:me', email:'me@example.com', csrf:'stub-csrf'}));
    if (path === '/api/reviews?scope=shared') return Promise.resolve(jsonRes({reviews: sharedIn}));
    if (path === '/api/reviews') return Promise.resolve(jsonRes({reviews: owned}));
    return orig(input, init);
  };
  // Resolve a design-token CSS value the way a real consumer sees it: a probe element, never
  // getComputedStyle(:root).getPropertyValue, which returns the raw light-dark(...) TEXT (#285).
  window.__tok = function(prop, value){
    var p = document.createElement('div');
    p.style.cssText = 'position:absolute;left:-9999px;top:-9999px;' + prop + ':' + value + ';';
    document.body.appendChild(p);
    var v = getComputedStyle(p).getPropertyValue(prop);
    p.remove();
    return v;
  };
})();
`;

let ws;
try {
  let target;
  for (let i = 0; i < 60; i++) {
    try {
      const tabs = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      target = (tabs || []).find(t => t.type === 'page' && !String(t.url).startsWith('chrome-extension://'));
      if (target) break;
    } catch {}
    await sleep(250);
  }
  if (!target) { console.error('no page target found'); done(); process.exit(2); }
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r, { once: true }));
  let id = 0; const pending = new Map();
  ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
  const cmd = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const evaluate = async expr => {
    const r = await cmd('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result?.exceptionDetails) throw new Error('page eval threw: ' +
      (r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text));
    return r.result?.result?.value;
  };
  const evalJSON = async expr => JSON.parse(await evaluate(expr));

  await cmd('Page.enable'); await cmd('Runtime.enable');
  await cmd('Emulation.setDeviceMetricsOverride', { width: 1200, height: 900, deviceScaleFactor: 1, mobile: false });
  await cmd('Page.addScriptToEvaluateOnNewDocument', { source: FIXTURE_SCRIPT });

  // Bounce through about:blank first: a hash-only "navigation" is same-document and would not
  // re-run Page.addScriptToEvaluateOnNewDocument, so boot=<state> would keep serving whatever the
  // FIRST navigation resolved (the #282 lesson, copied from admin-reskin-check.mjs).
  async function hardNav(hash) {
    await cmd('Page.navigate', { url: 'about:blank' });
    await cmd('Page.navigate', { url: DASH_URL + '#boot=' + hash });
  }
  async function navReady(hash, readyExpr) {
    await hardNav(hash);
    for (let i = 0; i < 100; i++) {
      if (await evaluate(readyExpr)) return true;
      await sleep(150);
    }
    return false;
  }

  // ================= main fixture: badges + the "Shared with you" group =================
  const READY_MAIN = `document.querySelectorAll('.grp-shared .rw').length===2 && ` +
    `document.querySelectorAll('#list .rw-badge').length===2 && ` +
    `document.querySelectorAll('.grp-h').length>=3`;
  const readyMain = await navReady('main', READY_MAIN);
  ok('dashboard loaded with the fixture rendered (probe is not vacuous)', readyMain,
     await evaluate(`document.readyState + ' badges=' + document.querySelectorAll('.rw-badge').length + ' sharedRows=' + document.querySelectorAll('.grp-shared .rw').length`));
  if (!readyMain) { console.log('\\naborting: nothing to sample'); throw new Error('fixture never rendered'); }

  const s = await evalJSON(`(() => {
    const q = sel => document.querySelector(sel);
    const qa = sel => Array.from(document.querySelectorAll(sel));
    const rowFor = title => qa('.rw').find(r => (r.querySelector('.rw-t')||{}).textContent === title);
    const pubRow = rowFor('Magic-link rate limiting');
    const sharedRow = rowFor('Retry semantics for the MCP bridge');
    const plainRow = rowFor('Lease freshness under partition');
    const pubBadge = pubRow ? pubRow.querySelector('.rw-badge.pub') : null;
    const sharedBadge = sharedRow ? sharedRow.querySelector('.rw-badge.shared') : null;
    const grpHeads = qa('.grp-h').map(h => h.textContent.trim());
    const inbHead = qa('.grp-h').find(h => h.textContent.trim() === 'Shared with you');
    const inbGrp = inbHead ? inbHead.closest('.grp') : null;
    const inbRows = inbGrp ? Array.from(inbGrp.querySelectorAll('.rw')) : [];
    const rowInfo = el => ({
      title: (el.querySelector('.rw-t')||{}).textContent,
      from: (el.querySelector('.rw-p')||{}).textContent,
      right: (el.querySelector('.rw-s')||{}).textContent,
      hasRm: !!el.querySelector('.rm'),
      hasDel: !!el.querySelector('.del'),
      rmTitle: el.querySelector('.rm') ? el.querySelector('.rm').getAttribute('title') : null
    });
    return JSON.stringify({
      pubBadgeText: pubBadge ? pubBadge.textContent.trim() : null,
      pubBadgeTitle: pubBadge ? pubBadge.getAttribute('title') : null,
      sharedBadgeText: sharedBadge ? sharedBadge.textContent.trim() : null,
      sharedBadgeTitle: sharedBadge ? sharedBadge.getAttribute('title') : null,
      plainRowBadgeCount: plainRow ? plainRow.querySelectorAll('.rw-badge').length : -1,
      grpHeads, grpOrder: JSON.stringify(grpHeads),
      inbRows: inbRows.map(rowInfo),
      ownedRowHasDel: !!pubRow.querySelector('.del'),
    });
  })()`);

  ok('AC2: PUBLIC badge text + title on the public-only row', s.pubBadgeText === 'PUBLIC' && s.pubBadgeTitle === 'Anyone with the link can open this', JSON.stringify(s));
  ok('AC2: people-count badge "2" + title on the named-share row', s.sharedBadgeText === '2' && s.sharedBadgeTitle === 'Shared with 2 people', JSON.stringify(s));
  ok('AC2: the unshared row renders NO badge element at all', s.plainRowBadgeCount === 0, s.plainRowBadgeCount);
  ok('AC1/AC6 order: "Shared with you" appears AFTER "With the agent"',
     s.grpHeads.indexOf('With the agent') >= 0 && s.grpHeads.indexOf('Shared with you') > s.grpHeads.indexOf('With the agent'),
     s.grpOrder);
  ok('owned rows keep their normal Delete control (regression: badges did not replace it)', s.ownedRowHasDel, JSON.stringify(s));

  const want = [
    { title: 'Quorum loss and the read path', from: 'from j.reyes', right: 'can comment', hasRm: true, hasDel: false, rmTitle: 'Remove from your list' },
    { title: 'Onboarding runbook, draft 2', from: 'from t.okafor', right: 'view only', hasRm: true, hasDel: false, rmTitle: 'Remove from your list' },
  ];
  ok('AC6: both shared-in rows read "from <local-part>" / "can comment" or "view only", X control, no Delete',
     JSON.stringify(s.inbRows) === JSON.stringify(want), JSON.stringify(s.inbRows));

  // ================= per-theme colour sweep (both themes forced via data-theme) =================
  async function themeSnapshot(theme) {
    return evalJSON(`(() => {
      document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)});
      const rowFor = title => Array.from(document.querySelectorAll('.rw')).find(r => (r.querySelector('.rw-t')||{}).textContent === title);
      const pubBadge = rowFor('Magic-link rate limiting').querySelector('.rw-badge.pub');
      const sharedBadge = rowFor('Retry semantics for the MCP bridge').querySelector('.rw-badge.shared');
      return JSON.stringify({
        pubColor: getComputedStyle(pubBadge).color,
        sharedColor: getComputedStyle(sharedBadge).color,
        warning: window.__tok('background-color','var(--warning)'),
        textSubtle: window.__tok('background-color','var(--text-subtle)'),
      });
    })()`);
  }
  const light = await themeSnapshot('light');
  const dark = await themeSnapshot('dark');
  ok('theme positive control: --warning differs light vs dark, never transparent',
     light.warning !== dark.warning && light.warning !== 'rgba(0, 0, 0, 0)' && dark.warning !== 'rgba(0, 0, 0, 0)',
     `light=${light.warning} dark=${dark.warning}`);
  for (const [theme, t] of [['light', light], ['dark', dark]]) {
    ok(`AC2 (${theme}): PUBLIC badge colour resolves to --warning`, t.pubColor === t.warning, `${t.pubColor} vs ${t.warning}`);
    ok(`AC2 (${theme}): people-count badge colour resolves to --text-subtle`, t.sharedColor === t.textSubtle, `${t.sharedColor} vs ${t.textSubtle}`);
  }

  // ================= positive control: boot=noshares must show NEITHER feature =================
  const READY_NONE = `document.querySelectorAll('.rw').length===4 && document.querySelectorAll('.grp-h').length>=1`;
  const readyNone = await navReady('noshares', READY_NONE);
  ok('positive control: the no-shares fixture also renders (not just erroring out)', readyNone,
     await evaluate(`document.readyState + ' rows=' + document.querySelectorAll('.rw').length`));
  const none = await evalJSON(`JSON.stringify({
    badges: document.querySelectorAll('.rw-badge').length,
    sharedHeading: Array.from(document.querySelectorAll('.grp-h')).some(h => h.textContent.trim()==='Shared with you'),
    sharedRows: document.querySelectorAll('.grp-shared .rw').length
  })`);
  ok('positive control: zero badges anywhere when no row is shared',
     none.badges === 0, JSON.stringify(none));
  ok('positive control: no "Shared with you" heading/group when scope=shared is empty',
     !none.sharedHeading && none.sharedRows === 0, JSON.stringify(none));

} finally {
  clearTimeout(overall);
  try { ws?.close(); } catch {}
  done();
}
console.log(failed ? `\n${failed} case(s) failed` : '\nall share-visibility cases pass');
process.exit(failed ? 1 : 0);
