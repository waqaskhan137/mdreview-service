// admin-reskin-check.mjs — #282. Samples RENDERED OUTCOMES (computed style, measured geometry,
// AX-tree roles, DOM state) for web/app/admin.html in a real headless Chrome, both themes forced
// via data-theme. Zero-dep: Node's built-in WebSocket + fetch driving CDP, same shape as
// scripts/theme-check.mjs / (#333's) scripts/latex-canvas-check.mjs.
//
// admin.html's DATA comes from fetch() calls to admin-gated endpoints (/admin/users, .../blocklist,
// .../audit, every POST action) that this ticket does not own and the groom verified separately
// against origin/dev. Rather than reproduce the magic-link login + CSRF flow here, this installs a
// window.fetch stub via Page.addScriptToEvaluateOnNewDocument — it runs before ANY page script,
// including the pre-paint theme applier — so admin.html's own boot()/loadUsers()/doAction() code
// runs for real against a known fixture. Subresources (<link>, <script src>) never go through
// window.fetch, so the real theme.css/basecoat/account.js/session.js still load from the real
// hosted server: only the page's OWN data calls are intercepted.
//
//   node scripts/admin-reskin-check.mjs http://127.0.0.1:PORT
// (PORT serves a hosted instance; tests/admin_reskin_selfcheck.sh provisions it.)
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BASE = process.argv[2];
if (!BASE) { console.error('usage: admin-reskin-check.mjs <hosted-origin>'); process.exit(2); }
const ADMIN_URL = BASE.replace(/\/$/, '') + '/admin';

const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }

let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c ? '' : `  (${d})`)); if (!c) failed++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

