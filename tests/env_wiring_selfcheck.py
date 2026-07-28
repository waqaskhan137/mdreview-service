#!/usr/bin/env python3
"""env_wiring_selfcheck.py — a documented knob must actually reach the container (#221).

The bug this guards, made and caught inside the #221 run (E4 in the run log):

    infra/deploy/.env.staging.example gained MDREVIEW_SESSION_TTL_S=2592000, and the runbook told
    the operator to append the same line to prod's .env. Neither compose service has an `env_file:`
    directive, so a key in that file is only available for ${...} substitution and NEVER reaches the
    container. Setting it produced no error, no warning, and no effect.

That is the dangerous shape: the operator recreates the container, sees success, and the setting is
silently inert. So the invariant is not "every var the app reads is declared" (most have code
defaults nobody overrides, and an allowlist of those would be noise). It is narrower and sharper:

    if the deploy docs present a key as settable, the compose file must actually pass it through.

Run: python3 tests/env_wiring_selfcheck.py   (exit 0 = wired correctly, exit 1 = a knob is inert)
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "infra" / "deploy"

# A key assignment, optionally commented out (a commented key still advertises the knob).
# Prose mentions like "# MDREVIEW_SESSION_SECRET signs the cookie" do not match: no "=".
KEY_ASSIGNMENT = re.compile(r"^\s*#?\s*(MDREVIEW_[A-Z0-9_]+)\s*=")
# A compose `environment:` entry: `  MDREVIEW_FOO: "..."`.
COMPOSE_ENTRY = re.compile(r"^\s+(MDREVIEW_[A-Z0-9_]+)\s*:")

failed = []


def check(name, cond, detail=""):
    if cond:
        print("ok   - " + name)
    else:
        print("FAIL - " + name + (("  (" + detail + ")") if detail else ""))
        failed.append(name)


def documented_keys(path):
    return {m.group(1) for line in path.read_text().splitlines()
            if (m := KEY_ASSIGNMENT.match(line))}


def compose_keys(path):
    return {m.group(1) for line in path.read_text().splitlines()
            if (m := COMPOSE_ENTRY.match(line))}


def has_env_file(path):
    return any(re.match(r"^\s+env_file\s*:", line) for line in path.read_text().splitlines())


staging_compose = DEPLOY / "docker-compose.staging.yml"
prod_compose = DEPLOY / "docker-compose.prod.yml"
staging_example = DEPLOY / ".env.staging.example"

# 1. Every knob advertised in .env.staging.example reaches the staging container. Secrets included:
#    an undeclared MDREVIEW_SESSION_SECRET would be a boot failure, not a silent one, but the same
#    wiring rule is what makes it work.
if has_env_file(staging_compose):
    check("staging: env_file present, so every .env key reaches the container", True)
else:
    advertised = documented_keys(staging_example)
    declared = compose_keys(staging_compose)
    inert = sorted(advertised - declared)
    check("staging: every key in .env.staging.example is declared in the compose environment block",
          not inert, "inert (set but never reaches the container): " + ", ".join(inert))

# 2. The specific knob #221 exists to deliver, on both tiers. Named explicitly because prod has no
#    committed .env.example for rule 1 to work from.
for label, path in (("staging", staging_compose), ("prod", prod_compose)):
    check(label + ": MDREVIEW_SESSION_TTL_S is declared, so the session lifetime is settable",
          has_env_file(path) or "MDREVIEW_SESSION_TTL_S" in compose_keys(path),
          "a 12h session cannot be raised without editing code")

print("\n" + (str(len(failed)) + " check(s) failed" if failed else "env wiring ok"))
sys.exit(1 if failed else 0)
