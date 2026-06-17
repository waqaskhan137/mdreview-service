---
review_of: epics/rich-rendering-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-18
verdict: PASS
status: resolved
---

## Verdict

Round-2 confirmation pass. The revised plan resolves the round-1 BLOCKER and all five SHOULDs;
the two NITs are also closed. The plan is internally consistent under the five-ticket renumber.
**G1 should pass — ready to spawn tickets.** No new blocker.

## Confirmation of round-1 findings

- **B1 (BLOCKER) — RESOLVED.** The binary-safe read is now a *listed code change*, not an
  afterthought. The plan adds `_read_bytes(path, default=b"")` (`open(path,"rb").read()`, catching
  `FileNotFoundError`) and swaps the `/static/` route onto it; `GET /asset/{stored}` (MR-023) also
  serves through it. The route→read mapping is stated explicitly (binary: `/static/*`,
  `/asset/{stored}`; text: source/feedback/notes/meta keep `_read`/`_read_json`). It appears in the
  Service/Math section (change "0"), the Assets section, Key constraints, Risks (failure-mode 1 of
  3), and the **scope of both MR-022 and MR-023** in the ticket table. Verified against source:
  `_read()` (app.py:49) is `encoding="utf-8"`; `_send()` (app.py:151–153) byte-accepts; the static
  handler (app.py:339) serves via `_read(p)` with a `.js`-only content-type map. The fix matches
  the defect exactly. This was the gate; it is closed.

- **S1 — RESOLVED.** MR-022's gating proof is now the `curl -sI .../static/*.woff2` MIME check
  **plus** a `file(1)` body check (promoted to the gate), with the `.katex` render-smoke explicitly
  downgraded to "math wiring fired, NOT fonts loaded." Stated in the MR-022 Verification block, the
  ticket-table scope note, and the G7 block — consistent across all three.

- **S2 — RESOLVED.** MR-025's image proof is pinned to (a) element exists, (b) a DOM assertion that
  `img.src` equals the served stored-name URL (a present-but-unrewritten 404ing `<img>` must fail),
  and (c) a `curl` of that exact URL returning image bytes via `file(1)`. Element presence alone is
  explicitly marked insufficient.

- **S3 — ADDRESSED (feature cut; check recorded for revival).** Since MR-024's `path` form is cut
  (S5), the `startswith` prefix-confusion bug cannot ship. The correct boundary check
  (`os.path.realpath(root) + os.sep` / `commonpath` with realpath on **both** sides, never naive
  `startswith`) plus negative-path ACs are recorded in Risks and the Non-goals MR-024 entry as a
  hard precondition of any revival. Correct disposition.

- **S4 — RESOLVED (by design).** The served URL keys on the `%2F`-free `sha1+ext` **stored name**
  (`/asset/{stored}`); the human `name` is kept only as a manifest match field. The served path
  never contains an encoded slash, so the reverse-proxy / PUBLIC_BASE deployment can't mangle it.
  Match key and served key are decoupled throughout (Storage bullet, route table, URL-form bullet,
  viewer rewrite step, Key constraints), and a PUBLIC_BASE `%2F`-free smoke is added to MR-025.

- **S5 — RESOLVED (cut, as recommended).** The `{name, path}` server-side local-read form is
  dropped from the epic to backlog; base64 (`content_b64`) is the sole transport. The `path` arg is
  removed from `attach_asset`, the ticket is renumbered, and the count is now **five** (MR-022..026,
  contiguous). Verified: no dangling `path` reference treats it as a live transport — every mention
  is framed as "cut / dropped / if revived." `depends_on` is coherent (MR-024←MR-023; MR-025←MR-023;
  MR-026←all; MR-022 independent). The viewer render sequence cited in N2 matches source exactly
  (viewer.html: 205 `await renderMermaid()`, 206 `reconcile()`, 207 `render()`).

- **N1 / N2 — RESOLVED.** N1: the false "ordering prevents shadowing" rationale is removed and
  flagged "not a constraint" under `re.fullmatch`. N2: the KaTeX insertion point is pinned between
  viewer.html:205 and :206 (before `reconcile`), with the render-once AC against the
  `renderComments()` setTimeout re-walks (viewer.html:402). N3 needed no change.

## Residual non-gating notes

- The back-compat bullet (plan line ~308) still lists `path` among "new POST fields
  (`content_b64`/`path`/`name`) are optional additions." With the `path` form cut, `path` is not a
  field this epic adds — harmless leftover wording, not a blocker. Trim it when MR-023 is written so
  the implementer doesn't add an unused field.

## Resolution log

_Round-2 confirmation by staff-critic, 2026-06-18 (Europe/London). Verified the revised plan and
its "Review resolutions" section against `app.py` (lines 49, 151–153, 333, 339) and
`viewer.html` (205–207)._

- **B1 — confirmed resolved.** Binary read listed; route→read mapping explicit; in MR-022 + MR-023
  scope; `file(1)` body check gates. Code claims verified.
- **S1 — confirmed resolved.** woff2 MIME + `file(1)` body is the gate; `.katex` downgraded.
- **S2 — confirmed resolved.** `img.src ==` served URL + byte fetch gating; presence insufficient.
- **S3 — confirmed addressed.** Boundary check + negative ACs recorded as revival precondition.
- **S4 — confirmed resolved.** Served URL keyed on `%2F`-free stored name; PUBLIC_BASE smoke added.
- **S5 — confirmed resolved.** `path` form cut; base64-only; five contiguous tickets; depends_on
  coherent; no dangling `path` transport reference.
- **N1/N2/N3 — confirmed resolved.**
- **Residual (non-gating):** stray `path` in the back-compat field list (plan ~line 308); trim at
  MR-023 implementation. Does not block G1.

**Verdict: PASS. G1 may pass; tickets may be spawned.**
