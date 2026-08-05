# Rules for coding agents in this repo

Work tracking is GitHub-only. The working agreement is `docs/process/README.md`; read it
before touching process state (labels, milestones, epic issues, gates). Non-negotiables:

1. **Branch from current `dev`; PR into `dev`; self-merge once `pr-checks` is green.**
   Enforced: `dev` only accepts PRs (0 approvals); direct pushes are rejected. `pr-checks`
   is the pre-merge gate that replaced the owner's merge gate (owner decision 2026-07-27) —
   it is a floor, not a substitute: both its smokes are server-side and neither reads
   `web/app/**`. The owner can still call a **batch merge gate** for a queue. Branch names:
   `<kind>/<issue>-slug`, e.g. `fix/15-comment-anchor`.
2. **Never open or merge a PR against `main`**, except the single standing `dev -> main` PR,
   which merges only on the owner's explicit go-ahead (G8), squash-merged in the GitHub UI
   (main requires signed commits; squash is the only strategy that passes with unsigned
   agent commits).
3. **Issues**: exactly one `status:` label per open issue; never use auto-close keywords
   (`closes #N`); an issue closes only on owner approval (G5).
4. **`docs/process/` frozen subdirs** (`tickets/ sprints/ epics/ reviews/ requirements/
   templates/`, plus `TRACKER.md` and `backlog.md`) are read-only archive. Never edit them.
5. **Commits**: conventional subject referencing the issue (`fix(ui): anchor comments to the
   clicked block (#15)`); keep the repo's `Co-Authored-By` trailer convention.
6. **Typography is FROZEN.** Never change a font family, font size, line-height, letter-spacing
   or weight under `web/app/**` — including `theme.css`'s `--font-*` and `--t-*` tokens — unless
   the owner asked for that specific change in the request you are answering. The reading face
   and type scale were chosen deliberately, and were twice changed as a *side effect* of other
   work (#277 moved the reading face to a webfont; #279 dropped the body from 20px to 18px with
   no ticket asking for it). A re-skin, a design-fidelity pass, or "matching the mock" is not
   permission. If a mock implies different type, flag it and ask. If a check fails because
   typography drifted, fix the drift, never the assertion. The reading surface is
   `Charter,Georgia,Cambria,"Times New Roman",serif` at 20px / 1.7, pinned by
   `tests/reading_font_selfcheck.sh` and `tests/viewer_polish_selfcheck.sh`.

The roadmap is the GitHub Project "mdreview Roadmap" (repo Projects tab); board state is
owner intent, do not re-sequence it.
