---
id: MR-051
title: Handoff baton contract — POST /handoff + 4 meta.json fields + /status surfacing
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs
priority: P1           # foundation — MR-052 and MR-053 both depend on it
sprint: sprint-14
epic: agent-handoff-baton
depends_on: []
branch:                # MR-051-handoff-baton-contract, once work starts
created: 2026-06-23
updated: 2026-06-23
---

## Goal

Add the server-side **turn baton** so the viewer (MR-052) and the agent (MR-053) have a contract to
build against: a `turn` per review that the human flips ("Send to agent"), the agent claims (a
cooperative lease) and hands back, with the human always able to reclaim. This is **one new route
arm and four additive `meta.json` fields** — additive and backward-compatible, so it **ships
invisibly** (no UI, no behaviour change to any existing flow). It is the only chunk in sprint-14 and
ships to its own PR.

## Acceptance criteria

- [ ] **Route.** `POST /api/reviews/{id}/handoff` added as a new `re.fullmatch` arm **after** the
      `/status` arm (`app.py:503-513`) and **before** `/history` (`app.py:515`). POST-only; any other
      method on that path falls through to the generic 404.
- [ ] **Locking.** The handler takes `_lock` **itself** and does a **guarded read-check-write** of
      `meta.json` (read current `meta(rid)`, decide the transition off the **current** `turn`/`owner`,
      mutate, `_write` the whole dict once inside the lock). It must **not** call bare `bump()`
      (`bump()` at `app.py:120-124` is an unlocked read-modify-write that assumes the caller holds
      `_lock`, like `PUT /source` at `app.py:475-478`).
- [ ] **Explicit dispatch precedence + malformed-body guard** (G1 SHOULD-3). Body forms are
      dispatched in a **pinned order** so an ambiguous body is deterministic:
      1. `{to:"reviewer", by:"reviewer"}` → **reclaim**: force `turn="reviewer"`, `turn_updated=now`
         (leave `agent_status` as-is). Checked first, so `{to:reviewer, by:reviewer, state:done}`
         resolves to reclaim, never hand-back.
      2. `{to:"reviewer", state:"done"|"blocked", message?}` → **hand-back**: `turn="reviewer"`,
         `agent_status={state, message, owner, at:now}`, `turn_updated=now`.
      3. `{to:"agent"}` → **flip**: if current `turn` is `reviewer`/absent → `turn="agent"`, **clear**
         `agent_status`, `handoff={by:"reviewer", at:now}`, `turn_updated=now`; if already `agent` →
         **idempotent no-op 200**, `turn_updated` **NOT** bumped.
      4. `{state:"working", owner?, message?}` (no `to`) → **lease claim/renew**: if
         `agent_status.owner` is unset **or** equals the body `owner` → set
         `agent_status={state:"working", message, owner, at:now}`, `turn_updated` **unchanged**; if
         `owner` is set and differs → **`409`** `{"error":"lease held","owner":…}`.
      - Any body matching none of the above → **`400`** `{"error":"unrecognized handoff body"}`.
- [ ] **`/status` surfacing.** `GET /status` (`app.py:503-513`) gains `turn` (default `"reviewer"`),
      `turn_updated` (default `0`), `handoff` (default `null`), `agent_status` (default `null`) —
      additive only, no removed keys, all defaulted from `meta` with `.get(...)`.
- [ ] **Back-compat.** A review that never calls `/handoff` behaves **exactly as today** on every
      existing endpoint. A legacy `meta.json` with no `turn` is read as `reviewer`; `agent_status`
      absent reads as parked/none. No partial-merge write ever drops existing meta keys.
- [ ] **Dashboard status invariance** (G1 SHOULD-2). A review mid-handoff (`turn="agent"`) derives the
      **same** `summary()` status (`app.py:143-148`) and counts as before — the new fields do not
      perturb `notes_total`/`notes_addressed`/`status`. `summary()` is **not** edited (the new keys
      flow through `dict(meta(rid))` for free); asserted in the smoke via `GET /api/reviews`.
- [ ] **Owner is client-supplied** (G1 Q1). The lease `owner` comes from the request body; the server
      never mints identity. An absent `owner` on a `working` claim is accepted as an unowned claim
      (recorded as sent, possibly `""`).
- [ ] **Validation.** `python3 -m py_compile app.py` passes; the epic's MR-051 curl round-trip passes
      on a **throwaway** container (scratch port, never 8139/8137), covering: flip; working-claim with
      `turn_updated` captured-and-compared **unchanged** (G1 NIT-1); foreign-owner `409` back-off;
      hand-back; reclaim; idempotent re-flip (`turn_updated` unchanged on the 2nd `{to:agent}`); a
      **`400`** on a malformed body (negative case, G1 SHOULD-3); `GET /status` shows all four new
      keys and `GET /api/reviews` shows `turn`; and the dashboard-status-invariance check.

## Notes / context

- Epic plan: [`epics/agent-handoff-baton-plan.md`](../epics/agent-handoff-baton-plan.md) §Service
  (`app.py`) and §Verification → MR-051.
- Code anchors: `route()`/method handlers `app.py:403-416`; `/status` arm `app.py:503-513`;
  `/history` arm `app.py:515`; `bump()` `app.py:120-124` (unlocked); `PUT /source` lock discipline
  `app.py:475-478`; `summary()`/`list_reviews()` `app.py:127-155`; `409` convention `app.py:337-338`;
  `_body_json()`/body parse helper, `_write()` `app.py:111`.
- **No UI and no MCP change in this ticket.** `summary()`/`list_reviews()` are untouched (the new
  meta keys flow through `dict(meta)` automatically). No new served file, so no Dockerfile change.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- MR-052 (viewer UI) and MR-053 (MCP tool + CLAUDE.md) build on this contract; both `depends_on:
  [MR-051]` and are scheduled into the sprint after sprint-14.
