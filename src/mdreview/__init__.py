"""mdreview-service: a stdlib-only, file-backed markdown review microservice.

Decomposed from the original single-file app.py (sprint-27): config + a Store persistence
seam + per-resource service objects (reviews, comments, assets, handoff) wired by constructor
injection at the server's composition root. Run with `python -m mdreview`.
"""
