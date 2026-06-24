# mdreview-service for agents

A networked, human-in-the-loop markdown review service. You POST markdown over HTTP, hand a
human the returned URL, and poll feedback back. It is a single running service; each review is
an isolated session keyed by `id`. You never spawn a process or touch shared files.

Base URL: wherever the container is published (default `http://localhost:8137`).

## The contract

```bash
BASE=http://localhost:8137

# 1. Submit a document for review. project/session/source_path are optional provenance
#    that groups the review on the dashboard (project > session > files).
resp=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"My draft","markdown":"# My draft\n\nFirst paragraph...\n",
       "project":"my-repo","session":"run-42","source_path":"docs/my-draft.md"}')
# resp = {"id":"...", "review_url":"...", "feedback_url":"...", "status_url":"...", ...}

# 2. Give review_url to the human. They open it and annotate.

# 3. Poll for feedback. status_url is cheap; feedback_url returns the notes.
curl -s "$BASE/api/reviews/<id>/status"     # {"source_updated":..., "feedback_updated":..., "comments_updated":...}
curl -s "$BASE/api/reviews/<id>/feedback"   # {"markdown":"...", "notes":[...], ...}

# 4. Apply the edits, then push the new version (the human's page live-reloads,
#    and notes your edit addressed get struck through).
curl -s -X PUT "$BASE/api/reviews/<id>/source" -H 'Content-Type: application/json' \
  -d '{"markdown":"# My draft\n\nTighter first paragraph...\n"}'

# 5. (optional) clean up
curl -s -X DELETE "$BASE/api/reviews/<id>"
```

## Rich content: math and images

The viewer renders math and diagrams the way a Jekyll/MathJax site does, so a math- or image-heavy
draft reviews as it will publish. **Author to it** — a flow / decision tree / state machine /
architecture belongs in a ```mermaid block (not ASCII art or a plain ``` fence, which renders as
monospace text); equations in `$…$`/`$$…$$`; label code fences for syntax highlighting:

- **Math** renders client-side (KaTeX): inline `$…$` / `\(…\)`, display `$$…$$` / `\[…\]`. A lone or
  currency `$` in prose (`$5 and $10`) stays literal, as does `$` inside code. Nothing to do — just
  POST the markdown.
- **Mermaid** ```` ```mermaid ```` fenced blocks render, and YAML front matter is stripped (not shown
  as text). Both already work.
- **GFM footnotes** (`[^id]` refs + `[^id]: …` definitions) render as superscript links to an ordered
  back-reference section, and **fenced code** (```` ```python ````) is syntax-highlighted (a
  dual-scheme theme that reads on light and dark panes; unlabelled code is best-effort auto-detected).
- **Images** with a **site-root (`/assets/x.png`), relative (`../img/y.svg`), or bare** src won't
  load on their own — the service has your document, not your asset directory. **Attach the bytes
  once** and the viewer serves and rewrites the `<img>` for you:

```bash
# attach an image, keyed by the EXACT src the draft uses (base64 body). Survives every PUT /source.
b64=$(base64 -i fig/plot.png | tr -d '\n')
curl -s -X POST "$BASE/api/reviews/<id>/assets" -H 'Content-Type: application/json' \
  -d "{\"name\":\"fig/plot.png\",\"content_b64\":\"$b64\"}"
# -> {"name":"fig/plot.png","stored":"<hash>.png","url":".../asset/<hash>.png","bytes":...,"ctype":"image/png"}
curl -s "$BASE/api/reviews/<id>/assets"   # list what's attached
```

