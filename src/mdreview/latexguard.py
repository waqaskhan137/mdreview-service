"""Creation-time LaTeX-intent detection (MR-100).

A pure, stdlib-only heuristic the POST /api/reviews arm uses to catch LaTeX content that a remote
agent submitted as a default (markdown) review — the silent-acceptance defect where a `.tex` paper
renders as broken markdown and never compiles. The guard only runs when latex mode is enabled and
the caller did NOT pass `kind` explicitly; an explicit `kind="markdown"` is always honored (the
escape hatch for prose that legitimately quotes LaTeX). This module is only *imported* by the
request layer and only *called* under ENABLE_LATEX, so the flag-off import graph is unchanged.

Detection (either signal is sufficient):
  - source_path ends `.tex` (a strong, unambiguous signal), OR
  - the body has a document preamble (`\\documentclass` / `\\begin{document}`) OUTSIDE any fenced
    code block. The fence exclusion is the false-positive guard: a markdown doc quoting
    `\\documentclass` inside a ``` (or ~~~) fence must NOT trip.
"""
import re

_PREAMBLE_RE = re.compile(r"\\documentclass|\\begin\{document\}")
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")


def _strip_code_fences(text):
    """Return text with the contents (and delimiters) of ``` / ~~~ fenced code blocks removed, so a
    preamble match only counts when it appears in real prose. A fence opens on a line whose first
    non-space run is 3+ backticks or tildes and closes on the next line opening with the same
    marker char; an unclosed fence swallows the rest of the document (CommonMark behavior)."""
    out = []
    fence_char = None
    for line in text.splitlines():
        m = _FENCE_RE.match(line.lstrip())
        if fence_char is None:
            if m:
                fence_char = m.group(1)[0]
                continue
            out.append(line)
        elif m and m.group(1)[0] == fence_char:
            fence_char = None
    return "\n".join(out)


def looks_like_latex(source_path, body):
    """True when the create looks like a LaTeX paper submitted as a markdown review."""
    if (source_path or "").strip().lower().endswith(".tex"):
        return True
    if body and _PREAMBLE_RE.search(_strip_code_fences(body)):
        return True
    return False


if __name__ == "__main__":
    # Self-check (MR-100 AC): every detection branch, run with `python3 -m mdreview.latexguard`.
    # A .tex source_path is caught even with a benign body.
    assert looks_like_latex("paper.tex", "") is True
    assert looks_like_latex("REPORT.TEX", "hello") is True
    # A \documentclass / \begin{document} preamble in prose is caught (no source_path).
    assert looks_like_latex("", r"\documentclass[10pt,twocolumn]{article}") is True
    assert looks_like_latex("", "intro\n\\begin{document}\nbody") is True
    # A normal markdown doc is NOT caught...
    assert looks_like_latex("notes.md", "# Title\n\nplain markdown, no latex.") is False
    # ...including one that QUOTES \documentclass inside a fenced code block (the false positive).
    fenced = "# LaTeX tips\n\nUse this preamble:\n\n```latex\n\\documentclass{article}\n\\begin{document}\n```\n\nThat's it."
    assert looks_like_latex("guide.md", fenced) is False
    assert looks_like_latex("", "~~~\n\\documentclass{article}\n~~~") is False
    print("latexguard self-check OK")
