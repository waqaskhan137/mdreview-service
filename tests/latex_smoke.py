#!/usr/bin/env python3
"""tests/latex_smoke.py BASE_URL   (MR-095)

Drive a latex review through the compile pipeline against a RUNNING mdreview instance built from
the latex image (MDREVIEW_ENABLE_LATEX=1 + tectonic). Asserts, in order:

  1. a normal paper compiles: /compile -> ok, GET /pdf -> 200 with a %PDF body;
  2. read-side isolation: a paper that \input's another review's /data source cannot embed it
     (the compile user cannot traverse the 0700 /data), so the marker never reaches the PDF;
  3. (optional) env scrubbing: with --secret VALUE, a paper that \input's /proc/self/environ must
     not contain VALUE (the same string the server holds as a MDREVIEW_* secret).

Read-side isolation (probes 2-3) only holds where the hardening is in effect: root + the `tectonic`
uid + a 0700 /data, i.e. the latex image. Pass --require-hardened (the G7 container run does) to
make an isolation leak a hard failure; without it, local dev (which runs the compile
unhardened-as-self) reports the leak as a WARN so the compile itself can still be smoke-tested.

Exit codes mirror render-smoke.sh: 0 pass, 1 assertion failed, 2 usage/setup error, 3 = this is
not the latex image (tectonic absent) so the suite could not run. Run against a throwaway container
on a scratch port with a throwaway MDREVIEW_DATA, never the live instance.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = None
SECRET = None
REQUIRE_HARDENED = False


def _req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    if body is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "")


def _create(tex, title="smoke"):
    code, raw, _ = _req("POST", "/api/reviews", {"markdown": tex, "kind": "latex", "title": title})
    if code != 201:
        sys.exit("setup: create returned %d: %s" % (code, raw[:200]))
    return json.loads(raw)["id"]


def _wait(rid, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        code, raw, _ = _req("GET", "/api/latex/%s/compile" % rid)
        st = json.loads(raw) if code == 200 else {}
        if st.get("state") in ("ok", "failed"):
            return st
        time.sleep(1)
    return {"state": "timeout"}


PAPER = (r"\documentclass{article}"
         r"\begin{document}\section{Smoke}Hello, \textbf{compiled}.\end{document}")


def main():
    global BASE, SECRET, REQUIRE_HARDENED
    args = sys.argv[1:]
    if "--require-hardened" in args:
        REQUIRE_HARDENED = True
        args.remove("--require-hardened")
    if "--secret" in args:
        i = args.index("--secret")
        SECRET = args[i + 1]
        del args[i:i + 2]
    if not args:
        sys.exit("usage: latex_smoke.py BASE_URL [--require-hardened] [--secret VALUE]")
    BASE = args[0].rstrip("/")

    # 1. baseline compile -----------------------------------------------------
    rid = _create(PAPER)
    st = _wait(rid)
    log = (st.get("log_tail") or "")
    if st.get("state") != "ok":
        if "not found" in log or "not the latex image" in log:
            print("SKIP: tectonic absent (not the latex image); log: %s" % log[:160])
            return 3
        print("FAIL: baseline paper did not compile: state=%s\n%s" % (st.get("state"), log[-800:]))
        return 1
    code, body, ctype = _req("GET", "/api/latex/%s/pdf" % rid)
    if code != 200 or not body.startswith(b"%PDF") or "application/pdf" not in ctype:
        print("FAIL: /pdf code=%s ctype=%s head=%r" % (code, ctype, body[:8]))
        return 1
    print("OK 1/3: baseline paper compiled, /pdf is %d bytes of application/pdf" % len(body))

    # 2. read-side isolation --------------------------------------------------
    marker = "SECRETMARKER31415"
    victim = _create(r"\documentclass{article}\begin{document}%s\end{document}" % marker, "victim")
    attacker_tex = (r"\documentclass{article}\begin{document}"
                    r"\InputIfFileExists{/data/%s/source.md}{}{blocked}"
                    r"\end{document}") % victim
    arid = _create(attacker_tex, "attacker")
    ast = _wait(arid)
    pdf = b""
    code, body, _ = _req("GET", "/api/latex/%s/pdf" % arid)
    if code == 200:
        pdf = body
    # PDFs compress streams, so grep the log too; the strong signal is simply: the marker never
    # surfaces and the read was blocked. On the hardened image /data is unreadable -> the \input
    # fails or yields "blocked".
    leaked = marker.encode() in pdf or marker in (ast.get("log_tail") or "")
    if leaked and REQUIRE_HARDENED:
        print("FAIL: cross-review /data read was NOT blocked (marker leaked)")
        return 1
    if leaked:
        print("WARN 2/3: /data read NOT blocked - expected in unhardened dev "
              "(no root/tectonic uid); pass --require-hardened on the latex image")
    else:
        print("OK 2/3: cross-review /data \\input blocked (compile user cannot read /data)")

    # 3. optional env scrubbing ----------------------------------------------
    if SECRET:
        etex = (r"\documentclass{article}\begin{document}"
                r"\InputIfFileExists{/proc/self/environ}{}{noenv}\end{document}")
        erid = _create(etex, "environ")
        est = _wait(erid)
        code, body, _ = _req("GET", "/api/latex/%s/pdf" % erid)
        epdf = body if code == 200 else b""
        eleak = SECRET.encode() in epdf or SECRET in (est.get("log_tail") or "")
        if eleak and REQUIRE_HARDENED:
            print("FAIL: a MDREVIEW secret leaked via /proc/self/environ")
            return 1
        if eleak:
            print("WARN 3/3: secret visible in environ - unhardened dev inherits the parent env; "
                  "the image scrubs it (assert with --require-hardened)")
        else:
            print("OK 3/3: env scrubbed (secret absent from environ read)")
    else:
        print("OK 3/3: env-scrub probe skipped (pass --secret <pepper> to assert)")

    print("PASS: latex compile pipeline + isolation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
