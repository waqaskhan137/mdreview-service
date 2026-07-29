# mdreview design system — extract of §01-§10

**This is an extract of a picture, not a spec.** The source is a rendered design document
(`mdreview Design System.dc.html`, 2026-07-25) that needs its own `support.js` to display, so its
text was extracted to markdown for citation. Read it as a record of intent.

Three rules for using it:

1. **Where this file is silent, the shipped app wins.** It describes five surfaces at one moment;
   it does not describe everything they do.
2. **Where this file conflicts with shipped code, the code wins and the conflict is recorded below**
   under "Known divergences". Do not change code to match a number in here without a ticket.
3. **Numbers in here are design intent, not measurements.** At least one is already wrong against
   the app (see §10.03).

Section headings carry their numbers (`## §10 Narrow widths`) so a `§10` citation in an issue
resolves by search. Mockup images are omitted with a note saying what they showed; the rules text
is the load-bearing part.

## §01 Color

Same token names in both themes — pages never branch on theme in markup.


### Light

| Token | Value |
|---|---|
| `--bg` | `#f7f7fa` |
| `--panel` | `#ffffff` |
| `--text` | `#16181d` |
| `--muted` | `#5c6270` |
| `--accent` | `#5b30d6` |
| `--blue` | `#1d4fbf` |
| `--green` | `#2f8f5b` |
| `--danger` | `#c0392b` |


### Dark

| Token | Value |
|---|---|
| `--bg` | `#0f1014` |
| `--panel` | `#17181d` |
| `--text` | `#e9eaf0` |
| `--muted` | `#9a9fb0` |
| `--accent` | `#b9a3f5` |
| `--blue` | `#9cc0f5` |
| `--green` | `#6dd39b` |
| `--danger` | `#f0857a` |


### Retired

- #7c6cff (account/admin violet)
- #0e0f13 / #15171c / #262a33 neutrals
- Blue→violet gradient logo & buttons

### Accent means one thing

- Violet = the baton, comments, you
- Blue = structure, links, headings
- Green / amber / red = outcome only

## §02 Type, space, shape

System sans for UI, Charter for document bodies. One 4px spacing grid.


### Type scale

| Role | Example |
|---|---|
| `display/32` | All reviews |
| `title/22` | Connect your agent |
| `card/16` | Retrieval latency budget |
| `body/14` | Default interface text and form labels. |
| `meta/12.5` | Timestamps, counts, breadcrumbs. |
| `eyebrow/11` | Recent activity |
| `doc/20` | The reading column stays serif at 20/1.7 — only the viewer body uses it. |

### Radius

`8 · controls` · `12 · cards` · `16 · panels` · `pill · status`

### Spacing · 4px grid

`8` · `12` · `16` · `24` · `32` · `48`

### Elevation

`rest` · `hover` · `overlay`

## §03 Components

Hover the buttons and fields — states are live.


mini — table rows only
.
Give the token a name so you can revoke it later.
Anyone with the link can read
Every pill: 12px semibold, pill radius, tinted background at ~8% of its hue, and a dot so state survives greyscale.
Could not reach the service. Retrying in 5s.

