"""Entry point for the HOSTED build: `python -m mdreview.hosted`.

This module IS the build-time tier selector (custody Decision 1). The hosted Docker image sets this
as its CMD; the local/slim image keeps `python -m mdreview`. There is no code path here that can
serve with the ownership check off: build_hosted selects the owner-only policy unconditionally and
refuses to boot without the hosted secrets.
"""
from mdreview.config import DATA_DIR, PORT
from mdreview.server import H, MdreviewServer
from mdreview.store import Store
from mdreview.hosted.compose import build_hosted


def main():
    app = build_hosted(Store(DATA_DIR))
    print("mdreview-service HOSTED (fail-closed identity core) listening on :%d  data=%s"
          % (PORT, DATA_DIR), flush=True)
    MdreviewServer(("0.0.0.0", PORT), H, app).serve_forever()


if __name__ == "__main__":
    main()
