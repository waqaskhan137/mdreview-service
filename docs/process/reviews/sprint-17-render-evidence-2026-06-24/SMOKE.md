# Sprint-17 G7 render-smoke evidence

Container-rebuild smoke for the sprint-17 close (G7 gate). Exercises the C1 agent-watcher
endpoints (MR-054 turn filter + `/wait` long-poll; MR-055 stale-lease takeover / fresh-foreign
409) and a viewer render-smoke, against a **throwaway** image + **disposable** container on a
**scratch** host port. No host volume mounted; the live instance (port 8139,
`mdreview-data` volume) and every other container were left untouched.

- Date: 2026-06-24 (Europe/London)
- Branch: `dev` @ HEAD `5b3255b` (Merge MR-055; MR-054 also merged — `d258528`)
- Docker server: 29.5.3
- Image tag: `mdreview-sprint17-smoke` (throwaway)
- Container: `mr17smoke` (disposable, removed at teardown)
- Scratch host port: **8162** (verified free via `lsof -iTCP:8162 -sTCP:LISTEN` → empty)
- Internal port: 8080 (container default; `MDREVIEW_DATA=/data`, fresh empty in-container dir, no `-v`)
- Test review id: `681d599285`

## Verdict summary

| Check | Result |
|-------|--------|
| docker build | **PASS** |
| a. `/healthz` | **PASS** |
| b. `/api/reviews` | **PASS** |
| c. turn filter `?turn=agent` (MR-054) | **PASS** |
| c. `/wait` steady-state already-agent → timeout (MR-054) | **PASS** |
| c. lease fresh-foreign 409 (MR-055) | **PASS** |
| d. viewer render-smoke | **PASS** |

---

## 1. docker build (tail)

`docker build -t mdreview-sprint17-smoke .` — succeeded.

```
#7 [3/5] COPY app.py viewer.html dashboard.html ./
#7 DONE 0.1s
#8 [4/5] COPY static/ ./static/
#8 DONE 0.1s
#9 [5/5] RUN mkdir -p /data
#9 DONE 0.4s
#10 exporting to image
#10 naming to docker.io/library/mdreview-sprint17-smoke:latest done
#10 unpacking to docker.io/library/mdreview-sprint17-smoke:latest 0.0s done
#10 DONE 0.2s
```

Run: `docker run -d --name mr17smoke -p 8162:8080 -e MDREVIEW_DATA=/data mdreview-sprint17-smoke`
→ `Up ... 0.0.0.0:8162->8080/tcp`.

---

## 2. Raw smoke output

### a. `/healthz` — PASS

```
$ curl -s localhost:8162/healthz
{"ok": true}
[http 200]
```

### b. `/api/reviews` — PASS (empty list on fresh in-container volume)

```
$ curl -s localhost:8162/api/reviews
{"reviews": []}
[http 200]
```

### c. C1 endpoints end-to-end (the merged code runs, not just compiles)

**c1. POST a review** → captured id `681d599285`:

```
$ curl -s -X POST localhost:8162/api/reviews -H 'Content-Type: application/json' -d '{"title":"smoke","markdown":"# smoke\n"}'
{"id": "681d599285", "review_url": "http://localhost:8162/review/681d599285", "feedback_url": "...", "source_url": "...", "status_url": "..."}
```

**c2. `GET /api/reviews?turn=agent` before handoff** → empty (filter excludes a reviewer-turn review):

```
$ curl -s "localhost:8162/api/reviews?turn=agent"
{"reviews": []}
[http 200]
```

**c3. `POST /api/reviews/<id>/handoff -d '{"to":"agent"}'`** → 200, `turn` flips to `agent`:

```
{"id": "681d599285", ..., "turn": "agent", "agent_status": null, "handoff": {"by": "reviewer", "at": 1782259473.305044}, "turn_updated": 1782259473.305044}
[http 200]
```

**c4. `GET /api/reviews?turn=agent` after handoff** → the review NOW appears (MR-054 filter):

```
count= 1
  id= 681d599285 turn= agent
```

**c5. `turn_updated` from `/status`** = `1782259473.305044`:

```
$ curl -s "localhost:8162/api/reviews/681d599285/status"
{"source_updated": 1782259473.1484904, "feedback_updated": 0, "comments_updated": 0, "turn": "agent", "turn_updated": 1782259473.305044, "handoff": {"by": "reviewer", "at": 1782259473.305044}, "agent_status": null}
```

**c6. `/wait` steady-state edge (already-agent does NOT return instantly)** — MR-054:

```
$ curl -s "localhost:8162/api/reviews/wait?turn=agent&since=1782259473.305044&timeout=2"
{"reviews": [], "timeout": true}
[http 200]
elapsed=2s
```

**c7. Lease arm owner=A** → 200 (`agent_status.owner = "A"`):

```
$ curl -s -X POST .../handoff -d '{"state":"working","owner":"A"}'
{..., "agent_status": {"state": "working", "message": "", "owner": "A", "at": 1782259482.0955465}, ...}
[http 200]
```

**c8. Immediate lease arm owner=B** → **409** fresh-foreign rejection — MR-055:

```
$ curl -s -X POST .../handoff -d '{"state":"working","owner":"B"}'
{"error": "lease held", "owner": "A"}
[http 409]
```

(The 180s-TTL stale-takeover path was smoke-proven at the unit level with
`MDREVIEW_LEASE_TTL_S=2`; in-container we confirm only the fresh-foreign 409, since the
default TTL can't be waited out here.)

### d. Viewer render-smoke — PASS

`scripts/render-smoke.sh` drives headless Chrome (`Google Chrome 149.0.7827.156`,
`--dump-dom` after a render-wait) and counts rendered DOM elements (not a substring grep).
Sprint-17 touched `viewer.html` with a CODE COMMENT only, so nothing should change visually;
this confirms first-paint and no regression.

```
$ scripts/render-smoke.sh http://localhost:8162/review/681d599285 #article #doctitle #dockbar #turnbanner #gutter
  ok : #article (1 node)
  ok : #doctitle (1 node)
  ok : #dockbar (1 node)
  ok : #turnbanner (1 node)
  ok : #gutter (1 node)
[exit 0]
```

HTML shell also serves 200 (`<title>mdreview</title>`, KaTeX/hljs stylesheets linked).

---

## 3. Teardown

```
$ docker rm -f mr17smoke      # container removed
$ docker rmi mdreview-sprint17-smoke   # throwaway image removed
$ docker ps -a --filter name=mr17smoke   # (empty — gone)
```

Live `mdreview` (8139) and all other containers/volumes untouched.
