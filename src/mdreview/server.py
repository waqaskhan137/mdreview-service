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
import hmac
import json
import os
import re
import shutil
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from mdreview.config import (
    DATA_DIR, DISK_FLOOR, LEASE_TTL_S, MAX_BODY, PORT, PROXY_SECRET, PUBLIC_BASE,
    REQUIRE_AUTH, RID, TOKEN_PEPPER, WAIT_TIMEOUT_S, WEB_DIR,
)
from mdreview.store import Store
from mdreview.comments import CommentService
from mdreview.assets import AssetService
from mdreview.reviews import ReviewService
from mdreview.handoff import HandoffService
from mdreview.users import UserService

class Services:
    """The composition root's bundle: one Store, injected into each service (constructor injection).
    The per-request handler reads these off the server as self.server.app.<name>, decoupled from how
    they are constructed; no service builds its own dependencies or its own lock."""

    def __init__(self, store):
        self.store = store
        self.comments = CommentService(store)
        self.assets = AssetService(store)
        self.reviews = ReviewService(store, self.comments)
        self.handoff = HandoffService(store, LEASE_TTL_S)
        self.users = UserService(store, TOKEN_PEPPER)


class MdreviewServer(ThreadingHTTPServer):
    """ThreadingHTTPServer carrying the wired Services bundle so the per-request handler can reach it
    via self.server.app (the IoC seam; the handler never constructs a service)."""

    def __init__(self, addr, handler, app):
        super().__init__(addr, handler)
        self.app = app


