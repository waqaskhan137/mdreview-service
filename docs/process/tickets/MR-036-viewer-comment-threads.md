---
id: MR-036
title: Viewer — threaded role-distinct gutter cards (keyed on comment_id), authoring → POST /comments, retire legacy author surfaces, Resolved panel + reopen, comments_updated live-reload
status: done
layer: ui
priority: P1
sprint: sprint-11
epic: comment-resolution
depends_on: [MR-033, MR-034]
branch: dev
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Evolve the MR-006 gutter into the Google-Docs comment UI: each card is a thread (reviewer vs agent
entries, visually distinct); authoring a highlight creates a **comment**; resolved threads hide from the
doc and move to a **Resolved** panel with a count; the reviewer can **reopen**. Crucially, this makes
comments the **single author surface** — every legacy note-author path is retired so the viewer writes
exactly one store (`comments.json`), preserving existing functionality by *evolving* it, not duplicating
it (plan BLOCKER-1, SHOULD-3). Live-reload so an agent's MCP action shows up in the open browser.

## Acceptance criteria

- [ ] **Threaded gutter cards.** `.gcard` renders a thread: header (anchor ref + quoted snippet) + a
      stack of `.gentry` entries `{author,role,text,ts}`. Reviewer vs agent **visually distinct**
      (distinct left-accent/tint per role using existing CSS vars — no new palette). Open cards have a
      reply box → `POST /comments/{cid}/reply` (role reviewer).
- [ ] **Single author surface (BLOCKER-1).** The highlight → selection popover (former "+ note") now
      authors a **comment** (`POST /comments` with `anchor{quoted_text,block_num,start,end}` + first
      reviewer entry). The legacy surfaces are **retired**: `#panel`/`#items` note list, `buildMd`/Collect
      modal, and the `save`/`sync` → `POST /feedback` write path — **no viewer code writes `notes.json`
      after this** (`#count` now counts open+reopened comments). Anchor resolution reuses
      `highlightNote()`/`reconcile()` (text-node `indexOf` + block fallback) unchanged.
- [ ] **comment_id keying (SHOULD-3).** `mark.cmt`/`.gcard` `data-id` values are `comment_id`
      (`/^c[A-Za-z0-9]{10}$/`), not the array index — asserted via DOM dump. Legacy-note *rendering* is
      retired (one `data-id` namespace); legacy `notes.json` data stays readable via `GET /feedback`
      (union projection) and history, just not rendered as live threads.
