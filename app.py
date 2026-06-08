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
  GET    /api/reviews/{id}/feedback                           -> {markdown, notes, ...meta}
  POST   /api/reviews/{id}/feedback   {markdown, notes}       -> {ok}   (viewer saves here)
  GET    /api/reviews/{id}/status                             -> {source_updated, feedback_updated}
  GET    /review/{id}                                         -> viewer HTML (human opens)
  GET    /static/{file}                                       -> assets (marked/mermaid)
  GET    /healthz                                             -> {ok}
"""
import json
import os
import re
import secrets
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("MDREVIEW_DATA", "/data")
PORT = int(os.environ.get("PORT", "8080"))
PUBLIC_BASE = os.environ.get("MDREVIEW_PUBLIC_BASE", "").rstrip("/")

os.makedirs(DATA_DIR, exist_ok=True)
_lock = threading.Lock()
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


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def meta(rid):
    return _read_json(os.path.join(_dir(rid), "meta.json"), {})


def bump(rid, field):
    p = os.path.join(_dir(rid), "meta.json")
    m = _read_json(p, {})
    m[field] = time.time()
    _write(p, json.dumps(m))


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
        "source_updated": now, "feedback_updated": 0,
        "project": project or "", "source_path": source_path or "",
        "session": session or "",
    }))
    return rid


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

        if path == "/" and m == "GET":
            return self._json(200, {
                "service": "mdreview",
                "post_a_review": "POST /api/reviews {markdown, title?}",
                "collect_feedback": "GET /api/reviews/{id}/feedback",
            })

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
                out["notes"] = _read_json(os.path.join(_dir(rid), "notes.json"), [])
                return self._json(200, out)
            if m == "POST":
                b = self._body_json()
                with _lock:
                    _write(os.path.join(_dir(rid), "feedback.md"), b.get("markdown", ""))
                    _write(os.path.join(_dir(rid), "notes.json"), json.dumps(b.get("notes", [])))
                    bump(rid, "feedback_updated")
                return self._json(200, {"ok": True})

        mo = re.fullmatch(r"/api/reviews/" + RID + r"/status", path)
        if mo and m == "GET":
            rid = mo.group(1)
            if not _exists(rid):
                return self._json(404, {"error": "not found"})
            mt = meta(rid)
            return self._json(200, {
                "source_updated": mt.get("source_updated", 0),
                "feedback_updated": mt.get("feedback_updated", 0),
            })

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
                ctype = "text/javascript" if fn.endswith(".js") else "application/octet-stream"
                return self._send(200, _read(p), ctype)
            return self._send(404, "not found", "text/plain")

        self._json(404, {"error": "no route", "method": m, "path": path})


def main():
    print(f"mdreview-service listening on :{PORT}  data={DATA_DIR}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()


if __name__ == "__main__":
    main()
