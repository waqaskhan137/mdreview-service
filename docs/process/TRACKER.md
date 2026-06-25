# TRACKER — the board

At-a-glance view of every ticket grouped by status. The ticket frontmatter is the source of
truth; move a row here whenever a ticket's `status` changes.

Last updated: 2026-06-25. **sprint-26 (viewer-transparency, GH #27) CLOSED at G7 — MR-073/075 done; epic complete; owner confirmed working; awaiting the standing dev→main PR.** **sprint-25 (watcher-container, GH #30) CLOSED at G7 — MR-069-072 done; epic complete; awaiting the standing dev→main PR.** **sprint-24 (watcher-observability, GH #26) CLOSED at G7 — MR-066/067/068 done; epic complete; awaiting the standing dev→main PR.** **sprint-12 (mcp-agent-effectiveness) CLOSED at G7 (staff-critic PASS, 0 BLOCKER/0 SHOULD/1 NIT)** — the MCP is now provably self-serve: `agent_smoke.py` drives the wrapper as an agent and proves create → `attach_asset(path=…)` → `<img>` renders (`naturalWidth>0`) with zero human curl, and a stale server is detectable (`server_info` `tools_hash` + `--print-version` + reconnect). G1 passed 2 rounds. **Awaiting the standing dev→main PR.** **sprint-11 (comment-resolution) + sprint-10 (dashboard) merged to main via PR #9.** sprint-09 (dashboard-redesign) merged to main (PR #8). sprint-08 (render-fidelity) merged to main (PR #7). sprint-07 (theme-awareness) merged to main (PR #6). sprint-06 (rich-rendering) merged to main (PR #5). sprint-05 (landing-page) merged to main (PR #4); page LIVE at https://mdreview.waqasrana.space/ (HTTPS enforced).

## Active sprint

**EPIC `oop-refactor-src-layout` ACTIVE. sprint-27 OPEN 2026-06-25** (G1 PASS 2026-06-25, 2 rounds, staff-critic PASS-WITH-NITS — r1 CHANGES-REQUESTED on 1 blocker [the router→service boundary missed the inline GET/DELETE comment arms + a gameable acceptance grep], fixed in r2). Tier B internal-quality refactor on branch `refactor/oop-src-layout` (off `dev`): all code under `src/`, a clean root, and `app.py`'s 833-line monolith decomposed into 7 single-responsibility modules (`config`/`store`/`comments`/`assets`/`reviews`/`handoff`/`server`) wired by **constructor injection** (one `Store` injected into service classes, bundled onto a `ThreadingHTTPServer` subclass the handler reads). **Pure internal refactor — API + `/data` format + viewer byte-identical** (a golden curl transcript is the oracle; no test framework). **Move-first** (Phase 0: MR-076-079 relocate to `src/`+`web/`+`tests/`, fix `HERE`→`WEB_DIR`, repoint the live `py_compile` gate) **then decompose** (Phase 1: MR-080-086 bottom-up, one module per commit, smoke-green each step). Infra stays at root. 11 tickets `ready`; validated against rebuilt throwaway containers on scratch ports, never the live `:8139`/`mdreview-data`.

**EPIC `viewer-transparency` (GH #27) COMPLETE. sprint-26 CLOSED at G7 2026-06-25** (staff-critic PASS, `reviews/sprint-26-close-review-2026-06-24.md`; independent — rebuilt container + node-CDP lifecycle re-drive incl. signal-honesty + no-regression + both panes; W1 resolved, owner confirmed working). G1 PASS 2026-06-24 (GO-WITH-NITS)**.** (staff-critic
GO-WITH-NITS, `reviews/viewer-transparency-plan-review-2026-06-24.md`; 2 nits folded; owner chose
**step-level** over the literal tool-call stream). While an agent works a turn, the viewer shows a
**live progress timeline** (Connected → Editing → Updating comments → Done/Stopped) **derived from the
`/status` signals it already polls** — no service change, no agent instrumentation — plus a **live
elapsed timer** + a **final revision duration**, so a long-but-working run reads as progress, not a
freeze (the owner watched a ~2.5-min run that looked frozen). Builds on MR-062/066/067/068, doesn't
redo them. **MR-073** `ready` (ui): the timeline + timer in `renderBanner` (cumulative steps,
signal-honest labels — "Updating comments", "Resolved" only on terminal `done`; client-captured final
duration). **MR-075** `ready` (docs, depends MR-073): docs sweep. **MR-074 cut** (the `ping_working`
`message` already round-trips). Tier-2 stream-json events deferred to backlog. G7 owes a node-CDP
lifecycle drive (render-smoke can't drive a time-dependent banner); evidence under
`reviews/sprint-26-render-evidence-2026-06-24/`.

**EPIC `watcher-container` (GH #30) COMPLETE. sprint-25 CLOSED at G7 2026-06-24** (staff-critic PASS, `reviews/sprint-25-close-review-2026-06-24.md`; independent — rebuilt the image, re-ran both auth gates + the compose e2e; W1/N1 resolved). G1 PASS 2026-06-24 (GO-WITH-NITS, 6 nits folded)**.** (staff-critic
GO-WITH-NITS, `reviews/watcher-container-plan-review-2026-06-24.md`; 6 nits folded). Makes the watcher
an OPT-IN docker service (`docker compose --profile watcher up`) authenticated by the user's Claude
**subscription** (not an API key — too expensive for most), so a local deploy can auto-action reviewer
comments. The public-instance fail-closed host watcher stays; this is the local-use path. Auth path
verified viable (`claude setup-token` is subscription-billed; `CLAUDE_CODE_OAUTH_TOKEN` is the headless
env var). **MR-069** `ready` (infra): promote the working agent-launch prototype into `watcher/` +
`.env.example` + gitignore `.env`. **MR-070** `ready` (infra, depends MR-069): `Dockerfile.watcher`
(Node + `claude` CLI) + the **gating in-container auth + MCP-round-trip proofs** (real flag shape,
trust dialog settled, non-root writable home) — needs a real `setup-token`. **MR-071** `ready` (infra,
depends MR-070): opt-in compose `profile: [watcher]` (off by default, `service_healthy`-gated) +
end-to-end Send→action; **closes GH #30**. **MR-072** `ready` (docs, depends MR-071): setup-token /
`.env` / rotation / startup-auth-probe runbook. Infra epic ⇒ docker build/compose are the G7 gates (no
render-smoke); all on throwaway names/ports, never the live `mdreview`/`mdreview-data`/:8139/:8137.

**EPIC `watcher-observability` (GH #26) COMPLETE. sprint-24 CLOSED at G7 2026-06-24** (staff-critic PASS,
`reviews/sprint-24-close-review-2026-06-24.md`; independent — rebuilt a throwaway container on scratch
port 8182 and re-drove all three tickets via node-CDP + real `watch.py` stub runs incl. the conflation
guard; F1 resolved, F2/F3/F4 accepted non-blocking). G1 PASS 2026-06-24 (GO-WITH-NITS, five nits folded). Makes a stuck/crashed agent run visible — triggered by a live
bug (Send-to-agent with no watcher running spun the banner ~20 min: the waiting-for-pickup state has
no timeout and MR-062's spinner made it look like "working"). Three tickets, no `app.py` change, no
auto-relaunch. **MR-066** `ready` (ui): client-side pickup-timeout in `renderBanner` — after
`PICKUP_GRACE_S=60` at `turn=agent`/`agent_status=null`, flip the parked spinner to a distinct
non-spinning `.warn` "no agent has picked this up — is a watcher running?" cue (defines the `.warn`
class; fixes the live bug alone). **MR-067** `ready` (svc/`watch.py`): capture the crashed child's
stderr + full `print()`→`logging` migration + `WATCH_LOG_FILE` (stderr-default) + a guarded crash
`hand_back{state:blocked}` signal (MANDATORY `/status` re-check skips the signal if the child already
handed back `done` — no false "stopped"). **MR-068** `ready` (ui, depends_on [MR-066, MR-067]):
render the crash signal as the "agent run stopped — Take back the turn" `.warn` banner end-to-end.
G7 owes node-CDP banner-drives (time-dependent + signal-driven; render-smoke can't drive either) +
the watcher crash-stub / false-positive-guard / happy-path runs; evidence under
`reviews/sprint-24-render-evidence-2026-06-24/`.

**EPIC `history-version-fix` COMPLETE.** **sprint-23 CLOSED at G7 2026-06-24** (staff-critic PASS,
`reviews/sprint-23-close-review-2026-06-24.md`; independent — the critic re-drove the History modal with a
fresh node-CDP script, 11/11 incl. the v0 edge; GH #18 closed). A small two-ticket
batch fixing the document History modal: it mislabels versions (tops out at `v(N-1)` while the
dashboard badge shows `vN`, never lists the current live draft) and stamps every round "0 notes" (the
retired `notes.json` count, untruthful and unrecoverable for existing rounds). Implements GH **#18**.
**MR-064** `ready` (svc): `snapshot_round` stops writing `notes_total`/`notes_addressed` into
`round.json` (the count lie has no backing data; the `summary()` per-review `notes_total` is a
different, untouched field) + update `README.md:55` `/history` per-round shape to `{round, ts}`;
svc + a README line → no render-smoke, gate is `py_compile app.py` + a curl smoke (POST → 2 PUTs →
`/history` + `/history/{n}` show the new `round.json` shape with no `notes_total`) + a README grep.
**MR-065** `ready` (ui, depends_on MR-064): the History modal lists the current draft as a top
`current (v{rev})` entry from `GET /source` + `revision` (no new endpoint; relocate the
`viewer.html:678` early-return so it always renders, plain `current` at revision 0), relabels archived
rounds `v{round} · earlier draft` newest-first (display-only — `round-n`/`/history/{n}` NOT
renumbered), and removes the "· N notes" label + empty per-round notes block. **MR-065 IS a
product-page change** (`viewer.html`) → G7 owes a **node-CDP modal-DOM verification** (the proven
`agent_smoke.py:112-148` pattern: `openHistory()` then read the modal back — `.histitem` >= 3, top
`current (v2)` == dashboard `.badge`, archived `v1`/`v0` newest-first, NO "notes" text on the rendered
DOM, current-entry click → `#histview .histdoc` with the draft text) **plus a screenshot**, NOT a bare
render-smoke against the modal selectors (the sprint-07 wall: the modal is `display:none` until a
click, so render-smoke's `--dump-dom` false-fails). Both rebuild a throwaway container on a scratch
port (never 8139/8137/compose); evidence under `reviews/sprint-23-render-evidence-2026-06-24/`.

**EPIC `watcher-ux-fixes` COMPLETE.** **sprint-22 (spinner + recipe arg-order) CLOSED at G7 2026-06-24**
(staff-critic PASS, `reviews/sprint-22-close-review-2026-06-24.md`; independent — the critic rebuilt a
throwaway image and re-ran the MR-062 render-smoke, State A waiting-for-pickup `.loading` present being
the headline; GH #25 closed). Epic cleared **G1 2026-06-24** (PASS-WITH-NITS, the MR-062 smoke-recipe nits folded:
viewer route `/review/{id}`, stale state non-force-stampable → code inspection, reviewer-flip body
`{to:reviewer,by:reviewer}`, reduced-motion probe targets `::before`). A small two-ticket batch
cleaning up watcher rough edges the product owner hit testing end-to-end — both fixes already designed
and validated, so the sprint is restore + verification, not redesign. **MR-062** `ready` (ui): restore
git `stash@{0}` ("spinner-wip (MR-062)") onto `viewer.html` — an 11px `--muted` rotating ring on
`#turnbanner.loading #turntext::before` (`animation:turnspin .8s linear infinite`) added by
`renderBanner` in **both** the waiting-for-pickup (`if(!as)`) and "Agent is working…" arms, **superseding
MR-061**'s pulse + `turnworking` keyframes (deleted), with a `prefers-reduced-motion` static-ring
fallback; no `loading` in the stale arm nor on a reviewer turn. **MR-062 IS a product-page change**
(`viewer.html`), so G7 owes a render-smoke (rebuilt throwaway container, scratch port, never
8139/8137/compose) asserting the bare class `.loading` present in States A/B (`{to:agent}` then
`{state:working,owner:smoke}`), absent after a `{to:reviewer,by:reviewer}` reclaim (exit 1 on 0 nodes),
the stale arm by code inspection (`viewer.html:241`), a CDP reduced-motion probe on `::before`
(`none`/`turnspin`), and both-pane scheme-emulated screenshots; evidence under
`reviews/sprint-22-render-evidence-2026-06-24/`. **MR-063** `ready` (docs): reorder the three scoped
watcher launch-recipe literals at `README.md:193/198/208` prompt-last
(`…,"--allowedTools","mcp__mdreview__*","-p","<prompt>"]`) so the variadic `--allowedTools` stops
swallowing the prompt, add the variadic note, confirm the full-autonomy recipe (`README:217`) is
already prompt-last; README-only (`CLAUDE.md` has no recipe literal), closes GH #25. Docs-only — no
render-smoke owed; gate is `py_compile app.py` + grep.

**EPIC `working-banner-animation` COMPLETE.** **sprint-21 (waiting ellipsis) CLOSED at G7 2026-06-24**
(staff-critic PASS, `reviews/sprint-21-close-review-2026-06-24.md`; independent — the critic rebuilt a
throwaway image and re-ran the render-smoke: `.working` present in the working state / absent after
reclaim, both-pane screenshots, reduced-motion probe `none`/`turnworking`; evidence under
`reviews/sprint-21-render-evidence-2026-06-24/`). Shipped MR-061 — a pure-CSS pulsing waiting ellipsis on
the viewer's `working`-state turn banner, only that state animates, with a `prefers-reduced-motion`
off-switch. `viewer.html` only. The cheap low-hanging slice of GH #27 (progress + streaming stay in #27). A standalone small `ui` enhancement — the cheap low-hanging slice of GH
**#27** (the rest of #27, behind-the-scenes progress steps + streamed/diff-animated document updates,
stays in #27). The viewer's turn banner is **static** ("Agent is working on your feedback…") while the
agent holds the turn — indistinguishable from a hung agent (the GH #25/#26 confusion). **MR-061**
`ready`: a CSS-only animated ellipsis on `#turntext::after`, gated to a `working` class that only
`renderBanner`'s working arm sets (a single `remove` at the top + `add` in the working arm), with a
REQUIRED `prefers-reduced-motion` off-switch; only the working state animates, every other banner
state is byte-for-byte unchanged. `viewer.html` only — no `app.py`/Dockerfile/MCP/`meta.json` change.
**This IS a product-page change**, so G7 owes a render-smoke (rebuilt throwaway container, scratch
port, never 8139/8137) asserting `#turnbanner`/`#turntext` + the bare class `.working` (present in the
working state, absent after a reclaim), both-pane screenshots, and the CDP reduced-motion probe
(`getComputedStyle($("#turntext"),'::after').animationName === 'none'` under reduce); evidence under
`reviews/sprint-21-render-evidence-2026-06-24/`.

**EPIC `watcher-launch-fix` COMPLETE.** **sprint-20 (inert default + runbook) CLOSED at G7 2026-06-24**
(staff-critic PASS, `reviews/sprint-20-close-review-2026-06-24.md`; independent — the critic re-ran the
startup-exit + configured-runs + docs-sweep against a `.scratch/` throwaway). Epic cleared G1 2026-06-24 (PASS-WITH-NITS, scaffolding findings
folded) — a small `svc`(+same-change `docs`) follow-up to the now-done `agent-watcher` epic. The shipped
watcher's runnable `DEFAULT_LAUNCH_CMD` (`claude -p …`) **silently no-ops headless** (MCP tool use routes
to a no-TTY approval prompt; the agent claims the lease and hands back without doing the work). Option B
(decided across both critic rounds): replace it with an **inert must-configure stub** so the watcher
**refuses to start at startup** (exit 2 with guidance, in `main()` after the trusted-base gate, before
`run()`) when `WATCH_LAUNCH_CMD` is unset — never claiming a lease it cannot honour — move the permission
posture into runbook recipes (scoped `dontAsk` + `allowedTools "mcp__mdreview__*"`, and the full-autonomy
recipe), sweep the 8 "default Claude headless" doc spots, and ship the injection caveat. **MR-060**
`ready`. No `app.py` / Dockerfile / UI change, no render-smoke (`watch.py` not containerized; docs are
Markdown) — the G7 smoke is `py_compile watch.py` + the 2-arm stub-launch end-to-end on a localhost
throwaway.

**EPIC `agent-watcher` COMPLETE (C1+C2+C3).** **sprint-19 (C3: watcher safety + ops) CLOSED at G7
2026-06-24** (staff-critic PASS-WITH-NITS, `reviews/sprint-19-close-review-2026-06-24.md`; independent —
the critic re-ran the full arming/cap matrix against a `.scratch/` throwaway service; one README-example
nit fixed) — the **FINAL** `agent-watcher` chunk. Relaxes C2's fail-closed refusal via a **local operator arming/allowlist**
(`WATCH_ARMED_FILE` primary + `WATCH_ARMED` env, unioned, **not** HTTP-settable) so the watcher can
auto-run **armed** reviews on a public/no-auth base — un-armed reviews are **skipped without a claim**
even at `turn==agent`; Step-0 becomes run-but-gate when armed (EXIT preserved when not). Adds a
**per-review attempt cap** bounding the legitimate **re-Send / re-surface loop** (the corrected B1 model —
NOT a crash-loop; crashes strand by design, no auto-relaunch), and the **full operator runbook**
(README + CLAUDE.md). **MR-058** + **MR-059** `ready`. No `app.py`/Dockerfile change, no render-smoke
(`watch.py` not containerized, docs are Markdown). **At close (G7 PASS) the `agent-watcher` epic is marked
`done`** (C1 sprint-17 + C2 sprint-18 + C3 sprint-19).

**sprint-18 (agent-watcher — C2: watcher core) CLOSED at G7 2026-06-24** (staff-critic PASS,
`reviews/sprint-18-close-review-2026-06-24.md`; independent — the critic re-ran the fail-closed exit,
the no-injection spawn, single-flight, the caps, and the B1 stranded-baton crash model). C2 shipped
`watch.py` — the first code outside the service container and the first credentialed process spawner:
long-polls C1's `/wait`, **fails closed** (refuses an untrusted base), **claims-before-spawn** (spawns
only on a `200` lease grant), runs the operator's configured launch command (default Claude) with a
child env contract, and bounds normal-load spend with a concurrency + launches/hour cap. **MR-056** +
**MR-057** done, merged to `dev`. No `app.py`/Dockerfile change. Next: C3 (arming relaxation for
untrusted/public bases + per-review attempt cap + full runbook).

**sprint-17 (agent-watcher — C1: server support) CLOSED at G7 2026-06-24** (staff-critic PASS,
`reviews/sprint-17-close-review-2026-06-24.md`; independent; container render-smoke
`reviews/sprint-17-render-evidence-2026-06-24/`). Epic `agent-watcher` cleared G1 2026-06-24
(PASS-WITH-NITS, findings folded). Shipped the three server-side primitives the (C2) watcher polls — a
`?turn=agent` queue filter, a `/wait` long-poll (Condition over `_lock`, required
`?since=<turn_updated>` edge cursor), and a stale-lease takeover on `/handoff {state:working}` —
entirely inside the existing container (no UI, no Dockerfile change). **MR-054** + **MR-055** done,
merged to `dev`. Next: C2 (the `watch.py` watcher core) as its own cycle.

_(previously)_ **EPIC `agent-handoff-baton` COMPLETE.** **sprint-16 (Chunk 3, agent surface) CLOSED
at G7 2026-06-23** (staff-critic PASS, `reviews/sprint-16-close-review-2026-06-23.md`; independent
`mcp_smoke` 44/44 + end-to-end baton drive over HTTP **and** MCP stdio, 0 BLOCKER / 0 SHOULD / 1 NIT).
MR-053 `done` on `dev` (`hand_back` + `ping_working` MCP tools over `/handoff` + the `CLAUDE.md`
agent contract; tools 18→20). No carry-overs. All 3 chunks shipped — **MR-051 + MR-052 + MR-053 in
the standing dev→main PR #17.** Concurrent co-editing (OT/CRDT) deferred as issue #16.

_(previously)_ **sprint-15 (agent-handoff-baton — Chunk 2, viewer turn UI) CLOSED at G7 2026-06-23**
(staff-critic PASS, `reviews/sprint-15-close-review-2026-06-23.md`; independent rebuild-from-disk +
render-smoke + all 6 banner rows driven + XSS probe, 0 BLOCKER / 0 SHOULD / 3 NITs, NITs addressed
post-review). MR-052 `done` on `dev` (`viewer.html`: Send button + 6-state banner + reclaim, screenshots
under `reviews/sprint-15-render-evidence-2026-06-23/`). No carry-overs. **In the standing dev→main PR
#17.** The `agent-handoff-baton` epic stays **active** — **MR-053 (Chunk 3, MCP + CLAUDE.md)** remains
`ready` for the next sprint.

_(previously)_ **sprint-14 (agent-handoff-baton — Chunk 1) CLOSED at G7 2026-06-23** (staff-critic
PASS, `reviews/sprint-14-close-review-2026-06-23.md`; independent rebuild + 15-step smoke, 0 BLOCKER /
0 SHOULD / 2 NITs). MR-051 `done` on `dev` (server baton contract: `POST /handoff` + 4 `meta.json`
fields + `/status` surfacing, additive, ships invisibly). No carry-overs. **In the standing dev→main
PR #17.** The `agent-handoff-baton` epic stays **active**.

_(previously)_ **sprint-13 (legacy-feedback-retire) CLOSED at G7** (staff-critic PASS,
`reviews/sprint-13-close-review-2026-06-19.md`; independent rebuild + smoke, every reader region
byte-compared). MR-046 + MR-047 `done` on `dev`, no carry-overs. Shipped: `POST /feedback` → 410
Gone (no write), `feedback_updated` writer dropped, docs steer agents to `comments_updated` — every
reader and all 61 live notes/feedback files untouched. No `mcp_server.py` change → no MCP reconnect.
**Merged to main 2026-06-23 (PR #11)** — together with MR-048 (MCP wrapper browser-open) and MR-049
(viewer comment UX: reliable selection→button + markdown comments + home link).

_(previously)_ **sprint-12 (mcp-agent-effectiveness) closed at G7** (staff-critic PASS,
`reviews/sprint-12-close-review-2026-06-19.md`). All 6 tickets `done` on `dev`; no carry-overs.
The headline `agent_smoke.py` proves the agent loop renders unaided. Pending the standing
`dev → main` PR (G8).

_(sprint-11 comment-resolution + sprint-10 dashboard already merged to main via PR #9.)_

**sprint-10 — dashboard-density** (`closed` out-of-cycle, 2026-06-19). Epic: `dashboard-density` (G1 passed 2 rounds; **G7 waived by user exception**). Shipped MR-032's density CSS **within a direct flat continuous-grid redesign** (commit `0f44c1b`): one packed grid (newest-first, project-as-inline-tag, zero gutters) is now the default, with a "Group by project" toggle to the grouped sections (which keep the MR-032 density). `dashboard.html` only. Render-validated via CDP; not independently G7-reviewed.

**sprint-09 — dashboard-redesign** (`closed`, 2026-06-19; merged to main, PR #8). Epic: `dashboard-redesign` (G1 passed 2 rounds; G7 PASS). Shipped MR-031: `dashboard.html` rewritten into a dense, full-width (capped 1600px), searchable grid of collapsed click-to-expand cards with collapsible project groups; open/delete/version/notes + pane-adaptive theme preserved (CDP-verified). `dashboard.html` only.

**sprint-08 — render-fidelity** (`closed`, 2026-06-18; merged to main, PR #7). Epic: `render-fidelity` (G1 passed 2 rounds; G7 PASS-WITH-CONDITIONS, resolved). Shipped MR-028 (GFM footnotes, vendored marked-footnote), MR-029 (syntax highlighting, vendored highlight.js common + marked-highlight, dual-scheme theme, mermaid skipped), MR-030 (docs). Viewer + vendored `static/` only.

**sprint-07 — theme-awareness** (`closed`, 2026-06-18; merged to main, PR #6). Epic: `theme-awareness` (G1 passed 2 rounds; G7 PASS). Shipped MR-027: a near-white mat behind `#article img` + `.histdoc img` so light-authored figures stay legible on a dark review pane (excludes mermaid/katex; CSS-only). Inverse case (dark-authored/white-on-transparent figures) is an accepted non-goal (luminance heuristic backlog).

**sprint-06 — rich-rendering** (`closed`, 2026-06-18; merged to main, PR #5). Epic: `rich-rendering` (G1 passed 2 rounds; G7 PASS). Shipped the two P0s: math rendering (KaTeX marked-extension) + per-review asset attach/serve over HTTP & MCP + viewer `<img>` rewrite. MR-022–026 all `done`; local-dir `path` read form cut to backlog (S5).

**sprint-05 — landing-page** (`closed`, 2026-06-09; merged to main, PR #4). Epic: `landing-page`. G7 PASS; MR-019 done, MR-020 done (carry-over discharged: DNS added, cert issued, HTTPS enforced, README URL recorded). MR-021 (GIF demo) remains backlog.
sprint-01/02/03/04/05/06/07/08/09 shipped to main (PR #1, #2, #3, #4, #5, #6, #7, #8).

## ready

| ID | Title | Layer | Pri | Sprint |
|----|-------|-------|-----|--------|

## in-progress

_none_

## review

_none_

## done

| ID | Title | Layer | Pri | Sprint |
|----|-------|-------|-----|--------|
| MR-086 | `src/app.py`->`src/mdreview/server.py` + `Services`/`MdreviewServer` composition root + `__main__`; no-store-helper ZERO; `python -m mdreview`; all smokes + container PASS | svc | P1 | sprint-27 |
| MR-085 | Extract `handoff.py` + `HandoffService` (turn baton + lease table); byte-identical + lease matrix 5/5 (TTL=0 stale paths) | svc | P1 | sprint-27 |
| MR-084 | Extract `reviews.py` + `ReviewService` (lifecycle/summary/list/history/source/feedback/delete); byte-identical incl. /feedback-with-comment | svc | P1 | sprint-27 |
| MR-083 | Extract `assets.py` + `AssetService` (content-hash + manifest); byte-identical + agent_smoke render proof (nw=1); folded agent_smoke 18->20 | svc | P1 | sprint-27 |
| MR-082 | Extract `comments.py` + `CommentService` (G1-blocker inline GET/DELETE arms -> named methods); byte-identical lifecycle | svc | P1 | sprint-27 |
| MR-081 | Extract `store.py` + `Store` (the one Condition + typed IO); byte-identical + long-poll wake smoke (1.08s, not 20s timeout) | svc | P1 | sprint-27 |
| MR-080 | Extract `config.py` (constants + `WEB_DIR` 3-deep anchor) + package skeleton (`src/mdreview/`); byte-identical | svc | P1 | sprint-27 |
| MR-079 | Repoint live `py_compile` gate + `render-smoke.sh` path + layer-table/page paths to `src/`+`tests/`+`web/` (frozen history untouched) | docs | P2 | sprint-27 |
| MR-078 | Move `mcp_server.py`/`watch.py`→`src/`, smokes→`tests/`; fix `SERVER` path + `Dockerfile.watcher` COPY (stable `/app` dests); mcp_smoke + watcher build green | infra | P1 | sprint-27 |
| MR-077 | Service `Dockerfile` → `src/`+`web/` layout (`MDREVIEW_WEB_DIR`/`PYTHONPATH`, `CMD python src/app.py`); build + container render-smoke green | infra | P1 | sprint-27 |
| MR-076 | Relocate `app.py`→`src/app.py` + frontend→`web/` + `HERE`→`WEB_DIR`; golden-transcript oracle (byte-identical) | svc | P1 | sprint-27 |
| MR-065 | History modal: list current draft as `current (vN)`, relabel rounds, drop "0 notes" (GH #18) | ui | P2 | sprint-23 |
| MR-064 | snapshot_round: stop writing the retired notes count into round.json (+ README /history shape) (GH #18) | svc | P2 | sprint-23 |
| MR-063 | Fix the scoped watcher launch recipe arg order — `-p` prompt last (GH #25) | docs | P1 | sprint-22 |
| MR-062 | Replace MR-061's pulse with a rotating CSS spinner on both agent-turn waiting states | ui | P2 | sprint-22 |
| MR-061 | Animate the viewer's `working`-state turn banner (CSS-only ellipsis) | ui | P2 | sprint-21 |
| MR-060 | Watcher must-configure launch stub — refuse-to-start at startup when `WATCH_LAUNCH_CMD` unset + runbook recipes + injection caveat | svc | P1 | sprint-20 |
| MR-059 | `watch.py` per-review attempt cap + full operator runbook — bound the re-Send loop, document the public-instance arming story | svc | P1 | sprint-19 |
| MR-058 | `watch.py` arming / allowlist — relax C2's fail-closed Step 0 (local `WATCH_ARMED_FILE`/`WATCH_ARMED`, run-but-gate) | svc | P1 | sprint-19 |
| MR-057 | `watch.py` spawn + child env contract + caps (generic launch template, default Claude) + trusted-base runbook stub | svc | P1 | sprint-18 |
| MR-056 | `watch.py` fail-closed loop core — trusted-base check + `/wait` long-poll + claim-before-spawn | svc | P1 | sprint-18 |
| MR-054 | Watcher detection — `?turn=agent` filter + `summary()` turn-default + `/wait` long-poll (Condition over `_lock`, required `?since=<turn_updated>` edge cursor) | svc | P1 | sprint-17 |
| MR-055 | Stale-lease takeover on `/handoff {state:working}` (TTL single-source + reclaim-vs-takeover re-check) | svc | P1 | sprint-17 |
| MR-053 | Agent surface — `hand_back` + `ping_working` MCP tools + `CLAUDE.md` contract (tools 18→20) | svc | P2 | sprint-16 |
| MR-052 | Viewer turn UI — Send button + 6-state banner + reclaim + `lastTurn` poll | ui | P2 | sprint-15 |
| MR-051 | Handoff baton contract — `POST /handoff` + 4 `meta.json` fields + `/status` surfacing (additive) | svc | P1 | sprint-14 |
| MR-050 | Viewer — reviewer can delete their own un-engaged comment (no-agent-entry rule; inline 2-step confirm; issue #12) | ui | P2 | — (out-of-cycle) |
| MR-049 | Viewer comment UX: reliable selection→comment button + markdown rendering in comment threads (XSS-safe) | ui | P2 | — (out-of-cycle) |
| MR-048 | MCP wrapper opens new `review_url` in default browser (opt-in `MDREVIEW_OPEN_BROWSER`) | svc | P3 | — (out-of-cycle) |
| MR-047 | Docs sweep: "human is done" → `comments_updated`; drop `POST /feedback` README row; fix `future-mcp.md:61` | docs | P2 | sprint-13 |
| MR-046 | Retire dead `POST /feedback` write (→ 410 Gone) + drop `feedback_updated` writer; keep every reader | svc | P2 | sprint-13 |
| MR-001 | Persist provenance (project/source_path/session) on POST + meta | svc | P1 | sprint-01 |
| MR-002 | summary() + list_reviews() + GET /api/reviews | svc | P1 | sprint-01 |
| MR-003 | Serve dashboard at /; move JSON descriptor to /api | svc | P1 | sprint-01 |
| MR-005 | History snapshots on PUT + /history routes | svc | P2 | sprint-01 |
| MR-004 | dashboard.html — Project>Session grouping, status pills, open/delete, revision badge | ui | P1 | sprint-01 |
| MR-006 | viewer.html — Google-Docs gutter comments + minimal history view | ui | P1 | sprint-01 |
| MR-007 | Docs — provenance/list/history fields + docs/future-mcp.md | docs | P2 | sprint-01 |
| MR-008 | Planner agent — fit-based-layout rule + Dockerfile-COPY footgun | docs | P2 | sprint-02 |
| MR-009 | Add scripts/render-smoke.sh (DOM-node assertion) | infra | P1 | sprint-02 |
| MR-010 | README + skill — render-smoke as the ui validation bar (G4 row) | docs | P1 | sprint-02 |
| MR-011 | README — reconcile DoD with bounded same-sprint docs-sweep (G7 row) | docs | P2 | sprint-02 |
| MR-012 | Planner agent — wire-enforcement-into-row + cite-by-name rules | docs | P1 | sprint-03 |
| MR-013 | README — citation-by-name convention + scope G7 render clause | docs | P2 | sprint-03 |
| MR-014 | Skill — pre-G7 board-reconciliation rail + SKILL.md invariant | docs | P2 | sprint-03 |
| MR-015 | mcp_server.py — stdio JSON-RPC core | svc | P1 | sprint-04 |
| MR-016 | tools/call dispatch → HTTP | svc | P1 | sprint-04 |
| MR-017 | mcp_smoke.py — stdlib smoke harness | svc | P1 | sprint-04 |
| MR-018 | Docs — MCP wrapper | docs | P2 | sprint-04 |
| MR-019 | Author buildless landing page (site/index.html) with dashboard tokens, static demo, CNAME | ui | P1 | sprint-05 |
| MR-020 | Publish to GitHub Pages — gh-pages pipeline, runbook, README URL (live at mdreview.waqasrana.space, HTTPS enforced) | infra | P1 | sprint-05 |
| MR-022 | KaTeX math render (marked-extension; binary `_read_bytes` + static content-types) | ui | P0 | sprint-06 |
| MR-023 | Per-review asset storage + manifest + `POST/GET /assets`, `GET /asset/{stored}` (base64) | svc | P0 | sprint-06 |
| MR-024 | MCP `attach_asset` + `list_assets` tools | svc | P0 | sprint-06 |
| MR-025 | Viewer rewrites local/relative/site-root `<img src>` to served asset URLs | ui | P0 | sprint-06 |
| MR-026 | Docs sweep: README API table, CLAUDE.md contract, AGENTS.md + MCP docstring (math + assets) | docs | P1 | sprint-06 |
| MR-027 | Viewer — neutral light mat behind `#article img` + `.histdoc img` (theme-safe images) | ui | P1 | sprint-07 |
| MR-028 | GFM footnotes in the viewer (vendored marked-footnote; refs + back-ref section) | ui | P2 | sprint-08 |
| MR-029 | Syntax highlighting in the viewer (vendored highlight.js + marked-highlight; dual-scheme, skips mermaid) | ui | P2 | sprint-08 |
| MR-030 | Docs — footnotes + syntax highlighting render in the viewer | docs | P2 | sprint-08 |
| MR-031 | Redesign `dashboard.html` — dense grid, collapsible cards, sticky search, collapsible groups (preserve open/delete/version/notes) | ui | P1 | sprint-09 |
| MR-032 | Dashboard density → shipped within a direct flat continuous-grid redesign + group-by toggle (out-of-cycle; G7 waived) | ui | P1 | sprint-10 |
| MR-033 | Comment store (`comments.json`) + `POST/GET /comments` + `GET /comments/{cid}` + `comments_updated` + comment-aware `GET /feedback`/`summary()` | svc | P1 | sprint-11 |
| MR-034 | Comment state machine — reply/resolve/reopen routes, `status_history`, 409 on illegal transitions | svc | P1 | sprint-11 |
| MR-035 | MCP tools `list_comments`/`get_comment`/`reply_to_comment`/`resolve_comment` + descriptions + `mcp_smoke` round-trip (14 tools) | svc | P1 | sprint-11 |
| MR-036 | Viewer — threaded `comment_id`-keyed gutter cards, authoring → `POST /comments`, retire legacy author surfaces, Resolved panel + reopen, live-reload | ui | P1 | sprint-11 |
| MR-037 | Docs sweep — README/CLAUDE/AGENTS/future-mcp + MCP docstring 10→14 + comment-aware feedback/dashboard | docs | P2 | sprint-11 |
| MR-038 | Retro: GFM table CSS in the viewer (done-on-arrival, `dae815e`) | ui | P2 | sprint-12 |
| MR-039 | Retro: click-to-zoom lightbox in the viewer (done-on-arrival, `2ed9593`) | ui | P2 | sprint-12 |
| MR-040 | MCP staleness signal — `tools_hash` + `server_info` tool + `--print-version` | svc | P1 | sprint-12 |
| MR-041 | `agent_smoke.py` — agent-loop render-proof (create→path-attach→repoint→naturalWidth>0) | svc | P1 | sprint-12 |
| MR-042 | `mcp_smoke.py` — assert `server_info` + the discoverability contract | svc | P1 | sprint-12 |
| MR-043 | Docs sweep — `server_info`/16-tool count + reconnect-on-stale guidance | docs | P2 | sprint-12 |
| MR-044 | `create_comment` MCP tool + viewer anchor-by-quoted-text (agents author review comments; 17 tools) | svc | P1 | — (out-of-cycle) |
| MR-045 | `delete_comment` — hard-remove junk comments (DELETE route + 18th tool) | svc | P2 | — (out-of-cycle) |

## blocked

_none_

## backlog

| ID | Title | Layer | Pri | Sprint |
|----|-------|-------|-----|--------|
| MR-021 | Replace static demo with animated GIF of the review loop (drop-in) and re-publish | ui | P2 | — (next cycle) |

## Epics

| Epic | Status | Gate | Sprint |
|------|--------|------|--------|
| review-dashboard | done (merged to main 2026-06-08, PR #1) | G1 passed 2026-06-08 | sprint-01 |
| process-hardening | done (merged to main 2026-06-08, PR #2) | G1 passed 2026-06-08 (2 rounds) | sprint-02 |
| process-hardening-2 | done (merged to main 2026-06-08, PR #2) | G1 passed 2026-06-09 (2 rounds) | sprint-03 |
| mcp-wrapper | done (merged to main 2026-06-09, PR #3) | G1 passed 2026-06-09 (2 rounds) | sprint-04 |
| landing-page | done (merged to main 2026-06-09, PR #4; live at mdreview.waqasrana.space; MR-021 GIF demo in backlog) | G1 passed 2026-06-09 (2 rounds) | sprint-05 |
| rich-rendering | done (merged to main 2026-06-18, PR #5) | G1 passed 2026-06-18 (2 rounds) | sprint-06 |
| theme-awareness | done (merged to main 2026-06-18, PR #6) | G1 passed 2026-06-18 (2 rounds) | sprint-07 |
| render-fidelity | done (merged to main 2026-06-18, PR #7) | G1 passed 2026-06-18 (2 rounds) | sprint-08 |
| dashboard-redesign | done (merged to main 2026-06-19, PR #8) | G1 passed 2026-06-19 (2 rounds) | sprint-09 |
| dashboard-density | active (G1 cleared; MR-032 ready) | G1 passed 2026-06-19 (2 rounds) | sprint-10 |
| comment-resolution | done (merged to main 2026-06-19, PR #9) | G1 passed 2026-06-19 (2 rounds) | sprint-11 |
| mcp-agent-effectiveness | done on `dev` (G7 PASS; pending dev→main PR) | G1 passed 2026-06-19 (2 rounds) | sprint-12 |
| legacy-feedback-retire | done (merged to main 2026-06-23, PR #11; with MR-048 + MR-049) | G1 passed 2026-06-19 (2 rounds) | sprint-13 |
| agent-handoff-baton | done on `dev` (3 chunks: MR-051+MR-052+MR-053; sprints 14/15/16 CLOSED G7 PASS; PR #17 pending) | G1 passed 2026-06-23 | sprint-14/15/16 |
| agent-watcher | **done** (all 3 chunks shipped: C1 sprint-17 + C2 sprint-18 + C3 sprint-19, each G7 PASS) | G1 passed 2026-06-24 (PASS-WITH-NITS) | sprint-17 (C1), sprint-18 (C2), sprint-19 (C3) |
| watcher-launch-fix | **done** (MR-060 shipped, sprint-20 G7 PASS 2026-06-24) — follow-up to the done agent-watcher epic (inert must-configure launch stub + runbook) | G1 passed 2026-06-24 (PASS-WITH-NITS) | sprint-20 |
| working-banner-animation | **done** (MR-061 shipped, sprint-21 G7 PASS 2026-06-24) — standalone small `ui` enhancement, slice of #27 (CSS-only animated ellipsis on the working-state turn banner) | G1 passed 2026-06-24 (PASS-WITH-NITS) | sprint-21 |
| watcher-ux-fixes | **done** (MR-062 + MR-063 shipped, sprint-22 G7 PASS 2026-06-24) — two-ticket watcher UX batch: a rotating spinner on both agent-turn waiting states (supersedes MR-061) + fixed the README scoped launch-recipe arg order (GH #25) | G1 passed 2026-06-24 (PASS-WITH-NITS) | sprint-22 |
| history-version-fix | **done** (MR-064 + MR-065 shipped, sprint-23 G7 PASS 2026-06-24, closes #18) — fixed the History modal's version labels (current-draft entry reconciles the off-by-one) + removed the untruthful per-round "0 notes" count | G1 passed 2026-06-24 (PASS-WITH-NITS) | sprint-23 |
| oop-refactor-src-layout | active (G1 cleared; MR-076-086 ready) — Tier B internal refactor: all code under `src/`, clean root, `app.py` decomposed into 7 SRP modules wired by constructor injection (a `Store` into service classes); pure internal refactor, byte-identical API/`/data`/viewer | G1 passed 2026-06-25 (2 rounds, PASS-WITH-NITS; r1 1 blocker) | sprint-27 |
