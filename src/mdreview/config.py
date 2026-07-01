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

os.makedirs(DATA_DIR, exist_ok=True)

# Bounded server-side timeout for the /wait long-poll (seconds); a client ?timeout= is capped to it.
WAIT_TIMEOUT_S = float(os.environ.get("MDREVIEW_WAIT_TIMEOUT_S", "25"))
# Lease staleness TTL in SECONDS (agent_status.at is epoch seconds, float, never milliseconds).
# A foreign /handoff {state:working} lease older than this is taken over (MR-055). MIRRORS the
# viewer's STALE_S in web/viewer.html: single source of truth, the two MUST move together (both seconds).
LEASE_TTL_S = float(os.environ.get("MDREVIEW_LEASE_TTL_S", "180"))
RID = r"([A-Za-z0-9]{4,40})"
