---
review_of: sprints/sprint-22.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS
status: resolved
---

# Sprint-22 G7 close review — watcher-ux-fixes (MR-062 spinner + MR-063 recipe arg-order)

Independent staff-critic close review of sprint-22 (epic `watcher-ux-fixes`, two tickets:
MR-062 ui + MR-063 docs). I did not implement either. I verified both against their acceptance
criteria by reading `viewer.html` / `README.md` / `CLAUDE.md` and the merge diffs, and for MR-062
(a product-page change) I **independently re-ran the render-smoke from a freshly rebuilt throwaway
image** — not a file diff, not the implementer's container.

- Scratch image `mdreview-mr062-critic`, disposable container `mr062critic` on **scratch port 8769**
  (never 8139 live / 8137 compose / `docker compose up`).
- Review id `d99b79e540`. All artifacts written under the gitignored `.scratch/`; container + image
  removed and `.scratch/` contents cleared at teardown. The pre-existing 8139 live instance was
  never touched (not started by this session).

## Verdict: PASS

Both tickets meet every acceptance criterion. MR-062's spinner shows in **both** agent-turn waiting
states (including the waiting-for-pickup state MR-061 missed — the headline fix), is absent on the
stale and reviewer states, MR-061's pulse + `turnworking` keyframes are fully removed with **no
orphan references**, and the reduced-motion fallback works. MR-063's three scoped recipes are all
prompt-last with the variadic note, the full-autonomy recipe is unchanged, and CLAUDE.md genuinely
carries no recipe literal. Scope is clean: `viewer.html` + `README.md` only; `app.py` / `Dockerfile`
/ `mcp_server.py` byte-unchanged across the whole sprint.

---

## MR-062 — banner loading spinner (ui, `viewer.html`)

### Code correctness (read `viewer.html`)

- **CSS (`viewer.html:84-89`)** matches the pinned spec exactly: `#turnbanner.loading
  #turntext::before` is an 11px ring, `border:2px solid var(--muted)`, `border-top-color:transparent`,
  `animation:turnspin .8s linear infinite`; `@keyframes turnspin{to{transform:rotate(360deg);}}`
  present; `@media (prefers-reduced-motion:reduce)` block sets `animation:none` and keeps a visible
  static ring (`border-top-color:var(--muted)`). Colour via theme var `--muted` — reads on both panes.
- **`renderBanner` (`viewer.html:232-255`)** places the `loading` class correctly:
  - `:237` `bar.classList.remove('loading')` at the top — clears on every re-render.
  - `:240` `if(!as)` waiting-for-pickup arm → `add('loading')` ✓ (the broadened MR-061 gap).
  - `:241` stale `else if(...>STALE_S)` arm → **no** `loading` ✓.
  - `:242` working arm → `add('loading')` ✓.
  - `:245-252` reviewer `else` branch → **no** `loading` ✓.
- **MR-061 supersession is clean.** `grep turnworking` → 0 hits; `grep '\.working'` / `turnbanner.working`
  → 0 hits. The `::after` pulse, the `@keyframes turnworking`, and the `.working`-scoped reduced-motion
  override are all gone, not co-existing. **No orphan references.**
- **Scope.** MR-062 feat commit `8673f61` is `viewer.html | 18 +++---------` — one file, 9/9. No
  `app.py` / `Dockerfile` / `mcp_server.py` touched.

### Re-run render-smoke (rebuilt throwaway image, scratch port 8769)

`docker build` from the working tree: **PASS**. `GET /healthz` → `{"ok": true}`: **PASS**.

| State | Handoff body | turn / agent_status | Selector(s) | Exit | Verdict |
|---|---|---|---|---|---|
| **A — waiting-for-pickup** | `{"to":"agent"}` only | `turn=agent`, `agent_status=null` | `#turntext`, `.loading` | 0 | **PASS** — spinner PRESENT (the key MR-061 fix) |
| **B — agent working** | `{"state":"working","owner":"smoke"}` | `turn=agent`, `state=working` | `.loading` | 0 | **PASS** — spinner PRESENT |
| **D — reviewer reclaim** | `{"to":"reviewer","by":"reviewer"}` | `turn=reviewer` | `.loading` | 1 | **PASS** — spinner ABSENT (0 nodes / exit 1 = expected) |
| **D — banner renders** | (same) | — | `#turntext` | 0 | **PASS** — banner still present |
| **C — stale** | not force-stampable | code inspection | `viewer.html:241` | n/a | **PASS** — stale arm adds no `loading` class |

**Reduced-motion CDP probe** (computed style of `#turntext::before`, via DevTools `Emulation.setEmulatedMedia`):

```json
{"without_emulation": "turnspin", "with_reduced_motion": "none"}
```

