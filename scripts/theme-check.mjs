// theme-check.mjs — the theme contract, asserted as RENDERED OUTCOMES in headless Chrome.
//
// #153 shipped this as an OS-driven check (does every page adapt to prefers-color-scheme and
// agree on one surface). #285 extended it to the full toggle matrix: 3 states (explicit light /
// explicit dark / auto) x 5 pages x both emulated OS schemes, reached by REAL clicks on the
// toggle, plus persistence, pre-paint, live-OS-flip, consumer (Mermaid / keysheet / hljs),
// no-rival-machinery and reduced-motion checks. Zero-dep: Node's built-in WebSocket + fetch
// driving CDP; schemes arrive via Emulation.setEmulatedMedia.
//
// Every assertion samples what the browser COMPUTED (body background, a probe element resolving
// a token, an SVG fill), never CSS text (#265's lesson). One deliberate exception to "computed
// --bg": getComputedStyle(:root).getPropertyValue('--bg') returns the RAW `light-dark(...)`
// string — custom properties resolve at the point of USE — so tokens are resolved through a
// probe element (`color: var(--tok)`), which is the value every consumer actually receives.
//
// Full matrix (all four flags required — the matrix is five pages by contract, #285 AC 1;
// tests/theme_toggle_selfcheck.sh starts the instances and wires the fixtures):
//   node scripts/theme-check.mjs --base http://127.0.0.1:PORT --review RID --latex RID \
//                                --admin http://127.0.0.1:PORT2
// --base serves /, /account and /review/{RID}; --admin is a HOSTED instance's origin (the admin
// console only exists on the hosted plane; its shell is served unauthenticated).
//
// Legacy mode (#153's original contract, kept because dashboard_reskin_selfcheck.sh calls it):
//   node scripts/theme-check.mjs <url>...
// asserts each URL adapts to the emulated OS scheme with the CONTRACT surfaces in its default
// (auto) state — no toggle interaction.
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const arg = (name) => {
  const i = process.argv.indexOf('--' + name);
  return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : null;
};
const BASE = arg('base'), REVIEW = arg('review'), LATEX = arg('latex'), ADMIN = arg('admin');
const LEGACY_URLS = process.argv.slice(2).filter(a => /^https?:\/\//.test(a));
const LEGACY = !BASE && LEGACY_URLS.length > 0;
if (!LEGACY && (!BASE || !REVIEW || !LATEX || !ADMIN)) {
  console.error('usage: theme-check.mjs --base URL --review RID --latex RID --admin URL\n' +
    '   or (legacy, auto-state only): theme-check.mjs <url>...');
  process.exit(2);
}
const PAGES = LEGACY ? {} : {
  dashboard: BASE + '/',
  account: BASE + '/account',
  viewer: BASE + '/review/' + REVIEW,
  latex: BASE + '/review/' + LATEX,
  admin: ADMIN + '/admin',
};

// The contract's --bg per theme (rev 3 / #277: light #FCFBF9, dark #14130F), as Chrome computes
// them. Only --bg is pinned by value here; the full-table guard is the AC-7 identity check below,
// which needs no value table at all.
const BG = { light: 'rgb(252, 251, 249)', dark: 'rgb(20, 19, 15)' };
// AC 5 consumer expectations, from the same contract table:
// keysheet card = --surface-raised / --text, kbd = --code-bg / --text; hljs keyword pair from
// hljs-github.css (github light/dark).
const TOK = {
  cardBg: { light: 'rgb(255, 255, 255)', dark: 'rgb(38, 35, 29)' },
  text: { light: 'rgb(31, 29, 26)', dark: 'rgb(232, 228, 220)' },
  kbdBg: { light: 'rgb(244, 242, 238)', dark: 'rgb(36, 33, 28)' },
  hlKeyword: { light: 'rgb(215, 58, 73)', dark: 'rgb(255, 123, 114)' },
};

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
setTimeout(() => { console.error('theme-check: overall timeout (240s)'); done(); process.exit(2); }, 240000).unref();

const sleep = ms => new Promise(r => setTimeout(r, ms));
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

let failed = 0;
const check = (name, cond, why) => {
  console.log((cond ? 'ok   - ' : 'FAIL - ') + name + (!cond && why ? '  <- ' + why : ''));
  if (!cond) failed++;
};

const media = (scheme, motion) => cmd('Emulation.setEmulatedMedia', {
  features: [{ name: 'prefers-color-scheme', value: scheme }]
    .concat(motion ? [{ name: 'prefers-reduced-motion', value: motion }] : []),
});
async function nav(url, extraSel) {
  await cmd('Page.navigate', { url });
  for (let i = 0; i < 100; i++) {
    if (await evaluate('document.readyState') === 'complete') break;
    await sleep(100);
  }
  for (const sel of ['#themetoggle'].concat(extraSel ? [extraSel] : [])) {
    let found = false;
    for (let i = 0; i < 100; i++) {
      if (await evaluate(`document.querySelector(${JSON.stringify(sel)})!==null`)) { found = true; break; }
      await sleep(150);
    }
    if (!found) throw new Error('never appeared on ' + url + ': ' + sel);
  }
}
// Reset to a clean auto WITHOUT going through the code under test (a reset via the toggle's own
// API would mask a gutted implementation).
const reset = () => evaluate(
  `localStorage.clear(); document.documentElement.removeAttribute('data-theme'); true`);
const bg = () => evaluate(`getComputedStyle(document.body).backgroundColor`);
// Resolve a token the way consumers receive it (see the header note on light-dark()).
const tokRes = tok => evaluate(`(()=>{const p=document.createElement('div');` +
  `p.style.color='var(${tok})';document.body.appendChild(p);` +
  `const v=getComputedStyle(p).color;p.remove();return v;})()`);
const clickToggle = () => evaluate(`document.getElementById('themetoggle').click(); true`);
const aria = () => evaluate(`document.getElementById('themetoggle').getAttribute('aria-label')`);
const attr = () => evaluate(`document.documentElement.getAttribute('data-theme')`);

try {
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

  /* ---- Legacy mode: default (auto) state adapts to the OS, contract surfaces ------------- */
  if (LEGACY) {
    for (const url of LEGACY_URLS) {
      for (const scheme of ['light', 'dark']) {
        await media(scheme);
        await cmd('Page.navigate', { url });
        for (let i = 0; i < 100; i++) {
          if (await evaluate('document.readyState') === 'complete') break;
          await sleep(100);
        }
        await sleep(250);
        const b = await bg();
        check(`auto under OS ${scheme}: ${url}`, b === BG[scheme], `body bg=${b} want ${BG[scheme]}`);
      }
    }
    console.log(failed ? `\n  FAIL (${failed})` : '\n  PASS — all pages adapt with the contract surfaces');
    done(); process.exit(failed ? 1 : 0);
  }

  /* ---- AC 1: click cycle, per page, both OS schemes -------------------------------------- */
  for (const [page, url] of Object.entries(PAGES)) {
    for (const os of ['light', 'dark']) {
      await media(os);
      await nav(url);
      await reset();
      const steps = [];
      const expectSeq = [['light', 'Theme: light'], ['dark', 'Theme: dark'], [os, 'Theme: system']];
      const startBg = await bg();
      if (startBg !== BG[os]) steps.push(`start(auto) bg=${startBg} want ${BG[os]}`);
      for (const [want, wantAria] of expectSeq) {
        await clickToggle();
        const b = await bg(), t = await tokRes('--bg'), a = await aria();
        if (b !== BG[want]) steps.push(`after click: body bg=${b} want ${BG[want]}`);
        if (t !== BG[want]) steps.push(`after click: var(--bg) resolves ${t} want ${BG[want]}`);
        if (a !== wantAria) steps.push(`after click: aria-label='${a}' want '${wantAria}'`);
      }
      if (await attr() !== null) steps.push(`after full cycle data-theme='${await attr()}', auto must be attribute-ABSENT`);
      check(`AC1 cycle light->dark->auto [${page}, OS ${os}]`, steps.length === 0, steps.join(' | '));
    }
  }

  /* ---- AC 4: auto is live, override is deaf, per page ------------------------------------ */
  for (const [page, url] of Object.entries(PAGES)) {
    await media('light');
    await nav(url);
    await reset();
    const s = [];
    if (await bg() !== BG.light) s.push(`auto under OS light: bg=${await bg()}`);
    await media('dark');                      // NO reload
    if (await bg() !== BG.dark) s.push(`auto did not follow a live OS flip to dark: bg=${await bg()}`);
    await media('light');
    if (await bg() !== BG.light) s.push(`auto did not follow the flip back: bg=${await bg()}`);
    check(`AC4 auto follows a live OS flip, no reload [${page}]`, s.length === 0, s.join(' | '));

    await clickToggle(); await clickToggle(); // auto -> light -> dark: explicit dark
    const d = [];
    for (const os of ['dark', 'light', 'dark']) {
      await media(os);
      if (await bg() !== BG.dark) d.push(`explicit dark moved on OS flip to ${os}: bg=${await bg()}`);
    }
    check(`AC4 explicit dark is deaf to OS flips [${page}]`, d.length === 0, d.join(' | '));
    await reset();
  }

  /* ---- AC 7 (behavioural): explicit dark === auto-under-OS-dark, every token ------------- */
  // Token names come from theme.css's own :root rule via CSSOM, so the check needs no value
  // table and cannot drift from the shipped contract. Each token's signature is its raw computed
  // text plus its resolution through a colour probe AND a shadow probe (colour tokens differ in
  // the first, shadow tokens in the second, non-colour tokens are identical in all three).
  const tokenSig = () => evaluate(`(()=>{
    const names=[...document.styleSheets].filter(s=>(s.href||'').includes('theme.css'))
      .flatMap(s=>{try{return [...s.cssRules]}catch(e){return []}})
      .filter(r=>r.selectorText===':root').flatMap(r=>[...r.style].filter(n=>n.startsWith('--')));
    const p=document.createElement('div');document.body.appendChild(p);
    const sig={};
    for(const n of [...new Set(names)]){
      const cs=getComputedStyle(document.documentElement).getPropertyValue(n).trim();
      p.style.color='';p.style.boxShadow='';p.style.color='var('+n+')';p.style.boxShadow='var('+n+')';
      const g=getComputedStyle(p);
      sig[n]=cs+'||'+g.color+'||'+g.boxShadow;
    }
    p.remove();
    sig['<body font-weight>']=getComputedStyle(document.body).fontWeight;
    return sig;})()`);
  for (const [page, url] of Object.entries(PAGES)) {
    await media('light');
    await nav(url);
    await reset();
    await clickToggle(); await clickToggle();   // explicit dark under OS light
    const sigExplicit = await tokenSig();
    await reset();
    await media('dark');                        // auto under OS dark
    const sigAuto = await tokenSig();
    const names = Object.keys(sigExplicit);
    const diff = names.filter(n => sigExplicit[n] !== sigAuto[n])
      .map(n => `${n}: explicit '${sigExplicit[n]}' vs auto '${sigAuto[n]}'`);
    check(`AC7 explicit dark and auto-OS-dark resolve identically, ${names.length} tokens [${page}]`,
      names.length > 20 && diff.length === 0,
      names.length <= 20 ? `only ${names.length} tokens enumerated — CSSOM parse broke` : diff.slice(0, 4).join(' | '));
    check(`AC7 dark body weight is 350 via both arrivals [${page}]`,
      sigExplicit['<body font-weight>'] === '350' && sigAuto['<body font-weight>'] === '350',
      `explicit=${sigExplicit['<body font-weight>']} auto=${sigAuto['<body font-weight>']}`);
    await media('light');
    check(`AC7 light body weight stays 400 [${page}]`,
      await evaluate(`getComputedStyle(document.body).fontWeight`) === '400',
      'auto under OS light should not carry the dark weight');
  }

  /* ---- AC 2: persistence (dashboard) ----------------------------------------------------- */
  {
    await media('light');
    await nav(PAGES.dashboard);
    await reset();
    await clickToggle(); await clickToggle();   // -> explicit dark, stored
    const s = [];
    const stored = await evaluate(`localStorage.getItem('mdr.theme')`);
    if (stored !== 'dark') s.push(`after choosing dark, mdr.theme='${stored}'`);
    await nav(PAGES.dashboard);                 // reload
    if (await bg() !== BG.dark) s.push(`reload with stored dark under OS light rendered bg=${await bg()}`);
    if (await evaluate(`localStorage.getItem('mdr.theme')`) !== 'dark') s.push('the key did not survive the reload');
    await clickToggle();                        // dark -> auto
    if (await evaluate(`localStorage.getItem('mdr.theme')`) !== null) s.push('choosing auto must REMOVE the key');
    if (await bg() !== BG.light) s.push(`auto after reload follows OS light, got bg=${await bg()}`);
    check('AC2 explicit choice persists across reload; auto removes the key [dashboard]',
      s.length === 0, s.join(' | '));

    await evaluate(`localStorage.setItem('mdr.theme','purple'); true`);
    await nav(PAGES.dashboard);
    const g = [];
    if (await bg() !== BG.light) g.push(`garbage value rendered bg=${await bg()}, must behave as auto (light)`);
    if (await attr() !== null) g.push(`garbage value set data-theme='${await attr()}'`);
    await clickToggle();                        // garbage==auto, so first click -> light
    if (await attr() !== 'light') g.push(`toggle did not cycle from garbage state (data-theme='${await attr()}')`);
    if (await evaluate(`localStorage.getItem('mdr.theme')`) !== 'light') g.push('click after garbage did not store light');
    check('AC2 a garbage mdr.theme behaves as auto and the toggle still cycles [dashboard]',
      g.length === 0, g.join(' | '));
    await reset();
  }

  /* ---- AC 3: no flash — sampled at the FIRST requestAnimationFrame ----------------------- */
  // The hook is installed via Page.addScriptToEvaluateOnNewDocument, which runs BEFORE any page
  // script. A DOMContentLoaded sample would pass with a deferred applier that still flashes;
  // the first rAF is the first produced frame, so a light frame cannot hide from it.
  {
    await media('light');
    await nav(PAGES.dashboard);
    await evaluate(`localStorage.setItem('mdr.theme','dark'); true`);
    const hook = await cmd('Page.addScriptToEvaluateOnNewDocument', { source: `
      window.__mdrFirstFrame = new Promise(function (res) {
        requestAnimationFrame(function () {
          var p = document.createElement('div'); p.style.color = 'var(--bg)';
          (document.body || document.documentElement).appendChild(p);
          var v = getComputedStyle(p).color; p.remove();
          res({ bg: v, attr: document.documentElement.getAttribute('data-theme') });
        });
      });` });
    await cmd('Page.navigate', { url: PAGES.dashboard });
    const first = await evaluate(`window.__mdrFirstFrame`);
    check('AC3 stored dark renders dark in the FIRST frame under OS light [dashboard]',
      first && first.bg === BG.dark && first.attr === 'dark',
      `first-rAF sample: bg=${first && first.bg} data-theme=${first && first.attr} (want ${BG.dark} / dark)`);
    await cmd('Page.removeScriptToEvaluateOnNewDocument', { identifier: hook.result?.identifier });
    for (let i = 0; i < 100; i++) { if (await evaluate('document.readyState') === 'complete') break; await sleep(100); }
    await reset();
  }

  /* ---- AC 5a: Mermaid follows the effective theme, including without a reload ------------ */
  {
    const sample = () => evaluate(`(()=>{const r=document.querySelector('#article .mermaid svg rect');` +
      `return r?getComputedStyle(r).fill:null;})()`);
    const waitSvg = async () => {
      for (let i = 0; i < 100; i++) {
        if (await evaluate(`document.querySelector('#article .mermaid svg rect')!==null`)) return true;
        await sleep(200);
      }
      return false;
    };
    await media('light');
    await nav(PAGES.viewer);
    await reset();
    await nav(PAGES.viewer);                    // deterministic boot in auto/light
    check('AC5a the fixture renders a Mermaid SVG [viewer]', await waitSvg(), 'no #article .mermaid svg rect');
    const fillLight = await sample();
    await clickToggle(); await clickToggle();   // -> explicit dark, no reload
    let fillDarkLive = null;
    for (let i = 0; i < 40; i++) {              // retheme re-renders asynchronously
      fillDarkLive = await sample();
      if (fillDarkLive && fillDarkLive !== fillLight) break;
      await sleep(250);
    }
    check('AC5a a toggle click rethemes the diagram WITHOUT a reload [viewer]',
      !!fillLight && !!fillDarkLive && fillDarkLive !== fillLight,
      `fill stayed '${fillLight}' after switching to explicit dark`);
    await nav(PAGES.viewer);                    // stored dark, OS light: dark arrival by reload
    await waitSvg();
    const fillDarkReload = await sample();
    await reset(); await media('dark');
    await nav(PAGES.viewer);                    // auto under OS dark: the OTHER dark arrival
    await waitSvg();
    const fillDarkAuto = await sample();
    check('AC5a explicit dark (OS light) matches auto dark (OS dark) [viewer]',
      !!fillDarkReload && fillDarkReload === fillDarkAuto && fillDarkReload !== fillLight,
      `reload-dark='${fillDarkReload}' auto-dark='${fillDarkAuto}' light='${fillLight}'`);
    await evaluate(`localStorage.setItem('mdr.theme','light'); true`);
    await nav(PAGES.viewer);                    // explicit light under OS dark: the mirror case
    await waitSvg();
    check('AC5a explicit light under OS dark renders the light diagram [viewer]',
      await sample() === fillLight, `fill='${await sample()}' want the light fill '${fillLight}'`);
    await reset();
  }

  /* ---- AC 5b: the keysheet, both properties, both mirror states -------------------------- */
  /* ---- AC 5c: hljs token colour, same states --------------------------------------------- */
  for (const [state, os, eff] of [['explicit dark under OS light', 'light', 'dark'],
                                  ['explicit light under OS dark', 'dark', 'light']]) {
    await media(os);
    await nav(PAGES.viewer);
    await evaluate(`localStorage.setItem('mdr.theme',${JSON.stringify(eff)}); true`);
    await nav(PAGES.viewer);
    await evaluate(`window.mdKeys.openSheet(); true`);
    const got = await evaluate(`(()=>{const c=document.querySelector('#keysheet .keysheet-card');` +
      `const k=document.querySelector('#keysheet kbd');if(!c||!k)return null;` +
      `const cc=getComputedStyle(c),kk=getComputedStyle(k);` +
      `return {cardBg:cc.backgroundColor,cardFg:cc.color,kbdBg:kk.backgroundColor,kbdFg:kk.color};})()`);
    const s = [];
    if (!got) s.push('keysheet did not open (window.mdKeys.openSheet)');
    else {
      if (got.cardBg !== TOK.cardBg[eff]) s.push(`card bg=${got.cardBg} want ${TOK.cardBg[eff]}`);
      if (got.cardFg !== TOK.text[eff]) s.push(`card colour=${got.cardFg} want ${TOK.text[eff]}`);
      if (got.kbdBg !== TOK.kbdBg[eff]) s.push(`kbd bg=${got.kbdBg} want ${TOK.kbdBg[eff]}`);
      if (got.kbdFg !== TOK.text[eff]) s.push(`kbd colour=${got.kbdFg} want ${TOK.text[eff]} (the unreadable-keycap regression)`);
    }
    check(`AC5b keysheet card+kbd match the effective theme [viewer, ${state}]`, s.length === 0, s.join(' | '));
    await evaluate(`window.mdKeys.closeSheet(); true`);

    let hl = null;
    for (let i = 0; i < 50; i++) {
      hl = await evaluate(`(()=>{const el=document.querySelector('#article .hljs-keyword');` +
        `return el?getComputedStyle(el).color:null;})()`);
      if (hl) break;
      await sleep(200);
    }
    check(`AC5c hljs keyword colour matches the effective theme [viewer, ${state}]`,
      hl === TOK.hlKeyword[eff], `computed ${hl}, want ${TOK.hlKeyword[eff]}`);
  }
  await nav(PAGES.viewer); await reset();

  /* ---- AC 6: no rival machinery (Basecoat pages) ----------------------------------------- */
  for (const page of ['dashboard', 'account', 'admin']) {
    await media('light');
    await nav(PAGES[page]);
    await reset();
    const s = [];
    for (let i = 1; i <= 3; i++) {
      await clickToggle();
      if (await evaluate(`document.documentElement.classList.contains('dark')`))
        s.push(`click ${i}: a .dark class appeared on <html> (basecoat.theme is running)`);
      if (await evaluate(`localStorage.getItem('themeMode')`) !== null)
        s.push(`click ${i}: a themeMode key appeared (basecoat.theme is writing storage)`);
    }
    check(`AC6 no .dark class, no themeMode key across a full cycle [${page}]`, s.length === 0, s.join(' | '));
    await reset();
  }

  /* ---- AC 8: reduced motion reaches the toggle ------------------------------------------- */
  {
    await media('light');
    await nav(PAGES.dashboard);
    const normal = await evaluate(`getComputedStyle(document.getElementById('themetoggle')).transitionDuration`);
    check('AC8 the toggle ships no transition of its own [dashboard]', normal === '0s',
      `transition-duration=${normal} — a transition here owes its own reduced-motion story`);
    await media('light', 'reduce');
    const reduced = await evaluate(`getComputedStyle(document.getElementById('themetoggle')).transitionDuration`);
    const ms = /^([\d.e-]+)s$/.test(reduced) ? parseFloat(reduced) * 1000 : parseFloat(reduced);
    check('AC8 under prefers-reduced-motion the global guard reaches the toggle [dashboard]',
      !Number.isNaN(ms) && ms <= 0.01 + 1e-9,
      `computed transition-duration=${reduced}, the #262 guard pins 0.01ms`);
    await media('light');
  }

  console.log(failed ? `\n  FAIL (${failed})` : '\n  PASS — full 3-state x 5-page matrix');
  done(); process.exit(failed ? 1 : 0);
} catch (e) {
  console.error('theme-check error:', e.message); done(); process.exit(2);
}
