#!/usr/bin/env python3
"""mdreview-service: containerized markdown review microservice.

An agent POSTs markdown and gets a review URL for a human; the human marks it up
in a browser; the agent polls feedback back over HTTP. Multi-session (isolated by
id), stdlib only, file-backed under DATA_DIR.

API
  POST   /api/reviews                 {markdown, title?}      -> {id, review_url, feedback_url, source_url}
  GET    /api/reviews/{id}                                    -> meta
  DELETE /api/reviews/{id}                                    -> {deleted}
  GET    /api/reviews/{id}/source                             -> raw markdown
  PUT    /api/reviews/{id}/source     {markdown}              -> meta (agent applies edits; live-reloads viewer)
  GET    /api/reviews/{id}/feedback                           -> {markdown, notes, ...meta}  (notes = legacy notes + projected comments)
  POST   /api/reviews/{id}/feedback                           -> 410    (retired MR-036/MR-046; viewer authors comments — POST /comments)
  GET    /api/reviews/{id}/comments   ?status=open|resolved|reopened|all  -> {comments}
  POST   /api/reviews/{id}/comments   {anchor, text, role?}   -> {comment}  (201; reviewer authors)
  GET    /api/reviews/{id}/comments/{cid}                     -> {comment}  (full thread + status_history)
  DELETE /api/reviews/{id}/comments/{cid}                     -> {deleted}  (hard-remove a junk comment)
  POST   /api/reviews/{id}/comments/{cid}/reply   {text}      -> {comment}  (append; status unchanged)
  POST   /api/reviews/{id}/comments/{cid}/resolve {justification?} -> {comment}  (agent resolves; 409 if not open/reopened)
  POST   /api/reviews/{id}/comments/{cid}/reopen  {text?}     -> {comment}  (reviewer reopens; 409 if not resolved)
  GET    /api/reviews/{id}/status                             -> {source_updated, feedback_updated, comments_updated}
  GET    /review/{id}                                         -> viewer HTML (human opens)
  GET    /static/{file}                                       -> assets (marked/mermaid)
  GET    /healthz                                             -> {ok}
"""
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("MDREVIEW_DATA", "/data")
PORT = int(os.environ.get("PORT", "8080"))
PUBLIC_BASE = os.environ.get("MDREVIEW_PUBLIC_BASE", "").rstrip("/")

os.makedirs(DATA_DIR, exist_ok=True)
# Condition over the ONE global lock (MR-054). A Condition is itself a context manager that
# acquires/releases its internal lock, so every existing `with _lock:` site is unchanged — the swap
# from Lock() to Condition() is transparent. The /wait long-poll parks on _lock.wait(timeout) (which
# releases the lock while blocked) and /handoff calls _lock.notify_all() after a write under the lock.
# One Condition over one lock: never a second lock, or a flip could be missed / a writer could run
# while a waiter holds the lock.
_lock = threading.Condition()
# Bounded server-side timeout for the /wait long-poll (seconds); a client ?timeout= is capped to it.
WAIT_TIMEOUT_S = float(os.environ.get("MDREVIEW_WAIT_TIMEOUT_S", "25"))
# The most recent turn-flip, recorded under _lock just before notify_all() so a woken /wait waiter
# does an O(1) match (one meta(rid) read) instead of re-scanning every review per wake.
_last_change = {"rid": None, "at": 0.0}
RID = r"([A-Za-z0-9]{4,40})"


def _dir(rid):
    return os.path.join(DATA_DIR, rid)


def _exists(rid):
    return os.path.isfile(os.path.join(_dir(rid), "meta.json"))


def _read(path, default=""):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return default


def _read_bytes(path, default=b""):
    """Binary read for assets served verbatim (fonts, images, css).

    The text _read above decodes utf-8 and raises on the first font/image byte;
    binary-served routes (/static/*, the asset GET) must use this instead.
    """
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return default


# Content types for files served out of static/ and for attached asset bytes (the type is
# inferred from the attached name's extension). Anything unlisted -> application/octet-stream.
_CTYPES = {
    ".js": "text/javascript",
    ".css": "text/css",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
}


def _ctype_for(name):
    return _CTYPES.get(os.path.splitext(name)[1].lower(), "application/octet-stream")


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _to_float(s, default):
    """Parse a query-string number, falling back to default on None/garbage (MR-054)."""
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def meta(rid):
    return _read_json(os.path.join(_dir(rid), "meta.json"), {})


