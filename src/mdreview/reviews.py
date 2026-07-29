"""Review lifecycle + summary/list + history + the document reads the router did inline (MR-084).

ReviewService owns everything review-scoped: meta + the bump timestamps, the comment-aware summary
and the cross-review list, the PUT-source snapshot/overwrite, the history rounds, the /feedback
projection (delegating to CommentService), and review deletion. It takes the single Store plus the
CommentService (summary folds comment counts; feedback projects comments). Mutating methods assume
the caller holds store.lock, exactly as the original free functions did.
"""
import json
import os
import secrets
import shutil
import time

from mdreview.errors import ReviewWriteRejected

# The 409 contract (#288): the payload is the instruction, because the plausible agent reaction to a
# bare 409 is "re-read the token and resend my buffer", which destroys the other writer's edit with
# a 200. Wording pinned by tests/revision_precondition_selfcheck.py; keep it in sync with the
# update_source tool description in src/mcp/tools.py.
STALE_REVISION_MSG = (
    "stale revision: the document changed since you read it. Re-read the source, re-apply your "
    "change onto the new text, and save with the new revision. Never resend a buffered draft "
    "after a 409 - it would silently overwrite the other writer's edit.")


class ReviewService:
    def __init__(self, store, comments):
        self.store = store
        self.comments = comments

    def _path(self, rid, name):
        return os.path.join(self.store.dir(rid), name)

    def exists(self, rid):
        return self.store.exists(rid)

    def meta(self, rid):
        return self.store.read_json(self._path(rid, "meta.json"), {})

    def owner(self, rid):
        """The account (user_id) that owns this review, or "" for a legacy/un-owned review. Distinct
        from agent_status.owner (the handoff lease holder, an opaque session id)."""
        return self.meta(rid).get("owner", "")

    def can_access(self, rid, uid):
        """True iff uid owns rid. Fail CLOSED on a missing owner: a legacy/un-owned review is
        inaccessible once auth is on, until its owner is reconciled through the human-confirm/
        quarantine tool (#112). There is no bulk owner-stamp."""
        o = self.owner(rid)
        return bool(o) and o == uid

    def bump(self, rid, field):
        p = self._path(rid, "meta.json")
        m = self.store.read_json(p, {})
        m[field] = time.time()
        self.store.write_text(p, json.dumps(m))

    def summary(self, rid):
        """meta augmented with note counts, revision, and a derived status.

        Comment-aware: counts fold in comments (each counts toward total; a resolved comment counts
        toward addressed) so the dashboard never shows "0 / awaiting" for a review with open comments.
        A review with no comments derives exactly as before (the comment contribution is zero).
        """
        m = dict(self.meta(rid))
        notes = self.store.read_json(self._path(rid, "notes.json"), [])
        comments = self.comments.list(rid)
        total = len(notes) + len(comments)
        addressed = (sum(1 for n in notes if n.get("addressed"))
                     + sum(1 for c in comments if c.get("status") == "resolved"))
        m["notes_total"] = total
        m["notes_addressed"] = addressed
        m["revision"] = m.get("revision", 0)
        # MR-054: legacy reviews with no turn key read as "reviewer" so the ?turn= filter is
        # filterable, never None/absent (the additive-default-safe rule).
        m["turn"] = m.get("turn", "reviewer")
        if not m.get("feedback_updated") and total == 0:
            m["status"] = "awaiting"
        elif total and addressed == total:
            m["status"] = "resolved"
        else:
            m["status"] = "feedback"
        # #187: a human's manual resolve overrides the derived value, and it is STICKY - a comment
        # arriving afterwards does not silently un-resolve the review (no state flapping under the
        # user). Purely a status flag: nothing else about the review changes. Cleared by the same
        # route, at which point the derived status above takes over again.
        if m.get("resolved_by_human"):
            m["status"] = "resolved"
        return m

    def set_resolved(self, rid, resolved):
        """Set or clear the human's manual resolve (#187). Caller holds store.lock.

        Additive-default-safe like kind/template: the keys are persisted ONLY while set and popped
        on un-resolve, so a review that was never (or is no longer) manually resolved keeps a
        byte-identical meta.json and summary() echoes nothing extra."""
        p = self._path(rid, "meta.json")
        m = self.store.read_json(p, {})
        if resolved:
            m["resolved_by_human"] = True
            m["resolved_at"] = time.time()
        else:
            m.pop("resolved_by_human", None)
            m.pop("resolved_at", None)
        self.store.write_text(p, json.dumps(m))

    def list_reviews(self, uid=None):
        """All review summaries, newest first. When uid is given (hosted multi-user), scope to the
        reviews that user owns; uid=None (local/single-user) returns all, unchanged."""
        out = [self.summary(name) for name in os.listdir(self.store.data_dir)
               if self.store.exists(name) and (uid is None or self.can_access(name, uid))]
        out.sort(key=lambda r: r.get("created", 0), reverse=True)
        return out

    def snapshot_round(self, rid):
        """Archive the current source + feedback as a closed history round; bump revision.

        Called under store.lock before a PUT overwrites source.md, so each agent revision leaves the
        outgoing draft and the feedback it accumulated recoverable.
        """
        d = self.store.dir(rid)
        m = self.store.read_json(os.path.join(d, "meta.json"), {})
        n = int(m.get("revision", 0) or 0)
        rd = os.path.join(d, "history", "round-%d" % n)
        os.makedirs(rd, exist_ok=True)
        for fn in ("source.md", "feedback.md", "notes.json"):
            src = os.path.join(d, fn)
            if os.path.isfile(src):
                shutil.copy(src, os.path.join(rd, fn))
        # round.json records only the round index + timestamp (MR-064 / #18). The per-round note
        # count was removed: it was computed from the retired notes.json (always 0 in the comments
        # era, the viewer authors comments since MR-036, and comments.json is not per-round
        # snapshotted, so a truthful count is unrecoverable). The comment-aware per-review
        # notes_total in summary() is a different field and is unaffected.
        self.store.write_text(os.path.join(rd, "round.json"), json.dumps({
            "round": n, "ts": time.time(),
        }))
        m["revision"] = n + 1
        self.store.write_text(os.path.join(d, "meta.json"), json.dumps(m))

    def create(self, markdown, title, project="", source_path="", session="", owner="",
               kind="markdown", template=""):
        rid = secrets.token_hex(5)
        d = self.store.dir(rid)
        os.makedirs(d, exist_ok=True)
        now = time.time()
        self.store.write_text(os.path.join(d, "source.md"), markdown or "")
        self.store.write_text(os.path.join(d, "feedback.md"), "")
        self.store.write_text(os.path.join(d, "notes.json"), "[]")
        meta = {
            "id": rid, "title": title or "", "created": now,
            "source_updated": now,
            # #288: the edit-precondition token, explicit from birth. Only summary() defaulted it
            # before; the new read paths (ETag on GET /source, GET /status) need it present so a
            # fresh review issues token 0 rather than an absent key.
            "revision": 0,
            "project": project or "", "source_path": source_path or "",
            "session": session or "",
            "owner": owner or "",       # account that owns it (hosted multi-user); "" for local
        }
        # kind is persisted ONLY when non-default: summary() echoes meta unwhitelisted, so a
        # default "markdown" key would leak into every read response and break the flag-off
        # byte-identical contract (MR-093; readers use meta.get("kind", "markdown")).
        if kind and kind != "markdown":
            meta["kind"] = kind
        # template persisted ONLY when set (same additive-default-safe rule as kind), so a markdown
        # review's meta stays byte-identical. The worker reads meta.template to apply companion files.
        if template:
            meta["template"] = template
        self.store.write_text(os.path.join(d, "meta.json"), json.dumps(meta))
        return rid

    def read_source(self, rid):
        return self.store.read_text(self._path(rid, "source.md"))

    def put_source(self, rid, markdown, expected_revision=None):
        """Snapshot the outgoing round, overwrite source.md, bump source_updated. Caller holds
        store.lock.

        expected_revision (#288) is the optimistic-concurrency precondition: when given, the write
        proceeds only if it equals the CURRENT revision (the monotonic counter snapshot_round owns;
        never source_updated, whose wall-clock values can collide). Compared here, under the
        caller-held store.lock and BEFORE the snapshot, so a stale write changes nothing at all.
        None = unconditional, exactly the pre-#288 behavior."""
        if expected_revision is not None:
            current = int(self.meta(rid).get("revision", 0) or 0)
            if int(expected_revision) != current:
                raise ReviewWriteRejected(
                    STALE_REVISION_MSG, status=409,
                    payload={"error": STALE_REVISION_MSG,
                             "expected_revision": int(expected_revision),
                             "current_revision": current})
        self.snapshot_round(rid)
        self.store.write_text(self._path(rid, "source.md"), markdown)
        self.bump(rid, "source_updated")

    def feedback(self, rid):
        """meta + feedback.md + a union of on-disk notes and a read-time projection of comments, so
        an agent's get_feedback still returns the human's live input. notes.json is never rewritten.
        """
        out = dict(self.meta(rid))
        out["markdown"] = self.store.read_text(self._path(rid, "feedback.md"))
        out["notes"] = (self.store.read_json(self._path(rid, "notes.json"), [])
                        + [self.comments.as_note(c) for c in self.comments.list(rid)])
        return out

    def delete(self, rid):
        shutil.rmtree(self.store.dir(rid), ignore_errors=True)

    def history(self, rid):
        hd = os.path.join(self.store.dir(rid), "history")
        rounds = []
        if os.path.isdir(hd):
            for name in os.listdir(hd):
                rj = self.store.read_json(os.path.join(hd, name, "round.json"), None)
                if rj:
                    rounds.append(rj)
        rounds.sort(key=lambda r: r.get("round", 0), reverse=True)
        return rounds

    def history_round(self, rid, n):
        """One past round (source + feedback + notes), or None if the round is missing."""
        rd = os.path.join(self.store.dir(rid), "history", "round-%s" % n)
        if not os.path.isfile(os.path.join(rd, "round.json")):
            return None
        out = dict(self.store.read_json(os.path.join(rd, "round.json"), {}))
        out["source"] = self.store.read_text(os.path.join(rd, "source.md"))
        out["feedback"] = self.store.read_text(os.path.join(rd, "feedback.md"))
        out["notes"] = self.store.read_json(os.path.join(rd, "notes.json"), [])
        return out
