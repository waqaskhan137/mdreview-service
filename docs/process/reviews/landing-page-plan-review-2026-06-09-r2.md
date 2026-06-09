---
review_of: epics/landing-page-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-09 (Europe/London)
verdict: PASS
status: resolved
---

# G1 re-review (round 2) — Landing page on GitHub Pages plan

## Summary

Round 1 issued **PASS-WITH-FIXES** with one BLOCKER (F1, a fictional render-smoke
screenshot capability) and six further findings. The revised plan resolves all seven,
and the resolutions hold up against the actual files — not just against the Resolution
log prose. No new blockers surfaced in the re-read. **Verdict: PASS.**

The fix for the BLOCKER is the important one to confirm independently, because the
round-1 defect was a false *capability* claim, not a judgement call: the plan asserted
`render-smoke.sh` had a "Chrome screenshot path." I verified the script line-by-line
(`scripts/render-smoke.sh:54-114`): it invokes Chrome with `--dump-dom` only, pipes the
serialized DOM into a stdlib `HTMLParser` that counts elements per selector, and never
writes an image — there is no `--screenshot` flag in it. The revised plan now says
exactly this, in three places, and removes every claim to the contrary. The two
replacement capture procedures are both real (details under F1 below).

## Finding-by-finding judgement

### F1 — BLOCKER — render-smoke screenshot path fictional — **RESOLVED**

Every screenshot claim about `render-smoke.sh` is gone. *Rollout phases -> Phase 1*
(the demo-capture bullet) now states plainly that render-smoke "does not and cannot
produce this — it only `--dump-dom`s the rendered page and counts DOM nodes; it never
writes an image," and *Decision 2* repeats it ("`scripts/render-smoke.sh` is not a
screenshot tool … so it is *not* used to produce the demo asset"). Both replacement
procedures check out:

- **(a) Manual browser capture** matches the repo's actual practice (the
  `sprint-01-render-evidence/*.png` precedent, per the feature-cycle skill). Honest,
  no new tooling. This is the default.
- **(b) Direct headless Chrome** invokes `"$CHROME" --headless=new
  --screenshot=site/demo.png --window-size=1280,800 …` *directly*, explicitly **not**
  via render-smoke, reusing the binary the script locates. I confirmed the cited range
  `scripts/render-smoke.sh:32-41` is exactly the `CHROME=""` / `RENDER_SMOKE_CHROME` /
  `CANDIDATES` block, and `--headless=new --screenshot=<path>` is a genuine Chrome
  capability consistent with how the script itself drives Chrome (`--headless=new
  --disable-gpu --no-sandbox --hide-scrollbars`, line 54). The command is honest about
  being a new ad-hoc invocation, not an existing tool, and MR-019 is told to pick (a)
  or (b) explicitly. Resolved.

### F2 — MAJOR — G7 per-page trigger does not name `site/index.html` — **RESOLVED**

The *Process / gate enforcement note* now does the opposite of asserting coverage: it
states the G7 row fires only for `viewer.html`/`dashboard.html`/`static/**`, that
`site/index.html` is none of those, and — verbatim — "**We do not assert the G7 trigger
covers `site/**`** … that would be claiming a gate row says something it does not (the
MR-012 / mcp-wrapper-B1 defect class)." The render obligation is relocated into MR-019's
own G4 acceptance criteria (*Verification -> Page render-smoke (MR-019)*, AC items 1-2),
so it has teeth in the enforcing artifact regardless of how the G7 trigger reads. This
is the preferred (a) direction from round 1, and it matches how this repo resolved the
same defect class before. Resolved.

### F3 — MAJOR — README G4 "rebuilt image" vs. an artifact never in any image — **RESOLVED**

