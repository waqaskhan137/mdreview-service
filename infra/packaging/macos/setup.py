"""py2app build config for mdreview.app (macOS) — P0 freeze spike.

Bundles the stdlib `mdreview` package (from ../../../src) + the `web/app` assets into a
self-contained .app. Build via build.sh, which uses a FRAMEWORK Python (py2app needs one).
"""
import os
import sys

from setuptools import setup

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))      # so py2app can discover the mdreview package

WEB = os.path.join(REPO, "web", "app")


def _tree(dest, src):
    """py2app data_files entries that preserve the web/app directory structure under Resources/."""
    out = []
    for root, _dirs, names in os.walk(src):
        rel = os.path.relpath(root, src)
        d = dest if rel == "." else os.path.join(dest, rel)
        out.append((d, [os.path.join(root, n) for n in names]))
    return out


OPTIONS = {
    "packages": ["mdreview"],
    "plist": {
        "CFBundleName": "mdreview",
        "CFBundleDisplayName": "mdreview",
        "CFBundleIdentifier": "space.waqasrana.mdreview",
        "CFBundleShortVersionString": "0.0.1",
        "CFBundleVersion": "0.0.1",
        "LSUIElement": False,
        "NSHighResolutionCapable": True,
    },
}

setup(
    name="mdreview",
    app=[os.path.join(HERE, "launcher.py")],
    data_files=_tree("web/app", WEB),
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
