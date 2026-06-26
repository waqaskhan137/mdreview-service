#!/usr/bin/env python3
"""Thin entry point for the mdreview watcher — the implementation lives in the `watcher` package.

Kept at the src/ root so the documented `python3 src/watch.py` invocation keeps working unchanged;
running this script puts src/ on sys.path, so `import watcher` resolves to the sibling package.
Canonical form: `python -m watcher`.
"""
from watcher.__main__ import main

if __name__ == "__main__":
    main()
