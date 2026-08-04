// palette-restyle-check.mjs — #283. Samples RENDERED OUTCOMES (computed style, measured
// geometry, DOM state) for the ⌘K palette restyle, in a real headless Chrome, in BOTH themes.
// Same zero-dep shape as scripts/theme-check.mjs / scripts/latex-canvas-check.mjs: Node's
// built-in WebSocket + fetch driving CDP directly (no cdp-shot.mjs — this needs
// Emulation.setEmulatedMedia for reduced-motion and a multi-round-trip keyboard-nav probe that
// cdp-shot's flat --step list can't express in one shot).
//
// WHY NOT A CSS-TEXT CHECK: tests/keys_selfcheck.js already lost two days once to a text-regex
// standing in for rendered geometry (the #265 note in dashboard.html). Every assertion here reads
// getComputedStyle / getBoundingClientRect / DOM structure on the page as Chrome actually painted
// it, never a string match on the CSS source.
//
// FIXTURE CONTRACT (created by tests/palette_restyle_selfcheck.sh before this runs — kept in sync
// by name, not re-derived here): 8 reviews across 5 projects, with project "auth-service" holding
// exactly 4 of them. That is simultaneously: >=2 reviews across >=1 project (AC3's group-header
// gate), a project whose hint must read exactly "4 reviews" (AC5), and — maxed against cmdBuild's
// slice(0,8)/slice(0,5) caps — the largest DOM the palette can ever render, which is what AC6's
// scroll assertion needs to force real overflow.
//
//   node scripts/palette-restyle-check.mjs <dashboard-url>     # exit 0 = pass
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const URL = process.argv[2];
if (!URL) { console.error('usage: node scripts/palette-restyle-check.mjs <dashboard-url>'); process.exit(2); }
const HERE = dirname(dirname(fileURLToPath(import.meta.url))); // repo root (scripts/..)

const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }

let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c && !d ? '' : d ? `  (${d})` : '')); if (!c) failed++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

