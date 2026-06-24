---
id: MR-063
title: "Fix the scoped watcher launch recipe arg order — `-p` prompt last (GH #25)"
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: docs            # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-22
epic: watcher-ux-fixes
depends_on: []
created: 2026-06-24
updated: 2026-06-24
---

## Goal

The documented scoped watcher launch recipe in the README does not actually run. `--allowedTools` is
variadic (a space-separated tool list), so a trailing `<prompt>` after `mcp__mdreview__*` is
swallowed as another tool name and `claude -p` dies with "Input must be provided … when using
--print". Reorder the three scoped-recipe literals to put `-p "<prompt>"` **last**, add a one-line
note saying why, and close GH **#25**. README-only — `CLAUDE.md` carries no recipe literal (only a
prose pointer to the runbook), and the full-autonomy recipe is already prompt-last.

## Acceptance criteria

- [ ] The three scoped-recipe literals at `README.md:193`, `README.md:198`, `README.md:208` are
      reordered to
      `["claude","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","-p","<prompt>"]`
      (prompt **last**, after the variadic `--allowedTools` flag).
- [ ] A one-line note is added by the scoped recipe (at `README.md:208`'s bullet):
      "`--allowedTools` is variadic — keep `-p "<prompt>"` last so the prompt isn't consumed as a
      tool name."
- [ ] The full-autonomy recipe (`README.md:217`),
      `["claude","--dangerously-skip-permissions","-p","<prompt>"]`, is **confirmed already
      prompt-last** and left **unchanged** (verify, don't edit).
- [ ] `CLAUDE.md` carries no scoped-recipe literal (its watcher paragraph is prose pointing to the
      README runbook); confirmed README-only, so `CLAUDE.md` is left **unchanged** (assumption A1).
- [ ] Local validation passes: `python3 -m py_compile app.py` (unchanged sanity; no code touched),
      plus a grep confirming the order:
      - `grep -n 'mcp__mdreview__\*","-p","<prompt>"' README.md` → 3 hits (the lines that were
        193/198/208);
      - `grep -n '"-p","--permission-mode"' README.md` → 0 hits (old wrong order gone);
      - `grep -n 'allowedTools is variadic' README.md` → 1 hit (the note);
      - `grep -n 'dangerously-skip-permissions","-p","<prompt>"' README.md` → 1 hit (full-autonomy
        recipe unchanged + prompt-last);
      - `grep -n 'allowedTools' CLAUDE.md` → 0 hits (no recipe literal to fix).
- [ ] Links / closes GH **#25** (closes when the standing dev→main PR is updated).

## Notes / context

- Epic plan: `docs/process/epics/watcher-ux-fixes-plan.md` — §"Recommended approach / Docs
  (`README.md`)" (the variadic-flag bug + the enumerated 3-spot table at `README.md:193/198/208`),
  §"Verification / MR-063" (the `py_compile` + grep confirmation), §"MR-063 acceptance criteria",
  and assumption **A1** (README-only; `CLAUDE.md` has no recipe literal, so inventing one would add
  surface, not fix a bug — flag at review only if the product owner wants new CLAUDE prose).
- The three literals all live in `README.md`'s "Watcher (optional) — operator runbook" section:
  `:193` (trusted-base / loopback `WATCH_LAUNCH_CMD=…`), `:198` (non-loopback
  `WATCH_TRUSTED_BASE` example), `:208` ("Scoped / recommended" recipe in the recipes list).
- `CLAUDE.md:130-139` is the watcher prose pointer ("See README … operator runbook"); the
  `allowedTools`/`dontAsk` grep returns only the README literals. README-only confirmed.
- Docs-only ticket: no `viewer.html`/`dashboard.html` change, so **no render-smoke is owed** at G7.

## Work log

_Filled in during implementation._

- `YYYY-MM-DD` — what changed, files touched.

## Validation

_How this was verified._

- `YYYY-MM-DD` — what was checked and the result.

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.
