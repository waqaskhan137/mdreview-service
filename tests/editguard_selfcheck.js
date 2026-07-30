#!/usr/bin/env node
// editguard_selfcheck.js — self-check for the markdown viewer's in-place editor logic (#290,
// epic #273 slice B): web/app/static/editguard.js.
//
// require()s the shipped file directly (same trick as diff_selfcheck.js / keys_selfcheck.js), so
// this exercises the EXACT bytes the browser runs, not a hand-copied restatement of them.
//
// Run: node tests/editguard_selfcheck.js   (exit 0 = all cases pass, exit 1 = a case failed)

const path = require('path');
const { parseRevision, shouldWarnRemoteChange, buildSaveHeaders } =
  require(path.join(__dirname, '..', 'web', 'app', 'static', 'editguard.js'));

let failed = 0;
function check(name, cond, detail) {
  if (cond) { console.log('ok   - ' + name); }
  else { console.log('FAIL - ' + name + (detail ? '  (' + detail + ')' : '')); failed++; }
}

// -------------------------------------------------------------- parseRevision

// 1. The normal case: GET /source's ETag is a quoted integer.
check('parseRevision strips ETag quotes', parseRevision('"3"') === 3, String(parseRevision('"3"')));

// 2. An unquoted value (e.g. read from a PUT response's meta.revision, not a header) still parses.
check('parseRevision accepts an unquoted integer', parseRevision('7') === 7, String(parseRevision('7')));

// 3. Revision 0 is a real, valid revision (a fresh review's starting token) — must NOT be treated
//    as absent. This is exactly the trap a loose `if (!rev)` falls into.
check('parseRevision(0) is 0, not null', parseRevision('"0"') === 0, String(parseRevision('"0"')));

// 4. Missing header (fetch's Headers.get returns null for an absent header).
check('parseRevision(null) -> null', parseRevision(null) === null, String(parseRevision(null)));
check('parseRevision(undefined) -> null', parseRevision(undefined) === null, String(parseRevision(undefined)));

// 5. Garbage input fails closed to null, never NaN (NaN !== NaN would silently defeat every
//    downstream equality check in shouldWarnRemoteChange and the 409 compare).
{
  const r = parseRevision('""');
  check('parseRevision("") -> null', r === null, String(r));
  const r2 = parseRevision('"not-a-number"');
  check('parseRevision(garbage) -> null, not NaN', r2 === null, String(r2));
}

// -------------------------------------------------------------- shouldWarnRemoteChange

// 6. The core case: editing, and the remote revision moved past what the editor is holding.
check('warns when editing and revisions differ',
      shouldWarnRemoteChange(true, 3, 4) === true);

// 7. Not editing -> never warn, regardless of revisions (this is what lets poll() skip the
//    remote-change branch entirely once the editor is closed).
check('never warns when not editing',
      shouldWarnRemoteChange(false, 3, 4) === false);

// 8. Same revision -> no warning (the common poll tick: nothing changed).
check('no warning when revisions match',
      shouldWarnRemoteChange(true, 5, 5) === false);

// 9. Revision 0 must compare as a real value, not fall through a falsy check (the same trap as
//    case 3, at the call site that actually matters).
check('revision 0 vs 0 is "no change" (not misread as "no data")',
      shouldWarnRemoteChange(true, 0, 0) === false);
check('revision 0 vs 1 IS a change',
      shouldWarnRemoteChange(true, 0, 1) === true);

// 10. Either side absent (the editor has not read a revision yet, or /status has not answered) ->
//     never warn. Warning on incomplete data would nag before the editor has even opened.
check('local revision unknown -> no warning',
      shouldWarnRemoteChange(true, null, 4) === false);
check('remote revision unknown -> no warning',
      shouldWarnRemoteChange(true, 3, null) === false);
check('remote revision undefined -> no warning',
      shouldWarnRemoteChange(true, 3, undefined) === false);

// -------------------------------------------------------------- buildSaveHeaders

// 11. The normal case: a revision was read and a session CSRF token is available.
{
  const h = buildSaveHeaders({ revision: 5, csrf: 'tok123' });
  check('If-Match carries the quoted revision', h['If-Match'] === '"5"', JSON.stringify(h));
  check('X-CSRF-Token is sent when a token exists', h['X-CSRF-Token'] === 'tok123', JSON.stringify(h));
  check('Content-Type is always set', h['Content-Type'] === 'application/json', JSON.stringify(h));
  // #289 attribution: the local-tier reviewer signal. Sent unconditionally — harmless on the
  // cookie/proxy planes (attribution there keys on `plane`, not this header) and required on the
  // local tier for a viewer-authored save to be attributed "reviewer" instead of "agent".
  check('X-Mdreview-Client: viewer is always sent', h['X-Mdreview-Client'] === 'viewer', JSON.stringify(h));
}

// 12. Revision 0 must still produce an If-Match header (the falsy-zero trap again, at the one
//     call site where getting it wrong sends an UNCONDITIONAL write instead of a guarded one).
{
  const h = buildSaveHeaders({ revision: 0, csrf: '' });
  check('If-Match is sent for revision 0', h['If-Match'] === '"0"', JSON.stringify(h));
}

// 13. No revision read yet (should not happen in practice — the editor always reads one on open —
//     but the header builder must not send the literal string "If-Match: null").
{
  const h = buildSaveHeaders({ revision: null, csrf: 'tok' });
  check('no If-Match when revision is null', !('If-Match' in h), JSON.stringify(h));
}

// 14. No session (local tier, or a hosted caller whose /auth/session fetch failed): omit the
//     header entirely rather than send an empty one. An empty X-CSRF-Token on a verified session
//     is a hard 403 under check_csrf; omitting it is only safe because the local tier never binds
//     check_csrf at all — this test pins that the header is actually absent, not empty-string.
{
  const h = buildSaveHeaders({ revision: 2, csrf: '' });
  check('no X-CSRF-Token when csrf is empty', !('X-CSRF-Token' in h), JSON.stringify(h));
}

if (failed) { console.error('\n' + failed + ' case(s) failed'); process.exit(1); }
console.log('\nAll editguard self-checks passed.');
