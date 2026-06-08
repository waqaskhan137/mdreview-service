# Plan: Review dashboard with project/session provenance

## Context

`mdreview-service` already persists everything per review (`source.md`, `feedback.md`,
`notes.json`, `meta.json` under `DATA_DIR/{id}`), but there is **no way to see what exists**.
Reviews are opaque random ids; once an agent loses the handle, the review is effectively
invisible. There is also no record of *where* a review came from — the agent only sends
`markdown` + `title`.

This adds two things:
1. **Provenance** — agents can tag a review with the `project` and `source_path` it came from.
2. **A human dashboard at `/`** that lists every review grouped by project, shows feedback
   status, and links into the existing viewer (open / delete).

Outcome: a person (or the agent's operator) can open `http://localhost:8137/` and see all
in-flight and past reviews, which project/file each belongs to, whether feedback is waiting,
and jump straight into any of them.

## Decisions (confirmed with user)
- Provenance via **new optional `project` + `source_path` fields** on `POST /api/reviews`,
  stored in `meta.json`. Reviews without `project` group under **"Ungrouped"**. Backward
  compatible — existing reviews simply lack the keys.
- Dashboard does **list + open + delete** (delete reuses existing `DELETE /api/reviews/{id}`).
- Dashboard served at **`/`**; the old JSON descriptor moves to `/api` (and `/` still returns
  JSON when the request sends `Accept: application/json`, so nothing that probes `/` breaks).

## Changes

### 1. `app.py` — persist provenance
- `create_review(markdown, title, project="", source_path="")`: add `project` and
  `source_path` to the `meta.json` dict written at `app.py:89`.
- `POST /api/reviews` handler (`app.py:166`): pull `b.get("project","")` and
  `b.get("source_path","")` from the body and pass them through.

### 2. `app.py` — list + summary
- Add helper `summary(rid)`: start from `meta(rid)`, read `notes.json`, add
  `notes_total`, `notes_addressed`, and a derived `status`:
  - `awaiting` — `feedback_updated == 0` and no notes
  - `resolved` — has notes and all `addressed`
  - `feedback` — otherwise (notes outstanding)
- Add `list_reviews()`: scan `DATA_DIR` for subdirs containing `meta.json`, map through
  `summary()`, sort by `created` desc. Reuse existing `_exists`/`_read_json`/`meta`.
- In `route()`, extend the `path == "/api/reviews"` block (`app.py:166`) to handle
  `m == "GET"` → `{"reviews": list_reviews()}`.

### 3. `app.py` — serve dashboard at `/`
- Replace the `path == "/"` branch (`app.py:159`): if the `Accept` header contains
  `application/json`, return the existing descriptor dict; otherwise serve
  `dashboard.html` via `_read(os.path.join(HERE, "dashboard.html"))` as `text/html`
  (mirrors how `viewer.html` is served at `app.py:238`).
- Add a `path == "/api"` GET branch returning the same descriptor JSON (with the new
  fields documented: `list_reviews`, `project`, `source_path`).

### 4. `dashboard.html` (new, project root next to `viewer.html`)
- Self-contained page matching `viewer.html`'s aesthetic: same CSS custom properties
  (`--bg/--text/--muted/--accent/--rule`), light/dark via `prefers-color-scheme`, the
  sans/serif/mono font stack, teal accent.
- On load `fetch('/api/reviews')`, group `reviews[]` by `project || 'Ungrouped'`.
- Each project section → cards. Card shows: `title || id`, `source_path` (monospace, muted),
  relative `created` time, a note-count badge (`notes_total`, `· N done` when
  `notes_addressed`), and a status pill colored by `status`
  (awaiting / feedback / resolved).
- Card actions: **Open** → `/review/{id}`; **Delete** → confirm, `DELETE /api/reviews/{id}`,
  then re-fetch the list.
- Empty state when no reviews exist. No external assets (no `/static` needed).

### 5. Docs — `AGENTS.md`, `README.md`, `CLAUDE.md`
- Document the new optional `project` / `source_path` POST fields in the API table and the
  agent contract example.
- Add `GET /api/reviews` (list) and the dashboard at `/` to the route table; note `/api`
  now serves the JSON descriptor.

## Files
- `app.py` — provenance fields, `summary()`, `list_reviews()`, `GET /api/reviews`, `/` + `/api` routes
- `dashboard.html` — **new** dashboard UI
- `AGENTS.md`, `README.md`, `CLAUDE.md` — document fields, list endpoint, dashboard

## Verification
1. Rebuild & run: `docker compose up -d --build` (serves `:8137`). (Old container already
   running on 8137/8150 — rebuild replaces it.)
2. Create a tagged review:
   ```bash
   curl -s -X POST localhost:8137/api/reviews -H 'Content-Type: application/json' \
     -d '{"title":"Q2 Update","markdown":"# Q2\n\nBody...\n","project":"acme-web","source_path":"docs/q2.md"}'
   ```
3. `curl -s localhost:8137/api/reviews | python3 -m json.tool` → review appears with
   `project`, `source_path`, `notes_total`, `status:"awaiting"`.
4. Open `http://localhost:8137/` → review shows under **acme-web** with its path + status pill.
   Pre-existing reviews (e.g. the seeded `f0b40ac6c8`) appear under **Ungrouped**.
5. Open a review from a card → viewer loads; add a note; back on `/`, badge shows the note
   and status flips to **feedback**.
6. Delete from a card → confirm, card disappears, `GET /api/reviews` no longer lists it.
7. Back-compat: `curl -s -H 'Accept: application/json' localhost:8137/` still returns the
   descriptor JSON; `curl -s localhost:8137/api` returns it too.
