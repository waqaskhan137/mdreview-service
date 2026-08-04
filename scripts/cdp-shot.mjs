#!/usr/bin/env node
// scripts/cdp-shot.mjs (issue #78) — checked-in CDP interaction-evidence helper.
//
// Drives headless Chrome over the DevTools Protocol using ONLY Node's built-in WebSocket + fetch
// (Node >= 21) — zero npm dependencies. It runs an ORDERED sequence of steps (click / type / resize /
// assert) and captures screenshots, so interaction states become reproducible gate evidence, beyond a
// single-shot render-smoke. Any failing step exits NON-ZERO (missing element, a thrown or falsy
// --eval, a failed navigate).
//
// PREREQUISITE: a Chrome/Chromium binary. THIS SCRIPT LAUNCHES IT headless with --remote-debugging-port
// (you do NOT start Chrome yourself). It tries `google-chrome`/`chromium`/… on PATH; override with
// CHROME=/path/to/chrome.
//
// USAGE
//   node scripts/cdp-shot.mjs --url <URL> [steps, processed left-to-right] ...
//     --url <url>            navigate and wait for load
//     --wait <ms>            sleep N ms
//     --wait-for <selector>  poll until the selector matches (10s timeout); fails if it never appears
//     --click <selector>     click the first match (fails if absent)
//     --type <selector=text> set an input/textarea value + fire an `input` event
//     --resize <WxH>         set the viewport via CDP Emulation.setDeviceMetricsOverride. This is a REAL
//                            relayout that changes window.innerWidth — use it (NOT an OS window resize,
//                            which leaves innerWidth unchanged) to exercise responsive breakpoints.
//     --move <selector>      move the REAL pointer (Input.dispatchMouseEvent) to the centre of the
//                            first match, so :hover actually applies (#278 hover-reveal rows). A
//                            synthetic mouseover event does NOT set :hover; only the input pipeline
//                            does. Fails if the selector matches nothing. Move to `body` (0-ish
//                            corner) to un-hover.
//     --eval <expr>          run JS; the step FAILS if it throws OR returns falsy. Use as an assertion,
//                            e.g. --eval "document.querySelectorAll('.gcard').length===1"
//     --shot <path>          write a PNG screenshot to <path>
//
// CAVEAT — headless/backgrounded tabs FREEZE CSS animations, so a pixel screenshot can't prove an
// animation ran. Assert the COMPUTED STYLE instead (step the clock, read it), e.g.
//   --eval "getComputedStyle(document.querySelector('.x')).animationName!=='none'"
//
// WORKED EXAMPLES — against a THROWAWAY local instance, NEVER the live container. Start one with:
//   PORT=8199 MDREVIEW_DATA=$(mktemp -d) MDREVIEW_WEB_DIR=$PWD/web/app PYTHONPATH=$PWD/src python3 -m mdreview &
//   rid=$(curl -s -XPOST localhost:8199/api/reviews -d '{"markdown":"# T\n\nA\n\nB\n\nC"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
//
//   # (a) composer screenshot: open a review, click a gutter number, shoot the composer
//   node scripts/cdp-shot.mjs --url http://127.0.0.1:8199/review/$rid \
//     --wait-for ".blk .num" --click ".blk:nth-of-type(3) .num" --wait 200 \
//     --eval "document.querySelector('#pop').style.display==='block'" --shot /tmp/composer.png
//
//   # (b) #79 scenario: add a note -> the gutter card appears WITHOUT a reload
//   node scripts/cdp-shot.mjs --url http://127.0.0.1:8199/review/$rid \
//     --wait-for ".blk .num" --click ".blk:nth-of-type(3) .num" \
//     --type "#popnote=looks good" --click "#popsave" --wait 600 \
//     --eval "document.querySelectorAll('.gcard').length>=1"
//
//   # (c) #79 scenario: resize -> relayout (real innerWidth change)
//   node scripts/cdp-shot.mjs --url http://127.0.0.1:8199/review/$rid \
//     --wait-for ".blk" --resize 700x900 --wait 200 --eval "window.innerWidth===700"

import { spawn, execSync } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const STEP_VERBS = ['url', 'wait', 'wait-for', 'click', 'type', 'resize', 'move', 'eval', 'shot',
  'clipboard', 'cookie', 'block'];