def bump(rid, field):
    p = os.path.join(_dir(rid), "meta.json")
    m = _read_json(p, {})
    m[field] = time.time()
    _write(p, json.dumps(m))


def summary(rid):
    """meta augmented with note counts, revision, and a derived status.

    Comment-aware: counts fold in comments (each counts toward total; a resolved comment counts
    toward addressed) so the dashboard never shows "0 / awaiting" for a review with open comments.
    A review with no comments derives exactly as before (the comment contribution is zero).
    """
    m = dict(meta(rid))
    notes = _read_json(os.path.join(_dir(rid), "notes.json"), [])
    comments = list_comments(rid)
    total = len(notes) + len(comments)
    addressed = (sum(1 for n in notes if n.get("addressed"))
                 + sum(1 for c in comments if c.get("status") == "resolved"))
    m["notes_total"] = total
    m["notes_addressed"] = addressed
    m["revision"] = m.get("revision", 0)
    # MR-054: legacy reviews with no turn key read as "reviewer" so the ?turn= filter is filterable,
    # never None/absent (the additive-default-safe rule).
    m["turn"] = m.get("turn", "reviewer")
    if not m.get("feedback_updated") and total == 0:
        m["status"] = "awaiting"
    elif total and addressed == total:
        m["status"] = "resolved"
    else:
        m["status"] = "feedback"
    return m


def list_reviews():
    out = [summary(name) for name in os.listdir(DATA_DIR) if _exists(name)]
    out.sort(key=lambda r: r.get("created", 0), reverse=True)
    return out


def snapshot_round(rid):
    """Archive the current source + feedback as a closed history round; bump revision.

    Called under _lock before a PUT overwrites source.md, so each agent revision leaves
    the outgoing draft and the feedback it accumulated recoverable.
    """
    d = _dir(rid)
    m = _read_json(os.path.join(d, "meta.json"), {})
    n = int(m.get("revision", 0) or 0)
    rd = os.path.join(d, "history", "round-%d" % n)
    os.makedirs(rd, exist_ok=True)
    for fn in ("source.md", "feedback.md", "notes.json"):
        src = os.path.join(d, fn)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(rd, fn))
    notes = _read_json(os.path.join(d, "notes.json"), [])
    _write(os.path.join(rd, "round.json"), json.dumps({
        "round": n, "ts": time.time(),
        "notes_total": len(notes),
        "notes_addressed": sum(1 for x in notes if x.get("addressed")),
    }))
    m["revision"] = n + 1
    _write(os.path.join(d, "meta.json"), json.dumps(m))


def create_review(markdown, title, project="", source_path="", session=""):
    rid = secrets.token_hex(5)
    d = _dir(rid)
    os.makedirs(d, exist_ok=True)
    now = time.time()
    _write(os.path.join(d, "source.md"), markdown or "")
    _write(os.path.join(d, "feedback.md"), "")
    _write(os.path.join(d, "notes.json"), "[]")
    _write(os.path.join(d, "meta.json"), json.dumps({
        "id": rid, "title": title or "", "created": now,
        "source_updated": now,
        "project": project or "", "source_path": source_path or "",
        "session": session or "",
    }))
    return rid


# ---- assets ----
# Per review, raw bytes live under _dir(rid)/assets/<stored> and a manifest at assets.json
# (siblings of source.md/history/, untouched by snapshot_round, so assets survive every PUT
# /source). The stored name is sha1(bytes)[:16] + the sanitized original extension: it can
# never contain '/', '..' or NUL, so it is path-traversal-proof by construction and dedupes
# identical bytes. The human-supplied name is kept only as a manifest match field; it never
# appears in a filesystem path or a served URL.
_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,8}$")


def _assets_dir(rid):
    return os.path.join(_dir(rid), "assets")


def _assets_manifest(rid):
    return os.path.join(_dir(rid), "assets.json")


def list_assets(rid):
    return _read_json(_assets_manifest(rid), [])


def _stored_name(name, data):
    mo = _EXT_RE.search(name or "")
    ext = mo.group(0).lower() if mo else ""
    return hashlib.sha1(data).hexdigest()[:16] + ext


