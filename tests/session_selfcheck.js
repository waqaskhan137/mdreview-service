#!/usr/bin/env node
// session_selfcheck.js — self-check for the shared session read (#221 web/app/static/session.js).
//
// The defect this guards: the dashboard, the account menu and the admin console all used to treat
// a FAILED /auth/session request as "anonymous", so a 502 during a container restart rendered the
// sign-in screen at a user whose cookie was still valid. The whole point of session.js is that
// `reachable` and `authenticated` are two different bits, so that is what this asserts.
//
// It require()s the exact file the browsers load (same trick as diff_selfcheck.js), so the check
// cannot drift from the shipped function.
//
// Run: node tests/session_selfcheck.js   (exit 0 = all cases pass, exit 1 = a case failed)

const path = require('path');
const { read } = require(path.join(__dirname, '..', 'web', 'app', 'static', 'session.js'));

let failed = 0;
function check(name, cond, detail) {
  if (cond) { console.log('ok   - ' + name); }
  else { console.log('FAIL - ' + name + (detail ? '  (' + detail + ')' : '')); failed++; }
}

// A fetch stub that replays a scripted list of outcomes and counts how often it was called.
function stub(outcomes) {
  const calls = [];
  const f = async (url, opts) => {
    calls.push({ url, opts });
    const o = outcomes[Math.min(calls.length - 1, outcomes.length - 1)];
    if (o.throws) throw new Error(o.throws);
    return { ok: o.status >= 200 && o.status < 300, status: o.status, json: async () => o.body };
  };
  f.calls = calls;
  return f;
}

(async () => {
  // 1. The happy path: a signed-in user is reachable AND authenticated.
  {
    const f = stub([{ status: 200, body: { authenticated: true, uid: 'u1', csrf: 'c' } }]);
    const r = await read(f, 0);
    check('200 authenticated -> reachable + authenticated', r.reachable === true && r.sess.authenticated === true);
    check('happy path does not retry', f.calls.length === 1, 'calls=' + f.calls.length);
  }

  // 2. The server ANSWERING "you are anonymous" is reachable. This must still show the sign-in form.
  {
    const f = stub([{ status: 200, body: { authenticated: false } }]);
    const r = await read(f, 0);
    check('200 {authenticated:false} -> reachable, not authenticated',
      r.reachable === true && r.sess.authenticated === false);
  }

  // 3. THE REGRESSION. A thrown fetch is NOT a sign-out. Before #221 this produced the sign-in
  //    screen; if this case ever reports reachable:true the bug is back.
  {
    const f = stub([{ throws: 'network down' }]);
    const r = await read(f, 0);
    check('network error -> NOT reachable', r.reachable === false);
    check('network error -> never claims authenticated', r.sess.authenticated === false);
    check('network error retries exactly once', f.calls.length === 2, 'calls=' + f.calls.length);
  }

  // 4. A 502 is the container restarting, not an answer. /auth/session replies 200 to an
  //    unauthenticated caller, so any non-2xx means the server failed to answer at all.
  {
    const f = stub([{ status: 502, body: null }]);
    const r = await read(f, 0);
    check('502 -> NOT reachable', r.reachable === false);
  }

  // 5. The retry is what makes a single blip invisible: fail once, succeed on the second attempt.
  {
    const f = stub([{ throws: 'blip' }, { status: 200, body: { authenticated: true } }]);
    const r = await read(f, 0);
    check('transient failure then success -> reachable + authenticated',
      r.reachable === true && r.sess.authenticated === true);
    check('recovered on the second call', f.calls.length === 2, 'calls=' + f.calls.length);
  }

  // 6. Cache busting must survive: a cached 200 would defeat the whole liveness question.
  {
    const f = stub([{ status: 200, body: { authenticated: true } }]);
    await read(f, 0);
    check('requests /auth/session with no-store', f.calls[0].url === '/auth/session' &&
      f.calls[0].opts && f.calls[0].opts.cache === 'no-store');
  }


// ---------------------------------------------------------------- #224: FOUR states, not two
// The original two-state model (reachable / not) could not tell "this build has no auth plane"
// from "the server is down", so the local tier's 404 hid the dashboard from self-hosters.
// These four are the complete set a caller must be able to distinguish.

// 7. NO AUTH PLANE. The local build serves no /auth/session at all.
{
  const f = stub([{ status: 404, body: { error: "no route" } }]);
  const r = await read(f, 0);
  check('404 -> noAuthPlane, a NAMED third state', r.noAuthPlane === true, JSON.stringify(r));
  check('404 -> not reachable (it is still not an answer)', r.reachable === false);
  check('404 -> never claims authenticated', r.sess.authenticated === false);
  // A route that does not exist will not exist in 600ms. Retrying is pure latency on every page
  // load of every local instance, and the sleep is what made this visible as a stall.
  check('404 does NOT retry', f.calls.length === 1, 'calls=' + f.calls.length);
}

// 8. UNREACHABLE must stay distinct from no-auth-plane, both for a 5xx and for a throw.
{
  const f = stub([{ status: 502, body: null }]);
  const r = await read(f, 0);
  check('502 -> unreachable, NOT noAuthPlane', r.reachable === false && r.noAuthPlane === false, JSON.stringify(r));
  check('502 still retries (a server can recover in 600ms)', f.calls.length === 2, 'calls=' + f.calls.length);
}
{
  const f = stub([{ throws: 'network down' }]);
  const r = await read(f, 0);
  check('network throw -> unreachable, NOT noAuthPlane', r.reachable === false && r.noAuthPlane === false);
}

// 9. The two 200 states must be untouched by the new branch.
{
  const f = stub([{ status: 200, body: { authenticated: false } }]);
  const r = await read(f, 0);
  check('200 anonymous -> reachable, not authenticated, NOT noAuthPlane',
    r.reachable === true && r.sess.authenticated === false && r.noAuthPlane === false, JSON.stringify(r));
}
{
  const f = stub([{ status: 200, body: { authenticated: true, uid: 'u1' } }]);
  const r = await read(f, 0);
  check('200 authenticated -> reachable, authenticated, NOT noAuthPlane',
    r.reachable === true && r.sess.authenticated === true && r.noAuthPlane === false, JSON.stringify(r));
}

  console.log(failed ? '\n' + failed + ' case(s) failed' : '\nall session cases pass');
  process.exit(failed ? 1 : 0);
})();
