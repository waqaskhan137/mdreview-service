---
slug: watcher-launch-fix
captured: 2026-06-24
source: this session — critic-gated mdreview proposal review 05ff768234 (TWO staff-critic rounds, verdict GO, all findings folded) + GitHub issue #23. Decision: Option B (recommended + confirmed both rounds). Follow-up fix to the done agent-watcher epic.
related_epic: epics/watcher-launch-fix-plan.md
---

# Fix: the watcher's default launch command can't run headless

A defect + a design decision found while testing the shipped `agent-watcher` watcher end-to-end against the live instance. Routing the fix through review before any code change. *(Revised over two independent staff-critic rounds — see the resolved threads.)*

## What happened (the evidence)

`watch.py` ships a default launch command (MR-057):

```python
DEFAULT_LAUNCH_CMD = ["claude", "-p", "<prompt: ping_working / read comments / update_source / hand_back>"]
```

Running the watcher with the default (`python3 watch.py`, no `WATCH_LAUNCH_CMD`) and pressing **Send to agent** on a review with two open comments: the spawned headless agent **claimed the lease and handed back without doing the work** — no `update_source`, comments untouched. The exact "I asked it to do something but it doesn't" failure.

**Root cause:** a headless `claude -p` with **no permission stance** runs in default mode, where tool use routes to an interactive approval prompt. With no TTY to answer it, the agent can't use tools and degrades to a claim-and-handback no-op. The precise blocking gate is the **MCP-tool permission prompt** — the agent's entire tool set is MCP (`ping_working`, `update_source`, `resolve_comment`, `hand_back`), not file edits or Bash. (Ruled out the simpler causes: the env/lease contract worked — the agent *did* claim and hand back via the same-owner path — and the prompt is fine; only the in-between MCP tool calls were blocked.) The work only happened once a local test wrapper added a permission flag — so the shipped default **is not actually runnable headless**; it silently degrades to a no-op.

## The tension (why this isn't a one-line patch)

The obvious "fix" is to bake `--dangerously-skip-permissions` into the default. **That contradicts the watcher's entire identity, and concretely it punches a hole through the one path the model added for safe public operation.** The watcher is a *fail-closed, credentialed process spawner*: C2 refuses a base it can't vouch for; C3's **arming** lets it run against a non-loopback/**public** base for allowlisted reviews. But arming gates **which reviews run — not what the spawned agent may do.** The moment an operator arms a review on a public base (a fully supported, documented path), a `--dangerously-skip-permissions` default hands them a fully autonomous, unsandboxed agent **executing attacker-authored comment content** (prompt injection), with no second opt-in. So the dangerous posture must be an explicit per-deployment choice, never a silent default.

Two things to settle:

1. **The default must not silently no-op** (the defect).
2. **The default must not be silently dangerous** either (the design constraint).

## Options

| # | Option | Pros | Cons |
|---|---|---|---|
| **A** | Add `--dangerously-skip-permissions` to `DEFAULT_LAUNCH_CMD` | one line, "just works" | ships the maximally-unsafe posture as the default of a fail-closed tool; **punches through the arming path** (armed review on a public base ⇒ autonomous agent on attacker comments, no second opt-in); rejected |
| **B** *(recommended)* | Make `DEFAULT_LAUNCH_CMD` an **inert must-configure stub** — at **startup** (in `main()`, before `run()`), if no `WATCH_LAUNCH_CMD` is set, print "set `WATCH_LAUNCH_CMD` to your agent command incl. its permission stance; see the runbook" and **exit 2**, so the watcher refuses to start rather than claiming a lease and dying per-review | the watcher is a *mechanism*; the agent + permission posture is *operator policy* — an explicit one-time choice is the honest default for a credentialed spawner; no dangerous default, no silent no-op; **most consistent with the generic-template charter** (removes the today-tension of a tool that claims to be agent-agnostic yet ships a Claude default) | one deliberate setup step |
| **C** | Ship a `claude -p` default with a permission flag so it runs out-of-the-box | runs headless with no setup | **`--permission-mode acceptEdits` does NOT clear the MCP gate** (it auto-approves file edits / filesystem Bash only — verified against the Claude Code permission docs), so it **reproduces the no-op**. The functional posture is `--permission-mode dontAsk` + `--allowedTools "mcp__mdreview__*"` — but that still (1) hard-codes a Claude-specific posture into the "generic template," and (2) means "**auto-acts on a public instance out of the box**," the exact posture a fail-closed tool shouldn't default to |
| **D** | Keep `claude -p` default, just document the missing flag | smallest change | the default still silently no-ops for anyone who runs it as-is — annotates the defect instead of fixing it |