def attach_asset(rid, name, data):
    """Store bytes under a content-hash name and upsert the manifest. Caller holds _lock."""
    ad = _assets_dir(rid)
    os.makedirs(ad, exist_ok=True)
    stored = _stored_name(name, data)
    with open(os.path.join(ad, stored), "wb") as f:
        f.write(data)
    entry = {"name": name, "stored": stored, "bytes": len(data),
             "ctype": _ctype_for(name), "ts": time.time()}
    manifest = [e for e in _read_json(_assets_manifest(rid), []) if e.get("name") != name]
    manifest.append(entry)
    _write(_assets_manifest(rid), json.dumps(manifest))
    return entry


# ---- comments ----
# Threaded, server-side comments live in _dir(rid)/comments.json (a sibling of notes.json,
# untouched by snapshot_round). Each is the single source of truth for one review thread, shared
# by the viewer and MCP; the state machine (open -> resolved -> reopened) is enforced server-side
# (apply_comment_transition, below). thread[] and status_history[] are append-only; status is a
# derived pointer. Legacy notes.json data on disk is never rewritten — but the agent/dashboard read
# paths (GET /feedback, summary()) are made comment-aware by *read-time projection* so nothing the
# human says is lost once viewer authoring moves onto comments.
def _comments_path(rid):
    return os.path.join(_dir(rid), "comments.json")


def list_comments(rid, status="all"):
    arr = _read_json(_comments_path(rid), [])
    if status and status != "all":
        return [c for c in arr if c.get("status") == status]
    return arr


def _write_comments(rid, arr):
    """Whole-file write of the comment array. Caller holds _lock."""
    _write(_comments_path(rid), json.dumps(arr))


def _find_comment(arr, cid):
    return next((c for c in arr if c.get("comment_id") == cid), None)


def _comment_as_note(c):
    """Read-time projection of one comment into the legacy {num,quote,note,addressed} note shape.

    Pure (no write). Used to keep GET /feedback returning the human's live input once authoring
    moves onto comments. `note` is the full thread, role-prefixed, so no entry is lost.
    """
    anc = c.get("anchor") or {}
    thread = c.get("thread") or []
    note = "\n".join("%s: %s" % (e.get("role", "reviewer"), e.get("text", "")) for e in thread)
    return {
        "num": anc.get("block_num", ""),
        "quote": anc.get("quoted_text", ""),
        "note": note,
        "addressed": c.get("status") == "resolved",
    }


def create_comment(rid, anchor, text, author=None, role="reviewer"):
    """Append a new open comment with one thread entry. Caller holds _lock."""
    now = time.time()
    role = role if role in ("reviewer", "agent") else "reviewer"
    author = author or role
    anchor = anchor or {}
    c = {
        "comment_id": "c" + secrets.token_hex(5),
        "status": "open",
        "anchor": {
            "quoted_text": anchor.get("quoted_text", ""),
            "block_num": anchor.get("block_num", ""),
            "start": anchor.get("start"),
            "end": anchor.get("end"),
        },
        "thread": [{"author": author, "role": role, "text": text or "", "ts": now}],
        "created_by": author,
        "created_at": now,
        "resolved_by": None,
        "resolved_at": None,
        "status_history": [{"from": None, "to": "open", "by": author, "ts": now}],
    }
    arr = _read_json(_comments_path(rid), [])
    arr.append(c)
    _write_comments(rid, arr)
    return c


