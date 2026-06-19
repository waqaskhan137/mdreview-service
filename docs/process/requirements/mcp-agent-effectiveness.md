---
slug: mcp-agent-effectiveness
captured: 2026-06-19
source: user request 2026-06-19 (waqas), this session — process critique after a string of operator hot-patches; chose "Full feature-cycle".
related_epic: epics/mcp-agent-effectiveness-plan.md
---

# Make the mdreview MCP genuinely self-serve for agents (and prove it)

Verbatim ask. Do not edit; append dated notes under Amendments if the requirement changes.

> so the thing is to fix mcp and agents can use it effectively not you just patching things on the
> go this is not improving the mcp or the process

(Asked how to harden it so agents self-serve, the user chose **"Full feature-cycle"**: run the gated
cycle for an `mcp-agent-effectiveness` epic — a version/staleness signal + capability discoverability,
with the G7 acceptance bar being *an autonomous agent completing create → embed-image-via-path →
renders → zoom with zero human curl*; the viewer fixes already shipped get retro-ticketed.)

## Scope notes (for grooming, not changes to the ask)

The trigger: an agent repeatedly failed to embed an image in a review. Two root causes were found
this session:

1. **A stale MCP server silently served old tools.** `attach_asset(path=…)`, the MCP `instructions`
   field on `initialize`, and `get_source` were on disk, but the running `mcp_server.py` process
   predated them — and **nothing (agent or human) could detect the staleness**. The agent saw the old
   schema and failed.
2. **No agent-driven verification of the loop.** The image only got attached because an **operator**
   ran curl / drove the wrapper by hand. There is no repeatable proof that an agent, given only the
   MCP, can complete a real task unaided.

**Already shipped directly this session (fold in / retro-ticket, do not redo):** `attach_asset(path=…)`
(wrapper encodes a local file, so no base64 through the agent's context), the MCP `instructions` field,
`get_source`, viewer **table CSS**, and a **click-to-zoom lightbox**.

**Goal:** an autonomous agent, given only the mdreview MCP server, completes the canonical loop —
create a review → reference an image in the markdown → attach it via `path` → the figure renders in
the viewer — with **zero human/curl intervention**; and a stale/outdated MCP server is **detectable**
by the agent and the human.

**In scope (planner designs the exact shape — the requirement does not prescribe it):**

1. **Staleness / version signal.** A way to detect that the running MCP server is older than the code,
   and to see its tool/capability set + version (e.g. `serverInfo.version` tied to the code, a build/
   version field, or a health/info tool). The stale-process problem is a **client-lifecycle reality** —
   the server can *signal* staleness, it cannot force a reconnect; document that honestly.
2. **Capability discoverability.** Confirm an agent can discover, from tools + instructions alone, how
   to do the things that tripped it — attach a large image via `path`, read the draft via `get_source`,
   run the comment loop.
3. **Agent-loop acceptance harness.** A stdlib (no-pip) harness that drives `mcp_server.py` over stdio
   **as an agent would** and completes create → reference image → attach via path → assert the asset is
   served **and** the viewer repoints the `<img>` (actually renders), **no human curl**. This becomes a
   repeatable gate — the proof the MCP is usable.
4. **Process hygiene.** Retro-ticket the two already-shipped viewer fixes (table CSS, click-to-zoom
   lightbox) so the board reflects them; this epic's own work goes through the gates.

## Constraints

- Stdlib-only / no new deps; the MCP wrapper stays a thin, stateless proxy.
- Do not break the existing 15 tools or the existing `mcp_smoke` assertions.
- Live instance on :8139 — throwaway containers for tests, never `docker compose`.
- Be honest where a limitation is structural (the client must reconnect to pick up new wrapper code;
  the server can only *surface* that it changed).

## Out of scope

- Forcing the client to reconnect / hot-reloading a running stdio server (not possible from the
  server side).
- Auth / multi-tenant identity (unchanged; roles are attribution only).
- Re-doing the already-shipped path/instructions/get_source/table/lightbox work — only fold it in and
  retro-ticket it.

## Acceptance (G7 bar)

The agent-loop harness passes end-to-end (the embed-image loop completes unaided) **and** a stale
server is detectable. Next ticket ids start at **MR-038**; next sprint is **sprint-12**.

## Amendments

_None yet._
