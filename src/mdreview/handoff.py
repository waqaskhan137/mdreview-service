"""Turn baton + agent lease: the /handoff read-decide-write (MR-085).

HandoffService owns the guarded turn/owner state machine. turn/owner are control state both the
viewer and an agent write concurrently, so apply() reads the CURRENT turn/owner, decides, and writes
once, under the caller's store.lock. Body forms dispatch in a PINNED order so an ambiguous body
(e.g. {to:reviewer,by:reviewer,state:done}) is deterministic: reclaim, hand-back, flip, lease;
anything else is a 400. On any successful write it notifies parked /wait waiters under that same
lock (MR-054), so the write and the wake are atomic and no flip is missed.
"""
import json
import os
import time


class HandoffService:
    def __init__(self, store, lease_ttl_s):
        self.store = store
        self.lease_ttl_s = lease_ttl_s

    def apply(self, rid, body):
        """Apply one handoff body to the review's meta.json. Caller holds store.lock.

        Returns None on success (and notifies waiters), or (http_code, payload) on an error (409 a
        held lease, 400 an unrecognized body).
        """
        to, by, state = body.get("to"), body.get("by"), body.get("state")
        p = os.path.join(self.store.dir(rid), "meta.json")
        err = None
        mt = self.store.read_json(p, {})
        now = time.time()
        if to == "reviewer" and by == "reviewer":
            # reclaim: force the turn back regardless of state (leave agent_status so the banner can
            # still read a stale state if it wants).
            mt["turn"] = "reviewer"
            mt["turn_updated"] = now
        elif to == "reviewer" and state in ("done", "blocked"):
            # hand-back: the agent returns the turn with its state + message.
            prev = mt.get("agent_status") or {}
            mt["turn"] = "reviewer"
            mt["agent_status"] = {"state": state, "message": body.get("message", ""),
                                  "owner": body.get("owner", prev.get("owner", "")), "at": now}
            mt["turn_updated"] = now
        elif to == "agent":
            # flip: idempotent. Bump turn_updated only on an actual reviewer->agent flip.
            if mt.get("turn", "reviewer") != "agent":
                mt["turn"] = "agent"
                mt["agent_status"] = None          # parked, not yet claimed
                mt["handoff"] = {"by": "reviewer", "at": now}
                mt["turn_updated"] = now
        elif state == "working":
            # lease claim/renew/takeover. turn_updated is NOT bumped (no flip).
            # Decision table (cur = existing lease owner; turn = mt["turn"]):
            #   cur unset/"" .......................... grant  (normal claim)
            #   cur == owner .......................... grant  (normal renew)
            #   foreign + fresh (now-at <= TTL) ....... 409    (live owner; never preempt)
            #   foreign + stale + turn == "agent" ..... grant  (MR-055 takeover; dead session)
            #   foreign + stale + turn != "agent" ..... 409    (already reclaimed by human)
            # The normal unset/equal-owner path grants regardless of turn; only the STALENESS grant is
            # gated on turn == "agent". turn is read and agent_status is written under the SAME lock as
            # the reclaim arm, so there is no TOCTOU vs a concurrent reclaim (the reclaim arm forces
            # turn="reviewer" but leaves agent_status, so a lease can be both stale AND already
            # reclaimed, and this re-check rejects that takeover).
            owner = body.get("owner", "")
            cur = mt.get("agent_status") or {}
            cur_owner = cur.get("owner")
            stale = (now - (cur.get("at") or 0)) > self.lease_ttl_s
            if cur_owner in (None, "", owner):
                grant = True
            elif stale and mt.get("turn") == "agent":
                grant = True            # stale foreign lease + turn still ours: take it over
            else:
                grant = False           # fresh foreign lease, or stale-but-already-reclaimed
            if grant:
                mt["agent_status"] = {"state": "working", "message": body.get("message", ""),
                                      "owner": owner, "at": now}
            else:
                err = (409, {"error": "lease held", "owner": cur_owner})
        else:
            err = (400, {"error": "unrecognized handoff body"})
        if err is None:
            self.store.write_text(p, json.dumps(mt))
            # MR-054: wake parked /wait waiters under the lock, so the write and the wake are atomic
            # and no flip is missed. notify on any successful write; the /wait predicate
            # (turn_updated > since), not this method, decides who actually returns.
            self.store.notify_all()
        return err