const port = 9300 + (Date.now() % 500);
const profile = mkdtempSync(join(tmpdir(), 'admin-reskin-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
const done = () => { try { chrome.kill(); } catch {} try { rmSync(profile, { recursive: true, force: true }); } catch {} };
const overall = setTimeout(() => { console.error('admin-reskin-check: overall timeout (150s)'); done(); process.exit(2); }, 150000);
overall.unref();

// ---- the fixture + window.fetch stub, injected before every navigation on this tab ----------
// Five users (order is the render order, and the LAST row is deliberately the banned one — AC7's
// own wording, "Ban (or Unban on the banned row)", names that as the expected last-row case):
//   0 owner            owner@example.com        is_owner            -> roles "owner",   no actions
//   1 ME (admin only)  a.kerr@example.com        is_admin            -> roles "admin",   "you" marker
//   2 admin+super-read b.chen@example.com        is_admin+super_read -> roles "admin · super-read"
//   3 plain member     c.diaz@example.com        (neither)           -> roles "member"; the AC6/AC8 ban target
//   4 banned           d.omar@example.com        status=banned       -> roles "member"; the AC7 menu target
const FIXTURE_SCRIPT = `
(function(){
  var T0 = 1700000000;
  var users = [
    {uid:'owner:1',  email:'owner@example.com', status:'active', is_owner:true,  is_admin:true,  super_read:false, created:T0},
    {uid:'u:admin1', email:'a.kerr@example.com', status:'active', is_owner:false, is_admin:true,  super_read:false, created:T0+1000},
    {uid:'u:admin2', email:'b.chen@example.com', status:'active', is_owner:false, is_admin:true,  super_read:true,  created:T0+2000},
    {uid:'u:member1',email:'c.diaz@example.com', status:'active', is_owner:false, is_admin:false, super_read:false, created:T0+3000},
    {uid:'u:banned1',email:'d.omar@example.com', status:'banned', is_owner:false, is_admin:false, super_read:false, created:T0+4000}
  ];
  var blocklist = [
    {value:'spam@evil.example', kind:'email', note:'repeat abuse'},
    {value:'203.0.113.7', kind:'ip', note:''}
  ];
  var audit = [
    {ts:T0+5000, event:'login', actor:'owner:1', email:'owner@example.com', target:null, detail:null, ip:'203.0.113.5'},
    {ts:T0+5100, event:'admin_role_granted', actor:'owner:1', email:'owner@example.com', target:'u:admin1', detail:'value=true', ip:'203.0.113.5'}
  ];
  var ME_UID = 'u:admin1';
  var boot = (location.hash.match(/boot=([a-z0-9]+)/) || [])[1] || 'main';
  var jsonRes = function(obj, status){ return new Response(JSON.stringify(obj), {status: status||200, headers:{'Content-Type':'application/json'}}); };
  var orig = window.fetch.bind(window);
  window.fetch = function(input, init){
    var url = typeof input === 'string' ? input : (input && input.url) || '';
    var method = (init && init.method) || 'GET';
    var path = url.replace(/^https?:\\/\\/[^/]+/, '');
    if (path === '/auth/session') {
      if (boot === 'noauthplane') return Promise.resolve(jsonRes({}, 404));
      if (boot === 'unreachable') return Promise.reject(new TypeError('stub: simulated network failure'));
      if (boot === 'signedout') return Promise.resolve(jsonRes({authenticated:false}));
      return Promise.resolve(jsonRes({authenticated:true, uid:ME_UID, email:'a.kerr@example.com', is_admin:true, csrf:'stub-csrf'}));
    }
    if (path === '/admin/users' && method === 'GET') {
      if (boot === 'forbidden403') return Promise.resolve(jsonRes({error:'admin only'}, 403));
      return Promise.resolve(jsonRes({users:users}));
    }
    var m = path.match(/^\\/admin\\/users\\/([^/]+)\\/([a-z-]+)$/);
    if (m && method === 'POST') {
      var uid = decodeURIComponent(m[1]), action = m[2];
      var u = null; for (var i=0;i<users.length;i++) if (users[i].uid===uid) u = users[i];
      if (!u) return Promise.resolve(jsonRes({error:'no such user'}, 404));
      var body = {}; try { body = init && init.body ? JSON.parse(init.body) : {}; } catch(e){}
      if (action === 'ban') u.status = 'banned';
      else if (action === 'unban') u.status = 'active';
      else if (action === 'admin') u.is_admin = !!body.value;
      else if (action === 'super-read') u.super_read = !!body.value;
      return Promise.resolve(jsonRes({ok:true, uid:uid, action:action}));
    }
    if (path === '/admin/blocklist' && method === 'GET') return Promise.resolve(jsonRes({blocklist:blocklist}));
    if (path === '/admin/blocklist' && method === 'POST') {
      var b = {}; try { b = init && init.body ? JSON.parse(init.body) : {}; } catch(e){}
      blocklist.push({value:b.value, kind:b.kind, note:b.note||''});
      return Promise.resolve(jsonRes({ok:true, value:b.value, kind:b.kind}, 201));
    }
    m = path.match(/^\\/admin\\/blocklist\\/(.+)$/);
    if (m && method === 'DELETE') {
      var value = decodeURIComponent(m[1]);
      var before = blocklist.length;
      blocklist = blocklist.filter(function(x){ return x.value !== value; });
      return Promise.resolve(blocklist.length < before ? jsonRes({ok:true,value:value}) : jsonRes({error:'not blocklisted'},404));
    }
    if (path.indexOf('/admin/audit') === 0) return Promise.resolve(jsonRes({events:audit, next_before:null}));
    return orig(input, init);
  };
  // Resolve a design-token CSS value the way a real consumer sees it: a probe element, never
  // getComputedStyle(:root).getPropertyValue, which returns the raw light-dark(...) TEXT (#285).
  window.__tok = function(prop, value){
    var p = document.createElement('div');
    p.style.cssText = 'position:absolute;left:-9999px;top:-9999px;' + prop + ':' + value + ';';
    document.body.appendChild(p);
    var v = getComputedStyle(p).getPropertyValue(prop);
    p.remove();
    return v;
  };
})();
`;

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
  ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
  const cmd = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const evaluate = async expr => {
    const r = await cmd('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result?.exceptionDetails) throw new Error('page eval threw: ' +
      (r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text));
    return r.result?.result?.value;
  };
  const evalJSON = async expr => JSON.parse(await evaluate(expr));

  await cmd('Page.enable'); await cmd('Runtime.enable'); await cmd('DOM.enable'); await cmd('Accessibility.enable');
  // Headless defaults to an 800px viewport, which never exercises the 940px container cap and
  // sits close to the 767px mobile type-scale breakpoint. Pin a desktop width.
  await cmd('Emulation.setDeviceMetricsOverride', { width: 1200, height: 900, deviceScaleFactor: 1, mobile: false });
  await cmd('Page.addScriptToEvaluateOnNewDocument', { source: FIXTURE_SCRIPT });

  const READY_MAIN = `document.querySelectorAll('#panel tbody tr').length===5 && ` +
    `document.querySelectorAll('#blockpanel .blockrow').length===2 && ` +
    `document.querySelectorAll('#auditpanel tbody tr').length===2 && ` +
    `!!document.querySelector('#acct .acct-trig')`;

  // A URL that differs only in its fragment is a same-document navigation (no reload, no fresh
  // Page.addScriptToEvaluateOnNewDocument run) — the fixture's mutable state and closures would
  // survive across "navigations" and boot=<state> would silently keep serving whatever the FIRST
  // navigation resolved. Bounce through about:blank first so every call is a real document teardown.
  async function hardNav(url) {
    await cmd('Page.navigate', { url: 'about:blank' });
    await cmd('Page.navigate', { url });
  }
  async function navMain(hash) {
    await hardNav(ADMIN_URL + '#' + hash);
    for (let i = 0; i < 100; i++) {
      if (await evaluate(READY_MAIN)) return true;
      await sleep(150);
    }
    return false;
  }
  const ready = await navMain('boot=main');
  ok('admin.html loaded with the fixture rendered (probe is not vacuous)', ready,
     await evaluate(`document.readyState + ' rows=' + document.querySelectorAll('#panel tbody tr').length`));
  if (!ready) { console.log('\\naborting: nothing to sample'); throw new Error('fixture never rendered'); }

  // ================= structural + AT checks (theme-independent) =================
  const s = await evalJSON(`(() => {
    const q = sel => document.querySelector(sel);
    const qa = sel => Array.from(document.querySelectorAll(sel));
    const rect = el => el.getBoundingClientRect();
    const brandMark = q('.brand-mark'), brandWord = q('.brand-word'), brandBadge = q('.brand-badge');
    // innerText, NOT textContent: textContent walks every descendant text node including the
    // literal source of inline <script> tags (this file's own doc comments happen to say
    // "reviewer" while explaining why it is NOT a real role), which is not rendered text a user
    // ever sees. innerText follows layout/visibility, matching what the AC actually means.
    const noBack = !document.body.innerText.includes('\\u2190 reviews');
    const h1 = q('h1'), sub = q('.sub');
    const bodyRow = qa('#panel tbody tr')[0];
    const bodyCellW = bodyRow ? Array.from(bodyRow.children).map(td => rect(td).width) : [];
    const headRow = q('#panel thead tr');
    const headCells = headRow ? Array.from(headRow.children) : [];
    const roleTexts = qa('#panel tbody tr').map(tr => tr.children[2].textContent.trim());
    const blockH2 = q('#blockcard h2'), blockCaption = q('#blockcard .caption'), blockHr = q('#blockcard .hr');
    return JSON.stringify({
      brandMarkText: brandMark.textContent.trim(), brandMarkW: rect(brandMark).width, brandMarkH: rect(brandMark).height,
      brandMarkRadius: getComputedStyle(brandMark).borderRadius,
      brandWordText: brandWord.textContent.trim(),
      brandBadgeText: brandBadge.textContent.trim(),
      brandBadgeFont: getComputedStyle(brandBadge).fontFamily,
      brandBadgeBorderW: getComputedStyle(brandBadge).borderWidth,
      brandBadgeBorderStyle: getComputedStyle(brandBadge).borderStyle,
      noBack, acctPresent: !!q('#acct .acct-trig'),
      h1Text: h1.textContent.trim(), h1Size: getComputedStyle(h1).fontSize,
      subText: sub.textContent.trim(), subColor: getComputedStyle(sub).color,
      bodyCellW, colGap: bodyRow ? getComputedStyle(bodyRow).columnGap : null,
      headBorderW: headRow ? getComputedStyle(headRow).borderBottomWidth : null,
      headBorderStyle: headRow ? getComputedStyle(headRow).borderBottomStyle : null,
      bodyBorderW: bodyRow ? getComputedStyle(bodyRow).borderBottomWidth : null,
      headFont: headCells[0] ? getComputedStyle(headCells[0]).fontFamily : null,
      headTransform: headCells[0] ? getComputedStyle(headCells[0]).textTransform : null,
      headLetterSpacing: headCells[0] ? getComputedStyle(headCells[0]).letterSpacing : null,
      lastHeadText: headCells[4] ? headCells[4].textContent.trim() : null,
      lastHeadAriaLabel: headCells[4] ? headCells[4].getAttribute('aria-label') : null,
      roleTexts,
      noReviewerWord: !document.body.innerText.includes('reviewer'),
      noSuspendedWord: !document.body.innerText.includes('SUSPENDED'),
      noBadgeClass: qa('.badge').length === 0,
      blockH2: blockH2.textContent.trim(), blockCaption: blockCaption.textContent.trim(),
      blockHrBg: getComputedStyle(blockHr).backgroundColor,
      noCardAnywhere: qa('.card').length === 0,
      blockValH: rect(q('#blockval')).height, blockKindH: rect(q('#blockkind')).height, blockBtnH: rect(q('#blockbtn')).height,
      bodyFont: getComputedStyle(document.body).fontFamily,
      bodyFontSize: getComputedStyle(document.body).fontSize,
      tBodyTok: window.__tok('font-size','var(--t-body)'),
      tEyebrowTok: window.__tok('font-size','var(--t-eyebrow)'),
      rControlTok: window.__tok('border-radius','var(--r-control)'),
    });
  })()`);

  ok('AC1: brand mark is "md", 24x24, radius=--r-control', s.brandMarkText === 'md' && Math.abs(s.brandMarkW-24)<=1 && Math.abs(s.brandMarkH-24)<=1 && s.brandMarkRadius===s.rControlTok, JSON.stringify(s));
  ok('AC1: wordmark text is "mdreview"', s.brandWordText === 'mdreview', s.brandWordText);
  ok('AC1: ADMIN badge text + mono font + border', s.brandBadgeText === 'ADMIN' && s.brandBadgeFont.startsWith('"Geist Mono"') && s.brandBadgeBorderW==='1px' && s.brandBadgeBorderStyle==='solid', JSON.stringify(s));
  ok('AC1: no "← reviews" element anywhere', s.noBack, 'noBack=false');
  ok('AC1: #acct mount present (account.js rendered a trigger)', s.acctPresent, 'acctPresent=false');
  ok('AC2: h1 is exactly "People", sized --t-title', s.h1Text === 'People', s.h1Text);
  ok('AC2: subtitle text exact', s.subText === 'Everyone on this instance, and who they can act as.', s.subText);
  ok('AC3: Status/Joined/trailing columns 112/104/88px (±2px)', Math.abs(s.bodyCellW[1]-112)<=2 && Math.abs(s.bodyCellW[3]-104)<=2 && Math.abs(s.bodyCellW[4]-88)<=2, JSON.stringify(s.bodyCellW));
  ok('AC3: User:Roles ratio ≈ 1.4:1 (±5%)', Math.abs((s.bodyCellW[0]/s.bodyCellW[2])-1.4) <= 0.07, JSON.stringify(s.bodyCellW));
  ok('AC3: 16px column gutters', s.colGap === '16px', s.colGap);
  ok('AC3: header row bottom border 1px solid; body rows have none', s.headBorderW==='1px' && s.headBorderStyle==='solid' && s.bodyBorderW==='0px', JSON.stringify(s));
  ok('AC3: header cells mono/uppercase/0.1em tracking', s.headFont.startsWith('"Geist Mono"') && s.headTransform==='uppercase' && Math.abs(parseFloat(s.headLetterSpacing)-0.1*parseFloat(s.tEyebrowTok))<0.3, JSON.stringify(s));
  ok('AC3: fifth header cell text-empty but aria-labelled Actions', s.lastHeadText==='' && s.lastHeadAriaLabel==='Actions', JSON.stringify([s.lastHeadText,s.lastHeadAriaLabel]));
  ok('AC5: role texts owner/admin/admin·super-read/member (banned row also member)', JSON.stringify(s.roleTexts) === JSON.stringify(['owner','admin','admin · super-read','member','member']), JSON.stringify(s.roleTexts));
  ok('AC5: word "reviewer" appears nowhere; SUSPENDED appears nowhere; no .badge class', s.noReviewerWord && s.noSuspendedWord && s.noBadgeClass, JSON.stringify(s));
  ok('AC9: Blocklist h2 + exact caption', s.blockH2==='Blocklist' && s.blockCaption==='refused at the sign-in link step', JSON.stringify(s));
  ok('AC9: hairline present (non-transparent)', s.blockHrBg !== 'rgba(0, 0, 0, 0)' && s.blockHrBg !== 'transparent', s.blockHrBg);
  ok('AC9: no Basecoat .card ancestor anywhere on the page', s.noCardAnywhere, 'a .card element exists');
  ok('AC9: value/kind/Block controls compute 34px tall', Math.abs(s.blockValH-34)<=1 && Math.abs(s.blockKindH-34)<=1 && Math.abs(s.blockBtnH-34)<=1, JSON.stringify([s.blockValH,s.blockKindH,s.blockBtnH]));
  // Chrome's font-family serializer only quotes names that need it (spaces/keywords); "Geist" is
  // a bare ident, so the computed value drops the quotes ("Geist Mono" keeps them, checked above).
  ok('AC10: body font begins Geist, size = --t-body', /^"?Geist"?(,|$)/.test(s.bodyFont) && s.bodyFontSize === s.tBodyTok, JSON.stringify(s));

  // ---- AC3 (AT half): the grid-ified table is still exposed as role table/row/columnheader/cell ----
  const ax = await cmd('Accessibility.getFullAXTree');
  const nodes = (ax.result && ax.result.nodes) || [];
  const roleCounts = {};
  for (const n of nodes) {
    if (n.ignored) continue;
    const role = n.role && n.role.value;
    if (!role) continue;
    roleCounts[role] = (roleCounts[role] || 0) + 1;
  }
  ok('AC3 (AT): accessibility tree exposes table/row/columnheader/cell',
     (roleCounts.table || 0) >= 1 && (roleCounts.row || 0) >= 6 &&
     (roleCounts.columnheader || 0) >= 5 && (roleCounts.cell || 0) >= 20,
     JSON.stringify(roleCounts));

  // ================= per-theme colour sweep (both themes forced via data-theme) =================
  async function themeSnapshot(theme) {
    return evalJSON(`(() => {
      document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)});
      const cs = (sel, prop) => getComputedStyle(document.querySelector(sel)).getPropertyValue(prop);
      const bar = document.getElementById('confirmbar');
      const prevDisplay = bar.style.display;
      bar.style.display = 'flex';
      const confirmBg = getComputedStyle(bar).backgroundColor, confirmBorder = getComputedStyle(bar).borderColor;
      bar.style.display = prevDisplay;
      const activeDot = document.querySelector('.stat-active .statdot');
      const bannedDot = document.querySelector('.stat-banned .statdot');
      const bannedRow = document.querySelector('tr.rowbanned');
      return JSON.stringify({
        accent: window.__tok('background-color','var(--accent)'),
        brandMarkBg: cs('.brand-mark','background-color'),
        badgeColor: cs('.brand-badge','color'),
        badgeBorderColor: cs('.brand-badge','border-color'),
        subColor: cs('.sub','color'),
        textMuted: window.__tok('background-color','var(--text-muted)'),
        textSubtle: window.__tok('background-color','var(--text-subtle)'),
        headColor: cs('#panel thead th','color'),
        headBorderColor: getComputedStyle(document.querySelector('#panel thead tr')).borderBottomColor,
        border: window.__tok('background-color','var(--border)'),
        success: window.__tok('background-color','var(--success)'),
        activeDotBg: activeDot ? getComputedStyle(activeDot).backgroundColor : null,
        activeTextColor: cs('.stat-active','color'),
        bannedDotBorder: bannedDot ? getComputedStyle(bannedDot).borderColor : null,
        bannedDotBg: bannedDot ? getComputedStyle(bannedDot).backgroundColor : null,
        bannedTextColor: cs('.stat-banned','color'),
        rolesColor: cs('.roles','color'),
        dangerBg: window.__tok('background-color','var(--danger-bg)'),
        dangerBorder: window.__tok('border-color','var(--danger-border)'),
        confirmBg, confirmBorder,
        bannedRowColor: bannedRow ? getComputedStyle(bannedRow.querySelector('.email')).color : null,
        bannedRowOpacity: bannedRow ? getComputedStyle(bannedRow).opacity : null
      });
    })()`);
  }
  const light = await themeSnapshot('light');
  const dark = await themeSnapshot('dark');

  ok('theme positive control: --accent differs light vs dark, and is never transparent',
     light.accent !== dark.accent && light.accent !== 'rgba(0, 0, 0, 0)' && dark.accent !== 'rgba(0, 0, 0, 0)',
     `light=${light.accent} dark=${dark.accent}`);

  for (const [theme, t] of [['light', light], ['dark', dark]]) {
    ok(`AC1 (${theme}): brand mark bg = --accent`, t.brandMarkBg === t.accent, `${t.brandMarkBg} vs ${t.accent}`);
    ok(`AC1 (${theme}): ADMIN badge color/border = --accent`, t.badgeColor === t.accent && t.badgeBorderColor === t.accent, JSON.stringify(t));
    ok(`AC2 (${theme}): subtitle color = --text-muted`, t.subColor === t.textMuted, `${t.subColor} vs ${t.textMuted}`);
    ok(`AC3 (${theme}): header text color = --text-subtle, border = --border`, t.headColor === t.textSubtle && t.headBorderColor === t.border, JSON.stringify(t));
    ok(`AC4 (${theme}): active dot+text = --success`, t.activeDotBg === t.success && t.activeTextColor === t.success, JSON.stringify(t));
    ok(`AC4 (${theme}): banned dot transparent bg, --text-subtle border+text`, t.bannedDotBg === 'rgba(0, 0, 0, 0)' && t.bannedDotBorder === t.textSubtle && t.bannedTextColor === t.textSubtle, JSON.stringify(t));
    ok(`AC4 (${theme}): banned row email color = --text-muted, opacity 1`, t.bannedRowColor === t.textMuted && t.bannedRowOpacity === '1', JSON.stringify(t));
    ok(`AC5 (${theme}): roles column color = --text-muted`, t.rolesColor === t.textMuted, `${t.rolesColor} vs ${t.textMuted}`);
    ok(`AC6 (${theme}): confirm bar bg/border = --danger-bg/--danger-border`, t.confirmBg === t.dangerBg && t.confirmBorder === t.dangerBorder, JSON.stringify(t));
  }

  // ================= AC7: open the LAST row's (banned) menu — geometry + content =================
  await evaluate(`(() => {
    const rows = document.querySelectorAll('#panel tbody tr');
    rows[rows.length-1].querySelector('.mtrig').click();
    return true;
  })()`);
  await sleep(150);
  const menu = await evalJSON(`(() => {
    const rows = document.querySelectorAll('#panel tbody tr');
    const row = rows[rows.length-1];
    const trig = row.querySelector('.mtrig');
    const popover = document.getElementById(trig.getAttribute('aria-controls'));
    const menuEl = popover.querySelector('[role=menu]');
    const items = Array.from(menuEl.querySelectorAll('[role=menuitem],[role=menuitemcheckbox]')).map(b => ({
      role: b.getAttribute('role'), text: b.textContent.replace('\\u2713','').trim(), checked: b.getAttribute('aria-checked')
    }));
    const headingEl = menuEl.querySelector('[role=heading]');
    const tRect = trig.getBoundingClientRect(), pRect = popover.getBoundingClientRect();
    return JSON.stringify({
      trigH: tRect.height, ariaHidden: popover.getAttribute('aria-hidden'),
      svgPath: trig.querySelector('svg path') ? trig.querySelector('svg path').getAttribute('d') : null,
      heading: headingEl ? headingEl.textContent.trim() : null,
      items,
      rightDiff: Math.abs(pRect.right - tRect.right),
      insideViewport: pRect.left >= 0 && pRect.right <= window.innerWidth && pRect.top >= 0 && pRect.bottom <= window.innerHeight
    });
  })()`);
  ok('AC7: trigger is 28px tall with the chevron path', Math.abs(menu.trigH-28)<=1 && menu.svgPath==='m6 9 6 6 6-6', JSON.stringify(menu));
  ok('AC7: menu open (aria-hidden=false), right-aligned within 1px, fully inside viewport',
     menu.ariaHidden==='false' && menu.rightDiff<=1 && menu.insideViewport, JSON.stringify(menu));
  const wantItems = [
    { role: 'menuitemcheckbox', text: 'Admin', checked: 'false' },
    { role: 'menuitemcheckbox', text: 'Super-read', checked: 'false' },
    { role: 'menuitem', text: 'Revoke tokens', checked: null },
    { role: 'menuitem', text: 'Revoke sessions', checked: null },
    { role: 'menuitem', text: 'Unban', checked: null },
  ];
  ok('AC7: menu content unchanged from #179 (Role heading, Admin/Super-read checkboxes, Revoke tokens/sessions, Unban on the banned row)',
     menu.heading === 'Role' && JSON.stringify(menu.items) === JSON.stringify(wantItems), JSON.stringify(menu));
  await evaluate(`document.body.click(); true`); // close the popover (outside click)
  await sleep(100);

  // ================= AC6 + AC8: Ban the member row -> confirm -> toast -> wait -> Undo =================
  await evaluate(`document.documentElement.setAttribute('data-theme','light'); true`);
  await evaluate(`(() => {
    const row = document.querySelectorAll('#panel tbody tr')[3]; // c.diaz@example.com
    row.querySelector('.mtrig').click();
    const popover = document.getElementById(row.querySelector('.mtrig').getAttribute('aria-controls'));
    popover.querySelector('[data-action=ban]').click();
    return true;
  })()`);
  await sleep(150);
  const confirmInfo = await evalJSON(`(() => {
    const bar = document.getElementById('confirmbar');
    return JSON.stringify({
      visible: getComputedStyle(bar).display !== 'none',
      msg: bar.querySelector('.msg').textContent,
      cfyText: document.getElementById('cfy').textContent,
      cfnText: document.getElementById('cfn').textContent,
      cfyBg: getComputedStyle(document.getElementById('cfy')).backgroundColor,
      cfyH: document.getElementById('cfy').getBoundingClientRect().height,
      cfnH: document.getElementById('cfn').getBoundingClientRect().height,
      cfnBorder: getComputedStyle(document.getElementById('cfn')).borderColor,
      cfnBg: getComputedStyle(document.getElementById('cfn')).backgroundColor,
      expectedDanger: window.__tok('background-color','var(--danger)'),
      expectedBorder: window.__tok('border-color','var(--border)'),
      expectedSurface: window.__tok('background-color','var(--surface)')
    });
  })()`);
  const WANT_MSG = "Ban c.diaz@example.com? They lose access immediately: open sessions and API tokens stop working. " +
                   "Their reviews are kept, and you can undo this for 10 seconds.";
  ok('AC6: confirm bar shows the exact shipped Ban sentence', confirmInfo.visible && confirmInfo.msg === WANT_MSG, confirmInfo.msg);
  ok('AC6: primary button reads "Ban", danger bg, 30px; secondary reads "Cancel", 30px',
     confirmInfo.cfyText === 'Ban' && confirmInfo.cfyBg === confirmInfo.expectedDanger && Math.abs(confirmInfo.cfyH-30)<=1 &&
     confirmInfo.cfnText === 'Cancel' && Math.abs(confirmInfo.cfnH-30)<=1 && confirmInfo.cfnBorder === confirmInfo.expectedBorder && confirmInfo.cfnBg === confirmInfo.expectedSurface,
     JSON.stringify(confirmInfo));
  ok('AC6: no "Suspend" wording anywhere', !(await evaluate(`document.body.innerText.includes('Suspend')`)), 'found "Suspend"');

  const t0 = Date.now();
  await evaluate(`document.getElementById('cfy').click(); true`);
  let bannedNow = false;
  for (let i = 0; i < 40; i++) {
    bannedNow = await evaluate(`document.querySelectorAll('#panel tbody tr')[3].textContent.includes('BANNED')`);
    if (bannedNow) break;
    await sleep(150);
  }
  ok('AC8: confirming Ban re-renders the row as BANNED', bannedNow, 'row never showed BANNED');
  const toastEarly = await evalJSON(`JSON.stringify({
    present: document.getElementById('toaster').textContent.includes('Banned c.diaz@example.com'),
    hasUndo: !!document.getElementById('toaster').querySelector('[data-toast-cancel]')
  })`);
  ok('AC8: toast titled "Banned c.diaz@example.com" with an Undo control appears', toastEarly.present && toastEarly.hasUndo, JSON.stringify(toastEarly));

  const elapsed = Date.now() - t0;
  if (elapsed < 9300) await sleep(9300 - elapsed);
  const toastLate = await evalJSON(`JSON.stringify({
    present: document.getElementById('toaster').textContent.includes('Banned c.diaz@example.com'),
    hasUndo: !!document.getElementById('toaster').querySelector('[data-toast-cancel]')
  })`);
  ok('AC8: toast (and its Undo control) still present ~9s after firing (promised 10s window)', toastLate.present && toastLate.hasUndo, JSON.stringify(toastLate));

  await evaluate(`document.getElementById('toaster').querySelector('[data-toast-cancel]').click(); true`);
  let activeAgain = false;
  for (let i = 0; i < 40; i++) {
    activeAgain = await evaluate(`document.querySelectorAll('#panel tbody tr')[3].textContent.includes('ACTIVE')`);
    if (activeAgain) break;
    await sleep(150);
  }
  ok('AC8: clicking Undo issues the unban; row returns to ACTIVE', activeAgain, 'row never returned to ACTIVE');

  // ================= AC12: reduced motion, on a FRESH navigation (no leftover toast) =================
  await cmd('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
  const readyRM = await navMain('boot=main');
  ok('AC12: fresh navigation under reduced-motion rendered the fixture', readyRM, 'fixture never rendered');
  const motion = await evalJSON(`(() => {
    const mtrig = document.querySelector('.mtrig');
    const ctl = document.getElementById('blockbtn');
    const animEls = Array.from(document.querySelectorAll('*')).filter(el => getComputedStyle(el).animationName !== 'none');
    return JSON.stringify({
      mtrigDur: getComputedStyle(mtrig).transitionDuration,
      ctlDur: getComputedStyle(ctl).transitionDuration,
      anyAnim: animEls.length > 0,
      animEls: animEls.slice(0,5).map(el => el.tagName + '.' + el.className + '#' + el.id + ' anim=' + getComputedStyle(el).animationName + ' dur=' + getComputedStyle(el).animationDuration)
    });
  })()`);
  ok('AC12: Manage trigger + Block button collapse to 0.01ms under reduced motion',
     parseFloat(motion.mtrigDur) <= 0.001 && parseFloat(motion.ctlDur) <= 0.001, JSON.stringify(motion));
  ok('AC12: no element has an active keyframe animation', !motion.anyAnim, JSON.stringify(motion));
  await cmd('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });

  // ================= AC11: the four shipped boot-state notices, unchanged strings =================
  async function noticeAt(hash) {
    await hardNav(ADMIN_URL + '#' + hash);
    for (let i = 0; i < 40; i++) {
      const t = await evaluate(`(document.querySelector('.notice b')||{}).textContent||''`);
      if (t) return evalJSON(`JSON.stringify({title: document.querySelector('.notice b').textContent, body: (document.querySelector('.notice').textContent||'').replace(document.querySelector('.notice b').textContent,'').trim(), linkText: document.querySelector('.notice a') ? document.querySelector('.notice a').textContent.trim() : null})`);
      await sleep(150);
    }
    return null;
  }
  const n1 = await noticeAt('boot=noauthplane');
  ok('AC11: no-auth-plane notice unchanged', !!n1 && n1.title === 'The admin console is not available on this build.' && n1.body === 'It manages accounts, which only the hosted service has.', JSON.stringify(n1));
  const n2 = await noticeAt('boot=unreachable');
  ok('AC11: unreachable notice unchanged', !!n2 && n2.title === 'Could not reach the service.' && n2.body === 'You have not been signed out. Reload to retry.', JSON.stringify(n2));
  const n3 = await noticeAt('boot=signedout');
  ok('AC11: signed-out notice unchanged (sign-in link)', !!n3 && n3.title === 'Sign in to continue' && n3.linkText && n3.linkText.includes('Go to sign in'), JSON.stringify(n3));
  const n4 = await noticeAt('boot=forbidden403');
  ok('AC11: 403 notice unchanged', !!n4 && n4.title === "You don't have admin access." && n4.body === 'This area is for administrators.', JSON.stringify(n4));

} finally {
  clearTimeout(overall);
  try { ws?.close(); } catch {}
  done();
}
console.log(failed ? `\n${failed} case(s) failed` : '\nall admin re-skin cases pass');
process.exit(failed ? 1 : 0);
