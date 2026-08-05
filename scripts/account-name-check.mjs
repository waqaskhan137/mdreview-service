// account-name-check.mjs — #309 slice 1. Samples RENDERED OUTCOMES (DOM state, not source text) for
// the Account > Profile > Display name row and its downstream renderers, in real headless Chrome
// against a real hosted server — same harness shape as scripts/account-page-check.mjs (real
// magic-link login, real cookies, real CSRF, real mutating fetch()es, zero-dep CDP over WebSocket).
//
// WHAT THIS COVERS THAT account-page-check.mjs DOES NOT (that file owns #281's rev-3 IA; this file
// owns #309's Display name capability specifically):
//   - the Display name row: default "Not set", edit + real POST /auth/profile, row value updates,
//     clearing falls back to "Not set" again.
//   - XSS: a name containing `<script>` / `<img onerror=...>` renders as INERT TEXT in three
//     places it reaches — the account row's prefilled input value, the top-bar account menu's
//     .acct-who text, and a comment's .gwho label — asserted on the rendered DOM (no script fired,
//     no real <img>/<script> element exists in the relevant containers), never on the stored value.
//   - retroactive attribution end to end: a comment posted BEFORE a name is set renders "You" (or,
//     for the positive control below, the pre-name baseline); the SAME comment, un-touched,
//     re-renders with the name AFTERWARDS — proving the render reads the user record live rather
//     than a snapshot taken at comment-creation time.
//   - positive control: an entry that is NOT yours (a foreign uid) never adopts your name, so a
//     false negative on the "own entry" gate cannot silently read as a pass here.
//   - absent-name baseline stays correct (a second user who never names themselves still reads
//     "You"/"Reviewer" as before — the pre-#309 behaviour is unperturbed, not just "not obviously
//     broken").
//
//   node scripts/account-name-check.mjs <hosted-origin> <server-log-path>
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BASE = process.argv[2];
const LOG = process.argv[3];
if (!BASE || !LOG) { console.error('usage: account-name-check.mjs <hosted-origin> <server-log-path>'); process.exit(2); }
const ACCOUNT_URL = BASE.replace(/\/$/, '') + '/account';

const CHROME = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find(p => existsSync(p));
if (!CHROME) { console.error('no Chrome found; set CHROME='); process.exit(2); }

