---
review_of: epics/oop-refactor-src-layout-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-25
verdict: PASS-WITH-NITS
status: resolved
round: 2
supersedes: oop-refactor-src-layout-plan-review-2026-06-25.md
---

# G1 Review (round 2): OOP Refactor + `src/` Restructure Plan

**Verdict: PASS-WITH-NITS. The round-1 BLOCKER is genuinely closed; G1 clears.** I re-verified every
claimed change against the revised plan and against `app.py` (I did not take the planner's word). The
boundary defect that gated round 1 is resolved three ways and, critically, the new acceptance check
is no longer gameable against the arm it was missing. Two small completeness gaps remain, both
SHOULD-not-BLOCKER and both one-line folds: the new grep contract omits `_read(`/`_read_bytes(`, and
the `_comment_as_note` projection in `GET /feedback` is still never diffed against a non-empty comment
list even though the reviews-extraction ticket names a "projection diff" as its gate. Neither can
produce a wrong ticket or a broken refactor; they are worth folding when the tickets are written. No
new regression was introduced by the revision.

Independence note: this round-2 review, not the author's appended resolution log, is what closes the
G1 review. I set `status: resolved` here because no BLOCKER remains.

## BLOCKER from round 1: verified CLOSED

**[BLOCKER-1] Incomplete router/service boundary + gameable acceptance grep.** Confirmed resolved.
I re-checked the two arms still exist where round 1 cited them (`_find_comment(list_comments(rid),
cid)` at `app.py:760`; the inline `_read_json(_comments_path(rid))` -> filter -> `_write_comments` ->
`bump` at `app.py:765-772`), then confirmed all three fixes:

1. **Both arms are now mapped to named service methods.** The `comments.py` row (plan table) lists
   `get_comment(rid, cid)` (lifts `app.py:760`) and `delete_comment(rid, cid) -> (code, payload)`
   (lifts `app.py:765-772`, including the 404-on-nothing-removed and the `comments_updated` bump,
   under `store.lock`), and explicitly flags that `765-772` sits outside the `276-382` range so the
   ticket author sees it. A new "Comment-arm read + mutate" bullet in the boundary prose names both.
2. **The gameable grep is replaced by a positive no-store-helper contract that actually catches the
   DELETE arm.** I verified the catch mechanically: the DELETE arm contains `_comments_path(`,
   `_read_json(`, and `_write_comments(`, all three are in the new forbidden list, so a `server.py`
   that retained the arm inline would get at least three hits and fail the gate. The old
   `_dir(`/`DATA_DIR` substring grep matched none of those tokens (the precise hole round 1 flagged).
   Fixed.
3. **The contract does not false-positive on the legitimate WEB_DIR reads.** I checked: the handler
   keeps three `WEB_DIR` reads via `store.read_text` / `store.read_bytes` / `store.ctype_for`, none
   of which appear in the forbidden list (the list targets underscore-prefixed internals + `_dir(`,
   not the public `Store` API). The token `_dir(` also does not match `store.dir(`. No legitimate
   read trips the gate.

The transcript additions (below) give both arms a diff oracle. This is a clean close.

## Remaining findings (SHOULD x2, no BLOCKER)

### [SHOULD] 1: The new no-store-helper grep omits `_read(` and `_read_bytes(`, so a partial extraction could still pass while reading `/data`

The positive contract (boundary "Acceptance check" paragraph + the rewritten Risk-register row) lists
`_comments_path(`, `_assets_dir(`, `_assets_manifest(`, `_dir(`, `_read_json(`, `_write(`,
`_write_comments(`, `_find_comment(`, `_comment_as_note(`, `_stored_name(`, and `os.path.join(` with a
`DATA_DIR`/`_dir`/`_assets_dir` argument. It does **not** list the two bare readers `_read(` and
`_read_bytes(`.

Today this is harmless because every `/data` read also names `_dir(`/`_assets_dir(` on the same or the
assignment line (I traced all of them: `GET /source` 551, `GET /feedback` 568, the `/history/{n}`
block 697-703, the asset GET 802-805, each caught via `_dir(` or `_assets_dir(`). But the grep is
sold as the *completeness proof* that `server.py` has zero `/data` access, and as a proof it has a
hole: a partial extraction such as `p = self.server.app.reviews.dir(rid); txt = _read(os.path.join(p,
"source.md"))` (handler holds a path from a public method, then reads it with the bare reader) would
leave a `/data` read in `server.py` that the grep passes. That is the same class of gaming the BLOCKER
fix set out to foreclose. Note the WEB_DIR reads are supposed to go through `store.read_text` /
`store.read_bytes` (public, no underscore), so the bare `_read(` / `_read_bytes(` should legitimately
be **zero** in `server.py` anyway.

**Fix:** add `_read(` and `_read_bytes(` to the forbidden-token list (require zero hits). One-line
edit to the contract; makes the proof actually closed rather than closed-by-happenstance-of-today's-
call-sites.

### [SHOULD] 2: `GET /feedback` is diffed only with zero comments, so the `_comment_as_note` projection (the reviews ticket's named gate) has no real oracle

`_comment_as_note` (`app.py:296`) has exactly one call site: the `GET /feedback` arm builds
`out["notes"] = notes.json + [_comment_as_note(c) for c in list_comments(rid)]` (`app.py:573`). The
revised transcript reads `/feedback` once, at line 463, **before** the comment is created at line
464. At that point `list_comments(rid)` is empty, the projection lambda never runs, and the diffed
bytes are `notes: []`. So a regression in `_comment_as_note`'s projection (a renamed key, a changed
role-prefix join, a dropped field) would not be caught, yet the `reviews.py` extraction ticket lists
"`/feedback` projection diff" as its acceptance gate (plan ticket table), the gate names a diff that
is vacuous for the projection path.