def apply_comment_transition(rid, cid, action, by, text=None):
    """The single writer for comment state transitions, shared by the viewer and MCP routes so the
    two can never diverge. Caller holds _lock.

    Returns (http_code, payload): 200 + the updated comment on success; 409 + {error,status} on an
    illegal transition (resolve a non-open/reopened, reopen a non-resolved); 404 + {error} when the
    comment is missing. thread[] and status_history[] are append-only — never rewritten.
    """
    arr = _read_json(_comments_path(rid), [])
    c = _find_comment(arr, cid)
    if c is None:
        return 404, {"error": "no such comment"}
    now = time.time()
    cur = c.get("status")
    if action == "reply":
        # legal in every state (incl. resolved — discussion without un-resolving); status unchanged.
        if not (text and text.strip()):
            return 400, {"error": "reply text required"}
        role = by if by in ("reviewer", "agent") else "reviewer"
        c["thread"].append({"author": role, "role": role, "text": text, "ts": now})
    elif action == "resolve":
        if cur not in ("open", "reopened"):
            return 409, {"error": "comment is not open/reopened", "status": cur}
        if text:  # optional justification, appended as the final agent entry before the flip
            c["thread"].append({"author": "agent", "role": "agent", "text": text, "ts": now})
        c["status"] = "resolved"
        c["resolved_by"] = "agent"
        c["resolved_at"] = now
        c["status_history"].append({"from": cur, "to": "resolved", "by": "agent", "ts": now})
    elif action == "reopen":
        if cur != "resolved":
            return 409, {"error": "comment is not resolved", "status": cur}
        if text:  # optional reviewer reply, appended before the flip
            c["thread"].append({"author": "reviewer", "role": "reviewer", "text": text, "ts": now})
        c["status"] = "reopened"
        c["resolved_by"] = None
        c["resolved_at"] = None
        c["status_history"].append({"from": cur, "to": "reopened", "by": "reviewer", "ts": now})
    else:
        return 400, {"error": "unknown action"}
    _write_comments(rid, arr)
    return 200, c


