// scripts/addressed-check.mjs — #331. Samples the RENDERED outcome of the viewer's ADDRESSED
// comment-card state in a real browser, never the presence of a CSS declaration (the #265
// lesson: a CSS-text assertion stayed green over a broken layout for two days).
//
// ADDRESSED = an OPEN thread (status != resolved) whose most recent entry is authored by the
// agent (web/app/viewer.html's isAddressed()). This checks all three boundaries the ticket
// names, plus a fourth that the naive "status === 'open'" reading would get wrong:
//   A. open,     agent replied last  -> badge shown, computed colour == --success
//   B. open,     human replied last  -> no badge anywhere in the card
//   C. resolved, agent's entry last  -> never a .gcard at all (renders as .rcard); no badge
//   D. reopened, agent's entry last  -> badge shown (status != resolved, not status === 'open')
//
// Zero-dep: Node's built-in WebSocket + fetch driving CDP, same shape as
// scripts/theme-check.mjs / scripts/latex-canvas-check.mjs (#333).
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const url = process.argv[2];
const ids = JSON.parse(process.argv[3] || '{}');   // {a,b,c,d}: comment_ids from the seeded fixture
const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }
if (!url || !ids.a || !ids.b || !ids.c || !ids.d) {
  console.error('usage: node scripts/addressed-check.mjs <review-url> <json {a,b,c,d}>');
  process.exit(2);
}

