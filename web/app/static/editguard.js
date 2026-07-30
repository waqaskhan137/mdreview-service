/* editguard.js (#290) — the pure decision logic behind the markdown viewer's in-place editor
 * (epic #273 slice B), factored out of viewer.html so it is unit-testable without a browser (same
 * shape as linediff.js / keys.js: a plain script tag defines window.mdEdit, and the
 * module.exports tail lets tests/editguard_selfcheck.js require() it directly).
 *
 * Three small functions, each a real bug source if inlined and eyeballed instead of tested:
 *
 *   parseRevision(etag)   The edit-precondition token (#288) arrives as an ETag header, e.g. '"3"'.
 *                         Forgetting to strip the quotes turns every If-Match into the literal
 *                         string '"3"' instead of 3 — the server's int() cast then 400s, silently
 *                         teaching an agent-shaped bug report ("editor is broken") instead of an
 *                         obvious one.
 *
 *   shouldWarnRemoteChange(editing, localRevision, remoteRevision)
 *                         The guard behind "a remote change detected while editing keeps the
 *                         buffer and offers reload/discard" (#273 slice B). Getting the null
 *                         handling wrong either nags on every poll tick before the editor has a
 *                         revision yet, or — worse — never fires because a loose `!=` treats
 *                         0 as falsy and null !== 0 gets short-circuited away.
 *
 *   buildSaveHeaders({revision, csrf})
 *                         The PUT /source header set: If-Match only when a revision was actually
 *                         read (never a bare "null"/"undefined" string), X-CSRF-Token only when a
 *                         token exists (an empty header is indistinguishable from "no session" to
 *                         a human reading network logs, but IS distinguishable to check_csrf, which
 *                         treats a present-but-wrong token as a hard 403 rather than the "no
 *                         session, no gate" pass an absent header gets on the proxy/bearer planes).
 */
(function (root) {
  "use strict";

  function parseRevision(etag) {
    if (etag === null || etag === undefined) return null;
    var s = String(etag).trim().replace(/^"|"$/g, "");
    if (s === "") return null;
    var n = parseInt(s, 10);
    return Number.isNaN(n) ? null : n;
  }

  function shouldWarnRemoteChange(editing, localRevision, remoteRevision) {
    if (!editing) return false;
    if (localRevision === null || localRevision === undefined) return false;
    if (remoteRevision === null || remoteRevision === undefined) return false;
    return localRevision !== remoteRevision;
  }

  function buildSaveHeaders(opts) {
    opts = opts || {};
    var h = { "Content-Type": "application/json", "X-Mdreview-Client": "viewer" };
    if (opts.revision !== null && opts.revision !== undefined) h["If-Match"] = '"' + opts.revision + '"';
    if (opts.csrf) h["X-CSRF-Token"] = opts.csrf;
    return h;
  }

  var api = { parseRevision: parseRevision, shouldWarnRemoteChange: shouldWarnRemoteChange,
              buildSaveHeaders: buildSaveHeaders };

  root.mdEdit = api;
  // Node (tests/editguard_selfcheck.js). Ignored by browsers, so the same file serves both.
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : this);
