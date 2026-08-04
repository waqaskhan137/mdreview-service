// account-page-check.mjs — #281. Samples RENDERED OUTCOMES (computed style, measured geometry,
// DOM state) for web/app/account.html + the account.js trigger in real headless Chrome, both
// themes forced via data-theme. Zero-dep: Node's built-in WebSocket + fetch driving CDP, same
// shape as scripts/admin-reskin-check.mjs / scripts/latex-canvas-check.mjs.
//
// UNLIKE admin-reskin-check.mjs, this does NOT stub window.fetch for the main pass: AC11-15
// explicitly require "the real POST", "the real DELETE", "next /auth/session is unauthenticated"
// -- a fixture cannot answer those. Login is genuine (magic-link -> redeem -> Set-Cookie, the
// same flow tests/account_tokens_csrf_selfcheck.py's login() drives directly over HTTP), and the
// resulting cookie is handed to Chrome via CDP Network.setCookie so every fetch() the PAGE makes
// is a real network call with a real cookie and a real CSRF token. (Verified separately: the
// session cookie is Secure-only -- src/mdreview/hosted/sessions.py always sets it -- and Chrome
// DOES send Secure cookies to http://127.0.0.1, which the spec treats as a potentially
// trustworthy origin for local development; this was checked empirically before relying on it.)
//
// Ordering (advisor guidance): non-destructive checks first (trigger, nav, Profile, Security
// tokens incl. mint/revoke/failed-mint, Devices ending only the OTHER session, Advanced, motion,
// mobile). Danger-zone (AC15) runs LAST, on its OWN separate login, because "sign out everywhere"
// kills that browser session server-side and would 401 every assertion that ran after it.
//
// A small stub-based phase (window.fetch overridden via Page.addScriptToEvaluateOnNewDocument,
// admin-reskin-check.mjs's technique) additionally exercises the three non-authenticated trigger
// states ON THIS PAGE (AC5's "extend ... to execute these branches, not regex them, if feasible");
// the static regex checks in account_menu_selfcheck.js stay as the floor either way.
//
//   node scripts/account-page-check.mjs <hosted-origin> <server-log-path>
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BASE = process.argv[2];
const LOG = process.argv[3];
if (!BASE || !LOG) { console.error('usage: account-page-check.mjs <hosted-origin> <server-log-path>'); process.exit(2); }
const ACCOUNT_URL = BASE.replace(/\/$/, '') + '/account';

const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }

let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c ? '' : `  (${JSON.stringify(d)})`)); if (!c) failed++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

// ---- real magic-link login over plain HTTP (no Chrome involved), same flow as the python
// selfchecks' login() helper: POST /auth/magic-link, read the redeem token the stub-email path
// writes to the server log, POST /auth/redeem with redirect suppressed to capture Set-Cookie. ----
async function login(email) {
  await fetch(BASE + '/auth/magic-link', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) });
  let tok;
  for (let i = 0; i < 60; i++) {
    const text = readFileSync(LOG, 'utf8');
    const m = [...text.matchAll(/auth\/redeem\?token=([A-Za-z0-9._~-]+)/g)];
    if (m.length) { tok = m[m.length - 1][1]; break; }
    await sleep(200);
  }
  if (!tok) throw new Error('no redeem token appeared in the server log for ' + email);
  const res = await fetch(BASE + '/auth/redeem', { method: 'POST', redirect: 'manual',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: 'token=' + encodeURIComponent(tok) });
  const cookie = (res.headers.get('set-cookie') || '').split(';')[0];
  if (!cookie.startsWith('mdr_session=')) throw new Error('login did not yield a session cookie: ' + JSON.stringify([res.status, cookie]));
  const sessRes = await fetch(BASE + '/auth/session', { headers: { Cookie: cookie } });
  const sess = await sessRes.json();
  return { cookie, csrf: sess.csrf, email: sess.email };
}

