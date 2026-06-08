# Phases 6-10 — close review (G7), fix, close, ship (G8), retro

## Phase 6 — render-smoke + independent close review (G7)

Precondition: every committed ticket is `done`.

0. **Reconcile the board to reality (you), BEFORE spawning the critic.** Keep the independent
   reviewer on substance, not bookkeeping:
   - every committed ticket is `done` in its frontmatter (not still `ready`/`review`) — restates
     the precondition above; confirm it;
   - **(new)** the sprint file's committed-ticket table / close-gate checkboxes are updated to
     match the ticket frontmatter;
   - **(new)** `TRACKER.md` rows are moved to the section matching each ticket's `status`.
   **Not in this step:** setting `close_review:`, setting `status: closed`, or writing the retro —
   those stay in **Phase 8**, because `close_review:` names the review file the critic *produces*
   and cannot exist before the critic runs.
1. **Render smoke (you):** rebuild the container (`docker compose up -d --build`), then:
   - `curl -s localhost:8137/healthz` -> `{"ok":true}`;
   - `curl -s localhost:8137/api/reviews` (or other touched endpoints) returns sane JSON;
   - **only if a product page (`viewer.html`/`dashboard.html`/`static/**`) was touched this
     sprint** (see the G7 pass-condition row): run `scripts/render-smoke.sh` against each touched
     page and **open it** (`/`, `/review/<id>`) in a browser, screenshotting to
     `reviews/sprint-NN-render-evidence-YYYY-MM-DD/` (a 200 is not proof a JS page renders). A
     docs/infra-only sprint that touches no product page skips this per-page step but still owes
     the rebuild + curl smoke above.
   - If any touched page fails to render -> **park** (do not pass G7): `## BLOCKED` note in the sprint +
     epic, draft `[BLOCKED]` PR, arm the retro marker, run Phase 10.
2. **Independent review (staff-critic):** spawn `staff-critic` (reviewer != implementer) on the
   shipped diff + the render evidence. It writes
   `reviews/sprint-NN-close-review-YYYY-MM-DD.md` (frontmatter `gate: G7`, `independent: true`,
   `verdict`, `status: open`), checking shipped work against **each ticket's acceptance criteria**.

## Phase 7 — fix findings (you)

Address the close-review findings as ordinary commits referencing the relevant ticket. Update the
review's Resolution log.

## Phase 8 — second critic pass + close

Re-spawn `staff-critic` until `status: resolved` (or findings explicitly carried to a follow-up
ticket / `backlog.md`). Max 3 rounds, then park. On resolution:

- write the sprint's **Notes / retro** + carry-overs;
- set `close_review:` in the sprint frontmatter and `status: closed`;
- update `TRACKER.md`.

## Phase 9 — ship (G8)

- Push `dev` to origin.
- **Update-or-open the single standing `dev -> main` PR** (never duplicate it). Title/body
  summarize the epic + inline the G1 and G7 gate evidence so the promotion is reviewable from the
  PR alone. Use `gh pr list --base main --head dev` to find the existing one.
- **Arm the retro marker** before finishing: write the slug into
  `.claude/.feature-cycle-pending-retro`.
- **STOP — never merge `dev -> main`.** That is the user's G8 decision.

## Phase 10 — cycle retrospective (automatic)

Spawn the **`cycle-retrospective`** agent to meta-review THIS run (the cycle, not the feature). It
writes `reviews/<slug>-cycle-retro-YYYY-MM-DD.md` with prioritized, tagged suggestions
(`[process]`/`[skill]`/`[agent]`/`[feature]`) and SUGGESTS ONLY. Then:

- clear the marker: `rm .claude/.feature-cycle-pending-retro`;
- report the PR URL + the retro's top suggestions to the user, and stop.

The `Stop` hook blocks finishing while the marker exists (failing open if `jq` is missing). Run
the retro; do not delete the marker by hand to escape.