class H(BaseHTTPRequestHandler):
    server_version = "mdreview/1.0"

    # ---- response helpers ----
    def _send(self, code, body=b"", ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", PUBLIC_BASE or "*")
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

    # ---- auth: resolve every request to (user_id, plane) ----
    # plane is "cookie" (human via oauth2-proxy), "token" (agent via Bearer), or "local" (auth off).
    # A None plane from _require_user/_authz means a 401/404 was already sent, so the caller returns.
    def _principal(self):
        if not REQUIRE_AUTH:
            return (None, "local")
        app = self.server.app
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            uid = app.users.resolve(auth)
            return (uid, "token") if uid else (None, None)
        # Cookie plane: trust the identity header ONLY behind the nginx proxy secret. Fail closed:
        # an empty PROXY_SECRET would make compare_digest("","") pass (config also refuses to boot).
        if PROXY_SECRET and hmac.compare_digest(self.headers.get("X-Mdreview-Proxy", ""), PROXY_SECRET):
            uid = app.users.canonical(self.headers.get("X-Mdreview-Provider", ""),
                                      self.headers.get("X-Auth-Request-User", ""))
            if uid:
                with app.store.lock:
                    app.users.ensure_user(uid, self.headers.get("X-Auth-Request-Email", ""))
                return (uid, "cookie")
        return (None, None)

    def _audit(self, event, **kv):
        # Structured stdout line for an internet-facing multi-user service. NEVER logs a secret,
        # token, or the proxy header, only ids and outcomes.
        kv.update(event=event, ip=(self.headers.get("X-Real-IP") or self.client_address[0]))
        print("AUDIT " + json.dumps(kv), flush=True)

    def _disk_low(self):
        try:
            return shutil.disk_usage(DATA_DIR).free < DISK_FLOOR
        except OSError:
            return False

    def _require_user(self):
        uid, plane = self._principal()
        if plane == "local":
            return (None, "local")
        if uid is None or not self.server.app.users.is_active(uid):
            self._audit("auth_fail", path=urlparse(self.path).path)
            self._json(401, {"error": "authentication required"})
            return (None, None)
        return (uid, plane)

    def _authz(self, rid):
        uid, plane = self._require_user()
        if plane is None:
            return (None, None)                       # 401 already sent
        app = self.server.app
        if not app.reviews.exists(rid) or (REQUIRE_AUTH and not app.reviews.can_access(rid, uid)):
            self._audit("denied_404", uid=uid, rid=rid)   # probing signal (missing or foreign owner)
            self._json(404, {"error": "not found"})       # 404 (not 403): ownership must not be probeable
            return (None, None)
        return (uid, plane)

    def _base(self):
        if PUBLIC_BASE:
            return PUBLIC_BASE
        host = self.headers.get("Host") or f"localhost:{PORT}"
        return f"http://{host}"

    def _wait(self, query, uid=None):
        """Long-poll for baton flips NEWER than a required ?since= cursor (MR-054).

        Edge-triggered, not level: returns only reviews matching the ?turn= filter whose
        turn_updated > since. A review already at turn==agent with turn_updated <= since does NOT
        return (the call blocks up to the bounded timeout), so the steady state of an agent working
        never busy-loops the watcher. Missing since defaults to now() (block for the next flip, the
        safer degrade); since=0 is the explicit backlog opt-in.

        Parks on app.store.lock.wait(timeout), which RELEASES app.store.lock while blocked, so a concurrent writer is
        never deadlocked behind a parked waiter. On wake it re-runs the predicate scan under the lock
        (notify_all wakes every waiter and wait() can wake spuriously). The scan is O(all-reviews),
        but at this scale (a handful of reviews, one operator) that is trivially cheap, and re-scanning
        is correct under rapid flips where carrying only the single last-changed rid could miss an edge.
        """
        app = self.server.app
        qs = parse_qs(query)
        turn_q = qs.get("turn", [""])[0]
        since_raw = qs.get("since", [None])[0]
        # Missing since => now (block for the next flip), NOT since=0 (the explicit backlog opt-in).
        since = time.time() if since_raw is None else app.store.to_float(since_raw, 0.0)
        client_timeout = app.store.to_float(qs.get("timeout", [None])[0], WAIT_TIMEOUT_S)
        timeout = max(0.0, min(client_timeout, WAIT_TIMEOUT_S))
        deadline = time.time() + timeout

        def matches(m):
            return ((not turn_q or m.get("turn") == turn_q)
                    and m.get("turn_updated", 0) > since)

        def changed_rows():
            return [r for r in app.reviews.list_reviews(uid) if matches(r)]

        with app.store.lock:
            rows = changed_rows()                       # baseline scan, once on entry
            while not rows:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return self._json(200, {"reviews": [], "timeout": True})
                app.store.lock.wait(remaining)   # releases app.store.lock while parked
                rows = changed_rows()   # re-scan on wake; cheap at this scale and correct under rapid flips
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
        app = self.server.app
        path = urlparse(self.path).path
        if len(path) > 1:
            path = path.rstrip("/")

        if m in ("POST", "PUT") and int(self.headers.get("Content-Length", 0) or 0) > MAX_BODY:
            return self._json(413, {"error": "request body too large"})

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
            return self._send(200, app.store.read_text(os.path.join(WEB_DIR, "dashboard.html")),
                              "text/html; charset=utf-8")

        # Account + per-user API tokens (cookie plane ONLY: an agent token can never mint/revoke a
        # token, defense-in-depth beyond the nginx routing).
        if path == "/account" and m == "GET":
            uid, plane = self._require_user()
            if plane is None:
                return
            return self._send(200, app.store.read_text(os.path.join(WEB_DIR, "account.html")),
                              "text/html; charset=utf-8")
        if path == "/account/tokens":
            uid, plane = self._require_user()
            if plane is None:
                return
            if plane == "token":
                return self._json(403, {"error": "tokens are managed from the browser, not via an API token"})
            if m == "GET":
                return self._json(200, {"tokens": app.users.list_tokens(uid), "base": self._base()})
            if m == "POST":
                label = (self._body_json().get("label") or "").strip()
                with app.store.lock:
                    token = app.users.mint_token(uid, label)
                return self._json(201, {"token": token, "base": self._base()})
        mo = re.fullmatch(r"/account/tokens/([A-Za-z0-9]{4,40})", path)
        if mo and m == "DELETE":
            uid, plane = self._require_user()
            if plane is None:
                return
            if plane == "token":
                return self._json(403, {"error": "tokens are managed from the browser"})
            with app.store.lock:
                ok = app.users.revoke_token(uid, mo.group(1))
            return self._json(200 if ok else 404,
                              {"revoked": mo.group(1)} if ok else {"error": "no such token"})

        if path == "/api/reviews" and m == "GET":
            uid, plane = self._require_user()
            if plane is None:
                return
            reviews = app.reviews.list_reviews(uid if REQUIRE_AUTH else None)
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
            uid, plane = self._require_user()
            if plane is None:
                return
            return self._wait(urlparse(self.path).query, uid if REQUIRE_AUTH else None)

        if path == "/api/reviews" and m == "POST":
            uid, plane = self._require_user()
            if plane is None:
                return
            if self._disk_low():
                return self._json(507, {"error": "insufficient storage"})
            b = self._body_json()
            rid = app.reviews.create(b.get("markdown", ""), b.get("title", ""),
                                  b.get("project", ""), b.get("source_path", ""),
                                  b.get("session", ""), owner=(uid or ""))
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
            uid, plane = self._authz(rid)
            if plane is None:
                return
            if m == "GET":
                return self._json(200, app.reviews.meta(rid))
            if m == "DELETE":
                app.reviews.delete(rid)
                return self._json(200, {"deleted": rid})

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/source", path)
        if mo:
            rid = mo.group(1)
            uid, plane = self._authz(rid)
            if plane is None:
                return
            if m == "GET":
                return self._send(200, app.reviews.read_source(rid),
                                  "text/markdown; charset=utf-8")
            if m == "PUT":
                b = self._body_json()
                with app.store.lock:
                    app.reviews.put_source(rid, b.get("markdown", ""))
                return self._json(200, app.reviews.meta(rid))

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/feedback", path)
        if mo:
            rid = mo.group(1)
            uid, plane = self._authz(rid)
            if plane is None:
                return
            if m == "GET":
                # comment-aware: meta + feedback.md + a union of on-disk notes and a read-time
                # projection of comments (ReviewService.feedback delegates the projection to
                # CommentService). notes.json on disk is never rewritten here.
                return self._json(200, app.reviews.feedback(rid))
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
            uid, plane = self._authz(rid)
            if plane is None:
                return
            mt = app.reviews.meta(rid)
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

        # Turn baton handoff (MR-051/054/055). The guarded read-decide-write of the turn/lease state
        # lives in HandoffService.apply, called under the one lock so the write and the /wait wake are
        # atomic (no flip is missed); the arm just frames the request.
        mo = re.fullmatch(r"/api/reviews/" + RID + r"/handoff", path)
        if mo and m == "POST":
            rid = mo.group(1)
            uid, plane = self._authz(rid)
            if plane is None:
                return
            with app.store.lock:
                err = app.handoff.apply(rid, self._body_json())
            if err:
                return self._json(*err)
            return self._json(200, app.reviews.meta(rid))

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/history", path)
        if mo and m == "GET":
            rid = mo.group(1)
            uid, plane = self._authz(rid)
            if plane is None:
                return
            return self._json(200, {"rounds": app.reviews.history(rid)})

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/history/(\d+)", path)
        if mo and m == "GET":
            rid, n = mo.group(1), mo.group(2)
            uid, plane = self._authz(rid)
            if plane is None:
                return
            out = app.reviews.history_round(rid, n)
            if out is None:
                return self._json(404, {"error": "no such round"})
            return self._json(200, out)

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/assets", path)
        if mo:
            rid = mo.group(1)
            uid, plane = self._authz(rid)
            if plane is None:
                return
            base = self._base()
            if m == "GET":
                out = []
                for e in app.assets.list(rid):
                    d = dict(e)
                    d["url"] = f"{base}/api/reviews/{rid}/asset/{e['stored']}"
                    out.append(d)
                return self._json(200, {"assets": out})
            if m == "POST":
                if self._disk_low():
                    return self._json(507, {"error": "insufficient storage"})
                b = self._body_json()
                name = b.get("name", "")
                c64 = b.get("content_b64")
                if not name or not c64:
                    return self._json(400, {"error": "name and content_b64 required"})
                try:
                    data = base64.b64decode(c64, validate=True)
                except (ValueError, TypeError):
                    return self._json(400, {"error": "content_b64 is not valid base64"})
                with app.store.lock:
                    entry = app.assets.attach(rid, name, data)
                return self._json(201, {
                    "name": entry["name"], "stored": entry["stored"],
                    "url": f"{base}/api/reviews/{rid}/asset/{entry['stored']}",
                    "bytes": entry["bytes"], "ctype": entry["ctype"],
                })

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/comments", path)
        if mo:
            rid = mo.group(1)
            uid, plane = self._authz(rid)
            if plane is None:
                return
            if m == "GET":
                q = parse_qs(urlparse(self.path).query)
                status = (q.get("status") or ["all"])[0] or "all"
                return self._json(200, {"comments": app.comments.list(rid, status)})
            if m == "POST":
                b = self._body_json()
                # Attribution from the authenticated plane, not spoofable body fields: a human on the
                # cookie plane is a reviewer; an agent on the token plane is an agent. Local/dev keeps
                # the body values for back-compat.
                if plane == "cookie":
                    author, role = uid, "reviewer"
                elif plane == "token":
                    author, role = uid, "agent"
                else:
                    author, role = b.get("author"), b.get("role", "reviewer")
                with app.store.lock:
                    c = app.comments.create(rid, b.get("anchor") or {}, b.get("text", ""),
                                         author, role)
                    app.reviews.bump(rid, "comments_updated")
                return self._json(201, c)

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/comments/(c[A-Za-z0-9]{10})", path)
        if mo and m in ("GET", "DELETE"):
            rid, cid = mo.group(1), mo.group(2)
            uid, plane = self._authz(rid)
            if plane is None:
                return
            if m == "GET":
                c = app.comments.get(rid, cid)
                if not c:
                    return self._json(404, {"error": "no such comment"})
                return self._json(200, c)
            # DELETE: hard-remove a comment (junk cleanup), distinct from resolve, which only hides it.
            with app.store.lock:
                if not app.comments.delete(rid, cid):
                    return self._json(404, {"error": "no such comment"})
                app.reviews.bump(rid, "comments_updated")
            return self._json(200, {"deleted": cid})

        mo = re.fullmatch(
            r"/api/reviews/" + RID + r"/comments/(c[A-Za-z0-9]{10})/(reply|resolve|reopen)", path)
        if mo and m == "POST":
            rid, cid, action = mo.group(1), mo.group(2), mo.group(3)
            uid, plane = self._authz(rid)
            if plane is None:
                return
            b = self._body_json()
            if action == "reply":
                by, text = b.get("role", "reviewer"), b.get("text", "")
            elif action == "resolve":
                by, text = "agent", b.get("justification")          # justification optional
            else:                                                    # reopen
                by, text = "reviewer", b.get("text")                 # reviewer reply optional
            with app.store.lock:
                code, payload = app.comments.apply_transition(rid, cid, action, by, text)
                if code == 200:
                    app.reviews.bump(rid, "comments_updated")
            return self._json(code, payload)

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/asset/([A-Za-z0-9._-]+)", path)
        if mo and m == "GET":
            rid, stored = mo.group(1), mo.group(2)
            uid, plane = self._authz(rid)
            if plane is None:
                return
            # resolve via the manifest only; never path-join the request segment
            entry = app.assets.find(rid, stored)
            if not entry:
                return self._send(404, "asset not found", "text/plain")
            p = app.assets.path(rid, stored)
            if not os.path.isfile(p):
                return self._send(404, "asset not found", "text/plain")
            return self._send(200, app.store.read_bytes(p), entry.get("ctype") or app.store.ctype_for(stored))

        mo = re.fullmatch(r"/review/" + RID, path)
        if mo and m == "GET":
            rid = mo.group(1)
            uid, plane = self._authz(rid)      # non-owner (or unauth) gets 404, no viewer shell leak
            if plane is None:
                return
            return self._send(200, app.store.read_text(os.path.join(WEB_DIR, "viewer.html")),
                              "text/html; charset=utf-8")

        mo = re.fullmatch(r"/static/([A-Za-z0-9._-]+)", path)
        if mo and m == "GET":
            fn = mo.group(1)
            p = os.path.join(WEB_DIR, "static", fn)
            if os.path.isfile(p):
                # binary read: KaTeX ships .woff2 fonts + .css that the utf-8 _read crashes on
                return self._send(200, app.store.read_bytes(p), app.store.ctype_for(fn))
            return self._send(404, "not found", "text/plain")

        self._json(404, {"error": "no route", "method": m, "path": path})


def main():
    app = Services(Store(DATA_DIR))
    print(f"mdreview-service listening on :{PORT}  data={DATA_DIR}", flush=True)
    MdreviewServer(("0.0.0.0", PORT), H, app).serve_forever()


if __name__ == "__main__":
    main()