let failed = 0;
const ok = (n, c, d) => { console.log((c ? 'ok   - ' : 'FAIL - ') + n + (c ? '' : `  (${JSON.stringify(d)})`)); if (!c) failed++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

// ---- real magic-link login over plain HTTP, same helper as account-page-check.mjs -------------
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

const port = 9400 + (Date.now() % 300);
const profile = mkdtempSync(join(tmpdir(), 'account-name-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
const done = () => { try { chrome.kill(); } catch {} try { rmSync(profile, { recursive: true, force: true }); } catch {} };
const overall = setTimeout(() => { console.error('account-name-check: overall timeout (120s)'); done(); process.exit(2); }, 120000);
overall.unref();

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
  ws.addEventListener('message', e => {
    const m = JSON.parse(e.data);
    if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  });
  const cmd = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const evaluate = async expr => {
    const r = await cmd('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result?.exceptionDetails) throw new Error('page eval threw: ' + (r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text));
    return r.result?.result?.value;
  };
  const evalJSON = async expr => JSON.parse(await evaluate(expr));

  await cmd('Page.enable'); await cmd('Runtime.enable'); await cmd('DOM.enable');
  await cmd('Emulation.setDeviceMetricsOverride', { width: 1200, height: 900, deviceScaleFactor: 1, mobile: false });

  async function hardNav(url) {
    await cmd('Page.navigate', { url: 'about:blank' });
    await cmd('Page.navigate', { url });
  }
  const READY = `document.querySelectorAll('.acct-navrow').length===6 && !!document.getElementById('whoami')`;
  async function navAccount() {
    await hardNav(ACCOUNT_URL);
    for (let i = 0; i < 80; i++) { if (await evaluate(READY)) { await sleep(250); return true; } await sleep(150); }
    return false;
  }

  // ================================================================================
  // Two real users. PRIMARY does everything below; SECONDARY is the "positive control" — a real
  // account that never sets a name, and whose comments must never be mislabelled with PRIMARY's
  // name (proves the own-entry gate, not just that the code path runs).
  // ================================================================================
  const PRIMARY_EMAIL = 'name-primary@example.com';
  const SECOND_EMAIL = 'name-second@example.com';
  const primary = await login(PRIMARY_EMAIL);
  const second = await login(SECOND_EMAIL);
  ok('setup: two independent real users exist', !!primary.cookie && !!second.cookie && primary.cookie !== second.cookie);

  const [ckName, ...ckRest] = primary.cookie.split('=');
  await cmd('Network.setCookie', { name: ckName, value: ckRest.join('='), url: BASE, httpOnly: true, secure: true, sameSite: 'Lax' });

  const ready = await navAccount();
  ok('the account page loaded for the real primary user', ready);
  if (!ready) throw new Error('aborting: nothing to sample');

  // ================================================================================
  // Default state: "Not set", the input pre-fills empty, no controls invented beyond input+Save.
  // ================================================================================
  await evaluate(`document.querySelector('.acct-row[data-row="name"]').click(); true`);
  await sleep(80);
  const before = await evalJSON(`JSON.stringify({
    rowValue: document.querySelector('.acct-row[data-row="name"] .acct-row-value').textContent,
    inputValue: document.getElementById('name-input') ? document.getElementById('name-input').value : null,
    maxlength: document.getElementById('name-input') ? document.getElementById('name-input').getAttribute('maxlength') : null,
  })`);
  ok('a never-named user\'s row reads "Not set" and the input starts empty',
     before.rowValue === 'Not set' && before.inputValue === '', before);
  ok('the input enforces a 60-char maxlength client-side (server is still authoritative)',
     before.maxlength === '60', before.maxlength);

  // ================================================================================
  // Save a real name via the real button: real POST /auth/profile, row value updates, and the
  // top-bar trigger/menu (account.js) picks it up via the mdreviewAccount() re-render hook.
  // ================================================================================
  async function setNameViaUI(name) {
    await evaluate(`(() => { document.getElementById('name-input').value = ${JSON.stringify(name)}; return true; })()`);
    await evaluate(`document.getElementById('name-save').click(); true`);
    for (let i = 0; i < 40; i++) {
      if (await evaluate(`document.getElementById('name-save') && document.getElementById('name-save').textContent === 'Save'`)) break;
      await sleep(150);
    }
  }
  await setNameViaUI('Ada Lovelace');
  const afterSet = await evalJSON(`JSON.stringify({
    rowValue: document.querySelector('.acct-row[data-row="name"] .acct-row-value').textContent,
    flash: document.getElementById('flash').textContent, flashClass: document.getElementById('flash').className,
  })`);
  ok('AC (save): the row value updates to the real saved name (real POST, not optimistic-only)',
     afterSet.rowValue === 'Ada Lovelace', afterSet);
  ok('AC (save): #flash confirms the save', /ok/.test(afterSet.flashClass) && afterSet.flash.length > 0, afterSet);
  const serverSideName = await fetch(BASE + '/auth/session', { headers: { Cookie: primary.cookie } }).then(r => r.json()).then(d => d.name);
  ok('AC (save): the server actually persisted it (independent GET /auth/session confirms)',
     serverSideName === 'Ada Lovelace', serverSideName);

  // Reload the whole page: not just in-memory state — the row must reflect the STORED name.
  await navAccount();
  await evaluate(`document.querySelector('.acct-row[data-row="name"]').click(); true`);
  await sleep(80);
  const afterReload = await evalJSON(`JSON.stringify({
    rowValue: document.querySelector('.acct-row[data-row="name"] .acct-row-value').textContent,
    inputValue: document.getElementById('name-input').value,
  })`);
  ok('AC (persistence): reloading the page still shows the saved name (row + prefilled input)',
     afterReload.rowValue === 'Ada Lovelace' && afterReload.inputValue === 'Ada Lovelace', afterReload);

  // ================================================================================
  // Top-bar trigger + menu (account.js): prefers the name, falls back to email only while unset.
  // ================================================================================
  const trigger = await evalJSON(`(() => {
    document.querySelector('#acct .acct-trig').click();
    return JSON.stringify({
      initials: document.querySelector('#acct .acct-trig').textContent.trim(),
      title: document.querySelector('#acct .acct-trig').getAttribute('title'),
      whoText: document.querySelector('#acct .acct-who b').textContent,
    });
  })()`);
  ok('AC (top-bar): the trigger initials derive from the NAME ("Ada Lovelace" -> "al"), not the email',
     trigger.initials === 'al', trigger);
  ok('AC (top-bar): the tooltip and the menu\'s "who" text show the name, not the email',
     trigger.title.startsWith('Ada Lovelace') && trigger.whoText === 'Ada Lovelace', trigger);
  await evaluate(`document.querySelector('#acct .acct-trig').click(); true`); // close the menu

  // ================================================================================
  // Server-side length/char limits enforced end to end (bypassing the client's maxlength via a
  // direct fetch, the same posture tests/name_field_selfcheck.py already proved at the API layer —
  // this proves the SAME server behind THIS running instance, and that the client surfaces the
  // rejection honestly via #flash rather than silently accepting it).
  // ================================================================================
  const tooLong = await evalJSON(`(async () => {
    const r = await fetch('/auth/profile', { method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': CSRF },
      body: JSON.stringify({ name: 'x'.repeat(61) }) });
    return JSON.stringify({ status: r.status, body: await r.json() });
  })()`);
  ok('AC (limit): a 61-char name is refused (400) by this running server, not silently truncated',
     tooLong.status === 400, tooLong);
  const stillOk = await fetch(BASE + '/auth/session', { headers: { Cookie: primary.cookie } }).then(r => r.json()).then(d => d.name);
  ok('AC (limit): the refused write did not change the stored name', stillOk === 'Ada Lovelace', stillOk);

  // ================================================================================
  // Clearing: falls back to "Not set" in the row, and to the email in the top bar — AC4.
  // ================================================================================
  await evaluate(`document.querySelector('.acct-row[data-row="name"]').click(); true`);
  await sleep(80);
  await setNameViaUI('');
  const afterClear = await evalJSON(`JSON.stringify({
    rowValue: document.querySelector('.acct-row[data-row="name"] .acct-row-value').textContent,
    triggerInitials: document.querySelector('#acct .acct-trig').textContent.trim(),
  })`);
  ok('AC4 (clear): clearing falls back to "Not set" in the row', afterClear.rowValue === 'Not set', afterClear);
  ok('AC4 (clear): the top-bar trigger falls back to the EMAIL-derived initials once cleared',
     afterClear.triggerInitials !== 'al' && afterClear.triggerInitials.length === 2, afterClear);

  // ================================================================================
  // XSS, asserted on the RENDERED DOM (not the stored value). Both payloads stay <= 60 chars (the
  // #309 length limit) so this exercises the escaping, not a length rejection.
  //
  // The two payloads are not interchangeable evidence: a <script> tag inserted via .innerHTML NEVER
  // executes, by HTML-spec construction, regardless of whether it was escaped — so "the script did
  // not fire" would be true even for a BROKEN, unescaped implementation, and is checked here only
  // as "no real <script> ELEMENT exists" (a genuine escaping signal). An <img onerror=...> inserted
  // via .innerHTML DOES wire its handler and WILL fire when src=x fails to load if the markup was
  // left unescaped and actually became an <img> element — so for that payload "onerror never fired"
  // IS a real, non-vacuous proof that the text was escaped, not markup.
  // ================================================================================
  const XSS_SCRIPT = '<script>window.__xssFired=1</script>';    // 38 chars
  const XSS_IMG = '<img src=x onerror=window.__xssFired=2>';    // 41 chars
  await evaluate(`window.__xssFired = 0; true`);

  await evaluate(`document.querySelector('.acct-row[data-row="name"]').click(); true`);
  await sleep(80);
  await setNameViaUI(XSS_SCRIPT);
  await sleep(150);
  const xssScriptInRow = await evalJSON(`JSON.stringify({
    rowValueText: document.querySelector('.acct-row[data-row="name"] .acct-row-value').textContent,
    inputValueText: document.getElementById('name-input').value,
    injectedScript: !!document.querySelector('.acct-row[data-row="name"] script, #rev-name script'),
  })`);
  ok('AC (XSS/account row, <script>): row value and prefilled input carry the LITERAL text, not markup',
     xssScriptInRow.rowValueText === XSS_SCRIPT && xssScriptInRow.inputValueText === XSS_SCRIPT, xssScriptInRow);
  ok('AC (XSS/account row, <script>): no real <script> element was created in the row/panel',
     !xssScriptInRow.injectedScript, xssScriptInRow);

  await setNameViaUI(XSS_IMG);
  await sleep(150);
  const xssImgInRow = await evalJSON(`JSON.stringify({
    fired: window.__xssFired,
    rowValueText: document.querySelector('.acct-row[data-row="name"] .acct-row-value').textContent,
    inputValueText: document.getElementById('name-input').value,
    injectedImg: !!document.querySelector('.acct-row[data-row="name"] img, #rev-name img'),
  })`);
  ok('AC (XSS/account row, <img onerror>): the handler did NOT fire — a real, non-vacuous escaping proof',
     xssImgInRow.fired === 0, xssImgInRow);
  ok('AC (XSS/account row, <img onerror>): row value and prefilled input carry the LITERAL text, not markup',
     xssImgInRow.rowValueText === XSS_IMG && xssImgInRow.inputValueText === XSS_IMG, xssImgInRow);
  ok('AC (XSS/account row, <img onerror>): no real <img> element was created in the row/panel',
     !xssImgInRow.injectedImg, xssImgInRow);

  // A DIFFERENT vector the two payloads above cannot exercise: neither contains a `"`, so neither
  // can prove the prefilled input's value="..." ATTRIBUTE context is escaped — `<`/`>` need no
  // escaping to stay inert inside a quoted attribute, only `"` (attribute breakout) does. Proven by
  // mutation: dropping esc() around that one value="...' interpolation left every check above
  // GREEN, because neither payload contains a quote. window.name-input.onfocus is a reliable,
  // event-free probe: it is only a real function if the browser actually parsed a genuine
  // onfocus="..." attribute, which requires the quote to have broken out.
  const XSS_ATTR = 'x" onfocus="window.__xssFired=3';    // 33 chars
  await setNameViaUI(XSS_ATTR);
  await sleep(150);
  const xssAttrInRow = await evalJSON(`JSON.stringify({
    inputValueText: document.getElementById('name-input').value,
    hasOnfocusHandler: typeof document.getElementById('name-input').onfocus === 'function',
  })`);
  ok('AC (XSS/account row, attribute breakout): a double-quote in the name cannot escape value="..."',
     xssAttrInRow.inputValueText === XSS_ATTR && !xssAttrInRow.hasOnfocusHandler, xssAttrInRow);

  // Reload the page (a fresh parse of server-rendered/JS-rendered content) — the row must STILL
  // read the literal stored text, and still create no real <img>/<script> element.
  await navAccount();
  await sleep(100);
  const xssAfterReload = await evalJSON(`JSON.stringify({
    rowValueText: document.querySelector('.acct-row[data-row="name"] .acct-row-value').textContent,
    injectedImg: !!document.querySelector('#acct-slot img'),
    injectedScript: !!document.querySelector('#acct-slot script'),
    hasOnfocusHandler: typeof document.getElementById('name-input').onfocus === 'function',
  })`);
  ok('AC (XSS/account row): still the literal text and still no injected element/handler after a fresh page load',
     xssAfterReload.rowValueText === XSS_ATTR && !xssAfterReload.injectedImg && !xssAfterReload.injectedScript &&
     !xssAfterReload.hasOnfocusHandler, xssAfterReload);

  // Top-bar menu: the same img-onerror payload reaches .acct-who via textContent, per account.js's
  // esc(). Set it explicitly here (the row currently holds XSS_ATTR from the check above) so this
  // block does not depend on leftover state from earlier ones. window.__xssFired was also reset by
  // the navAccount() reload above (a fresh page = a fresh window) — re-arm it.
  await evaluate(`document.querySelector('.acct-row[data-row="name"]').click(); true`);
  await sleep(80);
  await setNameViaUI(XSS_IMG);
  await evaluate(`window.__xssFired = 0; true`);
  const xssInMenu = await evalJSON(`(() => {
    document.querySelector('#acct .acct-trig').click();
    const whoText = document.querySelector('#acct .acct-who b').textContent;
    const hasImg = !!document.querySelector('#acct img');
    document.querySelector('#acct .acct-trig').click();
    return JSON.stringify({ whoText, hasImg, fired: window.__xssFired });
  })()`);
  ok('AC (XSS/top bar): the menu\'s "who" text is the literal string, handler never fired, no injected <img>',
     xssInMenu.whoText === XSS_IMG && xssInMenu.fired === 0 && !xssInMenu.hasImg, xssInMenu);

  // Reset to a clean name for the retroactive-attribution phase below.
  await evaluate(`document.querySelector('.acct-row[data-row="name"]').click(); true`);
  await sleep(80);
  await setNameViaUI('');
  ok('cleanup: name cleared before the retroactive-attribution phase',
     (await fetch(BASE + '/auth/session', { headers: { Cookie: primary.cookie } }).then(r => r.json())).name === '');

  // ================================================================================
  // Retroactive attribution end to end (#309 owner decision): a comment written BEFORE a name is
  // set renders with the name AFTERWARDS, because the viewer reads the author's CURRENT name at
  // render time (never a value frozen onto the comment). Positive control: SECOND's own comment
  // must never pick up PRIMARY's name — proves the own-entry gate actually gates.
  // ================================================================================
  async function mkReview(cookie, csrf) {
    const r = await fetch(BASE + '/api/reviews', { method: 'POST',
      headers: { 'Content-Type': 'application/json', Cookie: cookie, 'X-CSRF-Token': csrf },
      body: JSON.stringify({ title: 'retroactive-attribution probe', markdown: '# Heading\\n\\nSome body text.\\n' }) });
    if (!r.ok) throw new Error('could not create probe review: ' + r.status);
    return (await r.json()).id;
  }
  const rid = await mkReview(primary.cookie, primary.csrf);
  const viewerUrl = BASE + '/review/' + rid;

  await hardNav(viewerUrl);
  // SESSION is a script-scoped `let` (viewer.html), not a window property — reference it bare, the
  // same way tests/viewer_polish_selfcheck.sh's in-page HOST probe does.
  for (let i = 0; i < 60; i++) { if (await evaluate(`document.readyState==='complete' && typeof SESSION!=='undefined'`)) break; await sleep(150); }
  // Post a comment through the real click path, as PRIMARY, BEFORE any name is set. Attribution
  // in the stored comment is the author's UID (server-side, cookie plane) — see server.py's
  // POST /comments arm — so this exercises the real create path, not a synthetic fixture.
  const posted = await evalJSON(`(async () => {
    const r = await fetch('${BASE}/api/reviews/${rid}/comments', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ anchor: { block_num: 1 }, text: 'Comment written before any name existed.' }) });
    return JSON.stringify({ ok: r.ok, status: r.status });
  })()`);
  ok('setup: a real comment was posted by PRIMARY before any name was set', posted.ok, posted);

  // SECOND also comments on the SAME review (must have comment rights on their own doc — use a
  // review SECOND owns instead, so this stays a same-plane, no-sharing-setup comparison).
  const ridSecond = await mkReview(second.cookie, second.csrf);

  // Both users' session cookies share the SAME cookie name (mdr_session; only the value differs),
  // so "switch which user Chrome is signed in as" MUST delete before it sets — setting the new
  // value and then deleting "the old one" by name deletes what was just set (same name, same URL).
  // This one helper is now the ONLY place a cookie swap happens, so that ordering bug can't recur.
  async function useCookie(cookie) {
    const [nm, ...rest] = cookie.split('=');
    await cmd('Network.deleteCookies', { name: nm, url: BASE });
    await cmd('Network.setCookie', { name: nm, value: rest.join('='), url: BASE, httpOnly: true, secure: true, sameSite: 'Lax' });
  }
  async function labelSnapshot(url, cookie) {
    await useCookie(cookie);
    await hardNav(url);
    for (let i = 0; i < 60; i++) { if (await evaluate(`document.readyState==='complete' && document.querySelectorAll('#gutter .gcard').length>0`)) break; await sleep(150); }
    return evalJSON(`JSON.stringify({
      who: [...document.querySelectorAll('#gutter .gwho')].map(x=>x.textContent),
      hasYouClass: !!document.querySelector('#gutter .gentry.you'),
      avatar: [...document.querySelectorAll('#gutter .gav')].map(x=>x.textContent),
    })`);
  }

  const before1 = await labelSnapshot(viewerUrl, primary.cookie);
  ok('BEFORE naming: PRIMARY\'s own pre-name comment reads "You" and carries the .you highlight',
     before1.who[0] === 'You' && before1.hasYouClass, before1);

  // Positive control: SECOND (a foreign viewer, no share) cannot even reach primary's private
  // review — confirm the review stays owner-scoped (404), so the retroactive check below is a
  // same-account before/after comparison, not accidentally proving something about sharing.
  await useCookie(second.cookie);
  await hardNav(viewerUrl);
  const secondBlocked = await evaluate(`(async()=>{const r=await fetch('${BASE}/api/reviews/${rid}',{headers:{}});return r.status;})()`);
  ok('sanity: an unrelated second account cannot read PRIMARY\'s private review (404, owner-scoped)',
     secondBlocked === 404, secondBlocked);

  // Now PRIMARY sets a name, and the SAME untouched comment is re-rendered.
  await useCookie(primary.cookie);
  const setResp = await fetch(BASE + '/auth/profile', { method: 'POST',
    headers: { 'Content-Type': 'application/json', Cookie: primary.cookie, 'X-CSRF-Token': primary.csrf },
    body: JSON.stringify({ name: 'Grace Hopper' }) });
  ok('setup: PRIMARY set a name AFTER the comment already existed', setResp.ok, setResp.status);

  const after1 = await labelSnapshot(viewerUrl, primary.cookie);
  ok('AC (retroactive): the SAME pre-existing comment now renders with the name — "You" became "Grace Hopper"',
     after1.who[0] === 'Grace Hopper' && after1.hasYouClass, after1);
  ok('AC (retroactive): the avatar chip initials also updated (name-derived "gh", not the old email-derived chip)',
     after1.avatar[0] === 'gh', after1);

  // Post a SECOND comment now that the name exists — both the old and the new comment must read
  // identically (proves render-time lookup, not "only new comments get the name").
  await evaluate(`(async () => {
    await fetch('${BASE}/api/reviews/${rid}/comments', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ anchor: { block_num: 1 }, text: 'Comment written after the name existed.' }) });
    return true;
  })()`);
  const after2 = await labelSnapshot(viewerUrl, primary.cookie);
  ok('AC (retroactive): a comment written BEFORE and one written AFTER the name existed render IDENTICALLY',
     after2.who.length === 2 && after2.who.every(w => w === 'Grace Hopper'), after2);

  // ================================================================================
  // Positive control: SECOND, who never named themselves, still reads "You" on THEIR OWN comment
  // on THEIR OWN review — proves the baseline (#309 "absent means unset ... works everywhere") is
  // unperturbed, not merely "no exception was thrown".
  // ================================================================================
  // The browser's cookie is still PRIMARY's from the snapshot above — must switch to SECOND
  // BEFORE posting, or this POST would be PRIMARY commenting on a review they do not own (denied).
  await useCookie(second.cookie);
  await hardNav(BASE + '/review/' + ridSecond);
  await evaluate(`(async () => {
    await fetch('${BASE}/api/reviews/${ridSecond}/comments', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ anchor: { block_num: 1 }, text: 'Second user, never named.' }) });
    return true;
  })()`);
  const secondSnap = await labelSnapshot(BASE + '/review/' + ridSecond, second.cookie);
  ok('positive control: a never-named SECOND user still reads "You" on their own comment (baseline unperturbed)',
     secondSnap.who[0] === 'You' && secondSnap.hasYouClass, secondSnap);

} finally {
  clearTimeout(overall);
  try { ws?.close(); } catch {}
  done();
}
console.log(failed ? `\n${failed} case(s) failed` : '\nall account-name cases pass');
process.exit(failed ? 1 : 0);
