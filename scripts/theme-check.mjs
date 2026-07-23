// Verifies #153: every page adapts to prefers-color-scheme AND all pages agree on the same
// light/dark surface. Zero-dep: Node's built-in WebSocket + fetch driving headless Chrome over CDP.
// Asserts, rather than eyeballs: a page that ignores the system theme reports identical colours.
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const PAGES = process.argv.slice(2);
if (!PAGES.length) { console.error('usage: theme-check.mjs <url>...'); process.exit(2); }

const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }

const PORT = 9300 + (Date.now() % 500);
const profile = mkdtempSync(join(tmpdir(), 'theme-check-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
const done = () => { try { chrome.kill(); } catch {} try { rmSync(profile, { recursive: true, force: true }); } catch {} };

const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws, id = 0; const pending = new Map();
const cmd = (method, params = {}) => new Promise(res => {
  const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params }));
});
const evaluate = async expr =>
  (await cmd('Runtime.evaluate', { expression: expr, returnByValue: true })).result?.result?.value;

try {
  // must attach to a PAGE target: the browser-level endpoint has no execution context, so
  // Runtime.evaluate there silently yields nothing.
  let wsUrl;
  for (let i = 0; i < 60 && !wsUrl; i++) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
      wsUrl = targets.find(t => t.type === 'page')?.webSocketDebuggerUrl;
    } catch {}
    if (!wsUrl) await sleep(250);
  }
  if (!wsUrl) throw new Error('chrome did not expose a page target');
  ws = new WebSocket(wsUrl);
  ws.addEventListener('message', e => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  });
  await new Promise(r => ws.addEventListener('open', r));
  await cmd('Page.enable'); await cmd('Runtime.enable');

  const results = [];
  for (const url of PAGES) {
    const row = { url, light: null, dark: null };
    for (const scheme of ['light', 'dark']) {
      await cmd('Emulation.setEmulatedMedia', {
        features: [{ name: 'prefers-color-scheme', value: scheme }],
      });
      await cmd('Page.navigate', { url });
      for (let i = 0; i < 80; i++) {
        if (await evaluate('document.readyState') === 'complete') break;
        await sleep(100);
      }
      await sleep(250); // let late CSS apply
      row[scheme] = await evaluate('getComputedStyle(document.body).backgroundColor');
    }
    results.push(row);
  }

  let fail = 0;
  console.log('\n  page                                        light                dark              adapts');
  console.log('  ' + '-'.repeat(92));
  for (const r of results) {
    const adapts = r.light && r.dark && r.light !== r.dark;
    if (!adapts) fail++;
    const short = r.url.replace(/^http:\/\/localhost:\d+/, '');
    console.log(`  ${short.padEnd(42)}  ${String(r.light).padEnd(20)} ${String(r.dark).padEnd(18)} ${adapts ? 'YES' : 'NO  <-- FAIL'}`);
  }
  // consistency: every page must land on the SAME light surface and the SAME dark surface
  const lights = new Set(results.map(r => r.light)), darks = new Set(results.map(r => r.dark));
  console.log('');
  console.log(`  distinct light surfaces: ${lights.size} ${[...lights].join(' ')}  ${lights.size === 1 ? 'CONSISTENT' : '<-- INCONSISTENT'}`);
  console.log(`  distinct dark  surfaces: ${darks.size} ${[...darks].join(' ')}  ${darks.size === 1 ? 'CONSISTENT' : '<-- INCONSISTENT'}`);
  if (lights.size !== 1 || darks.size !== 1) fail++;
  console.log(fail ? `\n  FAIL (${fail})` : '\n  PASS — all pages adapt and agree');
  done(); process.exit(fail ? 1 : 0);
} catch (e) {
  console.error('theme-check error:', e.message); done(); process.exit(2);
}