## Recommendation

**Option B.** The critic's verification *strengthens* it: C's whole appeal was "runs out of the box," but C-as-`acceptEdits` is broken (doesn't clear the MCP gate), and the functional variant both erodes the generic-template charter and quietly means "auto-acts on a public instance by default." B forces the operator to confront the permission/injection trade-off once, at setup — the right default for a credentialed spawner.

**The permission posture is *runbook recipe content*, not an alternative default.** The runbook (README/CLAUDE.md) gives the opt-in recipes with the trade-off spelled out:

- **runs headless, scoped to the mdreview tools (the recommended recipe):**
  `WATCH_LAUNCH_CMD='["claude","-p","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","…"]'`. **`--allowedTools` alone is not robustly headless** — an unlisted tool the agent reaches for (`Read`/`Bash`/`TodoWrite`/a web fetch) falls through to the no-TTY permission prompt and stalls, a narrowed reprise of the defect. **`--permission-mode dontAsk` converts that fall-through into a clean deny** (listed tools approved, everything else denied outright, no prompt), so the agent fails fast on a stray tool and keeps using the mdreview tools it has. Anchoring rule: the server segment must be glob-free — `mcp__mdreview__*` is valid; `mcp__*` / `*` are ignored with a startup warning.
- **full autonomy, only if you accept it (trusted/localhost):**
  `WATCH_LAUNCH_CMD='["claude","--dangerously-skip-permissions","-p","…"]'`.
- **the injection caveat (load-bearing, below).**

## Scope / delivery

Small, but it touches the shipped C2 contract + the C3 runbook, so it runs as a **1-ticket follow-up `/feature-cycle`** on the (now-done) `agent-watcher` epic (a new `svc`+`docs` ticket):

- **`watch.py` (svc):** replace `DEFAULT_LAUNCH_CMD` with the inert stub, and **detect-and-exit at startup in `main()`** (beside `require_trusted_base_or_exit` / `_arming_startup_notice`), **before `run()`** — NOT inside `_spawn()`. *(Acceptance criterion: an unconfigured watcher exits 2 at startup with guidance; it must never claim a lease and then die, which would strand the review at `turn==agent` under the B1 no-relaunch model.)*
- **`README.md` / `CLAUDE.md` (docs):** the opt-in launch recipes above — the scoped recipe is **`--permission-mode dontAsk` + `--allowedTools "mcp__mdreview__*"`** (not allowedTools alone, which stalls on a stray non-mdreview tool); and **sweep every "default Claude headless" assertion** — they become wrong under B (at least README "Watcher" section incl. the env-var table, and the `watch.py` module docstring/config comments) — to "falls back to a must-configure stub that exits with guidance."
- **Injection caveat as an explicit acceptance + validation item (not a soft bullet):** the runbook must state that on a public/armed base the launched agent **executes instructions embedded in reviewer comments**, so the `WATCH_LAUNCH_CMD` permission posture bounds the blast radius of a hostile comment — use the scoped posture (`--permission-mode dontAsk` + `--allowedTools mcp__mdreview__*`), not `--dangerously-skip-permissions`, for any base where comments aren't fully trusted.
- **Validation:** `py_compile` + a stub-launch end-to-end proving (a) the **unconfigured default exits 2 at startup** (not a per-review spawn-time death), and (b) a configured `WATCH_LAUNCH_CMD` still runs the full loop.

## Out of scope

- Reworking the trusted-base / arming model (shipped in C2/C3, unchanged here).
- Bundling a specific agent runtime — the launch command stays a generic operator-configured template (B makes this *more* true, not less).
