// resolve-viewonly-check.mjs — #287 AC7: a view-only reader never sees the Resolve trigger.
// Real can_comment:false, not a hand-set body class: the fixture is a review made PUBLIC
// (D3 — public shares are view-only, no anonymous comments), so an anonymous browser tab with NO
// cookie at all gets a real can_read=true/can_comment=false from the live /status endpoint, and
// this script drives the actual page load + poll that turns into body.viewonly, exactly what a
// stranger following a shared link would experience.
//
//   node scripts/resolve-viewonly-check.mjs <public-review-url>     # exit 0 = pass
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const URL_ARG = process.argv[2];
if (!URL_ARG) { console.error('usage: node scripts/resolve-viewonly-check.mjs <public-review-url>'); process.exit(2); }

const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }

let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c && !d ? '' : d ? `  (${d})` : '')); if (!c) failed++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

const PORT = 9700 + (Date.now() % 300);
const profile = mkdtempSync(join(tmpdir(), 'resolve-viewonly-'));
// A FRESH profile with no prior visits/cookies is the point: this is what an anonymous stranger's
// browser looks like.
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

async function main() {
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
  // Wide viewport: the default headless window is narrow enough to trip the DOCKED gutter layout
  // (.gcard width:auto in a possibly-narrow panel), which can make a flush-right measurement pass
  // by coincidence (content roughly fills a narrow row) rather than by the actual margin-left:auto
  // mechanism. The 284px-wide rail layout (railFits(), viewer.html) is what the AC1 mock depicts.
  await cmd('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
  // No Network.setCookie call anywhere in this script — that IS the fixture: a cookie-less tab.
  await cmd('Page.navigate', { url: URL_ARG });

  let ready = false;
  for (let i = 0; i < 80; i++) {
    const st = await evaluate(`document.readyState + '|' + !!document.querySelector('.gcard')`);
    if (st === 'complete|true') { ready = true; break; }
    await sleep(250);
  }
  ok('positive control: the anonymous tab CAN read the public review (probe is not vacuous)', ready,
    await evaluate(`document.readyState + ' gcards=' + document.querySelectorAll('.gcard').length`));
  if (!ready) { console.log('\naborting: nothing to sample'); cleanup(); process.exit(1); }

  // The poll (2s interval) settles body.viewonly from the real /status.can_comment; give it room.
  let viewonly = false;
  for (let i = 0; i < 10; i++) {
    viewonly = await evaluate(`document.body.classList.contains('viewonly')`);
    if (viewonly) break;
    await sleep(500);
  }
  ok('AC7: the real /status.can_comment=false settles body.viewonly (not a hand-set class)', viewonly);

  const state = await evaluate(`(()=>{const btn=document.querySelector('.gcard [data-act=resolve]');
    if(!btn) return {present:false};
    const cs=getComputedStyle(btn);
    return {present:true, display:cs.display, offsetParent:!!btn.offsetParent};})()`);
  ok('AC7: the Resolve control is not visible to a view-only reader (computed display / offsetParent)',
    state.present === false || (state.display === 'none' && state.offsetParent === false),
    JSON.stringify(state));

  // Hiding .gres (which alone carries margin-left:auto) must not knock .gdel out of its
  // flush-right position — the AC7 fixture (one reviewer comment, no agent reply) is exactly the
  // case where .gdel renders (deletable=true), so this is a real regression risk from the same
  // change, not a hypothetical.
  const delRect = await evaluate(`(()=>{const del=document.querySelector('.gcard .gdel');
    const head=del ? del.closest('.ghead') : null;
    if(!del||!head) return {present:false};
    const d=del.getBoundingClientRect(), h=head.getBoundingClientRect();
    return {present:true, gap: h.right - d.right};})()`);
  ok('AC7: hiding Resolve does not knock Delete out of its flush-right position',
    delRect.present === true && Math.abs(delRect.gap) <= 1, JSON.stringify(delRect));

  console.log(failed ? `\n${failed} case(s) failed` : '\nall resolve-viewonly cases pass');
  cleanup();
  process.exit(failed ? 1 : 0);
}

main().catch(e => { console.error('FATAL:', e); cleanup(); process.exit(2); });
