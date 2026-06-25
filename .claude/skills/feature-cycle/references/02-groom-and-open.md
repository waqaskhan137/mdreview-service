# Phases 3-4 — tickets (G2) and sprint open (G6)

## Phase 3 — create + groom tickets (G2)

Precondition: the epic is `gate: passed`. From the epic's **Ticket breakdown** table, create one
file per ticket from `templates/ticket.md`.

**Safe ID allocation:** the next ID is `(highest existing MR-### across tickets/) + 1`. Scan
`tickets/` for the current max; never reuse an ID. If a target filename already exists, **fail
loud** — do not overwrite.

For each ticket fill: `id`, `title`, `layer` (`svc`/`ui`/`infra`/`docs`), `priority`,
`epic: <slug>`, `depends_on` (real ordering only), `created`/`updated`. Write:

- **Goal** — the outcome, not the implementation.
- **Acceptance criteria** — specific and checkable, including the validation line
  (`python3 -m py_compile src/mdreview/*.py src/mcp_server.py src/watch.py` plus the layer's smoke).
- **Notes / context** — `path:line` references into `src/mdreview/server.py` / `web/app/viewer.html` etc., and the epic.

A ticket reaches **G2 (`ready`)** only when AC are written, dependencies identified, `layer` +
`priority` set, no open questions, roughly sized. Set `status: ready`.

Link the created IDs back into the epic's `related_tickets:` frontmatter, and add a row per ticket
to `TRACKER.md` under the matching status.

## Phase 4 — open the sprint (G6)

**Safe sprint allocation:** next is `sprint-(NN+1)` after the highest existing in `sprints/`. One
lightweight sprint per epic (this repo is single-flight).

Copy `templates/sprint.md` -> `sprints/sprint-NN.md`. Set `goal`, `start` (today, Europe/London),
a reasonable `end`. List the epic's tickets in **Committed tickets** and a **Preferred execution
order** that respects `depends_on`. Point each committed ticket's `sprint:` field at this sprint.

**G6 passes** when every committed ticket is `ready` and the sprint has a goal + committed list.
Set the sprint `status: active`. Update `TRACKER.md`. Proceed to Phase 5 (implement).