Banner class confirmed `turnbanner show loading` in both probes (spinner element present);
`animationName` resolves to `turnspin` without emulation and `none` under `prefers-reduced-motion:
reduce`. **PASS** — animates normally, static ring under reduce.

**Both-pane screenshots** (scheme emulation `--blink-settings=preferredColorScheme=1` light / `=0`
dark, State B): the partial ring renders left of "Agent is working on your feedback…" and is legible
on both light and dark panes. **PASS.**

All five smoke results reproduce the implementer's `reviews/sprint-22-render-evidence-2026-06-24/SMOKE.md`
exactly, from a container I built independently.

---

## MR-063 — watcher launch recipe arg-order (docs, `README.md`)

Read `README.md:186-222` and `CLAUDE.md`. The grep gate from the AC, re-run independently:

- `grep 'mcp__mdreview__\*","-p","<prompt>"' README.md` → **3 hits** (lines 193, 198, 208) — the three
  scoped recipes are all prompt-last `["claude","--permission-mode","dontAsk","--allowedTools",
  "mcp__mdreview__*","-p","<prompt>"]`. ✓
- `grep '"-p","--permission-mode"' README.md` → **0 hits** — no wrong-order recipe survives. ✓
- The variadic note is present (`README.md:209-212`): "**Argument order matters:** `--allowedTools` is
  **variadic** ... keep `-p "<prompt>"` **last** — a prompt placed right after `--allowedTools` is
  swallowed as another tool name, and `claude` then errors `Input must be provided … when using
  --print`." Clear and correct. ✓
- `grep 'dangerously-skip-permissions","-p","<prompt>"' README.md` → **1 hit** (`README.md:221`) —
  full-autonomy recipe already prompt-last, unchanged. ✓
- `grep allowedTools CLAUDE.md` → **0 hits** — CLAUDE.md genuinely carries no recipe literal (prose
  pointer to the README runbook only). README-only was the right call, not a missed spot. ✓

The fix is substantively correct: `--allowedTools` is variadic in the Claude CLI, so a trailing
`<prompt>` after `mcp__mdreview__*` would be parsed as another allowed-tool token, leaving `-p` with
no argument and `--print` failing. Moving `-p "<prompt>"` last resolves it.

No code change; docs-only, so no render-smoke owed (correctly).

> Nit (non-blocking, informational only): the AC and the MR-063 work log reference exact README line
> numbers (193/198/208 for the recipes, 208's bullet for the note, 217/221 for full-autonomy). Post-edit
> the recipes do sit at 193/198/208 and full-autonomy at 221; the note lands at 209-212 rather than "at
> 208's bullet." Content is exactly right and all greps pass — line-number drift in prose is cosmetic,
> not a defect.

---

## Scope & non-regression

- Sprint diff (`d842bf7^..HEAD`) non-process files: `README.md` + `viewer.html` only. `git diff
  d842bf7^..HEAD -- app.py Dockerfile mcp_server.py` is **empty** — those are byte-unchanged.
- MR-062 supersedes MR-061 cleanly: pulse + keyframes removed, zero orphan references.
- The running 8139 live container is unaffected (no rebuild of it; app.py unchanged means even a future
  rebuild is render-only).

## Resolution log

- **2026-06-24 (staff-critic):** Independent G7 review complete. MR-062 verified by code reading +
  rebuilt-image render-smoke (States A/B/D + State-C code inspection + reduced-motion CDP probe +
  both-pane screenshots), all reproducing the implementer's evidence. MR-063 verified by reading
  README/CLAUDE.md + the full grep gate. Scope confirmed `viewer.html` + `README.md` only; app.py /
  Dockerfile / MCP byte-unchanged. **No blocking findings.** One cosmetic note on MR-063 prose
  line-number drift (content correct). **Verdict: PASS.** Throwaway container `mr062critic` + image
  `mdreview-mr062-critic` removed; `.scratch/` cleared; 8139/8137 untouched.

## Resolution log

- 2026-06-24 — Independent G7 review (2-ticket batch). Verdict PASS, no blockers. The critic rebuilt a
  throwaway image and re-ran the MR-062 render-smoke: State A (waiting-for-pickup) `.loading` present —
  the key MR-061-gap fix; State B (working) present; reviewer reclaim absent; reduced-motion
  `turnspin`/`none`; both panes legible. Confirmed MR-062 supersedes MR-061 cleanly (`grep turnworking`
  + `grep .working` = 0 hits) and MR-063's three recipes are prompt-last (0 wrong-order, CLAUDE.md clean).
  One non-blocking nit (cosmetic note line-number drift, content correct). Review status: resolved;
  sprint-22 closed at G7; the watcher-ux-fixes epic marked done. GH #25 closed.
