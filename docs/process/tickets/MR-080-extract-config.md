---
id: MR-080
title: Extract config.py (constants + WEB_DIR, drop HERE) + package skeleton
status: done
layer: svc
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-077, MR-078, MR-079]
branch: refactor/oop-src-layout
created: 2026-06-25
updated: 2026-06-25
---

## Goal

First decomposition step. Pull the env-read constants into `src/mdreview/config.py` and create the
package skeleton. Depends on all of Phase 0 so the decomposition starts on a fully-relocated,
building, gate-updated base.

## Acceptance criteria

- [x] `src/mdreview/__init__.py` created (empty or a version string).
- [x] `src/mdreview/config.py` holds `DATA_DIR`, `PORT`, `PUBLIC_BASE`, `WAIT_TIMEOUT_S`,
      `LEASE_TTL_S`, `RID`, the `os.makedirs(DATA_DIR, exist_ok=True)`, and `WEB_DIR`. **`WEB_DIR`'s
      anchor is now three `dirname`s** (`src/mdreview/config.py` → `src/mdreview/` → `src/` → repo
      root, `+ "/web"`), with the `MDREVIEW_WEB_DIR` env override and the `# ponytail:` comment.
- [x] `src/app.py` imports these from `config` (e.g. `from mdreview import config` / `from
      mdreview.config import DATA_DIR, ...`) and no longer defines them inline; `HERE` stays gone.
- [x] Behaviour identical: the golden-transcript sweep diffs **byte-identical** (timestamps/ids
      normalised); boot + the `#article`/`h1` + `#list`/`.card` render-smoke from a rebuilt throwaway
      container stay green; `/static`/viewer content-types unchanged.
- [x] Local validation: `python3 -m py_compile src/app.py src/mdreview/config.py`.

## Notes / context

- `app.py:40-59` (the constants + `os.makedirs`); the `WEB_DIR` snippet in the epic ("Path
  resolution after the move").
- Epic module table — `config.py` row. Dependency order: config first so every later module can
  import it.

## Work log

- `2026-06-25` — Created `src/mdreview/__init__.py` (package docstring) and `src/mdreview/config.py`
  holding `DATA_DIR`, `PORT`, `PUBLIC_BASE`, `WAIT_TIMEOUT_S`, `LEASE_TTL_S`, `RID`, `WEB_DIR`, and
  `os.makedirs(DATA_DIR)`. `WEB_DIR`'s anchor is now **3 `dirname`s** (`config.py` → `mdreview` →
  `src` → repo root). `src/app.py` now does `from mdreview.config import (...)` and no longer defines
  the constants; `_lock` stays in `app.py` (moves to `Store` in MR-081). De-em-dashed the moved
  comments per house style. Files: `src/mdreview/__init__.py`, `src/mdreview/config.py`, `src/app.py`.

## Validation

- `2026-06-25` — `python3 -m py_compile src/app.py src/mdreview/__init__.py src/mdreview/config.py`
  → OK. Golden sweep against the booted `src/app.py` → **byte-identical** to `golden.norm` (41/41
  sections). The viewer still serves non-empty (53481 bytes, SHA unchanged), proving the 3-deep
  `WEB_DIR` anchor from `src/mdreview/config.py` resolves to `<repo>/web`.

## Follow-ups

Anything deliberately deferred.