class H(BaseHTTPRequestHandler):
    server_version = "mdreview/1.0"

    # ---- response helpers ----
    def _send(self, code, body=b"", ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj), "application/json")

    def _body_json(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return {}

    def _base(self):
        if PUBLIC_BASE:
            return PUBLIC_BASE
        host = self.headers.get("Host") or f"localhost:{PORT}"
        return f"http://{host}"

    def _wait(self, query):
        """Long-poll for baton flips NEWER than a required ?since= cursor (MR-054).

        Edge-triggered, not level: returns only reviews matching the ?turn= filter whose
        turn_updated > since. A review already at turn==agent with turn_updated <= since does NOT
        return (the call blocks up to the bounded timeout), so the steady state of an agent working
        never busy-loops the watcher. Missing since defaults to now() (block for the next flip, the
        safer degrade); since=0 is the explicit backlog opt-in.

        Parks on _lock.wait(timeout), which RELEASES _lock while blocked, so a concurrent writer is
        never deadlocked behind a parked waiter. On wake it re-checks the predicate under the lock
        (notify_all wakes every waiter and wait() can wake spuriously), doing an O(1) match on the
        recorded changed rid rather than a full list_reviews() rescan per wake.
        """
        qs = parse_qs(query)
        turn_q = qs.get("turn", [""])[0]
        since_raw = qs.get("since", [None])[0]
        # Missing since => now (block for the next flip), NOT since=0 (the explicit backlog opt-in).
        since = time.time() if since_raw is None else _to_float(since_raw, 0.0)
        client_timeout = _to_float(qs.get("timeout", [None])[0], WAIT_TIMEOUT_S)
        timeout = max(0.0, min(client_timeout, WAIT_TIMEOUT_S))
        deadline = time.time() + timeout

        def matches(m):
            return ((not turn_q or m.get("turn") == turn_q)
                    and m.get("turn_updated", 0) > since)

        def changed_rows():
            return [r for r in list_reviews() if matches(r)]

        with _lock:
            rows = changed_rows()                       # baseline scan, once on entry
            while not rows:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return self._json(200, {"reviews": [], "timeout": True})
                _lock.wait(remaining)                    # releases _lock while parked
                rid = _last_change["rid"]                # O(1) match: only re-scan if the recorded
                if rid is not None and matches(meta(rid)):  # changed rid matches this waiter's filter
                    rows = changed_rows()
        return self._json(200, {"reviews": rows})

    def log_message(self, *a):
        pass

    # ---- verbs ----
    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_DELETE(self):
        self.route("DELETE")

    # ---- router ----
    def route(self, m):
        path = urlparse(self.path).path
        if len(path) > 1:
            path = path.rstrip("/")

        if path == "/healthz" and m == "GET":
            return self._json(200, {"ok": True})

        if path in ("/", "/api") and m == "GET":
            descriptor = {
                "service": "mdreview",
                "dashboard": "GET / (HTML; this descriptor on Accept: application/json or GET /api)",
                "list_reviews": "GET /api/reviews",
                "post_a_review": "POST /api/reviews {markdown, title?, project?, source_path?, session?}",
                "collect_feedback": "GET /api/reviews/{id}/feedback",
            }
            if path == "/api" or "application/json" in self.headers.get("Accept", ""):
                return self._json(200, descriptor)
            return self._send(200, _read(os.path.join(HERE, "dashboard.html")),
                              "text/html; charset=utf-8")

        if path == "/api/reviews" and m == "GET":
            reviews = list_reviews()
            # MR-054: optional ?turn= filter. Filtered in Python after list_reviews() (summary() is
            # where the turn default lands); an empty/absent value means no filter (return all),
            # preserving today's behavior. No new field, no cross-review aggregation.
            turn_q = parse_qs(urlparse(self.path).query).get("turn", [""])[0]
            if turn_q:
                reviews = [r for r in reviews if r.get("turn") == turn_q]
            return self._json(200, {"reviews": reviews})

        # MR-054: /wait long-poll. MUST precede the per-review RID arm — "wait" matches RID, so a
        # later placement would be shadowed into a review-id lookup (404). Collection-level: blocks
        # until a baton flips NEWER than the required ?since= cursor (an edge, not the steady-state
        # level of turn==agent), or a bounded timeout elapses.
        if path == "/api/reviews/wait" and m == "GET":
            return self._wait(urlparse(self.path).query)

        if path == "/api/reviews" and m == "POST":
            b = self._body_json()
            rid = create_review(b.get("markdown", ""), b.get("title", ""),
                                b.get("project", ""), b.get("source_path", ""),
                                b.get("session", ""))
            base = self._base()
            return self._json(201, {
                "id": rid,
                "review_url": f"{base}/review/{rid}",
                "feedback_url": f"{base}/api/reviews/{rid}/feedback",
                "source_url": f"{base}/api/reviews/{rid}/source",
                "status_url": f"{base}/api/reviews/{rid}/status",
            })

        mo = re.fullmatch(r"/api/reviews/" + RID, path)
        if mo:
            rid = mo.group(1)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            if m == "GET":
                return self._json(200, meta(rid))
            if m == "DELETE":
                shutil.rmtree(_dir(rid), ignore_errors=True)
                return self._json(200, {"deleted": rid})

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/source", path)
        if mo:
            rid = mo.group(1)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            if m == "GET":
                return self._send(200, _read(os.path.join(_dir(rid), "source.md")),
                                  "text/markdown; charset=utf-8")
            if m == "PUT":
                b = self._body_json()
                with _lock:
                    snapshot_round(rid)
                    _write(os.path.join(_dir(rid), "source.md"), b.get("markdown", ""))
                    bump(rid, "source_updated")
                return self._json(200, meta(rid))

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/feedback", path)
        if mo:
            rid = mo.group(1)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            if m == "GET":
                out = dict(meta(rid))
                out["markdown"] = _read(os.path.join(_dir(rid), "feedback.md"))
                # comment-aware: union of on-disk notes + a read-time projection of comments, so an
                # agent's existing get_feedback path still returns the human's live input once
                # authoring moves onto comments. notes.json on disk is never rewritten here.
                out["notes"] = (_read_json(os.path.join(_dir(rid), "notes.json"), [])
                                + [_comment_as_note(c) for c in list_comments(rid)])
                return self._json(200, out)
            if m == "POST":
                # Retired (MR-046). The viewer wrote notes/feedback here until MR-036; it authors
                # comments now (POST /comments). The write is gone — return an explicit 410 (not a
                # silent 404 fall-through) so any straggler caller on this no-auth surface gets a
                # clear "use comments" signal. No write, no bump: feedback_updated has no writer
                # anymore. The GET arm above is unchanged — feedback.md/notes.json stay read-live.
                return self._json(410, {"error": "gone, use comments"})

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/status", path)
        if mo and m == "GET":
            rid = mo.group(1)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            mt = meta(rid)
            return self._json(200, {
                "source_updated": mt.get("source_updated", 0),
                "feedback_updated": mt.get("feedback_updated", 0),
                "comments_updated": mt.get("comments_updated", 0),
                # turn baton (MR-051): additive; absent on legacy reviews -> defaults below
                "turn": mt.get("turn", "reviewer"),
                "turn_updated": mt.get("turn_updated", 0),
                "handoff": mt.get("handoff"),
                "agent_status": mt.get("agent_status"),
            })

        # Turn baton handoff (MR-051). Guarded read-check-write of meta.json under _lock: turn/owner
        # are control state both the viewer and an agent write concurrently, so read the CURRENT
        # turn/owner, decide, write once. Never a bare bump() (unlocked, assumes the caller holds
        # _lock, as PUT /source does). Body forms dispatch in a PINNED order so an ambiguous body
        # (e.g. {to:reviewer,by:reviewer,state:done}) is deterministic: reclaim, hand-back, flip,
        # lease; anything else is a 400.
        mo = re.fullmatch(r"/api/reviews/" + RID + r"/handoff", path)
        if mo and m == "POST":
            rid = mo.group(1)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            b = self._body_json()
            to, by, state = b.get("to"), b.get("by"), b.get("state")
            p = os.path.join(_dir(rid), "meta.json")
            err = None
            with _lock:
                mt = _read_json(p, {})
                now = time.time()
                if to == "reviewer" and by == "reviewer":
                    # reclaim: force the turn back regardless of state (leave agent_status so the
                    # banner can still read a stale state if it wants).
                    mt["turn"] = "reviewer"
                    mt["turn_updated"] = now
                elif to == "reviewer" and state in ("done", "blocked"):
                    # hand-back: the agent returns the turn with its state + message.
                    prev = mt.get("agent_status") or {}
                    mt["turn"] = "reviewer"
                    mt["agent_status"] = {"state": state, "message": b.get("message", ""),
                                          "owner": b.get("owner", prev.get("owner", "")), "at": now}
                    mt["turn_updated"] = now
                elif to == "agent":
                    # flip: idempotent. Bump turn_updated only on an actual reviewer->agent flip.
                    if mt.get("turn", "reviewer") != "agent":
                        mt["turn"] = "agent"
                        mt["agent_status"] = None          # parked, not yet claimed
                        mt["handoff"] = {"by": "reviewer", "at": now}
                        mt["turn_updated"] = now
                elif state == "working":
                    # lease claim/renew: only the current owner (or an unowned lease) writes; a
                    # foreign owner backs off with 409. turn_updated is NOT bumped (no flip).
                    owner = b.get("owner", "")
                    cur_owner = (mt.get("agent_status") or {}).get("owner")
                    if cur_owner in (None, "", owner):
                        mt["agent_status"] = {"state": "working", "message": b.get("message", ""),
                                              "owner": owner, "at": now}
                    else:
                        err = (409, {"error": "lease held", "owner": cur_owner})
                else:
                    err = (400, {"error": "unrecognized handoff body"})
                if err is None:
                    _write(p, json.dumps(mt))
                    # MR-054: record the changed rid (O(1) match for woken /wait waiters) and notify,
                    # both under the lock so the write and the wake are atomic — no flip is missed.
                    # Notify on any successful write; the /wait predicate (turn_updated > since), not
                    # the arm, decides whether a parked waiter actually returns.
                    _last_change["rid"] = rid
                    _last_change["at"] = now
                    _lock.notify_all()
            if err:
                return self._json(*err)
            return self._json(200, meta(rid))

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/history", path)
        if mo and m == "GET":
            rid = mo.group(1)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            hd = os.path.join(_dir(rid), "history")
            rounds = []
            if os.path.isdir(hd):
                for name in os.listdir(hd):
                    rj = _read_json(os.path.join(hd, name, "round.json"), None)
                    if rj:
                        rounds.append(rj)
            rounds.sort(key=lambda r: r.get("round", 0), reverse=True)
            return self._json(200, {"rounds": rounds})

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/history/(\d+)", path)
        if mo and m == "GET":
            rid, n = mo.group(1), mo.group(2)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            rd = os.path.join(_dir(rid), "history", "round-%s" % n)
            if not os.path.isfile(os.path.join(rd, "round.json")):
                return self._json(404, {"error": "no such round"})
            out = dict(_read_json(os.path.join(rd, "round.json"), {}))
            out["source"] = _read(os.path.join(rd, "source.md"))
            out["feedback"] = _read(os.path.join(rd, "feedback.md"))
            out["notes"] = _read_json(os.path.join(rd, "notes.json"), [])
            return self._json(200, out)

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/assets", path)
        if mo:
            rid = mo.group(1)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            base = self._base()
            if m == "GET":
                out = []
                for e in list_assets(rid):
                    d = dict(e)
                    d["url"] = f"{base}/api/reviews/{rid}/asset/{e['stored']}"
                    out.append(d)
                return self._json(200, {"assets": out})
            if m == "POST":
                b = self._body_json()
                name = b.get("name", "")
                c64 = b.get("content_b64")
                if not name or not c64:
                    return self._json(400, {"error": "name and content_b64 required"})
                try:
                    data = base64.b64decode(c64, validate=True)
                except (ValueError, TypeError):
                    return self._json(400, {"error": "content_b64 is not valid base64"})
                with _lock:
                    entry = attach_asset(rid, name, data)
                return self._json(201, {
                    "name": entry["name"], "stored": entry["stored"],
                    "url": f"{base}/api/reviews/{rid}/asset/{entry['stored']}",
                    "bytes": entry["bytes"], "ctype": entry["ctype"],
                })

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/comments", path)
        if mo:
            rid = mo.group(1)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            if m == "GET":
                q = parse_qs(urlparse(self.path).query)
                status = (q.get("status") or ["all"])[0] or "all"
                return self._json(200, {"comments": list_comments(rid, status)})
            if m == "POST":
                b = self._body_json()
                with _lock:
                    c = create_comment(rid, b.get("anchor") or {}, b.get("text", ""),
                                       b.get("author"), b.get("role", "reviewer"))
                    bump(rid, "comments_updated")
                return self._json(201, c)

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/comments/(c[A-Za-z0-9]{10})", path)
        if mo and m in ("GET", "DELETE"):
            rid, cid = mo.group(1), mo.group(2)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            if m == "GET":
                c = _find_comment(list_comments(rid), cid)
                if not c:
                    return self._json(404, {"error": "no such comment"})
                return self._json(200, c)
            # DELETE: hard-remove a comment (junk cleanup) — distinct from resolve, which only hides it.
            with _lock:
                arr = _read_json(_comments_path(rid), [])
                kept = [x for x in arr if x.get("comment_id") != cid]
                if len(kept) == len(arr):
                    return self._json(404, {"error": "no such comment"})
                _write_comments(rid, kept)
                bump(rid, "comments_updated")
            return self._json(200, {"deleted": cid})

        mo = re.fullmatch(
            r"/api/reviews/" + RID + r"/comments/(c[A-Za-z0-9]{10})/(reply|resolve|reopen)", path)
        if mo and m == "POST":
            rid, cid, action = mo.group(1), mo.group(2), mo.group(3)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            b = self._body_json()
            if action == "reply":
                by, text = b.get("role", "reviewer"), b.get("text", "")
            elif action == "resolve":
                by, text = "agent", b.get("justification")          # justification optional
            else:                                                    # reopen
                by, text = "reviewer", b.get("text")                 # reviewer reply optional
            with _lock:
                code, payload = apply_comment_transition(rid, cid, action, by, text)
                if code == 200:
                    bump(rid, "comments_updated")
            return self._json(code, payload)

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/asset/([A-Za-z0-9._-]+)", path)
        if mo and m == "GET":
            rid, stored = mo.group(1), mo.group(2)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            # resolve via the manifest only; never path-join the request segment
            entry = next((e for e in list_assets(rid) if e.get("stored") == stored), None)
            if not entry:
                return self._send(404, "asset not found", "text/plain")
            p = os.path.join(_assets_dir(rid), stored)
            if not os.path.isfile(p):
                return self._send(404, "asset not found", "text/plain")
            return self._send(200, _read_bytes(p), entry.get("ctype") or _ctype_for(stored))

        mo = re.fullmatch(r"/review/" + RID, path)
        if mo and m == "GET":
            rid = mo.group(1)
            if not _exists(rid):
                return self._send(404, "review not found", "text/plain")
            return self._send(200, _read(os.path.join(HERE, "viewer.html")),
                              "text/html; charset=utf-8")

        mo = re.fullmatch(r"/static/([A-Za-z0-9._-]+)", path)
        if mo and m == "GET":
            fn = mo.group(1)
            p = os.path.join(HERE, "static", fn)
            if os.path.isfile(p):
                # binary read: KaTeX ships .woff2 fonts + .css that the utf-8 _read crashes on
                return self._send(200, _read_bytes(p), _ctype_for(fn))
            return self._send(404, "not found", "text/plain")

        self._json(404, {"error": "no route", "method": m, "path": path})


def main():
    print(f"mdreview-service listening on :{PORT}  data={DATA_DIR}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()


if __name__ == "__main__":
    main()