- [ ] **Resolve hides + Resolved panel.** When `status=="resolved"`, the card + its `mark.cmt` leave the
      active doc and the thread moves into a docked **Resolved panel** (`#resolved`, sibling of `#gutter`)
      with a **`.resolved-count`** header. **No client-side resolve button** (recorded decision: resolve
      is the agent's action; the panel/count update from server state on poll).
- [ ] **Reviewer reopen.** Each resolved thread has a **Reopen** control (`POST /comments/{cid}/reopen`,
      optional reply textarea) → highlight restored, card back in the active gutter, status `reopened`,
      resolved-count drops.
- [ ] **Live-reload re-renders BOTH panels (SHOULD-4).** `poll()` watches `comments_updated`; on change
      it re-fetches `GET /comments` and re-renders **both** the active gutter **and** the Resolved-panel
      threads — so an agent resolve appears, and an agent **reply to an already-resolved comment** shows
      a new `.gentry` under `#resolved` (status unchanged).
- [ ] **Polish.** Dark theme via existing `prefers-color-scheme` vars; dense; open comments scannable,
      resolved ones one click away. No Dockerfile change (inline in `viewer.html`, already COPY'd).
- [ ] **GATING render evidence** (rebuilt throwaway :8138; flat render-smoke selectors; CDP via Node
      built-in WebSocket; both panes via `preferredColorScheme`/`setEmulatedMedia`, never
      `--force-dark-mode`): `render-smoke.sh '/review/$ID' '.gcard' '.gentry' '#resolved'
      '.resolved-count' 'mark.cmt'` all match; `.gentry.reviewer`/`.gentry.agent` each asserted; CDP
      states 1–5 from the epic plan (authoring POSTs `/comments` not `/feedback`; agent-resolve-on-poll
      hides + moves to `#resolved`; reviewer reopen restores; reply-to-resolved re-renders `#resolved`;
      role colors differ). Screenshots (open thread + Resolved panel, both panes) under
      `reviews/sprint-11-render-evidence-2026-06-19/`.
- [ ] Local validation passes: `python3 -m py_compile app.py`; `docker build`; the render-smoke +
      CDP set + screenshots.

## Notes / context

- Epic: `epics/comment-resolution-plan.md` — UI section (the per-surface fate table, threaded cards,
  Resolved panel, reopen, live-reload), SHOULD-1/3/4 resolutions, Verification → MR-036.
- Base: MR-006 gutter `viewer.html:423-527`; legacy surfaces to retire — popover authoring 363-389,
  `renderComments`/`highlightNote` 433-458, `#panel`/`#items` 350-359, `#count` 347-348,
  `buildMd`/Collect 393-409, `save`/`sync`→`/feedback` 340-344; `poll()` 412-419.
- Depends on MR-033 (store + routes + `comments_updated` + projections) + MR-034 (transitions). Drives a
  real agent resolve over MCP if MR-035 lands first.

## Work log

- `2026-06-19` — rewrote `viewer.html`'s inline JS from the single-`note` model onto threaded
  server-side comments as the **one author surface**. The selection popover + block-number click now
  `POST /comments`; the gutter renders thread cards (`.gcard` → `.ghead` + `.gthread` of
  `.gentry.reviewer`/`.gentry.agent` role-distinct entries + a reply box → `POST .../reply`); a docked
  **Resolved panel** (`#resolved` + `.resolved-count` + `.rcard` with a Reopen control →
  `POST .../reopen`). **Retired:** `#panel`/`#items`, `buildMd`/Collect `#modal`, `#toggle`, and the
  `save`/`sync` → `POST /feedback` path (no viewer code writes `notes.json`); `#count` counts open
  comments. Cards/highlights key on **`comment_id`** (`data-id`), not the array index. `poll()` now
  watches `comments_updated` and re-renders **both** the gutter and the Resolved panel; the second
  MR-006 `<script>` block was folded in and removed. Dropped the legacy-note seed (backlog). Dark
  theme via existing `prefers-color-scheme` vars; no Dockerfile change (inline).

## Validation

- `2026-06-19` — `python3 -m py_compile app.py` OK; `docker build` OK; rebuilt throwaway :8138.
  **render-smoke** (VTB 3000): `.gcard`(1) `.gentry`(3) `.gentry.reviewer`(2) `.gentry.agent`(1)
  `#resolved`(1) `.resolved-count`(1) `mark.cmt`(1) `.rcard`(1) — all ≥1. **CDP harness** (Node
  built-in WebSocket, 1500px wide) — **15/15 PASS**: data-id all `/^c[A-Za-z0-9]{10}$/`; legacy
  `#panel`/`#items`/`#collect`/`#modal`/`#toggle` gone; reviewer vs agent backgrounds distinct
  (`rgba(212,160,23,.09)` vs `rgba(45,212,191,.1)`); selection raised "+ comment" → **POSTed
  `/comments`, NOT `/feedback`** → new `.gcard`; out-of-band resolve (simulating MCP — no UI resolve
  button by design) on poll removed the highlight + moved the card to `#resolved` with count++; reviewer
  Reopen restored the highlight + card and count--; a reply to an already-resolved comment re-rendered
  its thread in `#resolved` (SHOULD-4). **Screenshots** (both panes via `setEmulatedMedia`
  prefers-color-scheme, never `--force-dark-mode`; body bg light `rgb(250,250,249)` / dark `rgb(17,17,17)`)
  under `reviews/sprint-11-render-evidence-2026-06-19/comments-{light,dark}.png`.

## Follow-ups

- A comment-thread markdown export (former Collect) → backlog. A manual viewer resolve affordance →
  backlog (touches role attribution; out of this epic).
- Minor: when the Resolved panel is toggled open, it overlays the lower active gutter cards
  (both dock bottom-right). Cosmetic; a left/stacked placement is a polish follow-up.
