// latex-canvas-check.mjs — #333. Samples COMPUTED colours in a real browser, both themes.
// Zero-dep: Node's built-in WebSocket + fetch driving CDP, the same shape as theme-check.mjs.
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const url = process.argv[2];
// Same discovery as scripts/theme-check.mjs — reuse the working one rather than a second guess.
const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }
let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c ? '' : `  (${d})`)); if (!c) failed++; };
const port = 9300 + (Date.now() % 500);
const profile = mkdtempSync(join(tmpdir(), 'latex-canvas-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws;
try {
  let tabs;
  // Filter to a real PAGE target: /json/list also returns extension background pages, and the
  // first attempt connected to one, so every sample came from chrome-extension://.../background.html.
  let target;
  for (let i = 0; i < 60; i++) {
    try {
      tabs = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      target = (tabs || []).find(t => t.type === 'page' && !String(t.url).startsWith('chrome-extension://'));
      if (target) break;
    } catch {}
    await sleep(250);
  }
  if (!target) { console.error('no page target found'); process.exit(2); }
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r, { once: true }));
  let id = 0; const pending = new Map();
  ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
  const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const evalJs = async expr => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }))?.result?.result?.value;

  await send('Page.enable'); await send('Runtime.enable');
  await send('Page.navigate', { url });
  // Poll for the page to be REALLY there. A fixed sleep after Page.navigate evaluated against
  // about:blank on the first attempt: .pdfpane was absent and every token resolved transparent,
  // which the "tokens are distinct" control caught rather than passing vacuously.
  let ready = false;
  for (let i = 0; i < 80; i++) {
    const st = await evalJs(`document.readyState + '|' + location.href + '|' + !!document.querySelector('.pdfpane')`);
    if (typeof st === 'string' && st.startsWith('complete') && st.endsWith('true')) { ready = true; break; }
    await sleep(250);
  }
  ok('the latex viewer actually loaded (probe is not vacuous)', ready,
     await evalJs(`document.readyState + ' ' + location.href`));
  if (!ready) { console.log('\naborting: nothing to sample'); ws.close(); chrome.kill(); process.exit(1); }
  await sleep(300);

  for (const theme of ['light', 'dark']) {
    const r = await evalJs(`(()=>{
      document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)});
      // A probe element is the ONLY way to read a light-dark() token as a resolved colour:
      // getPropertyValue returns the raw light-dark(...) text.
      const probe=document.createElement('div');
      probe.style.cssText='position:absolute;left:-9999px;background:var(--canvas)';
      document.body.appendChild(probe);
      const canvas=getComputedStyle(probe).backgroundColor;
      const codebg=(()=>{const p2=document.createElement('div');
        p2.style.cssText='position:absolute;left:-9999px;background:var(--code-bg)';
        document.body.appendChild(p2);const v=getComputedStyle(p2).backgroundColor;p2.remove();return v;})();
      probe.remove();
      const pane=document.querySelector('.pdfpane');
      return JSON.stringify({canvas,codebg,pane:pane?getComputedStyle(pane).backgroundColor:'(absent)'});
    })()`);
    const { canvas, codebg, pane } = JSON.parse(r);
    ok(`${theme}: .pdfpane renders --canvas`, pane === canvas, `pane=${pane} canvas=${canvas}`);
    ok(`${theme}: .pdfpane is NOT --code-bg`, pane !== codebg || canvas === codebg,
       `pane=${pane} code-bg=${codebg} — the pre-#333 value`);
    ok(`${theme}: --canvas and --code-bg are actually distinct, so the check can fail`,
       canvas !== codebg, `both ${canvas}`);
  }
} finally { try { ws?.close(); } catch {} try { chrome.kill(); } catch {}
  try { rmSync(profile, { recursive: true, force: true }); } catch {} }
console.log(failed ? `\n${failed} case(s) failed` : '\nall latex canvas cases pass');
process.exit(failed ? 1 : 0);