let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c ? '' : `  (${d})`)); if (!c) failed++; };
const port = 9500 + (Date.now() % 400);
const profile = mkdtempSync(join(tmpdir(), 'addressed-check-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws;
try {
  // /json/list also returns Chrome EXTENSION background pages; filter to a real page target, else
  // every sample below silently comes from chrome-extension://.../background.html.
  let tabs, target;
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
  // Poll for the page to be REALLY there. A fixed sleep after Page.navigate can sample about:blank
  // (the #333 lesson), which would make every assertion below pass or fail vacuously.
  let ready = false;
  for (let i = 0; i < 80; i++) {
    const st = await evalJs(`document.readyState + '|' + !!document.querySelector('#gutter')`);
    if (typeof st === 'string' && st.startsWith('complete') && st.endsWith('true')) { ready = true; break; }
    await sleep(250);
  }
  ok('the viewer actually loaded (probe is not vacuous)', ready,
     await evalJs(`document.readyState + ' ' + location.href`));
  if (!ready) { console.log('\naborting: nothing to sample'); ws.close(); chrome.kill(); process.exit(1); }

  // Wide viewport -> #gutter runs "gutter-on" (see layoutComments' railFits gate), so .gcard
  // renders in place without needing to dock it first.
  await send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
  await sleep(400);

  // Positive controls: the fixture actually produced open cards, and --success resolves to a
  // real, non-transparent colour distinct from a neutral text colour — else the colour
  // assertions below could pass vacuously against a broken or missing token. A probe element is
  // the only way to read a light-dark() token as a resolved colour (getPropertyValue returns the
  // raw "light-dark(...)" text, not a colour — the #285/#333 lesson).
  const controls = JSON.parse(await evalJs(`(()=>{
    const probe=document.createElement('div');
    probe.style.cssText='position:absolute;left:-9999px;color:var(--success)';
    document.body.appendChild(probe);
    const success=getComputedStyle(probe).color;
    probe.style.color='var(--text-muted)';
    const textMuted=getComputedStyle(probe).color;
    probe.remove();
    return JSON.stringify({cardCount:document.querySelectorAll('.gcard').length, success, textMuted});
  })()`));
  ok('fixture produced open .gcard elements', controls.cardCount >= 3, `cardCount=${controls.cardCount}`);
  ok('--success resolves to a real, non-transparent colour', !!controls.success && !/transparent|rgba?\(0,\s*0,\s*0,\s*0\)/.test(controls.success), controls.success);
  ok('--success is distinct from --text-muted (so the colour check below can fail)', controls.success !== controls.textMuted, `both ${controls.success}`);

  // Case A: open thread, agent replied last -> the ADDRESSED badge, in --success.
  const a = JSON.parse(await evalJs(`(()=>{
    const card=document.querySelector('.gcard[data-id=${JSON.stringify(ids.a)}]');
    if(!card) return JSON.stringify({present:false});
    const entries=[...card.querySelectorAll('.gentry')];
    const last=entries[entries.length-1];
    const badge=last&&last.querySelector('.gaddr');
    return JSON.stringify({present:true,lastRole:last&&last.className,
      badgeText:badge?badge.textContent:null, badgeColor:badge?getComputedStyle(badge).color:null,
      badgeTransform:badge?getComputedStyle(badge).textTransform:null});
  })()`));
  ok('case A (open, agent replied last): card renders in the gutter', a.present, JSON.stringify(a));
  ok('case A: the agent\'s (last) entry carries the Addressed badge', a.present && !!a.badgeText && /addressed/i.test(a.badgeText), JSON.stringify(a));
  ok('case A: badge computed colour equals resolved --success', a.present && a.badgeColor === controls.success, `badge=${a.badgeColor} success=${controls.success}`);
  // Capitalisation is a CSS text-transform, not literal "ADDRESSED" text (matches this file's own
  // .ghdr "Comments" convention) — assert what actually PAINTS uppercase, not the source string,
  // so deleting the transform is caught here rather than passing on textContent alone.
  ok('case A: badge actually PAINTS uppercase (text-transform, not just source text)', a.present && a.badgeTransform === 'uppercase', `transform=${a.badgeTransform}`);

  // Case B: open thread, human replied last -> no badge anywhere in the card.
  const b = JSON.parse(await evalJs(`(()=>{
    const card=document.querySelector('.gcard[data-id=${JSON.stringify(ids.b)}]');
    if(!card) return JSON.stringify({present:false});
    return JSON.stringify({present:true, badgeCount:card.querySelectorAll('.gaddr').length});
  })()`));
  ok('case B (open, human replied last): card renders in the gutter', b.present, JSON.stringify(b));
  ok('case B: no Addressed badge anywhere in the card', b.present && b.badgeCount === 0, JSON.stringify(b));

  // Case C: resolved thread whose own last entry is the agent's -> never rendered as a .gcard at
  // all (only active threads populate #gutter); once the Resolved panel is opened it shows as a
  // .rcard, which never carries the badge even though the agent technically spoke last.
  await evalJs(`document.querySelector('#resbtn').click(); true`);
  await sleep(200);
  const c = JSON.parse(await evalJs(`(()=>{
    const inGutter=!!document.querySelector('.gcard[data-id=${JSON.stringify(ids.c)}]');
    const rcard=document.querySelector('.rcard[data-id=${JSON.stringify(ids.c)}]');
    return JSON.stringify({inGutter, rcardPresent:!!rcard, badgeCount: rcard ? rcard.querySelectorAll('.gaddr').length : -1});
  })()`));
  ok('case C (resolved, agent\'s entry technically last): never an active .gcard', !c.inGutter, JSON.stringify(c));
  ok('case C: renders as .rcard in the Resolved panel instead', c.rcardPresent, JSON.stringify(c));
  ok('case C: resolved card carries no Addressed badge despite the agent speaking last', c.rcardPresent && c.badgeCount === 0, JSON.stringify(c));

  // Case D: reopened (status flipped back from resolved WITHOUT a trailing reviewer entry), so
  // the agent is still the thread's last speaker -> ADDRESSED. Proves the derivation keys off
  // "status !== resolved", not the narrower (and wrong) "status === 'open'".
  const d = JSON.parse(await evalJs(`(()=>{
    const card=document.querySelector('.gcard[data-id=${JSON.stringify(ids.d)}]');
    if(!card) return JSON.stringify({present:false});
    const entries=[...card.querySelectorAll('.gentry')];
    const last=entries[entries.length-1];
    const badge=last&&last.querySelector('.gaddr');
    return JSON.stringify({present:true, badgeText:badge?badge.textContent:null});
  })()`));
  ok('case D (reopened, agent still last): card renders in the gutter', d.present, JSON.stringify(d));
  ok('case D: reopened-but-agent-last still shows Addressed', d.present && !!d.badgeText && /addressed/i.test(d.badgeText), JSON.stringify(d));

} finally {
  try { ws?.close(); } catch {}
  try { chrome.kill(); } catch {}
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
}
console.log(failed ? `\n${failed} case(s) failed` : '\nall addressed-state cases pass');
process.exit(failed ? 1 : 0);