const argv = process.argv.slice(2);
if (argv.length === 0 || argv.includes('-h') || argv.includes('--help')) {
  console.error('usage: node scripts/cdp-shot.mjs --url <URL> [--click sel | --wait ms | --wait-for sel | --type sel=text | --resize WxH | --eval expr | --shot path | --clipboard origin]...');
  process.exit(argv.length === 0 ? 2 : 0);
}

const steps = [];
for (let i = 0; i < argv.length; i++) {
  const verb = argv[i].replace(/^--/, '');
  if (!STEP_VERBS.includes(verb)) { console.error('unknown flag: ' + argv[i]); process.exit(2); }
  if (argv[i + 1] === undefined) { console.error(argv[i] + ' needs a value'); process.exit(2); }
  steps.push([verb, argv[++i]]);
}

function findChrome() {
  if (process.env.CHROME) return process.env.CHROME;
  for (const c of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium']) {
    if (c.includes('/')) { if (existsSync(c)) return c; }
    else { try { execSync('command -v ' + c, { stdio: 'ignore' }); return c; } catch { /* not on PATH */ } }
  }
  die('no Chrome/Chromium found on PATH or in /Applications; set CHROME=/path/to/chrome');
}
const CHROME = findChrome();
const PORT = 9200 + (Date.now() % 600);
const profile = mkdtempSync(join(tmpdir(), 'cdp-shot-'));
let chrome, ws, closed = false, msgId = 0;
const pending = new Map();
const loadWaiters = [];

function cleanup() {
  if (closed) return; closed = true;
  try { ws && ws.close(); } catch {}
  try { chrome && chrome.kill('SIGKILL'); } catch {}
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
}
function die(msg) { console.error('cdp-shot: ' + msg); cleanup(); process.exit(1); }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function cmd(method, params = {}) {
  const id = ++msgId;
  return new Promise(res => { pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
}
async function check(method, params) {
  const r = await cmd(method, params);
  if (r.error) die(method + ' failed: ' + r.error.message);
  return r.result;
}
async function evalOrDie(expr, label) {
  const r = await check('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) die(label + ' threw: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
  return r.result?.value;
}
async function pollFor(sel) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    const v = await evalOrDie(`document.querySelector(${JSON.stringify(sel)})!==null`, 'wait-for');
    if (v) { console.log('ok  wait-for: ' + sel); return; }
    await sleep(150);
  }
  die('wait-for timed out (10s): ' + sel);
}
async function debuggerWsUrl() {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
      const page = list.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch {}
    await sleep(150);
  }
  die('Chrome DevTools endpoint never came up on port ' + PORT);
}

process.on('exit', cleanup);
process.on('SIGINT', () => { cleanup(); process.exit(130); });
setTimeout(() => die('overall timeout (120s) — Chrome wedged or a step hung'), 120000).unref(); // never hang CI

chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  '--no-default-browser-check', '--hide-scrollbars', `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
chrome.on('error', e => die(`failed to launch Chrome (${CHROME}): ${e.message}\nSet CHROME=/path/to/chrome`));

const wsUrl = await debuggerWsUrl();
ws = new WebSocket(wsUrl);
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { const res = pending.get(m.id); pending.delete(m.id); res(m); }
  else if (m.method === 'Page.loadEventFired') loadWaiters.splice(0).forEach(fn => fn());
};
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(); }).catch(() => die('could not connect to the Chrome CDP websocket'));
ws.onclose = () => { if (!closed) die('Chrome CDP websocket closed unexpectedly (Chrome crashed?)'); }; // don't hang on a dead browser

await check('Page.enable');
await check('Runtime.enable');
await check('Emulation.setDeviceMetricsOverride', { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false }); // sane default; --resize overrides

for (const [verb, val] of steps) {
  if (verb === 'clipboard') {
    // #189: navigator.clipboard needs BOTH, and the two failures look nothing alike. Without the
    // grant, reads reject NotAllowedError "Read permission denied"; without focus emulation, even
    // writeText rejects NotAllowedError "Document is not focused" — headless has no focused window.
    // Put this step BEFORE --url: grantPermissions is per-origin and survives the navigation.
    await check('Browser.grantPermissions', { origin: val, permissions: ['clipboardReadWrite', 'clipboardSanitizedWrite'] });
    await check('Emulation.setFocusEmulationEnabled', { enabled: true });
    console.log('ok  clipboard: granted read/write + focus emulation for ' + val);
    continue;
  }
  if (verb === 'cookie') {
    // #221 stage 8: authenticated surfaces (/admin, the account menu) cannot be reached at all
    // without a session, and there is no login UI to drive headlessly when links arrive by email.
    // Put this step BEFORE --url; a cookie set after navigation does not apply to the page already
    // loaded. Format: --cookie "name=value@https://host".
    const at = val.lastIndexOf('@'); if (at < 0) die('--cookie needs name=value@origin, got: ' + val);
    const nv = val.slice(0, at), origin = val.slice(at + 1);
    const eq = nv.indexOf('='); if (eq < 0) die('--cookie needs name=value@origin, got: ' + val);
    await check('Network.enable');
    const r = await cmd('Network.setCookie', {
      name: nv.slice(0, eq), value: nv.slice(eq + 1), url: origin, path: '/', httpOnly: true, secure: origin.startsWith('https'),
    });
    if (r.error || r.result?.success === false) die('could not set cookie: ' + JSON.stringify(r.error || r.result));
    // Never print the value: a session cookie in a log or a CI transcript is a live credential.
    console.log('ok  cookie: ' + nv.slice(0, eq) + ' set for ' + origin);
    continue;
  }
  if (verb === 'block') {
    // Prove a FAILURE path without breaking the server for everyone: block one URL pattern so the
    // page's fetch really fails. #221 needs this to show the connection state, which by definition
    // cannot be reached while the endpoint is healthy.
    await check('Network.enable');
    await check('Network.setBlockedURLs', { urls: val.split(',') });
    console.log('ok  block: ' + val);
    continue;
  }
  if (verb === 'url') {
    const loaded = new Promise(r => loadWaiters.push(r));
    await check('Page.navigate', { url: val });
    await Promise.race([loaded, sleep(15000)]);
    console.log('ok  url: ' + val);
  } else if (verb === 'wait') {
    await sleep(Number(val) || 0);
  } else if (verb === 'wait-for') {
    await pollFor(val);
  } else if (verb === 'click') {
    await evalOrDie(`(()=>{const el=document.querySelector(${JSON.stringify(val)});if(!el)throw new Error('no element: '+${JSON.stringify(val)});el.scrollIntoView({block:'center'});el.click();return true;})()`, 'click ' + val);
    console.log('ok  click: ' + val);
  } else if (verb === 'type') {
    const eq = val.indexOf('='); if (eq < 0) die('--type needs selector=text, got: ' + val);
    const sel = val.slice(0, eq), text = val.slice(eq + 1);
    await evalOrDie(`(()=>{const el=document.querySelector(${JSON.stringify(sel)});if(!el)throw new Error('no element: '+${JSON.stringify(sel)});el.focus();el.value=${JSON.stringify(text)};el.dispatchEvent(new Event('input',{bubbles:true}));return true;})()`, 'type ' + sel);
    console.log('ok  type: ' + sel);
  } else if (verb === 'resize') {
    const m = /^(\d+)x(\d+)$/.exec(val); if (!m) die('--resize needs WxH, got: ' + val);
    await check('Emulation.setDeviceMetricsOverride', { width: +m[1], height: +m[2], deviceScaleFactor: 1, mobile: false });
    console.log('ok  resize: ' + val);
  } else if (verb === 'move') {
    const pt = await evalOrDie(`(()=>{const el=document.querySelector(${JSON.stringify(val)});`
      + `if(!el)throw new Error('no element: '+${JSON.stringify(val)});`
      + `el.scrollIntoView({block:'center'});const b=el.getBoundingClientRect();`
      + `return {x:Math.round(b.x+b.width/2),y:Math.round(b.y+b.height/2)};})()`, 'move ' + val);
    await check('Input.dispatchMouseEvent', { type: 'mouseMoved', x: pt.x, y: pt.y, buttons: 0 });
    console.log('ok  move: ' + val + ' -> ' + pt.x + ',' + pt.y);
  } else if (verb === 'eval') {
    const v = await evalOrDie(val, 'eval');
    if (!v) die('assertion failed (--eval returned falsy): ' + val + '  => ' + JSON.stringify(v));
    console.log('ok  eval: ' + val + '  => ' + JSON.stringify(v));
  } else if (verb === 'shot') {
    const r = await check('Page.captureScreenshot', { format: 'png' });
    writeFileSync(val, Buffer.from(r.data, 'base64'));
    console.log('ok  shot: ' + val);
  }
}

console.log('cdp-shot: all steps ok');
cleanup();
process.exit(0);