`python3 -m http.server` is promoted from a Risk bullet to MR-019's **named G4
validation target**. *Verification* now states it as a ticket-level fact: the gate is
`python3 -m http.server 8200 --directory site` then `scripts/render-smoke.sh
http://localhost:8200/ <selectors>`, and "a missing container rebuild is **compliant**
for this artifact, not a gate miss." It also reconciles the script's own contract — I
confirmed the header says "Target a SERVED url … never a `file://` path"
(`scripts/render-smoke.sh:20-21`), and an `http.server` URL satisfies "served, not
file://." The Risk bullet now points at the AC rather than owning the reconciliation.
Resolved.

### F4 — MINOR — token set incomplete; mono-stack cite imprecise — **RESOLVED**

`--noteline:#d4a017` is now in the copied `:root` set in both *Recommended approach ->
UI* and *Decision 5*, with the rationale (it is the strike-through/annotation accent the
demo screenshot shows). Verified against the real file: `--noteline:#d4a017` is present
in `dashboard.html:8` (light `:root`) and `dashboard.html:9` (dark block). The palette
cite (`:8`), dark-mode cite (`:9`), and system-font-stack cite (`:11`) are all correct;
`max-width:920px` is indeed `dashboard.html:12` (cited correctly). The imprecise
`dashboard.html:20` mono cite is replaced with "the `ui-monospace,SFMono-Regular,Menlo,
monospace` stack used throughout `dashboard.html`." Resolved.

### F5 — MINOR — README URL recorded before publish verified — **RESOLVED**

*Rollout phases -> Phase 1* is re-sequenced: the one-time human Pages/DNS/HTTPS steps
come first, and the README canonical-URL edit is "sequenced last and gated on the
publish-verification block passing" (`dig` -> `<owner>.github.io`, `curl -sI … 200`,
live render-smoke). MR-020's ACs are told to order it "after publish-verification is
green," not in parallel. *Decision 3* repeats the gating. The README can no longer
assert a URL that 404s. Resolved.

### F6 — MINOR — MR-021 not `ready`; sprint scope unstated — **RESOLVED**

Stated explicitly in three places (*Phase 2*, *Preferred execution order*, and a new
**Sprint** column in the *Ticket breakdown* table) that MR-021 is "backlog / next
cycle, NOT committed to this sprint" because it cannot reach `ready` (no GIF asset; GIF-
vs-`<video>` open) and committing it would fail G6. "The epic's sprint commits MR-019 +
MR-020 only" appears verbatim. The committed set is now all-`ready`-able. Resolved.

### F7 — NIT — publish sequence never shown — **RESOLVED**

*Decision 3* now pins one concrete sequence and rejects the two alternatives
(`git subtree split` for history bloat, in-place throwaway checkout for working-tree
collision). I tested the load-bearing command on this machine (git 2.50.1):
`git worktree add --orphan -b gh-pages <path>` is valid syntax, exits 0, and creates an
unborn `gh-pages` branch (`symbolic-ref HEAD` -> `refs/heads/gh-pages`). The
`rsync -a --delete --exclude '.git' site/ <worktree>/` step is genuinely idempotent
(trailing-slash on `site/` copies contents, not the directory; `--delete` prunes removed
files), and `site/CNAME` lands at the branch root as claimed. The plan also includes the
correct fallback for an already-existing remote branch
(`git worktree add <path> gh-pages`). Resolved.

One forward note, not a finding: `--orphan` for `git worktree add` requires git >= 2.42
(2023). Modern, but if MR-020 ever runs on an older git the documented fallback path is
the one to use. Worth a one-line "git >= 2.42" note in MR-020's runbook; not a G1
blocker.

## New blockers

None. The re-read surfaced no new BLOCKER or MAJOR issue. The epic shape, ticket count,
and gate mapping are unchanged from round 1, which were already sound.

## Verdict

**PASS.** All seven round-1 findings (F1 BLOCKER through F7 NIT) are resolved, and the
resolutions hold against the actual files (`scripts/render-smoke.sh`, `dashboard.html`,
the `git worktree`/`rsync` mechanics, and the unchanged brief
`requirements/landing-page.md`). The round-1 review's `status` is flipped to `resolved`.
The plan is cleared at G1; the orchestrator may flip the epic to `gate: G1 passed` and
create MR-019/MR-020.
