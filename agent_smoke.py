#!/usr/bin/env python3
"""agent_smoke.py — agent-loop render-proof for mdreview's MCP.

Drives `mcp_server.py` over stdio AS AN AGENT WOULD and proves the canonical image-embed loop actually
RENDERS, with zero human curl: create_review -> attach_asset(path=...) -> asset served -> <img>
repointed -> naturalWidth>0. This is the proof the MCP is self-serve (vs an operator attaching by hand).

Two layers:
  (i)  always-on, stdlib-only gate: the asset serves 200 + image/* (urllib), AND the viewer repoints
       the <img> to the served asset URL (headless Chrome --dump-dom + stdlib HTML parse).
  (ii) render proof ("a 200 is not a render"): the <img> actually loaded (naturalWidth>0) AND its src is
       the asset URL — via the repo's Node built-in-`WebSocket` CDP pattern (zero pip). FAIL-LOUD SKIP
       (exit 3) if Chrome OR a WebSocket-capable Node is absent — never a silent pass.

Usage:  MDREVIEW_BASE=http://localhost:8155 python3 agent_smoke.py   (a throwaway container, never :8139)
Exit:   0 all pass; 1 real failure (asset not served / not repointed / not loaded); 3 render half
        skipped (no Chrome/Node) — the stdlib gate (i) still ran and passed.

Stdlib only for the gate; the render half shells out to Node (already the repo's render-evidence
toolchain — sprint-09 render-evidence, sprint-11 close). No bespoke WebSocket client here.
"""
import os
import sys
import json
import base64
import shutil
import subprocess
import tempfile
import urllib.request
from html.parser import HTMLParser

BASE = os.environ.get("MDREVIEW_BASE", "http://localhost:8137").rstrip("/")
HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "mcp_server.py")

# a real 1x1 PNG (the supported direction: a light-background raster); decodes to naturalWidth=1
PIX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

INIT = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
]

_fails = []


def check(label, cond):
    print(("  ok  " if cond else "  FAIL") + " " + label)
    if not cond:
        _fails.append(label)


def drive(messages):
    p = subprocess.run([sys.executable, SERVER],
                       input="".join(json.dumps(m) + "\n" for m in messages),
                       capture_output=True, text=True,
                       env={**os.environ, "MDREVIEW_BASE": BASE}, timeout=60)
    return [json.loads(l) for l in p.stdout.splitlines() if l.strip()]


def call(cid, name, args):
    """One tools/call as an agent would; return (parsed-or-text, isError)."""
    out = drive(INIT + [{"jsonrpc": "2.0", "id": cid, "method": "tools/call",
                         "params": {"name": name, "arguments": args}}])
    res = out[-1].get("result", {})
    txt = res.get("content", [{}])[0].get("text", "")
    try:
        return json.loads(txt), res.get("isError")
    except (ValueError, TypeError):
        return txt, res.get("isError")


def find_chrome():
    for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if os.path.isfile(c) or shutil.which(c):
            return c
    return None


def node_with_websocket():
    """A Node binary that has a global WebSocket (Node >= 21) — required for the CDP check."""
    node = shutil.which("node")
    if not node:
        return None
    try:
        r = subprocess.run([node, "-e", "process.exit(typeof WebSocket==='undefined'?9:0)"],
                           capture_output=True, timeout=10)
        return node if r.returncode == 0 else None
    except Exception:
        return None


class _Imgs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.srcs = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            src = dict(attrs).get("src")
            if src:
                self.srcs.append(src)


# the Node CDP render-check: launch headless Chrome, read #article img naturalWidth + src, print JSON.
# (Repo pattern: Node's built-in WebSocket over CDP, zero installs. URL passed as argv; pick the
# existing type=="page" target from GET /json — /json/new?url= is disabled in new headless.)
_NODE_CDP = r"""
const {spawn}=require('child_process');const http=require('http');
const CHROME=process.argv[2], URL=process.argv[3], PORT=9000+Math.floor(Math.random()*900);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const gj=p=>new Promise((res,rej)=>{http.get('http://localhost:'+PORT+p,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>res(JSON.parse(d)));}).on('error',rej);});
(async()=>{
  const c=spawn(CHROME,['--headless=new','--disable-gpu','--no-sandbox','--hide-scrollbars','--remote-debugging-port='+PORT,URL],{stdio:'ignore'});
  let t;for(let i=0;i<60;i++){try{t=await gj('/json');if(t.find(x=>x.type==='page'))break;}catch(e){}await sleep(150);}
  const pg=(t||[]).find(x=>x.type==='page'); if(!pg){console.error('no page target');c.kill();process.exit(2);}
  const ws=new WebSocket(pg.webSocketDebuggerUrl);let id=0;const pend=new Map();
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id);}});
  await new Promise(r=>ws.addEventListener('open',r));
  const send=(meth,par={})=>new Promise(res=>{const i=++id;pend.set(i,res);ws.send(JSON.stringify({id:i,method:meth,params:par}));});
  const ev=async x=>(await send('Runtime.evaluate',{expression:x,returnByValue:true,awaitPromise:true})).result.result.value;
  await send('Runtime.enable');
  for(let i=0;i<40;i++){if(await ev('document.querySelectorAll("#article img").length')>0)break;await sleep(250);}
  await sleep(1200);
  const out=await ev('JSON.stringify((Array.from(document.querySelectorAll("#article img")).map(i=>({src:i.src,nw:i.naturalWidth}))[0])||{})');
  console.log(out); ws.close(); c.kill(); process.exit(0);
})().catch(e=>{console.error(String(e));process.exit(2);});
"""


