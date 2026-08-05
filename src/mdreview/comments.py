"""Threaded comments: the open -> resolved -> reopened state machine (MR-082).

CommentService is the single writer for comment transitions, shared by the viewer and the MCP
routes so the two can never diverge. Comments live in <data>/<rid>/comments.json (a sibling of
notes.json, untouched by snapshot_round); thread[] and status_history[] are append-only, status a
derived pointer. Legacy notes.json is never rewritten: the agent/dashboard read paths stay
comment-aware via a read-time projection (as_note). Mutating methods assume the caller holds
store.lock (the route arm wraps the call), exactly as the original free functions did.
"""
import json
import os
import re
import secrets
import time

# issue #15: a block id is a content hash (hex) with an optional "-N" duplicate suffix. Persisted from
# the client anchor, so validate the charset before storing: the viewer looks it up via
# `.blk[data-bid="…"]`, and an injected quote would break that selector (self-DoS on the author's view).
_BID_RE = re.compile(r"[0-9a-f]{1,16}(-[0-9]+)?")


class CommentService:
    def __init__(self, store):
        self.store = store

    def _path(self, rid):
        return os.path.join(self.store.dir(rid), "comments.json")

    def list(self, rid, status="all"):
        arr = self.store.read_json(self._path(rid), [])
        if status and status != "all":
            return [c for c in arr if c.get("status") == status]
        return arr

    def _write(self, rid, arr):
        """Whole-file write of the comment array. Caller holds store.lock."""
        self.store.write_text(self._path(rid), json.dumps(arr))

    @staticmethod
    def _find(arr, cid):
        return next((c for c in arr if c.get("comment_id") == cid), None)

    def get(self, rid, cid):
        """One comment by id (was the inline _find_comment(list_comments(...)) in the GET arm)."""
        return self._find(self.list(rid), cid)

    @staticmethod
    def as_note(c):
        """Read-time projection of one comment into the legacy {num,quote,note,addressed} note shape.

        Pure (no write). Keeps GET /feedback returning the human's live input once authoring moves
        onto comments. `note` is the full thread, role-prefixed, so no entry is lost.
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

    @staticmethod
    def with_author_names(comments, users):
        """Read-time projection (#309 universal attribution): each thread entry in `comments`
        gains a 'name' -- the author's CURRENT display name, resolved fresh from `users` on every
        call. Nothing is stored and nothing on the write path (create/apply_transition) changes,
        which is exactly how retroactive attribution works: a name set today appears on every
        comment/reply the user already wrote, because no name was ever snapshotted onto one.

        "" (never a placeholder) when the entry does not resolve to a named user: a role-literal
        author -- the string "reviewer" or "agent", which is what EVERY reply/resolve/reopen
        entry carries (apply_transition, above) and what a non-cookie-plane comment's first entry
        falls back to (create()'s `author = author or role`) -- has no user record to look up, and
        a real uid with no name set resolves to "" too (UserService.name_for's own
        absent-means-unset contract). Both cases render EXACTLY as they did before #309.

        Deliberately does NOT touch resolved_by, status_history[].by, or any other field: those
        are #287's plane-derived reviewer-vs-agent ATTRIBUTION OF AN ACTION, a fact distinct from
        a user's chosen display LABEL, and must never be replaced or contaminated by one.

        One users.json read per thread entry, same as email_for/is_admin/is_active elsewhere in
        UserService -- no batching layer exists anywhere in this class, and a comment thread is
        small at this service's scale (per ReviewService's own #279 sizing note). Pure: returns
        new dicts, never mutates `comments` (callers hand this live records read with no lock)."""
        out = []
        for c in comments:
            c2 = dict(c)
            c2["thread"] = [dict(e, name=users.name_for(e.get("author", "")))
                            for e in (c.get("thread") or [])]
            out.append(c2)
        return out

    def create(self, rid, anchor, text, author=None, role="reviewer"):
        """Append a new open comment with one thread entry. Caller holds store.lock."""
        now = time.time()
        role = role if role in ("reviewer", "agent") else "reviewer"
        author = author or role
        anchor = anchor or {}
        anc = {
            "quoted_text": anchor.get("quoted_text", ""),
            "block_num": anchor.get("block_num", ""),
            "start": anchor.get("start"),
            "end": anchor.get("end"),
        }
        # issue #15: content-derived stable block id. Persisted ONLY when present AND selector-safe
        # (same additive-default-safe rule as reviews-meta kind/template), so every other comment's
        # anchor stays byte-identical. A whole-block (empty quoted_text) comment re-anchors by this
        # across a live-reload renumber; absent -> positional block_num fallback, exactly as before.
        bid = anchor.get("bid", "") or ""
        if _BID_RE.fullmatch(bid):
            anc["bid"] = bid
        c = {
            "comment_id": "c" + secrets.token_hex(5),
            "status": "open",
            "anchor": anc,
            "thread": [{"author": author, "role": role, "text": text or "", "ts": now}],
            "created_by": author,
            "created_at": now,
            "resolved_by": None,
            "resolved_at": None,
            "status_history": [{"from": None, "to": "open", "by": author, "ts": now}],
        }
        arr = self.store.read_json(self._path(rid), [])
        arr.append(c)
        self._write(rid, arr)
        return c

    def delete(self, rid, cid):
        """Hard-remove a comment, the junk-cleanup path (was inline in the DELETE arm). Caller holds
        store.lock. Returns True if a comment was removed, False if cid was absent (no write)."""
        arr = self.store.read_json(self._path(rid), [])
        kept = [x for x in arr if x.get("comment_id") != cid]
        if len(kept) == len(arr):
            return False
        self._write(rid, kept)
        return True

    def apply_transition(self, rid, cid, action, by, text=None):
        """The single writer for comment state transitions, shared by the viewer and MCP routes so
        the two can never diverge. Caller holds store.lock.

        Returns (http_code, payload): 200 + the updated comment on success; 409 + {error,status} on
        an illegal transition (resolve a non-open/reopened, reopen a non-resolved); 404 + {error}
        when the comment is missing. thread[] and status_history[] are append-only, never rewritten.
        """
        arr = self.store.read_json(self._path(rid), [])
        c = self._find(arr, cid)
        if c is None:
            return 404, {"error": "no such comment"}
        now = time.time()
        cur = c.get("status")
        if action == "reply":
            # legal in every state (incl. resolved: discussion without un-resolving); status unchanged.
            if not (text and text.strip()):
                return 400, {"error": "reply text required"}
            role = by if by in ("reviewer", "agent") else "reviewer"
            c["thread"].append({"author": role, "role": role, "text": text, "ts": now})
        elif action == "resolve":
            if cur not in ("open", "reopened"):
                return 409, {"error": "comment is not open/reopened", "status": cur}
            # #287 D2: `by` is now plane-derived by the caller (server.py), not hardcoded — a
            # human clicking Resolve must be recorded as the reviewer, never the agent (#187's
            # attribution-truth rule mirrored onto comments). Unrecognized/absent `by` keeps the
            # historical default so every pre-#287 caller (MCP resolve_comment, tests) is
            # unaffected.
            role = by if by in ("reviewer", "agent") else "agent"
            if text:  # optional justification, appended as the final entry before the flip
                c["thread"].append({"author": role, "role": role, "text": text, "ts": now})
            c["status"] = "resolved"
            c["resolved_by"] = role
            c["resolved_at"] = now
            c["status_history"].append({"from": cur, "to": "resolved", "by": role, "ts": now})
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
        self._write(rid, arr)
        return 200, c
