// session.js (#221) — the one place that asks "who am I?", shared by the dashboard's boot() and by
// the account menu in account.js.
//
// The bug this file exists to kill: both callers used to do
//
//     try { sess = await fetch("/auth/session").then(r => r.json()); } catch (_) {}
//
// and then treat the resulting empty object as "anonymous". A dropped connection, a 502 while the
// container restarted, or a non-JSON error page therefore rendered the sign-in screen at a user
// whose cookie was perfectly valid. "The server says you are signed out" and "I could not ask the
// server" are different answers, and the UI must never conflate them: one means sign in again, the
// other means wait.
//
// read() returns { sess, reachable }. reachable === false means the question was never answered,
// and the caller owes the user a connection state, never a sign-in form.
//
// A non-2xx counts as unreachable on purpose. /auth/session answers an unauthenticated caller with
// 200 {authenticated:false} (see AuthModule._session), so any other status is the server failing,
// not the server answering.

(function (root) {
  var RETRY_DELAY_MS = 600;   // one retry absorbs a restart blip; it is not an outage strategy

  function sleep(ms) {
    return new Promise(function (res) { setTimeout(res, ms); });
  }

  // fetchImpl and delayMs are injectable so tests/session_selfcheck.js can drive this without a
  // browser and without waiting real seconds. Browsers call read() with no arguments.
  async function read(fetchImpl, delayMs) {
    var f = fetchImpl || (typeof fetch !== "undefined" ? fetch : null);
    if (!f) return { sess: { authenticated: false }, reachable: false, noAuthPlane: false };
    var wait = delayMs === undefined ? RETRY_DELAY_MS : delayMs;

    for (var attempt = 0; attempt < 2; attempt++) {
      try {
        var r = await f("/auth/session", { cache: "no-store" });
        // #224: 404 is a THIRD state, not a failure. The local (non-hosted) build serves no
        // /auth/session at all, so treating its 404 as "unreachable" told self-hosters the server
        // was down and hid the dashboard from them entirely.
        // Returned as a named flag rather than a status code the callers re-interpret: an earlier
        // version threw the status into an Error message and discarded it, which is why this could
        // not be distinguished at all.
        if (r && r.status === 404) {
          // Deliberately NO retry: a route that does not exist will not exist in 600ms, and the
          // sleep is pure latency on every page load of every local instance.
          return { sess: { authenticated: false }, reachable: false, noAuthPlane: true };
        }
        if (!r || !r.ok) throw new Error("HTTP " + (r && r.status));
        return { sess: await r.json(), reachable: true, noAuthPlane: false };
      } catch (e) {
        if (attempt === 0) await sleep(wait);
      }
    }
    return { sess: { authenticated: false }, reachable: false, noAuthPlane: false };
  }

  var api = { read: read, RETRY_DELAY_MS: RETRY_DELAY_MS };

  root.mdSession = api;
  // Node (tests/session_selfcheck.js). Ignored by browsers, so the same file serves both.
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : this);
