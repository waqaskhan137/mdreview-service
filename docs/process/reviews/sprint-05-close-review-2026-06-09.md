---
review_of: sprints/sprint-05.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-09 (Europe/London)
verdict: PASS
status: resolved
---

# Sprint-05 (landing-page) — G7 sprint-close review

Independent close review. The reviewer did not implement this sprint. Every claim below
was reproduced from the tree, not read from the work logs.

## Summary

Sprint-05 ships a buildless landing page (`site/index.html` + `demo.png` + `CNAME`) and
publishes it to `gh-pages`. MR-019 is genuinely `done` and every one of its acceptance
criteria reproduces. MR-020 is `blocked` on a single human-only DNS record; everything
automatable is shipped and verified, and the remainder is proposed for explicit carry-over.

The G7 row passes on both arms it requires:

- **"Every committed ticket is `done` or explicitly carried over."** MR-019 is `done`.
  MR-020's remainder is a legitimate carry-over — it is an `infra` ticket, **not** a
  docs-sweep ticket, so the "a docs-sweep ticket is NOT eligible for carry-over" exclusion
  does not bite. The blocker is the textbook case the Blocking rule is written for: an
  unmet prerequisite only the domain owner can satisfy.
- **"No committed ticket has docs deferred to a docs-sweep ticket that is not yet `done`."**
  Satisfied vacuously: sprint-05 created no docs-sweep ticket. MR-020's one durable doc
  change (the README canonical URL) is **folded into MR-020 itself**, gated by that
  ticket's own AC ordering — not deferred to a trailing sweep ticket. The force-close clause
  for deferred docs therefore has nothing to act on.
- **Unconditional smoke** (rebuild + `curl /healthz` + `/api/reviews`): reproduced green
  (F6). The per-page DOM-assertion + screenshot trigger is **not** owed: the G7 row fires it
  "only if a product page (`viewer.html` / `dashboard.html` / `static/**`) was touched."
  `site/index.html` is none of those and is outside `static/**`. This was correctly
  anticipated in the G1-passed plan (Process / gate enforcement note), which routed the
  render obligation into MR-019's own G4 AC instead of leaning on the G7 trigger — and that
  AC is satisfied (F3).

Verdict: **PASS**. The two open items (F7, F8) are MINOR/NIT and do not block the close.
The sprint may move to `closed` once `close_review:` is set and the retro/carry-over note is
recorded (the sprint file already carries the carry-over rationale in its Notes).

## Findings

### F1 — Zero-build AC holds. (verified, no defect)
`find site -type f` returns exactly `CNAME`, `demo.png`, `index.html`. No
`package.json` / lockfile / `requirements.txt` / generator config anywhere associated with
the page. `site/index.html` is a single hand-written file with one inline `<style>` and zero
JS. No framework, bundler, preprocessor, or dependency manifest. AC met.

### F2 — No-drift AC holds. (verified, no defect)
Grep of `site/index.html` for the eight MCP tool names (`create_review` … `delete_review`)
and for README table-header rows returns nothing inline. The three changeable-fact references
are `href`s into the README, and all three anchors resolve to real headings:
`#api` -> `## API`, `#run` -> `## Run`, `#mcp-server-optional` -> `## MCP server (optional)`.
The links are not dead — this is the failure mode the no-drift principle exists to prevent,
and it is clean.

### F3 — MR-019 render obligation reproduces. (verified, no defect)
`python3 -m http.server 8201 --directory site` +
`scripts/render-smoke.sh http://localhost:8201/ .hero .demo img.demo-img .curl-flow .run-it .mcp .repo-link`
-> all 7 selectors ok (1 node each), exit 0. The render-evidence PNGs
(`reviews/sprint-05-render-evidence-2026-06-09/landing-page-light.png` and `-dark.png`) were
opened and show the actual page first-paint in both colour schemes: dark mode applies the
`--bg:#111` / `--accent:#2dd4bf` tokens, confirming the dark `:root` block is live, not just
present. `site/demo.png` shows the viewer mid-review with an **active** note (#4, highlighted
quote + gutter card) **and** a **struck-through addressed** note (#2) — both states the AC
demands — with the toolbar reading "1 note (1 done)". AC met.

### F4 — CNAME byte-exact. (verified, no defect)
`site/CNAME` is 24 bytes, `mdreview.waqasrana.space`, no trailing newline. The same content
lands at the `gh-pages` root (`git show origin/gh-pages:CNAME`). AC met.

### F5 — gh-pages publish is correct and parity-clean. (verified, no defect)
`git log origin/gh-pages --oneline` shows the single root commit `a528282`
("publish: site -> gh-pages (MR-020)"). `git ls-tree origin/gh-pages` is `CNAME`, `demo.png`,
`index.html` — i.e. the **contents** of `site/` at the branch root, not nested under `site/`,
exactly as Decision 3 specifies. `diff` of `git show origin/gh-pages:index.html` against
`site/index.html` is byte-identical: published artifact and editable source have not drifted.
`dev`/`main` are untouched by the publish (the worktree-on-orphan-branch path was used).

### F6 — G7 unconditional smoke reproduces; deviation from `docker compose up -d --build` is sound. (verified, no defect)
`docker build` from the tree succeeds; a throwaway container on `-p 8137:8080` returns
`/healthz` -> `{"ok": true}` and `/api/reviews` -> `{"reviews": []}`; the container was
removed. The deviation honors the smoke's **intent** (prove the image still builds and serves
from a clean tree) while protecting the user's live instance — and that instance is real: a
container named `mdreview` is bound to `0.0.0.0:8139->8080`, while the compose file maps 8137,
so `docker compose up -d --build` would have recreated/moved the live instance the MCP server
points at. The live 8139 instance answered `/healthz` ok **after** my smoke, confirming it was
never touched. The Dockerfile is absent from both sprint commits (`c6b30a4`, `47d110c`); the
page is correctly outside the image, by design.

