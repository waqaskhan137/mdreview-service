// scripts/latex-threeway-check.mjs — #332. Rendered-outcome checks for the Source/Split/Paper
// 3-way switch and the joined compile-status pill (mock scraps/04-latex.html). Zero-dep: raw CDP
// over Node's built-in WebSocket + fetch, same shape as scripts/latex-canvas-check.mjs (#333).
//
// WHAT THIS PINS:
//   T1 three-way switch: each of the three modes shows the RIGHT pane(s) — Source alone, Paper
//      alone, Split both — measured via computed display, not the CSS class name, in BOTH themes.
//      A positive control (Split really does differ from either single-pane mode) guards against a
//      vacuous "always true" comparison.
//   T2 pill joined geometry: the status segment's right edge meets the Recompile segment's left
//      edge with ZERO gap (not merely small — a small-but-nonzero gap would mean two adjacent
//      buttons, not one joined control), the container's border-radius resolves to --r-control,
//      and the divider between them is exactly 1px of --border. All via computed style + a probe
//      element for the light-dark() token, both themes.
//   T3 rail round trip through Paper mode: body.rail-off (#280's MANUAL comments-off state) must
//      survive Source -> Paper -> Split, and must not be reported by the responsive body.norail
//      class, which layoutCards() legitimately sets to TRUE while in Paper mode (the source pane,
//      and the rail inside it, are display:none, so clientWidth is 0 — the same "pane too narrow"
//      condition the responsive floor already handles) and must clear again once Split restores
//      the pane. This is the RB3 case's exact shape, in the new place the switch introduces it.
//
// Needs: a Chrome/Chromium binary. Runs against a THROWAWAY local instance; no host, no staging.
//   export PATH=".../node/bin:$PATH"; node scripts/latex-threeway-check.mjs
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

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
const dataDir = join(ROOT, '.scratch', 'threeway_data_' + Date.now());
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

// One review with two open comments, so the rail actually has content to hide/show across T3.
const createRes = await fetch(`http://127.0.0.1:${port}/api/reviews`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ title: 'threeway', kind: 'latex',
    markdown: '\\documentclass{article}\n\\begin{document}\n\\section{Model}\nsome text\nmore text\n\\end{document}' }),
});
const rid = (await createRes.json()).id;
await fetch(`http://127.0.0.1:${port}/api/reviews/${rid}/comments`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ anchor: { quoted_text: '\\section{Model}', block_num: '3', start: null, end: null }, text: 'c1' }),
});
const url = `http://127.0.0.1:${port}/review/${rid}`;

const profile = mkdtempSync(join(tmpdir(), 'threeway-'));
const cdpPort = 9300 + (Date.now() % 500);
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
const evalJs = async expr => {
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};

await send('Page.enable'); await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1500, height: 900, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url });
let ready = false;
for (let i = 0; i < 80; i++) {
  const st = await evalJs(`document.readyState+'|'+!!document.querySelector('.ln[data-num="3"]')+'|'+!!document.querySelector('#viewswitch')`);
  if (typeof st === 'string' && st.startsWith('complete|true|true')) { ready = true; break; }
  await sleep(250);
}
ok('the latex viewer actually loaded with the switch present (probe is not vacuous)', ready);
if (!ready) { console.log('\naborting'); await cleanup(); process.exit(1); }
await sleep(500);

// ---- T1: three-way switch, both themes ---------------------------------------------------------
async function paneState() {
  // display alone is not enough: a `flex:0 0 46%` pane can stay display:flex while its sibling is
  // display:none and just... sit at 46% width with a blank gap where the sibling used to be. The
  // single-pane modes are only real if the VISIBLE pane actually fills the split container, so
  // width is asserted alongside display, not display alone.
  return JSON.parse(await evalJs(`JSON.stringify({
    src: getComputedStyle(document.querySelector('.srcpane')).display,
    pdf: getComputedStyle(document.querySelector('.pdfpane')).display,
    srcW: Math.round(document.querySelector('.srcpane').getBoundingClientRect().width),
    pdfW: Math.round(document.querySelector('.pdfpane').getBoundingClientRect().width),
    splitW: Math.round(document.querySelector('.split').getBoundingClientRect().width),
  })`));
}
for (const theme of ['light', 'dark']) {
  await evalJs(`(document.documentElement.setAttribute('data-theme',${JSON.stringify(theme)}),true)`);
  await evalJs(`(document.querySelector('#tab-split').click(),true)`);
  await sleep(150);
  const split = await paneState();
  ok(`${theme}: Split shows both panes`, split.src !== 'none' && split.pdf !== 'none', split);

  await evalJs(`(document.querySelector('#tab-src').click(),true)`);
  await sleep(150);
  const src = await paneState();
  ok(`${theme}: Source hides the paper pane AND fills the split container (not just display, WIDTH)`,
     src.src !== 'none' && src.pdf === 'none' && src.srcW >= src.splitW - 4, src);

  await evalJs(`(document.querySelector('#tab-pdf').click(),true)`);
  await sleep(150);
  const pdf = await paneState();
  ok(`${theme}: Paper hides the source pane AND fills the split container (not just display, WIDTH)`,
     pdf.pdf !== 'none' && pdf.src === 'none' && pdf.pdfW >= pdf.splitW - 4, pdf);

  // Positive control: the three states are not all the same (a vacuous "display is truthy" check
  // would pass even if the switch did nothing).
  ok(`${theme}: the three modes are genuinely distinct (not a vacuous comparison)`,
     JSON.stringify(split) !== JSON.stringify(src) && JSON.stringify(src) !== JSON.stringify(pdf), { split, src, pdf });

  await evalJs(`(document.querySelector('#tab-split').click(),true)`);
  await sleep(150);
}