const port = 9700 + (Date.now() % 300);
const profile = mkdtempSync(join(tmpdir(), 'account-page-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
const done = () => { try { chrome.kill(); } catch {} try { rmSync(profile, { recursive: true, force: true }); } catch {} };
const overall = setTimeout(() => { console.error('account-page-check: overall timeout (170s)'); done(); process.exit(2); }, 170000);
overall.unref();

const TOK_HELPER = `
window.__tok = function(prop, value){
  var p = document.createElement('div');
  p.style.cssText = 'position:absolute;left:-9999px;top:-9999px;' + prop + ':' + value + ';';
  document.body.appendChild(p);
  var v = getComputedStyle(p).getPropertyValue(prop);
  p.remove();
  return v;
};`;

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
  const netLog = [];
  ws.addEventListener('message', e => {
    const m = JSON.parse(e.data);
    if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === 'Network.requestWillBeSent') {
      netLog.push({ method: m.params.request.method, url: m.params.request.url, ts: Date.now() });
    }
  });
  const cmd = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const evaluate = async expr => {
    const r = await cmd('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result?.exceptionDetails) throw new Error('page eval threw: ' + (r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text));
    return r.result?.result?.value;
  };
  const evalJSON = async expr => JSON.parse(await evaluate(expr));

  await cmd('Page.enable'); await cmd('Runtime.enable'); await cmd('DOM.enable'); await cmd('Network.enable');
  await cmd('Emulation.setDeviceMetricsOverride', { width: 1200, height: 900, deviceScaleFactor: 1, mobile: false });

  async function hardNav(url) {
    await cmd('Page.navigate', { url: 'about:blank' });
    await cmd('Page.navigate', { url });
  }

  // ================================================================================
  // Real login. Two sessions for the SAME user up front (AC14 needs two live devices); a third,
  // separate login is minted later, just before Danger zone, so its death cannot touch anything
  // that ran earlier.
  // ================================================================================
  const EMAIL = 'a.kerr@example.com';
  const primary = await login(EMAIL);
  const secondary = await login(EMAIL);   // a genuine second device/session, never touched by Chrome
  ok('setup: two independent real sessions exist for the same user', !!primary.cookie && !!secondary.cookie && primary.cookie !== secondary.cookie,
     { primary: primary.cookie.slice(0, 30), secondary: secondary.cookie.slice(0, 30) });

  const [ckName, ...ckRest] = primary.cookie.split('=');
  await cmd('Network.setCookie', { name: ckName, value: ckRest.join('='), url: BASE, httpOnly: true, secure: true, sameSite: 'Lax' });
  await cmd('Page.addScriptToEvaluateOnNewDocument', { source: TOK_HELPER });

  const READY = `document.querySelectorAll('.acct-navrow').length===6 && document.getElementById('whoami').textContent===${JSON.stringify(EMAIL)}`;
  async function navAccount() {
    await hardNav(ACCOUNT_URL);
    for (let i = 0; i < 80; i++) { if (await evaluate(READY)) { await sleep(250); return true; } await sleep(150); }
    return false;
    // The extra 250ms after READY flips true: boot() assigns the .active class to the Profile nav
    // row a beat after the rows are inserted, which is a genuine background/color TRANSITION
    // (transparent -> --code-bg over 160ms), not just a DOM-presence change. Reading computed
    // style before it settles samples a blended, in-flight colour (an early version of this
    // check did exactly that and got a translucent rgba() that matched neither theme).
  }
  const ready = await navAccount();
  ok('the account page actually loaded, authenticated, for the real user (probe is not vacuous)', ready,
     await evaluate(`document.readyState + ' nav=' + document.querySelectorAll('.acct-navrow').length + ' who=' + document.getElementById('whoami').textContent`));
  if (!ready) { throw new Error('aborting: nothing to sample'); }

  // ================================================================================
  // AC5 extension: the three non-authenticated TRIGGER states, exercised on THIS real page (not
  // just via account_menu_selfcheck.js's static regexes). /account is server-gated
  // (_require_user()): an anonymous GET 401s before any HTML is served, so these three states
  // cannot be reached by simply omitting the cookie. Instead the REAL cookie stays valid (the
  // server-side gate passes, the real page loads) and only the PAGE's client-side re-check of
  // /auth/session is stubbed, via Page.addScriptToEvaluateOnNewDocument -- the same technique
  // scripts/admin-reskin-check.mjs uses, run BEFORE any page script including the pre-paint
  // applier. This is a faithful reproduction of what actually differs between the four states
  // (what /auth/session answers), not a fetch stub standing in for the whole server.
  // ================================================================================
  const FOURSTATE_STUB = `(function(){
    var boot = (location.hash.match(/boot=([a-z]+)/)||[])[1] || 'main';
    var jsonRes = function(o,s){ return new Response(JSON.stringify(o), {status:s||200, headers:{'Content-Type':'application/json'}}); };
    var orig = window.fetch.bind(window);
    window.fetch = function(input, init){
      var url = typeof input==='string' ? input : (input&&input.url)||'';
      var path = url.replace(/^https?:\\/\\/[^/]+/, '');
      if (path === '/auth/session') {
        if (boot === 'noauthplane') return Promise.resolve(jsonRes({}, 404));
        if (boot === 'unreachable') return Promise.reject(new TypeError('stub: simulated network failure'));
        if (boot === 'signedout') return Promise.resolve(jsonRes({authenticated:false}));
      }
      return orig(input, init);
    };
  })();` + TOK_HELPER;
  const { identifier: fourStateScriptId } = (await cmd('Page.addScriptToEvaluateOnNewDocument', { source: FOURSTATE_STUB })).result;
  async function fourStateSnapshot(hash) {
    await hardNav(ACCOUNT_URL + '#' + hash);
    for (let i = 0; i < 60; i++) {
      if (await evaluate(`document.readyState === 'complete' && !!document.getElementById('acct')`)) break;
      await sleep(150);
    }
    let stable = null;
    for (let i = 0; i < 40; i++) {
      stable = await evalJSON(`JSON.stringify({
        acctChildren: document.getElementById('acct').children.length,
        acctHTML: document.getElementById('acct').innerHTML
      })`);
      if (stable.acctHTML !== '' || hash.includes('noauthplane')) break;
      await sleep(150);
    }
    return stable;
  }
  const s0 = await fourStateSnapshot('boot=noauthplane');
  ok('AC5 (noAuthPlane, real page): #acct renders nothing', s0.acctChildren === 0, s0);
  await sleep(750); // session.js retries once after 600ms before giving up on a real network failure
  const s1 = await fourStateSnapshot('boot=unreachable');
  ok('AC5 (unreachable, real page): "Reconnecting…" with the grey dot', /Reconnecting/.test(s1.acctHTML) && /#9aa0a6/.test(s1.acctHTML), s1);
  const s2 = await fourStateSnapshot('boot=signedout');
  ok('AC5 (anonymous, real page): a "Sign in" link renders', /acct-in[\s\S]*Sign in/.test(s2.acctHTML), s2);
  await cmd('Page.removeScriptToEvaluateOnNewDocument', { identifier: fourStateScriptId });
  const readyAgain = await navAccount();
  ok('setup: real authenticated state comes back after removing the stub', readyAgain, readyAgain);

  // ================================================================================
  // AC1-4: the avatar-initials trigger, both themes.
  // ================================================================================
  async function triggerSnapshot(theme) {
    return evalJSON(`(() => {
      document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)});
      const trig = document.querySelector('#acct .acct-trig');
      const corner = trig.querySelector('.acct-corner');
      const tr = trig.getBoundingClientRect(), cr = corner.getBoundingClientRect();
      const cs = getComputedStyle(trig), cornerCs = getComputedStyle(corner);
      return JSON.stringify({
        trigW: tr.width, trigH: tr.height,
        text: trig.textContent.trim(), hasEmailSpan: !!trig.querySelector('.acct-email'),
        bg: cs.backgroundColor, radius: cs.borderRadius, borderColor: cs.borderColor,
        title: trig.getAttribute('title'),
        cornerW: cr.width, cornerH: cr.height,
        cornerRightOffset: cr.right - tr.right, cornerBottomOffset: cr.bottom - tr.bottom,
        cornerBg: cornerCs.backgroundColor, cornerBorderW: cornerCs.borderTopWidth,
        cornerBorderStyle: cornerCs.borderTopStyle, cornerBorderColor: cornerCs.borderTopColor,
        haspopup: trig.getAttribute('aria-haspopup'), tag: trig.tagName, type: trig.getAttribute('type'),
        codeBg: window.__tok('background-color','var(--code-bg)'),
        rControl: window.__tok('border-radius','var(--r-control)'),
        success: window.__tok('background-color','var(--success)'),
        bgTok: window.__tok('background-color','var(--bg)'),
        textSubtle: window.__tok('background-color','var(--text-subtle)'),
      });
    })()`);
  }
  for (const theme of ['light', 'dark']) {
    const t = await triggerSnapshot(theme);
    ok(`AC1 (${theme}): trigger is 28x28, exactly two characters, no email text node`,
       Math.abs(t.trigW - 28) <= 1 && Math.abs(t.trigH - 28) <= 1 && t.text.length === 2 && !t.hasEmailSpan, t);
    ok(`AC1 (${theme}): computed background = --code-bg, border-radius = --r-control`,
       t.bg === t.codeBg && t.radius === t.rControl, t);
    ok(`AC1 (${theme}): title carries the email and Admin`, t.title === EMAIL + ' · Admin', t.title);
    ok(`AC2 (${theme}): corner dot 8x8, --success bg, 2px solid --bg border, overlapping the bottom-right corner`,
       Math.abs(t.cornerW - 8) <= 1 && Math.abs(t.cornerH - 8) <= 1 && t.cornerBg === t.success &&
       t.cornerBorderW === '2px' && t.cornerBorderStyle === 'solid' && t.cornerBorderColor === t.bgTok &&
       Math.abs(t.cornerRightOffset - 2) <= 1 && Math.abs(t.cornerBottomOffset - 2) <= 1, t);
    ok(`AC4 (${theme}): real button[type=button][aria-haspopup=menu]`, t.tag === 'BUTTON' && t.type === 'button' && t.haspopup === 'menu', t);
  }

  // AC3: hover changes computed border-color to --text-subtle. A real mouse move (not .focus()),
  // then reset away so it does not leak into later screenshots/assertions. The trigger has its own
  // 160ms border-color transition, which the theme flip ALSO triggers (the resolved --border value
  // changes) -- sleeps here are longer than 160ms so each read lands after that settles, not
  // mid-interpolation (the first version of this check read too early and sampled a blended colour).
  await evaluate(`document.documentElement.setAttribute('data-theme','light'); true`);
  await sleep(220);
  const trigBox = await evalJSON(`JSON.stringify(document.querySelector('#acct .acct-trig').getBoundingClientRect())`);
  const beforeHover = await evaluate(`getComputedStyle(document.querySelector('#acct .acct-trig')).borderColor`);
  await cmd('Input.dispatchMouseEvent', { type: 'mouseMoved', x: trigBox.x + trigBox.width / 2, y: trigBox.y + trigBox.height / 2 });
  await sleep(220);
  const afterHover = await evaluate(`getComputedStyle(document.querySelector('#acct .acct-trig')).borderColor`);
  const textSubtleLight = await evaluate(`window.__tok('background-color','var(--text-subtle)')`);
  await cmd('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 2, y: 2 });
  ok('AC3: hover changes computed border-color to resolved --text-subtle', afterHover !== beforeHover && afterHover === textSubtleLight,
     { beforeHover, afterHover, textSubtleLight });

  // ================================================================================
  // AC6-8: nav structure, order, separator, active-row styling.
  // ================================================================================
  const nav = await evalJSON(`(() => {
    const rows = Array.from(document.querySelectorAll('.acct-navrow'));
    const sep = document.querySelector('.acct-navsep');
    const navEl = document.querySelector('nav[aria-label="Sections"]');
    const active = document.querySelector('.acct-navrow.active');
    const inactive = rows.find(r => !r.classList.contains('active'));
    const dangerRow = document.querySelector('.acct-navrow.danger');
    const navRect = navEl.getBoundingClientRect(), paneRect = document.querySelector('.acct-pane').getBoundingClientRect();
    const wrapRect = document.querySelector('.acct-wrap').getBoundingClientRect();
    return JSON.stringify({
      order: rows.map(r => r.textContent.trim()),
      sepBeforeDanger: sep && sep.nextElementSibling === dangerRow,
      sepHeight: sep ? getComputedStyle(sep).height : null,
      activeWeight: active ? getComputedStyle(active).fontWeight : null,
      activeBg: active ? getComputedStyle(active).backgroundColor : null,
      activeBarBg: active ? getComputedStyle(active.querySelector('.acct-navbar')).backgroundColor : null,
      inactiveBg: inactive ? getComputedStyle(inactive).backgroundColor : null,
      inactiveColor: inactive ? getComputedStyle(inactive).color : null,
      dangerColor: dangerRow ? getComputedStyle(dangerRow).color : null,
      navW: navRect.width, paneMaxW: getComputedStyle(document.querySelector('.acct-pane')).maxWidth,
      wrapW: wrapRect.width,
      codeBg: window.__tok('background-color','var(--code-bg)'),
      accent: window.__tok('background-color','var(--accent)'),
      textMuted: window.__tok('background-color','var(--text-muted)'),
      textSubtle: window.__tok('background-color','var(--text-subtle)'),
    });
  })()`);
  ok('AC6: nav order is exactly Profile, Billing, Security, Notifications, Advanced, Danger zone',
     JSON.stringify(nav.order) === JSON.stringify(['Profile', 'Billing', 'Security', 'Notifications', 'Advanced', 'Danger zone']), nav.order);
  ok('AC6: a 1px separator sits immediately before Danger zone', nav.sepBeforeDanger && nav.sepHeight === '1px', nav);
  ok('AC7: nav column is 148px; pane content max-width 600px', Math.abs(nav.navW - 148) <= 1 && nav.paneMaxW === '600px', nav);
  ok('AC7: the two-column row is centered inside a 900px shell', nav.wrapW <= 900, nav.wrapW);
  ok('AC8: active row: font-weight 600, bg=--code-bg, accent bar bg=--accent', nav.activeWeight === '600' && nav.activeBg === nav.codeBg && nav.activeBarBg === nav.accent, nav);
  ok('AC8: inactive row: transparent bg, color=--text-muted; Danger zone color=--text-subtle',
     nav.inactiveBg === 'rgba(0, 0, 0, 0)' && nav.inactiveColor === nav.textMuted && nav.dangerColor === nav.textSubtle, nav);

  // AC7 sticky: pad the page so 600px of scroll room exists, scroll, then read the nav's rect.top.
  // The spacer must extend the PANE (inside .acct-cols, the sticky nav's containing block), not
  // just the page: a spacer appended to <body> lengthens the document but not .acct-cols itself,
  // so the nav runs out of containing-block room and stops sticking well before 600px -- the
  // first version of this check did that and read a plain, un-stuck scroll position.
  await evaluate(`(() => { const spacer = document.createElement('div'); spacer.id='__spacer'; spacer.style.height='1400px'; document.getElementById('acct-slot').appendChild(spacer); return true; })()`);
  await evaluate(`window.scrollTo(0, 600); true`);
  await sleep(100);
  const stickyTop = await evalJSON(`JSON.stringify({top: document.querySelector('nav[aria-label="Sections"]').getBoundingClientRect().top, s6: window.__tok('margin-top','var(--s-6)')})`);
  ok('AC7: after scrolling the pane 600px, the sticky nav parks at resolved --s-6 (24px)',
     Math.abs(parseFloat(stickyTop.top) - parseFloat(stickyTop.s6)) <= 1, stickyTop);
  await evaluate(`(() => { window.scrollTo(0,0); const sp = document.getElementById('__spacer'); if (sp) sp.remove(); return true; })()`);

  // ================================================================================
  // AC9: clicking a nav entry swaps the pane (exactly one section root), sectionIn animation, and
  // its reduced-motion branch. animation-NAME is the discriminator that proves the rule fired;
  // duration alone is vacuous under the guard (theme.css:348 forces .01ms on every element).
  // ================================================================================
  async function clickSection(id) {
    await evaluate(`document.querySelector('.acct-navrow[data-section="${id}"]').click(); true`);
    await sleep(80);
    return evalJSON(`(() => {
      const roots = document.querySelectorAll('#acct-slot > .acct-section');
      const r = roots[0];
      const cs = r ? getComputedStyle(r) : null;
      return JSON.stringify({
        rootCount: roots.length, sectionId: r ? r.getAttribute('data-section-root') : null,
        animName: cs ? cs.animationName : null, animDur: cs ? cs.animationDuration : null,
      });
    })()`);
  }
  const swap1 = await clickSection('security');
  ok('AC9: exactly one section root after a switch, and it is the clicked section', swap1.rootCount === 1 && swap1.sectionId === 'security', swap1);
  ok('AC9 (normal motion): animation-name=sectionIn, duration=0.15s', swap1.animName === 'sectionIn' && swap1.animDur === '0.15s', swap1);
  await clickSection('profile');
  await cmd('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
  const swap2 = await clickSection('advanced');
  // Chrome serializes a very small computed duration as e.g. "1e-05s" rather than "0.01ms" --
  // compare numerically (milliseconds) rather than by exact string.
  const durMs = str => { const n = parseFloat(str); return /ms$/.test(str) ? n : n * 1000; };
  ok('AC9 (reduced motion): animation-name STILL sectionIn (the rule fired) but duration collapses to 0.01ms (the guard reached it)',
     swap2.animName === 'sectionIn' && Math.abs(durMs(swap2.animDur) - 0.01) < 0.001, swap2);
  await cmd('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });

  // ================================================================================
  // AC10: Profile rows.
  // ================================================================================
  await clickSection('profile');
  const profile = await evalJSON(`(() => {
    const rows = Array.from(document.querySelectorAll('#acct-slot .acct-row'));
    const email = rows.find(r => r.dataset.row === 'email'), role = rows.find(r => r.dataset.row === 'role');
    const chev = email.querySelector('.acct-row-chev svg');
    const before = getComputedStyle(email).backgroundColor;
    return JSON.stringify({
      emailLabel: email.querySelector('.acct-row-label').textContent,
      emailLabelColor: getComputedStyle(email.querySelector('.acct-row-label')).color,
      emailValue: email.querySelector('.acct-row-value').textContent,
      emailValueColor: getComputedStyle(email.querySelector('.acct-row-value')).color,
      roleValue: role.querySelector('.acct-row-value').textContent,
      chevW: chev.getBoundingClientRect().width, chevH: chev.getBoundingClientRect().height,
      chevColor: getComputedStyle(email.querySelector('.acct-row-chev')).color,
      text: window.__tok('background-color','var(--text)'),
      textMuted: window.__tok('background-color','var(--text-muted)'),
      textSubtle: window.__tok('background-color','var(--text-subtle)'),
      codeBg: window.__tok('background-color','var(--code-bg)'),
      before,
    });
  })()`);
  ok('AC10: Sign-in email row shows the REAL session email; label=--text, value=--text-muted',
     profile.emailLabel === 'Sign-in email' && profile.emailValue === EMAIL &&
     profile.emailLabelColor === profile.text && profile.emailValueColor === profile.textMuted, profile);
  ok('AC10: Role row shows Admin', profile.roleValue === 'Admin', profile.roleValue);
  ok('AC10: 16x16 chevron, color=--text-subtle', Math.abs(profile.chevW - 16) <= 1 && Math.abs(profile.chevH - 16) <= 1 && profile.chevColor === profile.textSubtle, profile);
  const hoverBg = await evalJSON(`(() => {
    const row = document.querySelector('#acct-slot .acct-row[data-row="email"]');
    const r = row.getBoundingClientRect();
    return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2});
  })()`);
  await cmd('Input.dispatchMouseEvent', { type: 'mouseMoved', x: hoverBg.x, y: hoverBg.y });
  await sleep(250);
  const rowHoverColor = await evaluate(`getComputedStyle(document.querySelector('#acct-slot .acct-row[data-row="email"]')).backgroundColor`);
  await cmd('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 2, y: 2 });
  ok('AC10: row hover background = resolved --code-bg', rowHoverColor === profile.codeBg, { rowHoverColor, codeBg: profile.codeBg });

  // ================================================================================
  // AC11-13: Security > Agent tokens: mint two real tokens, verify the grid, revoke one for
  // real (2xx), then a FORCED 403 (corrupt CSRF in-page) to prove a failed revoke/mint leaves
  // state untouched and surfaces in #flash.
  // ================================================================================
  await clickSection('security');
  await evaluate(`document.querySelector('.acct-row[data-row="tokens"]').click(); true`);
  await sleep(80);
  async function mintOne(label) {
    await evaluate(`(() => { const i = document.getElementById('tok-label'); if (i) i.value = ${JSON.stringify(label)}; return true; })()`);
    await evaluate(`document.getElementById('tok-mint').click(); true`);
    for (let i = 0; i < 40; i++) { if (await evaluate(`!!document.getElementById('tok-plain')`)) break; await sleep(150); }
    const minted = await evalJSON(`JSON.stringify({
      plain: document.getElementById('tok-plain') ? document.getElementById('tok-plain').textContent : null,
      mcpText: document.getElementById('tok-mcp') ? document.getElementById('tok-mcp').textContent : null,
      step1Bg: document.querySelector('.acct-minted-step1') ? getComputedStyle(document.querySelector('.acct-minted-step1')).backgroundColor : null,
      mcpBg: document.querySelector('.acct-mcp-wrap') ? getComputedStyle(document.querySelector('.acct-mcp-wrap')).backgroundColor : null,
      mcpWhiteSpace: document.getElementById('tok-mcp') ? getComputedStyle(document.getElementById('tok-mcp')).whiteSpace : null,
      successBg: window.__tok('background-color','var(--success-bg)'),
      codeBg: window.__tok('background-color','var(--code-bg)'),
    })`);
    return minted;
  }
  const mint1 = await mintOne('laptop');
  ok('AC12: mint 1 (real POST) shows the plaintext token exactly once, step-1 bg=--success-bg',
     !!mint1.plain && mint1.plain.startsWith('mdr_') && mint1.step1Bg === mint1.successBg, mint1);
  ok('AC12: step-2 <pre> bg=--code-bg, white-space:pre, and its text parses as the MCP config JSON',
     mint1.mcpBg === mint1.codeBg && mint1.mcpWhiteSpace === 'pre', mint1);
  let mcpJson1;
  try { mcpJson1 = JSON.parse(mint1.mcpText); } catch (e) { mcpJson1 = null; }
  // The server reports its OWN configured base (PUBLIC_BASE when set, e.g. this test harness's
  // https://l.test) via the same GET the page itself calls -- not necessarily Chrome's connected
  // origin -- so ask the server what it actually said rather than assume it equals BASE.
  const serverReportedBase = await fetch(BASE + '/account/tokens', { headers: { Cookie: primary.cookie } }).then(r => r.json()).then(d => d.base);
  ok('AC12: mcpServers.mdreview.env.MDREVIEW_TOKEN equals the minted token; MDREVIEW_BASE is the server-reported base',
     !!mcpJson1 && mcpJson1.mcpServers?.mdreview?.env?.MDREVIEW_TOKEN === mint1.plain &&
     mcpJson1.mcpServers?.mdreview?.env?.MDREVIEW_BASE === serverReportedBase,
     { mcpJson1, want: mint1.plain, serverReportedBase });
  // "Done" removes the block from the DOM (not display:none with the token still present).
  await evaluate(`document.getElementById('tok-done').click(); true`);
  await sleep(80);
  const afterDone = await evalJSON(`JSON.stringify({plain: document.getElementById('tok-plain'), htmlHasToken: document.getElementById('rev-tokens').innerHTML.includes(${JSON.stringify(mint1.plain)})})`);
  ok('AC12: "Done" removes the just-minted block from the DOM entirely (token nowhere in the reveal)', afterDone.plain === null && !afterDone.htmlHasToken, afterDone);
  // Reload -> never re-shows the token (shown-once honesty: MINTED lives only in a JS variable).
  await navAccount();
  await evaluate(`document.querySelector('.acct-navrow[data-section="security"]').click(); true`);
  await sleep(80);
  await evaluate(`document.querySelector('.acct-row[data-row="tokens"]').click(); true`);
  await sleep(80);
  const afterReload = await evalJSON(`JSON.stringify({hasPlain: !!document.getElementById('tok-plain'), pageHasToken: document.body.innerHTML.includes(${JSON.stringify(mint1.plain)})})`);
  ok('AC12: reloading the page never re-shows the token', !afterReload.hasPlain && !afterReload.pageHasToken, afterReload);

  const mint2 = await mintOne('ci');
  ok('AC12: mint 2 also succeeds (now two real tokens exist)', !!mint2.plain && mint2.plain !== mint1.plain, { mint1: mint1.plain, mint2: mint2.plain });
  await evaluate(`document.getElementById('tok-done').click(); true`);
  await sleep(80);

  const grid = await evalJSON(`(() => {
    const val = document.querySelector('.acct-row[data-row="tokens"] .acct-row-value').textContent;
    const rows = Array.from(document.querySelectorAll('#rev-tokens .acct-tgrid-row'));
    const dataRow = rows.find(r => r.textContent.includes('laptop') || r.textContent.includes('ci'));
    return JSON.stringify({ val, rowCount: rows.length, cols: dataRow ? getComputedStyle(dataRow).gridTemplateColumns : null });
  })()`);
  ok('AC11: Agent tokens row reads "2 active"', grid.val === '2 active', grid.val);
  ok('AC11: expanded grid resolves to 4 columns (1fr -> px, 136px, 96px, 72px)',
     /^\d+(\.\d+)?px 136px 96px 72px$/.test(grid.cols), grid);

  // ---- AC13: a FORCED failed mint (real 4xx from the real server: corrupt CSRF in-page) ----
  const beforeFailedMint = await evalJSON(`JSON.stringify({val: document.querySelector('.acct-row[data-row="tokens"] .acct-row-value').textContent})`);
  await evaluate(`window.__realCSRF = CSRF; CSRF = 'not-the-real-token'; true`);
  await evaluate(`(() => { document.getElementById('tok-label').value = 'should-fail'; return true; })()`);
  await evaluate(`document.getElementById('tok-mint').click(); true`);
  await sleep(400);
  const afterFailedMint = await evalJSON(`JSON.stringify({
    hasMinted: !!document.getElementById('tok-plain'),
    val: document.querySelector('.acct-row[data-row="tokens"] .acct-row-value').textContent,
    flash: document.getElementById('flash').textContent, flashClass: document.getElementById('flash').className,
  })`);
  await evaluate(`CSRF = window.__realCSRF; true`);
  ok('AC13: a real 4xx on mint (bad CSRF) shows no minted block, no new token row, and #flash reports the failure',
     !afterFailedMint.hasMinted && afterFailedMint.val === beforeFailedMint.val && /err/.test(afterFailedMint.flashClass) && afterFailedMint.flash.length > 0,
     { beforeFailedMint, afterFailedMint });

  // ---- AC11: a FORCED failed revoke (403) leaves the row in place; then a REAL revoke (2xx) removes it ----
  const beforeRevoke = await evalJSON(`JSON.stringify({rows: document.querySelectorAll('#rev-tokens .acct-revoke').length})`);
  await evaluate(`window.__realCSRF = CSRF; CSRF = 'not-the-real-token'; true`);
  await evaluate(`document.querySelector('#rev-tokens .acct-revoke').click(); true`);
  await sleep(400);
  const afterFailedRevoke = await evalJSON(`JSON.stringify({
    rows: document.querySelectorAll('#rev-tokens .acct-revoke').length,
    flashClass: document.getElementById('flash').className,
  })`);
  await evaluate(`CSRF = window.__realCSRF; true`);
  ok('AC11: intercepting a 403 on revoke leaves the row in place and #flash surfaces the failure',
     afterFailedRevoke.rows === beforeRevoke.rows && /err/.test(afterFailedRevoke.flashClass), { beforeRevoke, afterFailedRevoke });
  await evaluate(`document.querySelector('#rev-tokens .acct-revoke').click(); true`);
  for (let i = 0; i < 40; i++) { if (await evaluate(`document.querySelectorAll('#rev-tokens .acct-revoke').length`) < beforeRevoke.rows) break; await sleep(150); }
  const afterRealRevoke = await evalJSON(`JSON.stringify({
    rows: document.querySelectorAll('#rev-tokens .acct-revoke').length,
    val: document.querySelector('.acct-row[data-row="tokens"] .acct-row-value').textContent,
  })`);
  ok('AC11: a real 2xx revoke removes the row and updates the summary to "1 active"',
     afterRealRevoke.rows === beforeRevoke.rows - 1 && afterRealRevoke.val === '1 active', afterRealRevoke);

  // ================================================================================
  // AC14: Devices. Two real sessions exist (primary=this browser, secondary=the other login).
  // Only end the OTHER one here; ending "this device" is exercised later, inside Danger zone,
  // on the disposable third login.
  // ================================================================================
  await evaluate(`document.querySelector('.acct-row[data-row="devices"]').click(); true`);
  await sleep(80);
  const devices = await evalJSON(`(() => {
    const val = document.querySelector('.acct-row[data-row="devices"] .acct-row-value').textContent;
    const rows = Array.from(document.querySelectorAll('#rev-devices .acct-device-row'));
    const cur = rows.find(r => r.textContent.includes('this device'));
    const other = rows.find(r => !r.textContent.includes('this device'));
    return JSON.stringify({ val, count: rows.length, hasCurrent: !!cur, hasOther: !!other });
  })()`);
  ok('AC14: Devices row reads "2 signed in", one marked "this device"', devices.val === '2 signed in' && devices.count === 2 && devices.hasCurrent && devices.hasOther, devices);
  await evaluate(`(() => {
    const rows = Array.from(document.querySelectorAll('#rev-devices .acct-device-row'));
    const other = rows.find(r => !r.textContent.includes('this device'));
    other.querySelector('button[data-jti]').click();
    return true;
  })()`);
  for (let i = 0; i < 40; i++) { if (await evaluate(`document.querySelector('.acct-row[data-row="devices"] .acct-row-value').textContent`) === '1 signed in') break; await sleep(150); }
  const afterEndOther = await evaluate(`document.querySelector('.acct-row[data-row="devices"] .acct-row-value').textContent`);
  ok('AC14: ending the OTHER session issues a real DELETE and the row leaves on 2xx ("1 signed in")', afterEndOther === '1 signed in', afterEndOther);
  const stillReachable = await fetch(BASE + '/auth/session', { headers: { Cookie: primary.cookie } }).then(r => r.json());
  ok('AC14: ending the other session did NOT touch this (primary) session', stillReachable.authenticated === true, stillReachable);

  // ================================================================================
  // Advanced: Theme (second control over #285 state) + Sharing (present, no data required by
  // any AC beyond "real endpoint" -- exercised here as a smoke pass).
  // ================================================================================
  await clickSection('advanced');
  await evaluate(`document.querySelector('.acct-row[data-row="theme"]').click(); true`);
  await sleep(80);
  const themeBefore = await evalJSON(`JSON.stringify({val: document.querySelector('.acct-row[data-row="theme"] .acct-row-value').textContent, mode: window.mdTheme.mode()})`);
  await evaluate(`document.querySelector('[data-theme-opt="dark"]').click(); true`);
  await sleep(80);
  const themeAfter = await evalJSON(`JSON.stringify({val: document.querySelector('.acct-row[data-row="theme"] .acct-row-value').textContent, mode: window.mdTheme.mode(), dataTheme: document.documentElement.getAttribute('data-theme')})`);
  ok('Advanced > Theme: picking Dark updates #285 state, the row value, and the toggle stay in sync',
     themeAfter.mode === 'dark' && themeAfter.dataTheme === 'dark' && themeAfter.val === 'Dark', { themeBefore, themeAfter });
  await evaluate(`document.querySelector('[data-theme-opt="auto"]').click(); true`);

  await evaluate(`document.querySelector('.acct-row[data-row="sharing"]').click(); true`);
  await sleep(200);
  const sharing = await evalJSON(`JSON.stringify({revealText: document.getElementById('rev-sharing').textContent.trim().slice(0,80), val: document.querySelector('.acct-row[data-row="sharing"] .acct-row-value').textContent})`);
  ok('Advanced > Sharing: the row loads real data from /api/account/shares without erroring (empty is a valid honest state)',
     sharing.val === 'Nothing shared' || /public|shared/.test(sharing.val), sharing);

  // ================================================================================
  // Billing / Notifications: sections present, honest not-available message, no controls.
  // ================================================================================
  await clickSection('billing');
  const billing = await evalJSON(`JSON.stringify({hasControls: document.querySelectorAll('#acct-slot button, #acct-slot input').length, text: document.getElementById('acct-slot').textContent.trim()})`);
  ok('Billing: section renders, contains an honest not-available message, zero controls', billing.hasControls === 0 && billing.text.length > 0, billing);
  await clickSection('notifications');
  const notif = await evalJSON(`JSON.stringify({hasControls: document.querySelectorAll('#acct-slot button, #acct-slot input').length, text: document.getElementById('acct-slot').textContent.trim()})`);
  ok('Notifications: section renders, contains an honest not-available message, zero controls', notif.hasControls === 0 && notif.text.length > 0, notif);
  ok('No fake Two-factor row anywhere on the page', !(await evaluate(`document.body.innerText.includes('Two-factor')`)), 'found "Two-factor"');
  ok('No fake Display name / Reading width / Diff view / Export / Delete account row anywhere',
     !(await evaluate(`/Display name|Reading width|Diff view|Export your data|Delete account/.test(document.body.innerText)`)), 'found a backend-blocked row');

  // ================================================================================
  // AC16-17: mobile <=720px -- chip nav, no page overflow, minted <pre> wraps.
  // ================================================================================
  await cmd('Emulation.setDeviceMetricsOverride', { width: 360, height: 800, deviceScaleFactor: 1, mobile: true });
  await navAccount();
  await sleep(150);
  const mobile = await evalJSON(`(() => {
    const nav = document.querySelector('nav[aria-label="Sections"]');
    const rows = Array.from(document.querySelectorAll('.acct-navrow'));
    const tops = rows.map(r => Math.round(r.getBoundingClientRect().top));
    const active = document.querySelector('.acct-navrow.active');
    return JSON.stringify({
      singleRow: new Set(tops).size === 1,
      overflowX: getComputedStyle(nav).overflowX,
      navBg: getComputedStyle(nav).backgroundColor, activeBg: active ? getComputedStyle(active).backgroundColor : null,
      pageOverflow: document.documentElement.scrollWidth > window.innerWidth,
      codeBg: window.__tok('background-color','var(--code-bg)'), surface: window.__tok('background-color','var(--surface)'),
    });
  })()`);
  ok('AC16: mobile nav is one scrollable row of chips (overflow-x scrollable), bg=--code-bg, active chip bg=--surface',
     mobile.singleRow && mobile.overflowX === 'auto' && mobile.navBg === mobile.codeBg && mobile.activeBg === mobile.surface, mobile);
  ok('AC16: no horizontal page overflow at 360px', !mobile.pageOverflow, mobile);
  await evaluate(`document.querySelector('.acct-navrow[data-section="security"]').click(); true`);
  await sleep(80);
  await evaluate(`document.querySelector('.acct-row[data-row="tokens"]').click(); true`);
  await sleep(80);
  const mint3 = await mintOne('phone');
  const mobilePre = await evalJSON(`JSON.stringify({
    ws: document.getElementById('tok-mcp') ? getComputedStyle(document.getElementById('tok-mcp')).whiteSpace : null,
    owa: document.getElementById('tok-mcp') ? getComputedStyle(document.getElementById('tok-mcp')).overflowWrap : null,
    clientW: document.getElementById('tok-mcp') ? document.getElementById('tok-mcp').clientWidth : 0,
    scrollW: document.getElementById('tok-mcp') ? document.getElementById('tok-mcp').scrollWidth : 0,
    pageOverflow: document.documentElement.scrollWidth > window.innerWidth,
  })`);
  ok('AC17: at 360px the minted <pre> wraps (pre-wrap + overflow-wrap:anywhere) rather than overflowing the viewport',
     mobilePre.ws === 'pre-wrap' && mobilePre.owa === 'anywhere' && !mobilePre.pageOverflow, mobilePre);
  ok('AC17: mint 3 (phone, mobile viewport) still produced a real token', !!mint3.plain, mint3.plain);
  await cmd('Emulation.setDeviceMetricsOverride', { width: 1200, height: 900, deviceScaleFactor: 1, mobile: false });

  // ================================================================================
  // AC18: --r-item resolves to 6px, both themes.
  // ================================================================================
  for (const theme of ['light', 'dark']) {
    const v = await evaluate(`(() => { document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)}); return getComputedStyle(document.documentElement).getPropertyValue('--r-item').trim(); })()`);
    ok(`AC18 (${theme}): --r-item resolves to 6px`, v === '6px', v);
  }

  // ================================================================================
  // AC15: Danger zone, LAST, on a disposable third login so its destruction cannot affect
  // anything checked above. Confirm-gated: zero network calls until the second click.
  // ================================================================================
  const disposable = await login(EMAIL);
  const [dName, ...dRest] = disposable.cookie.split('=');
  await cmd('Network.deleteCookies', { name: ckName, url: BASE });
  await cmd('Network.setCookie', { name: dName, value: dRest.join('='), url: BASE, httpOnly: true, secure: true, sameSite: 'Lax' });
  await navAccount();
  // mint one token on this disposable session too, so "revoke all" has something real to revoke
  await evaluate(`document.querySelector('.acct-navrow[data-section="security"]').click(); true`);
  await sleep(80);
  await evaluate(`document.querySelector('.acct-row[data-row="tokens"]').click(); true`);
  await sleep(80);
  await mintOne('for-revoke-all');
  await evaluate(`document.getElementById('tok-done') && document.getElementById('tok-done').click(); true`);

  await clickSection('danger');
  netLog.length = 0;
  await evaluate(`document.querySelector('[data-confirm-start="revokeAll"]').click(); true`);
  await sleep(150);
  const deleteCallsBeforeConfirm = netLog.filter(n => n.method === 'DELETE').length;
  ok('AC15: the FIRST click on "Revoke all" fires zero DELETE requests (confirm-gated)', deleteCallsBeforeConfirm === 0, netLog.map(n => n.method + ' ' + n.url));
  const sureVisible = await evaluate(`document.querySelector('[data-actions="revokeAll"]').textContent.includes('Sure?')`);
  ok('AC15: the confirm step actually shows "Sure?"', sureVisible, sureVisible);
  await evaluate(`document.querySelector('[data-actions="revokeAll"] [data-go]').click(); true`);
  for (let i = 0; i < 40; i++) {
    const t = await evaluate(`fetch('/account/tokens',{headers:{Accept:'application/json'}}).then(r=>r.json()).then(d=>d.tokens.length)`);
    if (t === 0) break; await sleep(200);
  }
  const tokAfterRevokeAll = await evaluate(`fetch('/account/tokens',{headers:{Accept:'application/json'}}).then(r=>r.json()).then(d=>d.tokens.length)`);
  ok('AC15: confirming "Revoke all" leaves GET /account/tokens empty', tokAfterRevokeAll === 0, tokAfterRevokeAll);

  netLog.length = 0;
  await evaluate(`document.querySelector('[data-confirm-start="signout"]').click(); true`);
  await sleep(150);
  const deleteCallsBeforeConfirm2 = netLog.filter(n => n.method === 'DELETE').length;
  ok('AC15: the FIRST click on "Sign out everywhere" fires zero DELETE requests (confirm-gated)', deleteCallsBeforeConfirm2 === 0, netLog.map(n => n.method + ' ' + n.url));
  await evaluate(`document.querySelector('[data-actions="signout"] [data-go]').click(); true`);
  await sleep(1200);
  const afterSignout = await fetch(BASE + '/auth/session', { headers: { Cookie: disposable.cookie } }).then(r => r.json());
  ok('AC15: "Sign out everywhere" ends with the current browser signed out (next /auth/session is unauthenticated)',
     afterSignout.authenticated !== true, afterSignout);
  const sessAfter = await fetch(BASE + '/auth/sessions', { headers: { Cookie: primary.cookie } }).then(r => r.status === 200 ? r.json() : { error: r.status });
  const othersLeft = (sessAfter.sessions || []).filter(s => !s.current).length;
  ok('AC15: zero OTHER sessions remain server-side after "Sign out everywhere"', othersLeft === 0, sessAfter);

} finally {
  clearTimeout(overall);
  try { ws?.close(); } catch {}
  done();
}
console.log(failed ? `\n${failed} case(s) failed` : '\nall account-page cases pass');
process.exit(failed ? 1 : 0);