### F7 — MINOR: demo.png was captured against the live 8139 instance, not the plan's prescribed local 8137. (open)
MR-019's Work log records the demo screenshot was staged on "the local running instance
(port 8139)". Epic Decision 2 explicitly prescribes capture "against a **local**
docker-compose viewer on `localhost:8137` (deterministic, no dependence on the live
instance)." The captured asset itself is correct and was visually verified (F3), so this is
not a defect in the artifact — but the procedure used the very live instance the plan told it
to avoid, defeating the determinism guard. Impact is nil for the shipped PNG; flag it so a
future re-capture (MR-021's GIF swap) uses a throwaway instance per Decision 2 and does not
stage-then-delete a review on the user's live container.

### F8 — NIT: the README-URL withholding is correct and does NOT violate the DoD docs rule. (open, informational)
MR-020's README canonical-URL AC is deliberately unchecked. This is correct, not a DoD miss:
the docs change is **folded into MR-020** (gated by the ticket's own AC ordering — "record the
URL *after* the verification block is green"), not deferred to a docs-sweep ticket. The DoD
allows the docs change "in the same change," which is exactly the plan: it travels with MR-020
when MR-020 finishes. Confirmed `README.md` contains no `mdreview.waqasrana.space` string today
(it must not, since the URL 404s without DNS). The resume sequence in the ticket re-checks all
four verification commands before the README edit. No carry-over of *docs* across a sprint
boundary occurs here — the docs ride the carried `infra` ticket, which is permitted; only
docs-sweep *tickets* are carry-over-ineligible, and none exists.

## Per-ticket AC verification

### MR-019 — Author buildless landing page (status: done)

| # | Acceptance criterion | Result | Evidence |
|---|----------------------|--------|----------|
| 1 | Single hand-written HTML, inline `<style>`, no framework/bundler/manifest | PASS | F1 |
| 2 | Six landmarked sections (.hero/.demo+img.demo-img/.curl-flow/.run-it/.mcp/.repo-link) | PASS | F3 (render-smoke 7/7) |
| 3 | Full dashboard `:root` set incl. `--noteline`, dark block, both font stacks | PASS | index.html:10-16; dark tokens visible in dark PNG (F3) |
| 4 | Responsive as behavior (max-width 920px, img max-width:100%, pre scroll) | PASS | index.html:14,33,38 |
| 5 | demo.png mid-review (active + struck note), procedure recorded | PASS | F3; Work log records procedure (b) |
| 6 | CNAME exactly `mdreview.waqasrana.space` | PASS | F4 |
| 7 | No-drift: no API/config/MCP text inline; changeable facts are hrefs | PASS | F2 |
| 8 | G4 target: http.server + render-smoke exits 0 | PASS | F3 |
| 9 | Rendered-page screenshot committed under render-evidence | PASS | F3 (light+dark) |
| 10 | py_compile app.py | PASS | reproduced green; app.py untouched |

MR-019: all 10 AC met.

### MR-020 — Publish to GitHub Pages (status: blocked, remainder carried over)

| # | Acceptance criterion | Result | Evidence |
|---|----------------------|--------|----------|
| 1 | gh-pages orphan branch = contents of site/ at root incl. CNAME, via worktree seq | PASS | F5 (root `a528282`; ls-tree; identical) |
| 2 | One-time setup runbook recorded, each step marked done/automated/human-pending | PASS | MR-020 Work log; steps 1-2 done, 3 human-pending, 4 pending-on-3 |
| 3 | Publish-verification block green OR blocked items recorded with re-run command | PASS (with carry) | edge-verified via `--resolve`; DNS/HTTPS recorded human-pending w/ exact resume cmds |
| 4 | README records canonical URL — only after verification passes | DEFERRED (correct) | F8 — folded into MR-020, gated by AC ordering; carries with the ticket |
| 5 | py_compile app.py | PASS | reproduced green |

MR-020: every automatable AC met; AC 3's live arm and AC 4 are gated on the human DNS step.
Remainder is a legitimate explicit carry-over (Summary).

## Carry-over decision

**Approved.** MR-020 carries to the next cycle (which already holds MR-021) with its remainder
being: (1) the human DNS `CNAME mdreview -> waqaskhan137.github.io` record; (2) HTTPS enforce;
(3) the README canonical-URL edit — all sequenced in the ticket's recorded resume block. This
carry-over is valid under the G7 row because MR-020 is `infra`, not a docs-sweep ticket, and no
deferred-docs-to-a-sweep-ticket condition exists.

## Resolution log

- 2026-06-09 — Review opened. Verdict PASS. F1-F6 verified, no defect. F7 (MINOR) and F8
  (NIT/informational) left open as advisories; neither blocks the close. Orchestrator to set
  `close_review:` in `sprints/sprint-05.md` frontmatter and record the carry-over in the retro
  before flipping the sprint to `closed`. F7 should be honored when MR-021 re-captures the demo
  asset (use a throwaway instance per Decision 2).
- 2026-06-09 — **F7 carried** into `tickets/MR-021-animated-demo.md` (Notes / context: throwaway
  local instance for the GIF capture, citing this review). **F8** informational, no action. All
  findings resolved or carried -> `status: resolved` (orchestrator, closing the sprint).