The plan does say `_comment_as_note` is "moved verbatim," which makes byte-identity *likely*, but
"moved verbatim" is precisely the claim a diff exists to verify, and the reviews ticket already
promises to verify it. This is the same shape as the round-1 SHOULD-2 (a real code path with no
oracle), just one the revision's new transcript still misses.

**Fix:** add one `curl -s "$B/api/reviews/$id/feedback"` **after** the comment exists (e.g. right
after the resolve/reopen sequence, before the DELETE-comment at 481) so the projected `notes[]` is
non-empty and the `_comment_as_note` output bytes are in the oracle. One extra line in the sweep.

## Round-1 SHOULD/NIT items: verified addressed

- **SHOULD-2 (transcript missing 5 arms): addressed.** Verified present and correctly ordered:
  `GET /api/reviews/$id` (meta, line 460); `GET .../comments/$cid` (single thread, 466); the reopen
  branch as resolve -> reopen-200 (471) -> reopen-on-non-resolved-409 (472), I traced this against
  `app.py:361-378` and the expected 200-then-409 is correct; `DELETE .../comments/$cid` then a second
  DELETE -> 404 (481-482); and `DELETE /api/reviews/$id2` on a **separate** throwaway review created
  at 484, deleted 485, re-GET -> 404 at 486. The destructive review-delete is last and on `id2`, so it
  cannot kill the main sweep; no later curl references `$cid` (only the DELETE retry) or `$id2`.
  Transcript determinism holds.
- **SHOULD-3 (pin "no service re-acquires `store.lock`"): addressed, and the wording is right.** The
  new Key-constraints bullet ("Services never acquire `store.lock`...") states the lock is taken only
  at the arms + `_wait` that take it today, bars a service re-acquiring it, requires
  `list_reviews`/`summary` to stay lock-free, and correctly reproduces my RLock analysis (re-
  acquisition does not deadlock and `wait()` still fully releases, so it is a contract/clarity
  violation rather than a crash, but it is barred because it defeats the single-lock reasoning). The
  Risk-register row now mandates grepping `store.lock`/`.lock:` *acquisition* sites, not just a second
  `Lock(`/`Condition(` constructor. I re-confirmed `list_reviews`/`summary` take no lock today and
  `_wait` holds the lock across its `list_reviews()` call (`app.py:452-459`), so the constraint
  matches reality.
- **NIT-4 (`_dir` count): addressed.** Corrected to 9 with the line list (`542, 551, 557, 568, 572,
  613, 682, 697` + `_assets_dir` at 802), and the plan now states the hand-count is illustrative and
  the grep is the proof. Count verified correct.
- **NIT-5 (`to_float` placement): addressed.** The choice is now called explicitly: kept on `Store` as
  `store.to_float`, used only by `server.py`'s `_wait`/query parsing, touches no `/data`, and the
  boundary grep deliberately does not flag it. Implementer discretion to make it a free function is
  noted. Reasonable.
- **NIT-6 ("~290" figure): addressed.** The specific number is dropped in all three places and
  described qualitatively; assumption #5 records that the earlier "~290" was scope-dependent. Fine.

## What I re-verified against code this round (so the close is grounded)

- The two comment arms still live at `app.py:760` and `app.py:765-772`; the reopen branch at
  `app.py:370-378` produces 200 (resolved -> reopened) then 409 (reopened -> reopen) exactly as the
  transcript expects.
- The new forbidden-token list catches the DELETE arm (via `_comments_path(` / `_read_json(` /
  `_write_comments(`) and every other current `/data` arm (via `_dir(` / `_assets_dir(`), and does
  not match the public `store.read_text` / `read_bytes` / `ctype_for` / `dir` the handler keeps.
- `python3 -m py_compile app.py` is clean (baseline unbroken).
- No new regression: the grep list introduces no false-positive on a method the handler must retain;
  the transcript reordering is deterministic and leaves no dangling id/cid reference.

## Resolution log

- [x] **BLOCKER-1 (round 1): CLOSED.** Both comment arms mapped to `CommentService.get_comment` /
  `delete_comment`; boundary prose names them; gameable substring grep replaced by a positive
  no-store-helper contract that catches the DELETE arm without false-positiving on the WEB_DIR reads.
  Verified against `app.py`.
- [x] Round-1 SHOULD-2 / SHOULD-3 / NIT-4 / NIT-5 / NIT-6: verified addressed (details above).
- [ ] **SHOULD-1 (round 2, new):** add `_read(` and `_read_bytes(` to the forbidden-token grep so the
  boundary proof is closed, not closed-by-happenstance. Fold into the server ticket's acceptance
  criteria.
- [ ] **SHOULD-2 (round 2, new):** add one `GET /feedback` read *after* a comment exists so the
  `_comment_as_note` projection has a real diff oracle (the reviews ticket's named "projection diff").
  Fold into the golden transcript + the reviews ticket.

Both round-2 SHOULDs are non-blocking and may be folded when the tickets are authored; they do not
hold G1.
