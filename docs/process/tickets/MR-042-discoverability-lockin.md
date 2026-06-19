---
id: MR-042
title: "mcp_smoke.py — assert server_info + the discoverability contract"
status: ready
layer: svc
priority: P1
sprint: sprint-12
epic: mcp-agent-effectiveness
depends_on: [MR-040]
branch:
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Make the already-shipped discoverability (the `instructions` + tool descriptions an agent reads to
self-serve) **load-bearing under test**, so a future refactor can't quietly drop the path-attach /
get_source / comment-loop guidance and re-open the exact gap that tripped the agent. Verification-only —
no production behavior change.

## Acceptance criteria

- [ ] **Tool count is 16** and the name set includes `server_info` (the existing exact-15 check updated).
- [ ] **`serverInfo.tools_hash`** present on `initialize`; **three-way hash identity (NIT-1):**
      `serverInfo.tools_hash` == the `server_info` tool's `tools_hash` == `python3 mcp_server.py
      --print-version`'s `tools_hash`.
- [ ] **Discoverability contract:** `attach_asset` description mentions `path`; `get_source` description
      tells when to read the draft; `INSTRUCTIONS` names path-attach, get_source, and the comment loop.
- [ ] **Honest-staleness regression-lock (SHOULD-1):** assert `INSTRUCTIONS`/the `server_info` description
      state comparison-to-on-disk is a human/CI step and **do not** claim the agent self-detects staleness.
- [ ] All **existing 22** assertions still pass end-to-end.
- [ ] Local validation: `python3 -m py_compile mcp_smoke.py`; `MDREVIEW_BASE=<throwaway> python3
      mcp_smoke.py` → `PASS`.

## Notes / context

- Epic: `epics/mcp-agent-effectiveness-plan.md` — Decision 3, Verification → MR-042.
- Code: `mcp_smoke.py` (the exact-15/name-set assertion at ~:63-67; the existing 22 checks).
- Depends on MR-040 (`server_info`, `tools_hash`, `--print-version`).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

_None._