// ---- T2: joined pill geometry, both themes -------------------------------------------------------
for (const theme of ['light', 'dark']) {
  const r = await evalJs(`(()=>{
    document.documentElement.setAttribute('data-theme',${JSON.stringify(theme)});
    const probe=t=>{const p=document.createElement('div');p.style.cssText='position:absolute;left:-9999px;background:var('+t+')';document.body.appendChild(p);const v=getComputedStyle(p).backgroundColor;p.remove();return v;};
    const rc=(()=>{const p=document.createElement('div');p.style.cssText='display:none;border-radius:var(--r-control)';document.body.appendChild(p);const v=getComputedStyle(p).borderRadius;p.remove();return v;})();
    const status=document.querySelector('#pdfstate'),sep=document.querySelector('.cp-sep'),rec=document.querySelector('#recompilebtn'),pill=document.querySelector('#compilepill');
    const sb=status.getBoundingClientRect(),rb=rec.getBoundingClientRect(),sepb=sep.getBoundingClientRect();
    return JSON.stringify({
      // The divider physically occupies the pixel between the two segments, so a flush join is
      // TWO zero gaps (status->divider, divider->recompile), not one — measuring status->recompile
      // directly would always read back the divider's own width and never assert flushness at all.
      gapBeforeSep: sepb.left - sb.right,
      gapAfterSep: rb.left - sepb.right,
      sepWidth: Math.round(sepb.width),
      sepColor: getComputedStyle(sep).backgroundColor,
      borderToken: probe('--border'),
      pillRadius: getComputedStyle(pill).borderRadius,
      rcToken: rc,
      recBg: getComputedStyle(rec).backgroundColor,
      accentToken: probe('--accent'),
    });
  })()`);
  const d = JSON.parse(r);
  ok(`${theme}: status segment and Recompile segment are flush around the divider (gap===0 on both sides, not merely small)`,
     d.gapBeforeSep === 0 && d.gapAfterSep === 0, d);
  ok(`${theme}: the divider is 1px of --border`, d.sepWidth === 1 && d.sepColor === d.borderToken, d);
  ok(`${theme}: pill container border-radius resolves to --r-control`, d.pillRadius === d.rcToken, d);
  ok(`${theme}: Recompile segment is accent-filled`, d.recBg === d.accentToken, d);
}

// ---- T3: rail-off survives Source -> Paper -> Split (the RB3 case, in the new place) -----------
async function railState() {
  return JSON.parse(await evalJs(`JSON.stringify({
    raild: getComputedStyle(document.querySelector('.railcol')).display,
    railOff: document.body.classList.contains('rail-off'),
    noRail: document.body.classList.contains('norail'),
    ariaPressed: document.querySelector('#cmtbtn').getAttribute('aria-pressed'),
  })`));
}
await evalJs(`(document.documentElement.setAttribute('data-theme','light'),true)`);
await evalJs(`(document.querySelector('#tab-split').click(),true)`);
await sleep(200);
let s = await railState();
ok('T3 setup: rail visible before the manual toggle', s.raild !== 'none' && !s.railOff, s);
await evalJs(`(document.querySelector('#cmtbtn').click(),true)`);
await sleep(200);
s = await railState();
ok('T3 setup: manual rail-off engaged (rail hidden, rail-off true)', s.raild === 'none' && s.railOff === true, s);

await evalJs(`(document.querySelector('#tab-src').click(),true)`);
await sleep(200);
let srcRail = await railState();
ok('T3: Source mode — rail-off still true (untouched by the view switch)', srcRail.railOff === true, srcRail);

