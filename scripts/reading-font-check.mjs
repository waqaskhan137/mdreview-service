// reading-font-check.mjs — what the document body ACTUALLY renders in.
// Zero-dep CDP, same shape as scripts/latex-canvas-check.mjs (readiness poll, real page target).
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const url = process.argv[2];
const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }

let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c ? '' : `  (${d})`)); if (!c) failed++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const port = 9300 + (Date.now() % 500);
const profile = mkdtempSync(join(tmpdir(), 'reading-font-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
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
  if (!target) { console.error('no page target'); process.exit(2); }
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r, { once: true }));
  let id = 0; const pending = new Map();
  ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
  const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const evalJs = async expr => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }))?.result?.result?.value;

  await send('Page.enable'); await send('Runtime.enable');
  await send('Page.navigate', { url });
  let ready = false;
  for (let i = 0; i < 80; i++) {
    const st = await evalJs(`document.readyState + '|' + !!document.querySelector('#article p')`);
    if (typeof st === 'string' && st.startsWith('complete') && st.endsWith('true')) { ready = true; break; }
    await sleep(250);
  }
  ok('the viewer loaded with real prose (probe is not vacuous)', ready);
  if (!ready) { ws.close(); chrome.kill(); process.exit(1); }
  await sleep(400);

  const r = JSON.parse(await evalJs(`(() => {
    const p = document.querySelector('#article p');
    const cs = getComputedStyle(p);
    const body = getComputedStyle(document.body);
    return JSON.stringify({
      stack: cs.fontFamily,
      size: body.fontSize,
      lineHeight: body.lineHeight,
      // Which face did the browser actually pick? fonts.check answers for the real document,
      // rather than us reading the CSS back to ourselves.
      charterAvailable: document.fonts.check('20px Charter'),
      georgiaAvailable: document.fonts.check('20px Georgia'),
      sourceSerifLoaded: [...document.fonts].some(f => f.family === 'Source Serif 4' && f.status === 'loaded'),
    });
  })()`));

  ok('the reading stack starts with Charter, not a webfont',
     /^\s*Charter\s*,/.test(r.stack), r.stack);
  ok('"Source Serif 4" is NOT in the reading stack', !/Source Serif 4/.test(r.stack), r.stack);
  ok('body renders at 20px', r.size === '20px', r.size);
  ok('line-height is unchanged at 1.7', Math.abs(parseFloat(r.lineHeight) / 20 - 1.7) < 0.02, r.lineHeight);
  ok('at least one face in the stack is actually available, so this is not silent fallback to a UA default',
     r.charterAvailable || r.georgiaAvailable,
     `charter=${r.charterAvailable} georgia=${r.georgiaAvailable}`);
  ok('Source Serif 4 is not downloaded for the reading surface (unreferenced faces cost nothing)',
     !r.sourceSerifLoaded, `loaded=${r.sourceSerifLoaded}`);
} finally {
  try { ws?.close(); } catch {}
  try { chrome.kill(); } catch {}
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
}
console.log(failed ? `\n${failed} case(s) failed` : '\nall reading-font cases pass');
process.exit(failed ? 1 : 0);
