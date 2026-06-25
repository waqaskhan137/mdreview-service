# Phase 5 — implement (G3/G4/G5)

Work the active sprint's tickets in the **Preferred execution order**, honoring `depends_on`.

For each ticket:

1. **G3 pickup:** confirm it belongs to the active sprint, `status: ready`, every `depends_on` is
   `done`, and nothing else is `in-progress`. Set `status: in-progress`, update `updated:`.
2. **Restate** the goal + acceptance criteria before touching code.
3. **Implement.** Small/solo changes may commit straight to `dev`; larger ones use a ticket branch
   `MR-###-slug` cut from `dev` and merged back. Keep changes surgical and in the ticket's
   `layer`; if you discover a missing prerequisite, **stop and apply the blocking rule** (new
   prerequisite ticket or deliberate scope widen), never bury it.
4. **Validate (G4):**
   - `svc`: `python3 -m py_compile src/mdreview/*.py src/mcp_server.py src/watch.py`; then run it and curl the affected endpoints
     (`PORT=8137 MDREVIEW_DATA=/tmp/mr PYTHONPATH=src python3 -m mdreview` on a free port, or rebuild the container).
   - `infra`: `docker build -f infra/Dockerfile -t mdreview-service .` must pass.
   - `ui`: rebuild from the image (`make up`) and run
     **`tests/render-smoke.sh <url> <selector>...`** against the published port to assert the
     expected DOM nodes rendered (the viewer/dashboard are JS-rendered; a 200 is not a render and
     a screenshot proves first-paint only). This is the README G4 rule for `ui` tickets — run it,
     do not restate it.
   - There is no test framework; the smoke IS the gate.
5. **Commit** referencing the ticket: `feat(svc): add list endpoint (MR-002)` (conventional
   subject + the `Co-Authored-By: Claude` trailer this repo keeps).
6. Fill the ticket's **Work log** (what changed, files touched) and **Validation** (what you
   checked, the result). Update durable docs (`README.md`/`CLAUDE.md`) **in the same
   change** when behavior changes.
7. **G4 -> review:** set `status: review`. **G5 -> done:** once AC are met, validation passed,
   docs updated, Work log/Validation filled, and committed, set `status: done`. Move the row in
   `TRACKER.md`.

Never run `docker compose ... --build` against a port already serving a different instance without
checking `lsof -iTCP:<port> -sTCP:LISTEN` first.

When every committed ticket is `done`, proceed to Phase 6 (close review).
