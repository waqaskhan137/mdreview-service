"""Environment-derived configuration, read once at import. No behaviour, just values.

Extracted verbatim from app.py (MR-080). The only change is WEB_DIR's anchor depth: living at
src/mdreview/config.py it walks up three dirs (config.py -> mdreview -> src -> repo root) to reach
/web, where the relocated frontend lives.
"""
import os

# ponytail: repo-root anchor; MDREVIEW_WEB_DIR overrides in container/tests.
# src/mdreview/config.py -> up 3 (config -> mdreview -> src -> repo root), then /web/app.
WEB_DIR = os.environ.get("MDREVIEW_WEB_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web", "app")
DATA_DIR = os.environ.get("MDREVIEW_DATA", "/data")
PORT = int(os.environ.get("PORT", "8080"))
PUBLIC_BASE = os.environ.get("MDREVIEW_PUBLIC_BASE", "").rstrip("/")
# App-mode = the packaged local .app (set by the macOS launcher). Enables the dashboard "Quit"
# control + POST /api/app/quit. OFF for the shared/Docker service so a browser can't shut it down.
APP_MODE = bool(os.environ.get("MDREVIEW_APP_MODE"))

# --- Phase 1 multi-user auth (hosted). OFF by default so local/dev stays open + single-user. ---
# When ON, every request must resolve to a user: browser via a trusted proxy header, agent via a
# per-user Bearer token. See server.H._principal.
REQUIRE_AUTH = os.environ.get("MDREVIEW_REQUIRE_AUTH", "").lower() in ("1", "true", "yes")
# Shared secret proving a request came THROUGH nginx (the cookie/browser plane). nginx sets the
# X-Mdreview-Proxy header to this value; the app trusts the vouched identity header only on a match.
PROXY_SECRET = os.environ.get("MDREVIEW_PROXY_SECRET", "")
# HMAC pepper for API-token digests (env only, never in the data volume), so a users.json leak alone
# cannot forge a token.
TOKEN_PEPPER = os.environ.get("MDREVIEW_TOKEN_PEPPER", "")

# Fail CLOSED: hmac.compare_digest("", "") returns True, so an empty PROXY_SECRET would trust any
# client-supplied identity header (impersonation), and an empty pepper would make token digests
# forgeable. If auth is required, refuse to boot rather than run wide open. A non-empty default flag
# is not a non-empty secret.
if REQUIRE_AUTH and not (PROXY_SECRET and TOKEN_PEPPER):
    raise SystemExit(
        "MDREVIEW_REQUIRE_AUTH is on but MDREVIEW_PROXY_SECRET and/or MDREVIEW_TOKEN_PEPPER is unset")

os.makedirs(DATA_DIR, exist_ok=True)

# Bounded server-side timeout for the /wait long-poll (seconds); a client ?timeout= is capped to it.
WAIT_TIMEOUT_S = float(os.environ.get("MDREVIEW_WAIT_TIMEOUT_S", "25"))
# Lease staleness TTL in SECONDS (agent_status.at is epoch seconds, float, never milliseconds).
# A foreign /handoff {state:working} lease older than this is taken over (MR-055). MIRRORS the
# viewer's STALE_S in web/viewer.html: single source of truth, the two MUST move together (both seconds).
LEASE_TTL_S = float(os.environ.get("MDREVIEW_LEASE_TTL_S", "180"))
RID = r"([A-Za-z0-9]{4,40})"