def node_render(node, chrome, url):
    """Return {src,nw} from the page's first #article img, or None on any CDP/launch error."""
    f = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False)
    f.write(_NODE_CDP)
    f.close()
    try:
        r = subprocess.run([node, f.name, chrome, url], capture_output=True, text=True, timeout=90)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return None
    finally:
        os.unlink(f.name)


def main():
    print("agent_smoke against MDREVIEW_BASE=%s" % BASE)

    # which wrapper version is this run proving? (local tool, no HTTP)
    info, _ = call(2, "server_info", {})
    ok_info = isinstance(info, dict) and info.get("tool_count") == 17 and info.get("tools_hash")
    check("server_info: 17 tools + tools_hash", bool(ok_info))
    if ok_info:
        print("  ..  proving tools_hash=%s" % info["tools_hash"])

    # 1. create a review whose markdown references an image
    md = "# Agent loop\n\nThe figure renders below.\n\n![plot](/assets/plot.png)\n"
    rv, err = call(3, "create_review", {"markdown": md, "title": "agent_smoke"})
    rid = rv.get("id") if isinstance(rv, dict) else None
    check("create_review -> id", bool(rid) and not err)
    if not rid:
        print("\nFAILED: no review id (is the service up at %s?)" % BASE)
        sys.exit(1)

    # 2. attach via PATH — the branch that tripped the agent; no base64 through context
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(PIX)
    tmp.close()
    at, err = call(4, "attach_asset", {"id": rid, "name": "/assets/plot.png", "path": tmp.name})
    os.unlink(tmp.name)
    stored = at.get("stored") if isinstance(at, dict) else None
    asset_url = at.get("url") if isinstance(at, dict) else None
    check("attach_asset(path=) -> stored + url, isError false", bool(stored and asset_url) and not err)
    if not asset_url:
        call(9, "delete_review", {"id": rid})
        print("\nFAILED: path-attach failed")
        sys.exit(1)

    # 3a. gate (stdlib): the asset is actually served
    try:
        with urllib.request.urlopen(asset_url, timeout=15) as r:
            code, ctype = r.status, r.headers.get("Content-Type", "")
    except Exception as e:
        code, ctype = 0, str(e)
    check("asset served: 200 + image/* (%s %s)" % (code, ctype),
          code == 200 and ctype.startswith("image/"))

    review_url = "%s/review/%s" % (BASE, rid)
    chrome = find_chrome()
    node = node_with_websocket()

    # 3b. gate (stdlib + Chrome): the viewer repoints the <img> to the served asset URL
    if chrome:
        dom = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                              "--virtual-time-budget=3000", "--dump-dom", review_url],
                             capture_output=True, text=True, timeout=60).stdout
        pr = _Imgs()
        pr.feed(dom)
        check("viewer repoints <img> to the asset (--dump-dom)",
              any(stored in s for s in pr.srcs))
    else:
        print("  SKIP  repoint gate — no Chrome")

    # 4. RENDER PROOF (Node-CDP): the <img> actually loaded (naturalWidth>0) AND src is the asset
    skipped = False
    if chrome and node:
        res = node_render(node, chrome, review_url)
        if res is None:
            check("render proof (naturalWidth>0) — CDP/launch error", False)
        else:
            nw, src = res.get("nw", 0), res.get("src", "")
            check("render proof: #article img naturalWidth>0 AND src==asset (nw=%s)" % nw,
                  isinstance(nw, int) and nw > 0 and stored in src)
    else:
        skipped = True
        missing = "Chrome" if not chrome else "WebSocket-capable Node (>=21)"
        print("  SKIP  render proof (naturalWidth) — no %s" % missing)

    # cleanup
    call(9, "delete_review", {"id": rid})

    print()
    if _fails:
        print("FAILED: %d assertion(s): %s" % (len(_fails), "; ".join(_fails)))
        sys.exit(1)
    if skipped:
        print("GATE PASS (asset served + <img> repointed); render half SKIPPED (no Chrome/Node) — exit 3.")
        sys.exit(3)
    print("PASS: agent loop renders — asset 200 image/*, <img> repointed, AND #article img naturalWidth>0.")
    sys.exit(0)


if __name__ == "__main__":
    main()