const PORT = 9400 + (Date.now() % 500);
const profile = mkdtempSync(join(tmpdir(), 'palette-restyle-'));
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
const resize = (w, h) => cmd('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: false });

// Resolve a light-dark() token the way a real consumer receives it: getPropertyValue on :root
// returns the raw `light-dark(...)` TEXT, not a colour, so every colour comparison goes through a
// probe element (the #285 lesson, same helper shape as theme-check.mjs's tokRes).
const bgOf = tok => evaluate(`(()=>{const p=document.createElement('div');
  p.style.cssText='position:absolute;left:-9999px;background:var(${tok})';
  document.body.appendChild(p);const v=getComputedStyle(p).backgroundColor;p.remove();return v;})()`);
const colorOf = tok => evaluate(`(()=>{const p=document.createElement('div');
  p.style.cssText='position:absolute;left:-9999px;color:var(${tok})';
  document.body.appendChild(p);const v=getComputedStyle(p).color;p.remove();return v;})()`);
const borderColorOf = tok => evaluate(`(()=>{const p=document.createElement('div');
  p.style.cssText='position:absolute;left:-9999px;border:1px solid var(${tok})';
  document.body.appendChild(p);const v=getComputedStyle(p).borderColor;p.remove();return v;})()`);
// Plain (non-colour) length tokens resolve fine straight off :root — only light-dark() colours
// need the probe trick.
const rawTok = tok => evaluate(`getComputedStyle(document.documentElement).getPropertyValue(${JSON.stringify(tok)}).trim()`);

async function main() {
  let target;
  for (let i = 0; i < 60 && !target; i++) {
    try {
      const tabs = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      // /json/list also returns Chrome EXTENSION background pages — filter to a real page.
      target = (tabs || []).find(t => t.type === 'page' && !String(t.url).startsWith('chrome-extension://'));
    } catch {}
    await sleep(250);
  }
  if (!target) { console.error('no page target found'); process.exit(2); }
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r, { once: true }));
  ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });

  await cmd('Page.enable'); await cmd('Runtime.enable');
  await cmd('Page.navigate', { url: URL });
  // Poll for real readiness — a fixed sleep after Page.navigate can sample about:blank.
  let ready = false;
  for (let i = 0; i < 80; i++) {
    const st = await evaluate(`document.readyState + '|' + (typeof allReviews!=='undefined' ? allReviews.length : -1)`);
    if (typeof st === 'string' && st.startsWith('complete|')) {
      const n = Number(st.split('|')[1]);
      if (n >= 8) { ready = true; break; }
    }
    await sleep(250);
  }
  // Positive control #1: the probe is not vacuous. If the fixture never loaded, every assertion
  // below would read against an empty palette and could pass for the wrong reason.
  ok('the dashboard loaded with the 8-review fixture (probe is not vacuous)', ready,
     await evaluate(`document.readyState + ' allReviews=' + (typeof allReviews!=='undefined' ? allReviews.length : 'undefined')`));
  if (!ready) { console.log('\naborting: nothing to sample'); cleanup(); process.exit(1); }

  await resize(1280, 900);
  const panelBgByTheme = {};

  for (const theme of ['light', 'dark']) {
    await evaluate(`document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)})`);
    await evaluate(`cmdOpen(); true`);
    // Basecoat animates scale 0.95 -> 1 over 100ms (the #265 mid-transition trap, recorded in
    // dashboard.html); wait it out before measuring geometry.
    await sleep(400);

    // ---- AC1: panel face -------------------------------------------------------------------
    const bgWant = await bgOf('--bg');
    const panel = await evaluate(`(()=>{const p=document.querySelector('#cmdk .command');const cs=getComputedStyle(p);
      return JSON.stringify({bg:cs.backgroundColor,pt:cs.paddingTop,pr:cs.paddingRight,pb:cs.paddingBottom,pl:cs.paddingLeft,
        w:p.getBoundingClientRect().width});})()`).then(JSON.parse);
    panelBgByTheme[theme] = panel.bg;
    ok(`${theme}: panel background resolves --bg`, panel.bg === bgWant, `panel=${panel.bg} want=${bgWant}`);
    ok(`${theme}: panel padding is 0 on all sides`,
      panel.pt === '0px' && panel.pr === '0px' && panel.pb === '0px' && panel.pl === '0px',
      `pt=${panel.pt} pr=${panel.pr} pb=${panel.pb} pl=${panel.pl}`);

    // ---- AC2: header ------------------------------------------------------------------------
    const subtleWant = await colorOf('--text-subtle');
    const accentWant = await colorOf('--accent');
    const borderFaintWant = await borderColorOf('--border-faint');
    const tCard = await rawTok('--t-card');
    const header = await evaluate(`(()=>{const h=document.querySelector('#cmdk .command>header');
      const icon=document.querySelector('#cmdicon'); const q=document.querySelector('#cmdq');
      const p=document.querySelector('#cmdk .command');
      return JSON.stringify({iconColor:getComputedStyle(icon).color, iconHidden:icon.getAttribute('aria-hidden'),
        qFontSize:getComputedStyle(q).fontSize, qCaret:getComputedStyle(q).caretColor,
        headerBg:getComputedStyle(h).backgroundColor, headerBottomColor:getComputedStyle(h).borderBottomColor,
        headerW:h.getBoundingClientRect().width, panelW:p.getBoundingClientRect().width});})()`).then(JSON.parse);
    ok(`${theme}: magnifier icon is aria-hidden and coloured --text-subtle`,
      header.iconHidden === 'true' && header.iconColor === subtleWant, JSON.stringify(header));
    ok(`${theme}: #cmdq font-size resolves --t-card`, header.qFontSize === tCard, `got=${header.qFontSize} want=${tCard}`);
    ok(`${theme}: #cmdq caret-color resolves --accent`, header.qCaret === accentWant, `got=${header.qCaret} want=${accentWant}`);
    ok(`${theme}: header face is transparent (or equals the panel's)`,
      header.headerBg === 'rgba(0, 0, 0, 0)' || header.headerBg === panel.bg, header.headerBg);
    ok(`${theme}: header spans the panel's full width (edge-to-edge rule)`,
      Math.abs(header.headerW - header.panelW) <= 1, `header=${header.headerW} panel=${header.panelW}`);
    ok(`${theme}: header bottom rule resolves --border-faint`,
      header.headerBottomColor === borderFaintWant, `got=${header.headerBottomColor} want=${borderFaintWant}`);

    // ---- AC3: groups --------------------------------------------------------------------------
    const tEyebrow = await rawTok('--t-eyebrow');
    const groups = await evaluate(`(()=>{const gs=[...document.querySelectorAll('.cmdgroup')];
      return JSON.stringify(gs.map(g=>{const cs=getComputedStyle(g);
        return {text:g.textContent, role:g.getAttribute('role'), tabindex:g.getAttribute('tabindex'),
          font:cs.fontFamily, size:cs.fontSize, ls:cs.letterSpacing, tt:cs.textTransform, color:cs.color};}));})()`).then(JSON.parse);
    ok(`${theme}: exactly two group headers, "Reviews" then "Projects"`,
      groups.length === 2 && groups[0].text === 'Reviews' && groups[1].text === 'Projects', JSON.stringify(groups.map(g=>g.text)));
    for (const g of groups) {
      ok(`${theme}: group "${g.text}" carries no role and no tabindex (not a menuitem, not focusable)`,
        g.role === null && g.tabindex === null, JSON.stringify(g));
      ok(`${theme}: group "${g.text}" is Geist Mono, uppercase, --t-eyebrow, --text-subtle`,
        g.font.includes('Geist Mono') && g.tt === 'uppercase' && g.size === tEyebrow && g.color === subtleWant,
        JSON.stringify(g));
    }

    // Reviews-before-projects in DOM order, and ArrowDown from the LAST review lands on the
    // FIRST project — derived from the DOM (group-header adjacency), not a hardcoded index, so it
    // stays correct however many fixture rows exist.
    const order = await evaluate(`(()=>{
      const kids=[...document.querySelector('#cmdlist').children];
      const ri=kids.findIndex(k=>k.className==='cmdgroup'&&k.textContent==='Reviews');
      const pi=kids.findIndex(k=>k.className==='cmdgroup'&&k.textContent==='Projects');
      return JSON.stringify({ri,pi});})()`).then(JSON.parse);
    ok(`${theme}: Reviews group precedes Projects group in DOM order`, order.ri >= 0 && order.pi > order.ri, JSON.stringify(order));

    const nav = await evaluate(`(()=>{
      const q=document.querySelector('#cmdq');
      const fire=()=>q.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));
      const pg=[...document.querySelectorAll('.cmdgroup')].find(g=>g.textContent==='Projects');
      const lastReview=pg && pg.previousElementSibling, firstProject=pg && pg.nextElementSibling;
      if(!lastReview||!firstProject||!lastReview.classList.contains('cmdrow')||!firstProject.classList.contains('cmdrow'))
        return JSON.stringify({error:'fixture missing a clean group boundary'});
      const target=Number(lastReview.dataset.i);
      for(let i=0;i<target;i++) fire();
      const atLastReview=lastReview.getAttribute('aria-selected');
      fire();
      const atFirstProject=firstProject.getAttribute('aria-selected');
      const stillOnLastReview=lastReview.getAttribute('aria-selected');
      return JSON.stringify({atLastReview,atFirstProject,stillOnLastReview});})()`).then(JSON.parse);
    ok(`${theme}: ArrowDown reaches the last review row (headers skipped by construction)`,
      nav.atLastReview === 'true', JSON.stringify(nav));
    ok(`${theme}: one more ArrowDown selects the first project row, not the header`,
      nav.atFirstProject === 'true' && nav.stillOnLastReview === 'false', JSON.stringify(nav));

    // ---- AC4: rows ----------------------------------------------------------------------------
    const rControl = await rawTok('--r-control');
    const tBody = await rawTok('--t-body');
    const rowStatic = await evaluate(`(()=>{const r=document.querySelector('.cmdrow[aria-selected="false"]');
      const cs=getComputedStyle(r);
      return JSON.stringify({radius:cs.borderRadius, size:cs.fontSize,
        pt:cs.paddingTop, pr:cs.paddingRight, pb:cs.paddingBottom, pl:cs.paddingLeft,
        x:r.getBoundingClientRect().x+r.getBoundingClientRect().width/2,
        y:r.getBoundingClientRect().y+r.getBoundingClientRect().height/2});})()`).then(JSON.parse);
    ok(`${theme}: unselected row border-radius resolves --r-control`, rowStatic.radius === rControl, `got=${rowStatic.radius} want=${rControl}`);
    ok(`${theme}: unselected row font-size resolves --t-body`, rowStatic.size === tBody, `got=${rowStatic.size} want=${tBody}`);
    ok(`${theme}: unselected row padding is 10px 11px`,
      rowStatic.pt === '10px' && rowStatic.pr === '11px' && rowStatic.pb === '10px' && rowStatic.pl === '11px',
      JSON.stringify(rowStatic));

    // A REAL pointer move (not a synthetic mouseover — only the input pipeline sets :hover).
    await cmd('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rowStatic.x, y: rowStatic.y, buttons: 0 });
    await sleep(400); // clear of the 160ms transition window before sampling
    const codeBgWant = await bgOf('--code-bg');
    const rowHover = await evaluate(`(()=>{const r=document.querySelector('.cmdrow[aria-selected="false"]');
      const cs=getComputedStyle(r);
      return JSON.stringify({bg:cs.backgroundColor, prop:cs.transitionProperty, dur:cs.transitionDuration, timing:cs.transitionTimingFunction});})()`).then(JSON.parse);
    ok(`${theme}: real hover resolves row background to --code-bg`, rowHover.bg === codeBgWant, `got=${rowHover.bg} want=${codeBgWant}`);
    ok(`${theme}: row transition is background, 160ms, ease-out`,
      rowHover.prop.includes('background') && rowHover.dur === '0.16s' && rowHover.timing === 'ease-out', JSON.stringify(rowHover));
    await cmd('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 1, y: 1, buttons: 0 }); // un-hover

    const accentMutedWant = await bgOf('--accent-muted');
    const rowSel = await evaluate(`(()=>{const r=document.querySelector('.cmdrow[aria-selected="true"]');
      const cs=getComputedStyle(r), before=getComputedStyle(r,'::before'), rr=r.getBoundingClientRect();
      const hint=r.querySelector('.cmdhint'); const hcs=hint&&getComputedStyle(hint);
      return JSON.stringify({bg:cs.backgroundColor, color:cs.color, weight:cs.fontWeight,
        beforeW:before.width, beforeH:before.height, rowH:rr.height,
        hintFont:hcs&&hcs.fontFamily, hintSize:hcs&&hcs.fontSize, hintColor:hcs&&hcs.color, hintOpacity:hcs&&hcs.opacity});})()`).then(JSON.parse);
    ok(`${theme}: selected row bg=--accent-muted color=--accent weight=600`,
      rowSel.bg === accentMutedWant && rowSel.color === accentWant && rowSel.weight === '600', JSON.stringify(rowSel));
    ok(`${theme}: selected row ::before is a 2px rule inset 8px top/bottom`,
      rowSel.beforeW === '2px' && Math.abs(parseFloat(rowSel.beforeH) - (rowSel.rowH - 16)) <= 1,
      JSON.stringify(rowSel));
    ok(`${theme}: hint spans are Geist Mono at --t-eyebrow`,
      rowSel.hintFont && rowSel.hintFont.includes('Geist Mono') && rowSel.hintSize === tEyebrow, JSON.stringify(rowSel));
    ok(`${theme}: selected hint colour resolves --accent at opacity .75`,
      rowSel.hintColor === accentWant && Math.abs(parseFloat(rowSel.hintOpacity) - 0.75) < 0.01, JSON.stringify(rowSel));

    const rowUnsel = await evaluate(`(()=>{const r=document.querySelector('.cmdrow[aria-selected="false"]');
      const hint=r.querySelector('.cmdhint'); const hcs=hint&&getComputedStyle(hint);
      return JSON.stringify({hintColor:hcs&&hcs.color});})()`).then(JSON.parse);
    ok(`${theme}: unselected hint colour resolves --text-subtle`, rowUnsel.hintColor === subtleWant, JSON.stringify(rowUnsel));

    // ---- AC5: hint content ----------------------------------------------------------------
    const hints = await evaluate(`(()=>{const rows=[...document.querySelectorAll('.cmdrow')];
      const byLabel={}; for(const r of rows){const spans=r.querySelectorAll('span');
        const label=spans[0]&&spans[0].textContent, hint=r.querySelector('.cmdhint');
        byLabel[label]=hint?hint.textContent:null;}
      return JSON.stringify(byLabel);})()`).then(JSON.parse);
    ok(`${theme}: a review row's hint is its project name`,
      hints['Palette fixture auth 1'] === 'auth-service', JSON.stringify(hints['Palette fixture auth 1']));
    ok(`${theme}: the auth-service project row (4 fixture reviews) hints exactly "4 reviews"`,
      hints['auth-service'] === '4 reviews', JSON.stringify(hints['auth-service']));
    ok(`${theme}: the literal hint "project" appears on no row`,
      !Object.values(hints).includes('project'), JSON.stringify(hints));

    // ---- AC6: footer --------------------------------------------------------------------------
    const s4 = await rawTok('--s-4');
    const footer = await evaluate(`(()=>{const f=document.querySelector('#cmdk .command>footer');
      const spans=[...f.querySelectorAll('span')].map(s=>s.textContent); const cs=getComputedStyle(f);
      return JSON.stringify({spans, borderTop:cs.borderTopColor, font:cs.fontFamily, size:cs.fontSize,
        color:cs.color, gap:cs.columnGap});})()`).then(JSON.parse);
    ok(`${theme}: footer has exactly the three hint spans`,
      JSON.stringify(footer.spans) === JSON.stringify(['↑↓ move', '↵ open', 'esc close']), JSON.stringify(footer.spans));
    ok(`${theme}: footer rule resolves --border-faint, mono --t-eyebrow --text-subtle, gap --s-4`,
      footer.borderTop === borderFaintWant && footer.font.includes('Geist Mono') && footer.size === tEyebrow
      && footer.color === subtleWant && footer.gap === s4, JSON.stringify(footer));

    await evaluate(`cmdClose(); true`);
  }

  // Positive control #2: the two themes actually resolved to different, non-transparent colours.
  // Without this, a broken probe (e.g. a typo'd token name resolving to nothing) reads as green
  // in both branches above.
  ok('light and dark panel backgrounds are distinct and non-transparent (probe is not vacuous)',
    panelBgByTheme.light !== panelBgByTheme.dark
    && panelBgByTheme.light !== 'rgba(0, 0, 0, 0)' && panelBgByTheme.dark !== 'rgba(0, 0, 0, 0)',
    JSON.stringify(panelBgByTheme));

  // ---- AC6 continued: footer pinned at the narrow (#265) breakpoint, list scrolls ------------
  // 606 is the established full-screen-breakpoint width (tests/palette_fullscreen_selfcheck.sh).
  // Height is deliberately 500, not that check's 900: cmdBuild caps at 8 reviews + 5 projects, and
  // at 900 that content fits without overflowing, which would make the "list actually scrolls"
  // assertion pass vacuously. 500 is short enough that the fixture's max DOM overflows for real.
  await evaluate(`document.documentElement.setAttribute('data-theme', 'light')`);
  await resize(606, 500);
  await evaluate(`cmdOpen(); true`);
  await sleep(400);
  const narrow = await evaluate(`(()=>{const f=document.querySelector('#cmdk .command>footer');
    const list=document.querySelector('#cmdlist');
    return JSON.stringify({footerBottom:f.getBoundingClientRect().bottom, innerH:window.innerHeight,
      scrollH:list.scrollHeight, clientH:list.clientHeight});})()`).then(JSON.parse);
  ok('606x500: footer bottom edge sits at the viewport bottom',
    Math.abs(narrow.footerBottom - narrow.innerH) <= 1, JSON.stringify(narrow));
  ok('606x500: #cmdlist actually overflows with the fixture (scroll is real, not assumed)',
    narrow.scrollH > narrow.clientH, JSON.stringify(narrow));
  await evaluate(`cmdClose(); true`);
  await resize(1280, 900);

  // ---- AC7: reduced motion, no rival guard added ----------------------------------------------
  await media('reduce');
  await evaluate(`cmdOpen(); true`);
  await sleep(200);
  const reduced = await evaluate(`getComputedStyle(document.querySelector('.cmdrow')).transitionDuration`);
  // Chrome serializes computed transition-duration in SECONDS, not the declared unit: 0.01ms
  // comes back as "1e-05s", not the literal string "0.01ms". Parse it rather than string-match.
  const reducedMs = parseFloat(reduced) * 1000;
  ok('under prefers-reduced-motion, row transition collapses to 0.01ms (theme.css global guard)',
    Math.abs(reducedMs - 0.01) < 1e-6, `got=${reduced} = ${reducedMs}ms`);
  await evaluate(`cmdClose(); true`);
  await media(null);

  const src = readFileSync(join(HERE, 'web', 'app', 'dashboard.html'), 'utf8');
  const rivalGuards = (src.match(/@media\s*\(prefers-reduced-motion/g) || []).length;
  ok('dashboard.html adds no rival prefers-reduced-motion block (theme.css stays the only one)',
    rivalGuards === 0, `found ${rivalGuards}`);

  console.log(failed ? `\n${failed} case(s) failed` : '\nall palette restyle cases pass');
  cleanup();
  process.exit(failed ? 1 : 0);
}

main().catch(e => { console.error('palette-restyle-check: ' + (e?.stack || e)); cleanup(); process.exit(2); });