**Over MCP, pass `path`, not base64.** Call `attach_asset(id, name, path="fig/plot.png")` — the
local MCP wrapper reads and encodes the file itself, so the bytes never pass through your context.
Do **not** hand-carry `content_b64` for anything bigger than a tiny icon (a 38KB SVG is ~50K chars of
base64 you'll corrupt). Over raw HTTP with a shell, the `base64 file | curl` recipe above does the
same — the bytes go file→pipe→service, never through your tokens. `content_b64` is the last resort
(no local file, no shell).

Attach under the same `name` as the `src` in your markdown (full path, or a unique basename); the
viewer matches by full src then basename and repoints the `<img>` — your `source.md` is never
rewritten. Absolute `http(s)` and `data:` images already work as-is (data-URIs are fine for tiny
assets, but attach is the way for anything real — you don't resend the blob through `PUT /source`).
Animated/filtered SVGs (CSS/SMIL, `feTurbulence`) render once reachable; attaching is all they need.
Images render on a neutral light mat so a light-authored figure stays legible on a dark review pane;
a figure drawn for a dark background (white-on-transparent) is the unsupported direction and can look
washed out — author figures light-background-first.

## Detecting "the human is done"

There is no explicit "submit" from the human; feedback streams as they type. Practical options:

- **Explicit handoff (preferred): watch `turn` on `/status`.** When the human presses **"Send to
  agent"** in the viewer, `turn` flips to `"agent"` — an explicit "your move" that replaces the
  guesses below. See **"The turn baton"** below for the loop (`ping_working` → act → `hand_back`).
- Poll `status_url` and watch `comments_updated` — the live signal the viewer bumps as the human
  comments. When it has not changed for a while (e.g. a few minutes) and is non-zero, treat the
  round as complete. (`feedback_updated` is legacy: the pre-MR-036 notes write was retired, so
  nothing bumps it anymore — watch `comments_updated` instead.)
- Or just tell the human "reply 'done' when finished," and read `feedback_url` once on their
  signal.

`notes` is the structured form (each has `num`, `quote`, `note`, `addressed`); `markdown` is the
same content as a readable block per note. Use whichever you prefer. `notes[]` now also includes a
**projection of the comments** (below) — each as `{num, quote, note, addressed}` (`note` = the
thread, `addressed` = the comment is resolved) — so this read path keeps surfacing the human's live
input even though the viewer authors comments now, not notes.

## The turn baton (working with the human live)

The viewer has a **"Send to agent"** button and a status banner, backed by a `turn` baton per review
(`reviewer` | `agent`) and an `agent_status` lease — all surfaced on `GET /status` (and `get_status`).
This makes a review a back-and-forth workspace. Your side of the loop:

1. **Find work.** Poll `list_reviews` (or `get_status` on reviews you own) for ones with
   `turn == "agent"` — the human handed you that one. Filter to reviews you own by the
   `project`/`session` provenance you set on `create_review` (ownership is a tag convention, not
   auth). A baton handed to you while you were offline is **parked**, waiting; you pick it up on your
   next poll. (`turn`/`agent_status` flow through `GET /api/reviews` too, so the list is the queue.)
2. **Claim the lease.** `ping_working(document_id, owner="<your session id>")` right away, then
   periodically while you work, so the viewer shows *"Agent is working…"* instead of a stale
   *"Agent may have stopped"* hint. A review already leased by a **different**, **live** owner returns
   **409** — back off and skip it (one agent per review). A lease whose last ping is older than
   `LEASE_TTL_S` (180s) is **stale** and a foreign owner may take it over (recovery from a dead
   session), so a 409 means the holder is alive, not merely present. (A stale lease the human has
   already reclaimed — `turn` back to the reviewer — still 409s; takeover requires `turn == "agent"`.)
3. **Act, then hand back.** The open **comments are the instruction** — read them, edit,
   `update_source`, reply/resolve the comments you addressed, then `hand_back(document_id,
   message="…")`; `turn` returns to the human with your one-line summary in their banner. If you need
   them, `hand_back(state="blocked")` **and** leave a comment **reply** with the question — never
   `reopen` (that's the reviewer's UI action, deliberately not an MCP tool).

The human can **take the turn back** at any moment (the banner's "Take back the turn"), so don't
assume you still hold it across a long job — re-check `turn` / keep pinging. This explicit baton
replaces the old "watch `comments_updated` go quiet" heuristic. **Reconnect note:** `hand_back` /
`ping_working` are new MCP tools, so a stale stdio server won't list them until the client reconnects
(a render/HTTP change needs no reconnect; a new tool does — see "Calling it over MCP").

**Automating your side of the baton (`watch.py`).** An optional stdlib sibling, `watch.py`, closes
this loop without a human relaying the URL: it long-polls for reviews flipped to `turn==agent`,
claims the lease, and spawns a configured agent command (default Claude headless) whose child env is
the `REVIEW_ID` / `MDREVIEW_BASE` / `MDREVIEW_OWNER` contract above — so the spawned agent renews the
**same** lease and hands back. It runs where your agent runs (like `mcp_server.py`, not containerized)
and is **fail-closed**: it refuses a non-loopback base without an exact `WATCH_TRUSTED_BASE` vouch. It
can run against a **public instance only for armed reviews** — a local operator allowlist
(`WATCH_ARMED_FILE`); a review cannot arm itself (provenance is not a trust boundary on the no-auth
service). See README **"Watcher (optional) — operator runbook"** for arming, the per-review attempt
cap, and the full env-var reference.

## Comments (threaded resolution)

The viewer's primary feedback surface is **threaded comments** (a reviewer highlights text → a
thread). They live server-side (shared by the viewer and MCP), with an `open → resolved → reopened`
state machine the service enforces. Your loop:

```bash
# 1. List what the reviewer raised (default open). document_id == the review id.
curl -s "$BASE/api/reviews/<id>/comments?status=open"        # {"comments":[{comment_id,status,anchor,thread,...}]}
curl -s "$BASE/api/reviews/<id>/comments/<cid>"              # one full thread + status_history

# 2. Reply to discuss WITHOUT resolving (a question, a clarification):
curl -s -X POST "$BASE/api/reviews/<id>/comments/<cid>/reply" \
  -H 'Content-Type: application/json' -d '{"text":"Do you mean X or Y?","role":"agent"}'

# 3. Resolve once you've actually addressed it. justification is OPTIONAL (appended to the thread,
#    attributed to you) but recommended — the reviewer can reopen, so a clear note saves a round.
curl -s -X POST "$BASE/api/reviews/<id>/comments/<cid>/resolve" \
  -H 'Content-Type: application/json' -d '{"justification":"Fixed in the next revision."}'
```

- Always `list_comments(status="open")` first; only address what the reviewer raised. Use `reply`
  for discussion, `resolve` only when the issue is genuinely fixed.
- You can also **author** a comment yourself with `create_comment(document_id, quoted_text, text,
  role?="agent")` (or `POST /comments`) — to leave review feedback at a specific spot. `quoted_text`
  is the exact phrase to anchor to; the viewer highlights it wherever it occurs (omit it for a
  doc-level note). Agent-authored comments are tagged `agent` (distinct colour in the viewer).
- Made a junk/mistaken comment? `delete_comment(document_id, comment_id)` (or `DELETE /comments/{cid}`)
  **hard-removes** it. That's different from `resolve` — only ever delete your own junk, never use it
  to dismiss the reviewer's feedback (resolve that).
- **You never reopen** — reopen is the reviewer's UI action. After a reviewer reopen, you see the
  comment again via the list (status `reopened`/`open`) and can reply or resolve again.
- Roles `reviewer`/`agent` are **attribution, not auth**; "reviewer-only reopen" is a convention on
  the no-auth service, not an enforced boundary. Poll `comments_updated` (on `GET /status`) to know
  when threads changed.
- Resolving sets `resolved_by`/`resolved_at` and moves the thread to the viewer's Resolved panel;
  `thread[]` and `status_history[]` are append-only (full history, never overwritten).

## Discovering and revisiting reviews

- `GET /api/reviews` lists every review with `notes_total`, `notes_addressed`, `revision`, and a
  derived `status` (`awaiting` | `feedback` | `resolved`) — the same data the dashboard at `/`
  renders. Use it to find reviews you created or to poll many at once.
- Each `PUT /source` snapshots a **history round** (the outgoing draft + the feedback it
  accumulated) and bumps `revision`. Revisit past versions with
  `GET /api/reviews/{id}/history` and `GET /api/reviews/{id}/history/{n}`. An earlier draft and
  the feedback it received are always recoverable, not just the latest state.

## Calling it over MCP (optional)

`mcp_server.py` is a thin, stdlib-only stdio MCP server (JSON-RPC 2.0, spec rev `2025-06-18`)
exposing the API as 20 tools (`create_review`, `list_reviews`, `get_review`, `get_source`, `get_feedback`,
`get_status`, `update_source`, `get_history`, `attach_asset`, `list_assets`, `delete_review`, `server_info`,
the comment tools `create_comment` (author a comment), `delete_comment` (hard-remove a junk comment), `list_comments`, `get_comment`, `reply_to_comment`,
`resolve_comment` — there is **no `reopen` tool**, reopen is the reviewer's UI action — and the
**turn-baton** tools `hand_back` (return the turn to the reviewer) and `ping_working` (claim/renew
your lease while you hold the turn; **409** on a foreign owner)). The comment and baton
tools take `document_id` (= the review id); their descriptions encode the workflow above. Run
`MDREVIEW_BASE=http://localhost:8137 python3 mcp_server.py`; smoke with `mcp_smoke.py`. It wraps a
running service and adds no state. Set `MDREVIEW_PUBLIC_BASE` on the service so a relayed
`review_url` is reachable. See `README.md` and `docs/future-mcp.md`.

**If a tool you expect is missing, the running MCP server is probably stale.** A stdio server loads
its code + tool list once at process start; editing `mcp_server.py` does nothing until the client
**reconnects**. To check: `server_info` reports the *running* wrapper's `tools_hash`/version; a
**human/CI** compares it to the on-disk `python3 mcp_server.py --print-version` and reconnects the MCP
client on a mismatch. The server can *signal* its identity but cannot reload itself, and an MCP-only
agent has no on-disk comparand over MCP — so it surfaces its version for the human/CI to compare, it
does not decide "stale" on its own. (This is why a render/HTTP change needs **no** reconnect — the
wrapper just proxies — but a change to `mcp_server.py` itself does.)

## Why this shape

- **One service, many sessions.** Isolated by `id`, so any number of agents and reviews run
  concurrently with no port juggling and no shared state.
- **Decoupled.** You talk HTTP; you do not need the service's filesystem, a local process, or
  the same machine. Point `BASE` at wherever it runs.
- **Stateless client.** The POST response is your handle. Persist the `id` / urls on your side.

## Rules

- Treat `id` as opaque. Operate only on reviews you created.
- The service has no auth. If it is exposed beyond localhost, expect a proxy/token in front;
  do not assume isolation between tenants beyond the `id` namespace.
- `PUT /source` is for pushing your applied edits; do not use it to overwrite a review you did
  not create.

## Running your own instance

```bash
cd mdreview-service
docker compose up -d --build         # localhost:8137
# or pick another host port:
docker run -d -p 9000:8080 -v my-mdreview:/data mdreview-service
```

Each container is independent; point your `BASE` at it. See `README.md` for the full API table
and config.

## Delivery process

Feature work in this repo runs through a file-based, gated delivery process under
`docs/process/` (committed + pushed, so any session reconstructs state from frontmatter + git).
Read `docs/process/README.md` for the gates (G0-G8), conventions, and layout. The
`/feature-cycle` skill (`.claude/skills/feature-cycle/`) drives a brief through
plan -> independent review (G1) -> tickets -> sprint -> implement -> close review (G7) -> PR,
using the `mdreview-planner` and `cycle-retrospective` agents and the global `staff-critic`.

- Tickets `MR-###` in `docs/process/tickets/`; the board is `docs/process/TRACKER.md`.
- Validation gate: `python3 -m py_compile app.py` (+ `docker build` for infra, a browser render
  for UI). No test framework.
- Commits: conventional subject with the ticket ID; this repo keeps the `Co-Authored-By: Claude`
  trailer.
- For the current epic / sprint and shipped history, see `docs/process/TRACKER.md` (source of
  truth) — don't hard-code it here, it goes stale.