*(Mockup omitted: the section's screenshot showed a rendered components example; the rules below are the load-bearing part.)*

## §04 Empty, loading, error

Same three shapes on every surface.


Docs arrive from your agent. Mint a token, drop it in your MCP config, and every
lands here.
Skeletons for content that will appear; the ring only for a running agent turn.
The service returned 503. Nothing was changed.

*(Mockup omitted: the section's screenshot showed a rendered empty, loading, error example; the rules below are the load-bearing part.)*

## §05 The shell — no chrome

No sidebar anywhere in the app. One top line, one 680px column, one thing to do next.


retrieval-service · v4 · 2h ago
Retrieval latency budget for the v2 index
Three of your comments have replies waiting. §4 was rewritten with the offline-eval table.
Failure modes in the shard rebalancer
Failure modes in the shard rebalancer
Shard map v3 — resolved

*(Mockup omitted: the section's screenshot showed a rendered the shell — no chrome example; the rules below are the load-bearing part.)*

### Rules

#### §05.01 One violet per screen.

The primary button. Everything else is neutral — status is carried by weight and colour of the text itself.

#### §05.02 No cards, no pills.

Rules at 1px #f2f2f6 separate rows; the container is the page.

#### §05.03 Three weights of row.

500 = yours, 400 muted = agent's, strikethrough-free resolved lives behind "browse all".

#### §05.04 Column never exceeds 680px

— same measure as the viewer, so the two screens feel like one document.


## §06 Account & admin, inside the shell

Same top line, same components, same 680px measure — no more dark-only islands.


Mint a token, drop it into your agent's MCP config once, and every review lands in your dashboard.
Copy it now — it is shown only once.
Manage the people on this mdreview instance.
The admin workflow, end to end
Who gets in, how they get there, and the three things they actually do.
— the avatar menu is the only entry point. Non-admins never see the row.

*(Mockup omitted: the section's screenshot showed a rendered account & admin, inside the shell example; the rules below are the load-bearing part.)*

### Rules

#### §06.01 Two tabs, no more

— People and Instance. Admin is a settings page, not a product.

#### §06.02 One menu per row

replaces the old button cluster; role and ban live together because they are the same decision.

#### §06.03 Every destructive action states its blast radius

and offers Undo for 10s — no confirm() .

#### §06.04 Owner ≠ admin.

One owner, cannot be demoted or banned; their row shows "—".

#### §06.05 Banning never deletes content

— reviews and comments stay, authored by a greyed-out name.


## §07 Viewer

The reading surface keeps its serif column; chrome adopts the shell's language.


Your turn — 3 open comments
Last agent reply 2h ago
The p95 budget is 240ms end to end. Today the reranker alone spends 180ms of it, which leaves nothing for the network hop or the cold-cache case.
Cutting the candidate set from 200 to 64 recovers
with a 0.4pt drop in recall@10.
Where does the 0.4pt figure come from?

*(Mockup omitted: the section's screenshot showed a rendered viewer example; the rules below are the load-bearing part.)*

## §08 Sharing

One popover, three states — private, invited people, public link. Then what the recipient sees.


— the default. No link exists yet.
Off — only invited people
— a person is added; roles are two words, not a matrix.
3 · Public link on
— the link appears in place, already copied.
Anyone with the link can read

*(Mockup omitted: the section's screenshot showed a rendered sharing example; the rules below are the load-bearing part.)*

### Rules

#### §08.01 The button states what is true

— "Share" when private, "Shared" in violet once a link or person exists, with the people count.

#### §08.02 Copy happens on enable

— flipping the toggle puts the link on the clipboard; the button confirms rather than asks.

#### §08.03 Two roles only

— can read, can comment. Anything finer belongs in admin.

#### §08.04 Recipients never see the baton.

Send-to-agent, resolve and delete are hidden, not disabled.

#### §08.05 Turning the link off is instant

and needs no confirm — it is reversible.


## §09 Dark, same markup

Token swap only — account and admin finally follow the OS like every other page.


retrieval-service · v4 · 2h ago
Retrieval latency budget for the v2 index
Three of your comments have replies waiting. §4 was rewritten with the offline-eval table.
Failure modes in the shard rebalancer

*(Mockup omitted: the section's screenshot showed a rendered dark, same markup example; the rules below are the load-bearing part.)*

## §10 Narrow widths

The layout barely changes — that is the payoff of having no sidebar.


retrieval-service · v4 · 2h ago
Retrieval latency budget for the v2 index
Three of your comments have replies waiting.
Failure modes in the shard rebalancer

*(Mockup omitted: the section's screenshot showed a rendered narrow widths example; the rules below are the load-bearing part.)*

### Rules

#### §10.01 44px minimum hit target

— rows, filter words and the primary button all clear it on touch.

#### §10.02 ⌘K becomes a tap target

— the same palette, full-screen on mobile; it replaces search, filters and project switching.

#### §10.03 Headline steps down

40 → 27px; body and rows keep their size, so the measure stays readable.

#### §10.04 Reduced motion respected

— shimmer and spinners fall back to a static tint.


### What changes in the codebase

- New
- static/theme.css
- — tokens, resets, buttons, fields, pills, cards, flash, skeletons, focus. Linked by all five pages.
- account.html + admin.html
- — drop the dark-only block, adopt the top line and the 680px column, restyle tables as rules-and-rows, replace
- alert()
- with the flash bar.
- dashboard.html
- — rebuilt on the no-chrome layout: one "next up", quiet lists, ⌘K palette for search / filters / projects.
- viewer + latex-viewer
- — mostly unchanged: top-bar buttons, banner and comment cards align to the shared component styles.

---

## Known divergences from shipped code

Recorded 2026-07-29 while extracting. Each is the document being wrong about the app, not a defect.

| Where | The document says | The app ships |
|---|---|---|
| §10.03 | Headline steps down **40 -> 27px** | `--t-display` is **32px**, and #184 shipped the narrow step as **32 -> 24px**. The 40px baseline never existed in `theme.css`. |
| §01 | `--accent: #5b30d6`, and `#7c6cff` is retired | `theme.css` names it `--brand: #5b30d6`. The retired `#7c6cff` still appears hardcoded in the admin pill in `web/app/static/account.js` (#262 removes it). |
| §04 | Skeletons and a running-agent ring | Neither exists in first-party code. Verified 2026-07-28 and again 2026-07-29: zero `@keyframes`, zero `animation:` declarations under `web/app` outside vendored bundles. |

## Standing rules added after the extract

Rules agreed after the document was captured. They are **not** part of the extract and are recorded
here because they would otherwise live only in issue comments.

### Motion carries its own reduced-motion fallback

Recorded 2026-07-28 by product-owner (owner proxy) as a dated amendment comment on epic #152,
replacing #184's descoped `prefers-reduced-motion` clause (decision D6 in
`docs/process/runs/2026-07-28-sprints-35-36.md`). Quoted from that comment:

> **Any ticket under this epic that introduces motion (a skeleton shimmer, a spinner or progress
> ring, a pulse, any `@keyframes` or `animation:` declaration) ships its `prefers-reduced-motion`
> fallback in the same change**, verified by computed `animationName`/`currentTime` stepping under a
> CDP `Emulation.setEmulatedMedia` override, never by screenshot (automation tabs are backgrounded
> and CSS animations freeze there).

**Why it lives here.** The rule existed only as a comment on an epic that is a close candidate, so
closing #152 would have deleted a live rule. This file is its tracked home. It applies to any
surface in this system, not only to work under #152.

**Falsified if** motion ships without a fallback (the rule failed and needs to be a gate, not a
document), or if the owner reinstates skeletons and spinners as scoped work, in which case the
fallback attaches to that work.
