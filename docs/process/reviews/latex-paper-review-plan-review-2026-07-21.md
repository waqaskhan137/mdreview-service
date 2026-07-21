---
review_of: docs/process/epics/latex-paper-review-plan.md
gate: G1
reviewer: staff-critic (agent)
independent: true
timestamp: 2026-07-21
verdict: proceed with named risks accepted (round 2; round 1 was needs-revision)
status: resolved
---

# G1 review: latex-paper-review epic plan

The plan was authored, critiqued, and approved on hosted mdreview review `9215476104`
(https://app.mdreview.space/review/9215476104); this file is the committed gate record. The
reviewer was the `staff-critic` agent, independent of the plan's author; it verified the plan's
load-bearing claims directly against the repo (route chain `server.py:224-557`, composition root
`49-60`, opaque `block_num` at `comments.py:69`, `snapshot_round` sibling-dir behavior
`reviews.py:82-106`, MCP whitelist `client.py:56`, amd64-only watcher precedent `release.yml:59`,
dev 31-behind/0-ahead) and Tectonic upstream facts (biber not integrated, issues #35/#1010; no
filesystem sandbox, issue #8).

## Round 1 (verdict: needs revision), 7 findings, all applied in plan revision 7

1. **MUST-FIX. Default `kind` key breaks the plan's own flag-off oracle.** `summary()` returns
   `dict(meta)` unwhitelisted (reviews.py:54) and is echoed by the item and list endpoints, so
   persisting `kind="markdown"` by default would add a key the baseline never emitted and the
   golden-transcript diff would be non-empty. Fix applied: persist `kind` only when
   `!= "markdown"`; all five core edits enumerated honestly.
2. Worth-considering: span tokenization breaks the single-text-node `indexOf` quote highlight.
   Fix: offset-mapped textContent search wrapped per intersected segment.
3. Worth-considering: multi-arch Tectonic warm-up under QEMU repeats the pain the watcher image
   dodged. Fix: amd64-only v1.
4. Worth-considering: asset copy-in naming opened a write-side traversal (manifest `name` is
   free-form). Fix: basename-only with separator/`..` flattening; figures bare-filename-only v1.
5. Worth-considering: MCP `update_source`/`get_source` descriptions would instruct markdown
   authoring into a `.tex` source. Fix: latex-aware wording across the loop.
6. Worth-considering: `Content-Disposition` cannot be produced through `_send`'s fixed header set.
   Fix: HTML5 `download` attribute, endpoint always inline.
7. Worth-considering: orphan states (flag-off-created review, queue lost to container recreate)
   left a blank PDF pane with no recovery. Fix: compile-on-demand self-heal + delete-race guard.

## Round 2 (verdict: PROCEED WITH NAMED RISKS ACCEPTED)

All 7 fixes verified as addressing their findings; no new must-fix; 0 new comments. Two
non-blocking implementation checkpoints recorded for tickets: (a) MR-097 wraps the quote highlight
per intersected text segment (Range cannot surroundContents across element boundaries); (b) MR-095
documents that two assets sharing a basename collide in the job dir (within the accepted
bare-filename-only scope).

## Owner decisions (2026-07-21, comments on review 9215476104)

- Base branch: consolidate `dev` (fast-forward to main) first, then cut `feat/latex-review` from
  `dev`; the written cut-from-dev rule stands.
- Figures: bare-filename-only v1 accepted.
- Hosted rollout: deferred until the owner tests locally and approves; merges flag-off.
- Compile security: accepted in hardened form; the owner directed two additional mitigations into
  scope (scrubbed subprocess env so `/proc/self/environ` carries no secrets; unprivileged compile
  uid with `/data` 0700 so cross-user reads are impossible). Residual risk (world-readable
  container files only) explicitly accepted.

## Resolution log

- [x] Round-1 must-fix (kind/oracle): applied in revision 7, verified in round 2.
- [x] Round-1 worth-considering 2-7: applied in revision 7, verified in round 2.
- [x] Mermaid syntax error in the 3.3 diagram (owner-reported): fixed in revision 8.
- [x] Owner decisions recorded in revision 9; hardened security posture in revision 10.
- [x] G1 closed: owner said "approved" on 2026-07-21 with zero open comments on the review.
