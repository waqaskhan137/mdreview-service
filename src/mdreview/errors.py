"""Core-defined exceptions the request layer catches (MR-102).

Kept in core so an opt-in feature module can raise a subclass and the always-present request handler
can catch the BASE type without importing the module. This is the seam that lets latex_review reject
a write (an unknown template id, or a latex review's source that is not TeX) while core stays free of
any template or LaTeX knowledge and the flag-off import graph is unchanged.

MR-102 shipped this as `ReviewCreateRejected`, and the frozen docs under docs/process/ still name it
that. #188 gave it a second call site on PUT /source, where a create-named exception read as a bug in
itself, so it was renamed. Nothing else changed.
"""


class ReviewWriteRejected(Exception):
    """A write was rejected for a reason the caller should see as a 4xx. Carries the HTTP status and
    an optional structured payload (e.g. the list of valid template ids) that the handler renders."""

    def __init__(self, message, status=400, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}
