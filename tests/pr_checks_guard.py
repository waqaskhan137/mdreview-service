#!/usr/bin/env python3
"""The invariants pr-checks.yml's safety argument rests on.

`pr-checks` is the gate that replaced the owner's merge gate, so it runs on `pull_request` —
where the checked-out ref is the PR head, i.e. unreviewed code. That is only safe while the
workflow cannot publish anything. If it ever gains `packages: write` or an image push, every PR
would publish its head as `:dev` and the staging timer would adopt it within 15 minutes.

The job KEY is also load-bearing: a required status check matches the job name, not the workflow
name, so renaming the job silently breaks enforcement (and, if the check is required, hangs every
PR at "Expected" with no override path at 0 approvals).

ponytail: no yaml dep in this repo, and regex over the non-comment lines is enough to catch the
four ways this file can go wrong. Swap to a parser if the workflow ever grows real structure.
"""
import pathlib
import re
import sys

WF = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows" / "pr-checks.yml"


def code_lines(text):
    """The file minus comment lines — prose about Docker is not a Docker step."""
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def main():
    if not WF.exists():
        print(f"FAIL missing {WF}")
        return 1

    raw = WF.read_text()
    body = code_lines(raw)
    fails = []

    if not re.search(r"^  pr-checks:$", body, re.M):
        fails.append("job key must be exactly `pr-checks` — it is the status-check context name")

    if not re.search(r"^on:\n  pull_request:\n    branches: \[dev\]$", body, re.M):
        fails.append("trigger must be `pull_request: branches: [dev]`")

    if re.search(r"^\s*packages:", body, re.M):
        fails.append("pr-checks must never hold a `packages:` scope — it runs on unreviewed PR heads")

    if not re.search(r"^permissions:\n  contents: read$", body, re.M):
        fails.append("declare `permissions: contents: read` in the file, not via a repo default")

    for forbidden in ("push: true", "docker login", "docker build", "build-push-action"):
        if forbidden in body:
            fails.append(f"pr-checks must not publish an image (found {forbidden!r})")

    for step in ("tests/hosted_boot_smoke.py", "tests/custody_regression_smoke.py"):
        if step not in body:
            fails.append(f"pr-checks must run {step}")
        elif not (WF.parent.parent.parent / step).exists():
            fails.append(f"{step} is referenced but does not exist")

    for f in fails:
        print(f"FAIL {f}")
    if fails:
        return 1

    print("  ok   job key is `pr-checks` (the required-status-check context name)")
    print("  ok   triggers only on pull_request into dev")
    print("  ok   no packages scope, no image push — cannot publish from a PR head")
    print("  ok   permissions: contents: read declared in-file")
    print("  ok   both smokes referenced and present")
    print("pr-checks guard: all clear")
    return 0


if __name__ == "__main__":
    sys.exit(main())