await evalJs(`(document.querySelector('#tab-pdf').click(),true)`);
await sleep(200);
let pdfRail = await railState();
// In Paper mode the source pane (and the rail inside it) is display:none, so layoutCards() finds
// clientWidth 0 and legitimately sets the RESPONSIVE norail — that is not the bug #280/D2 guards
// against. What must NOT happen is rail-off getting cleared, or #cmtbtn losing track of it.
ok('T3: Paper mode — rail-off is NOT cleared by the switch (the D2 conflation this ticket must avoid)',
   pdfRail.railOff === true, pdfRail);
ok('T3: Paper mode — the responsive norail is a SEPARATE, legitimate reason the rail is hidden here (zero-width pane)',
   pdfRail.noRail === true, pdfRail);

await evalJs(`(document.querySelector('#tab-split').click(),true)`);
await sleep(200);
let splitRail = await railState();
ok('T3: back to Split — the MANUAL rail-off state is restored (rail stays hidden)',
   splitRail.raild === 'none' && splitRail.railOff === true, splitRail);
ok('T3: back to Split — the RESPONSIVE norail clears now that the pane has real width again',
   splitRail.noRail === false, splitRail);
ok('T3: #cmtbtn governs the rail again (aria-pressed=false, rail off)', splitRail.ariaPressed === 'false', splitRail);

// Undo the manual toggle and confirm the rail comes back cleanly (sanity, not a new case).
await evalJs(`(document.querySelector('#cmtbtn').click(),true)`);
await sleep(200);
const restored = await railState();
ok('sanity: a second click restores the rail (railOff false, rail visible)',
   restored.railOff === false && restored.raild !== 'none', restored);

// ---- T4: timeAgo() honest-fallback logic, exercised in the live page (not reimplemented here) --
const t4 = JSON.parse(await evalJs(`JSON.stringify({
  justNow: timeAgo(Date.now()/1000 - 5),
  twoMin: timeAgo(Date.now()/1000 - 125),
  twoHour: timeAgo(Date.now()/1000 - 7500),
  twoDay: timeAgo(Date.now()/1000 - 179000),
  nullTs: timeAgo(null),
  zeroTs: timeAgo(0),
})`));
ok('T4: timeAgo(~5s ago) reads "just now"', t4.justNow === 'just now', t4);
ok('T4: timeAgo(~125s ago) reads "2m ago"', t4.twoMin === '2m ago', t4);
ok('T4: timeAgo(~2h5m ago) reads "2h ago"', t4.twoHour === '2h ago', t4);
ok('T4: timeAgo(~2d ago) reads "2d ago"', t4.twoDay === '2d ago', t4);
ok('T4: timeAgo(null) is null, not "NaNm ago" (the honest-fallback contract)', t4.nullTs === null, t4);
ok('T4: timeAgo(0) is ALSO null (falsy timestamp, same as absent)', t4.zeroTs === null, t4);

// ---- T5: topbar does not overflow at narrow widths --------------------------------------------
// The switch and pill are two substantial new elements in a fixed-height, single-row topbar whose
// filename already truncates via ellipsis. Mutation-testing flex-shrink:0 on them clipped the
// ENTIRE "<- Reviews | filename | LATEX" group off-canvas at 600px (body{overflow:hidden} makes
// this a SILENT clip, not a scrollbar) — a break tests/latex_reskin_selfcheck.sh's RB4 would never
// catch, since it only asserts pane display at 800px, never topbar geometry. 800px is asserted
// because it is the exact width RB4/RB5 already load; the narrower widths are this ticket's own
// regression, caught here since nothing else in the suite would.
for (const w of [800, 640, 560]) {
  await evalJs(`(document.querySelector('#tab-split').click(),true)`);
  const r = await send('Emulation.setDeviceMetricsOverride', { width: w, height: 900, deviceScaleFactor: 1, mobile: false });
  await sleep(250);
  const d = JSON.parse(await evalJs(`JSON.stringify({
    overflowX: document.body.scrollWidth > window.innerWidth,
    homeRect: document.querySelector('.home').getBoundingClientRect(),
    pillRight: document.querySelector('#compilepill').getBoundingClientRect().right,
    innerWidth: window.innerWidth,
  })`));
  ok(`${w}px: no horizontal overflow (topbar content clipped off-canvas)`, d.overflowX === false, d);
  ok(`${w}px: "Reviews" link stays on-screen (not crushed by the new pill/switch, the mutation this caught)`,
     d.homeRect.width > 0 && d.homeRect.left >= 0, d);
  ok(`${w}px: the compile pill's right edge stays within the viewport`, d.pillRight <= d.innerWidth, d);
}
await send('Emulation.setDeviceMetricsOverride', { width: 1500, height: 900, deviceScaleFactor: 1, mobile: false });

console.log(failed ? `\n${failed} case(s) failed` : '\nall #332 three-way/pill cases pass');
await cleanup();
process.exit(failed ? 1 : 0);
