#!/usr/bin/env python3
"""latex_recompile_gate_ui_selfcheck.py — #332/#320: a comment-only share grantee gets no Recompile
affordance, end to end (real hosted-tier auth, real browser, real DOM), not just a backend 404.

THE GAP THIS GUARDS: #332 turned Recompile from a failure-gated button into a permanent pill
segment. src/latex_review/module.py's _recompile docstring says auth "mirrors every /api/latex
arm: 401 anon, 404 non-owner" — recompile was ALWAYS owner-only server-side — but before #332 the
button was invisible to everyone except during body.compile-failed, which incidentally hid that a
non-owner reader could see (and click, and get a 404 from) a control that was never theirs. Making
it permanent removes that cover, so #320's existing owner-gate (canEdit, the same one #editbtn
already uses) has to reach this control too, or every comment/view grantee sees a dead affordance
in every state instead of only some.

This drives the HOSTED tier (the local tier has no non-owner concept — can_edit is unconditionally
true there, "owner by construction" per src/mdreview/server.py) with a real magic-link login for a
second user, invites them with a "comment" share right (can_comment true, can_edit false — exactly
the case #320's own docstring names as the one that must NOT see author surfaces), and asserts the
SERVED PAGE, in a real browser with that user's real session cookie, hides #recompilebtn/#cpsep
while leaving #pdfstate (the read surface) visible. The owner, same review, keeps seeing it.

Run: python3 tests/latex_recompile_gate_ui_selfcheck.py     (exit 0 = pass)
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
failed = []


def check(name, cond, detail=""):
    print(("ok   - " if cond else "FAIL - ") + name + (("  (" + str(detail) + ")") if detail and not cond else ""))
    if not cond:
        failed.append(name)


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def req(url, method="GET", data=None, headers=None):
    r = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


data = tempfile.mkdtemp(prefix="mdr332gate-")
port = free_port()
env = dict(os.environ, MDREVIEW_DATA=data, PORT=str(port),
           MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"), MDREVIEW_ENABLE_LATEX="1",
           PYTHONPATH=os.path.join(ROOT, "src"),
           MDREVIEW_REQUIRE_AUTH="1", MDREVIEW_ALLOW_PROXY_PLANE="0", MDREVIEW_PROXY_SECRET="inert",
           MDREVIEW_SESSION_SECRET="test-session-secret", MDREVIEW_TOKEN_PEPPER="test-pepper",
           MDREVIEW_OWNER_EMAIL="owner@example.com", MDREVIEW_ALLOW_STUB_EMAIL="1",
           MDREVIEW_PUBLIC_BASE="https://local.test")
log_path = os.path.join(data, "server.log")
log = open(log_path, "w")
srv = subprocess.Popen([sys.executable, "-m", "mdreview.hosted"], env=env, stdout=log, stderr=log)
base = "http://127.0.0.1:%d" % port
try:
    for _ in range(60):
        try:
            req(base + "/healthz"); break
        except Exception:
            time.sleep(0.25)

    def login(email):
        req(base + "/auth/magic-link", "POST", json.dumps({"email": email}).encode(),
            {"Content-Type": "application/json"})
        time.sleep(0.3)
        with open(log_path) as f:
            toks = re.findall(r"auth/redeem\?token=([A-Za-z0-9._~-]+)", f.read())
        r = urllib.request.Request(base + "/auth/redeem", data=("token=" + toks[-1]).encode(),
                                   headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k): return None
        opener = urllib.request.build_opener(NoRedirect)
        try:
            resp = opener.open(r, timeout=15)
        except urllib.error.HTTPError as e:
            resp = e
        cookie = resp.headers.get("Set-Cookie", "").split(";")[0]
        _, _, raw = req(base + "/auth/session", headers={"Cookie": cookie})
        return cookie, json.loads(raw).get("csrf", "")

    owner_cookie, owner_csrf = login("owner@example.com")
    _, _, raw = req(base + "/api/reviews", "POST",
                    json.dumps({"title": "gate", "kind": "latex", "source": "x"}).encode(),
                    {"Content-Type": "application/json", "Cookie": owner_cookie, "X-CSRF-Token": owner_csrf})
    rid = json.loads(raw)["id"]

    grantee_cookie, grantee_csrf = login("grantee@example.com")
    # Invite as "comment" — can_comment true, can_edit false. Exactly the case #320 names.
    code, _, raw = req(base + "/api/reviews/%s/shares" % rid, "POST",
                       json.dumps({"email": "grantee@example.com", "right": "comment"}).encode(),
                       {"Content-Type": "application/json", "Cookie": owner_cookie, "X-CSRF-Token": owner_csrf})
    check("setup: owner invited grantee@example.com as a comment grantee", code in (200, 201), (code, raw))

    # Confirm the SERVER's own can_edit value for each session before trusting the frontend to
    # read it correctly — if this were wrong the DOM check below would be validating nothing.
    _, _, raw = req(base + "/api/reviews/%s/status" % rid, headers={"Cookie": owner_cookie})
    check("owner: /status can_edit is true", json.loads(raw).get("can_edit") is True, raw)
    _, _, raw = req(base + "/api/reviews/%s/status" % rid, headers={"Cookie": grantee_cookie})
    grantee_status = json.loads(raw)
    check("grantee: /status can_edit is false (comment right, not owner)", grantee_status.get("can_edit") is False, raw)
    check("grantee: /status can_comment is true (so this is #320's exact case, not view-only)",
          grantee_status.get("can_comment") is not False, raw)

    # Real browser, real cookie (cdp-shot.mjs's --cookie step, built for exactly this — see its
    # own header comment), real DOM read.
    grantee_cookie_nv = grantee_cookie.split(";")[0]
    owner_cookie_nv = owner_cookie.split(";")[0]
    # Both the IDL `.hidden` property AND computed display: `.hidden` reflects only the HTML
    # ATTRIBUTE, unaffected by CSS, so a mutation that drops the "#recompilebtn[hidden]{display:
    # none}" override (the exact "authored display beats the UA's [hidden]" trap this file
    # documents for .difftoggle/.srcscroll elsewhere) leaves `.hidden` true while the element still
    # RENDERS via its own authored display:inline-flex. Asserting only the IDL property missed
    # this in the first pass — caught by mutation-testing that CSS line out, which this rewrite
    # fixes. Both must agree for the gate to be real.
    eval_expr = ("JSON.stringify({recHidden:document.querySelector('#recompilebtn').hidden,"
                 "recDisplay:getComputedStyle(document.querySelector('#recompilebtn')).display,"
                 "sepHidden:document.querySelector('#cpsep').hidden,"
                 "sepDisplay:getComputedStyle(document.querySelector('#cpsep')).display,"
                 "pdfstateVisible:getComputedStyle(document.querySelector('#pdfstate')).display!=='none'})")

    def dom_check(cookie_nv, label):
        out = subprocess.run(
            ["node", os.path.join(ROOT, "scripts", "cdp-shot.mjs"),
             "--cookie", "%s@%s" % (cookie_nv, base),
             "--url", base + "/review/" + rid,
             "--resize", "1500x900", "--wait-for", "#compilepill", "--wait", "600",
             "--eval", eval_expr],
            capture_output=True, text=True, timeout=60)
        # --eval logs `=> ` + JSON.stringify(result). The eval expression itself returns a STRING
        # (its own JSON.stringify), so the logged value is that string re-quoted/escaped by
        # cdp-shot's own JSON.stringify — i.e. a JSON string literal, not a bare object. Parse
        # twice: once to unescape cdp-shot's quoting, once for the actual payload.
        m = re.search(r"=> (\".*\")\s*$", out.stdout, re.MULTILINE)
        if not m:
            check(label + ": cdp-shot produced a measurement", False, out.stdout[-800:] + out.stderr[-400:])
            return None
        return json.loads(json.loads(m.group(1)))

    grantee_dom = dom_check(grantee_cookie_nv, "grantee")
    if grantee_dom:
        check("grantee: #recompilebtn is hidden (no author surface for a comment-only reader)",
              grantee_dom["recHidden"] is True, grantee_dom)
        check("grantee: #recompilebtn ACTUALLY RENDERS none, not just the attribute (the [hidden]-vs-authored-display trap)",
              grantee_dom["recDisplay"] == "none", grantee_dom)
        check("grantee: #cpsep (the divider) is hidden alongside it, not a dangling line",
              grantee_dom["sepHidden"] is True and grantee_dom["sepDisplay"] == "none", grantee_dom)
        check("grantee: #pdfstate (the READ surface) stays visible — this is a gate, not a blanket hide",
              grantee_dom["pdfstateVisible"] is True, grantee_dom)

    owner_dom = dom_check(owner_cookie_nv, "owner")
    if owner_dom:
        check("owner: #recompilebtn is NOT hidden (the gate does not also hide it from the owner)",
              owner_dom["recHidden"] is False, owner_dom)
finally:
    srv.terminate(); shutil.rmtree(data, ignore_errors=True)

print("\n" + ("%d case(s) failed" % len(failed) if failed else "all recompile-gate UI cases pass"))
sys.exit(1 if failed else 0)
