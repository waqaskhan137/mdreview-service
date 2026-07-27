"""LaTeX content detection, in both directions (MR-100 create guard, #188 write guard).

Pure, stdlib-only. Two predicates that answer opposite questions and therefore want opposite error
biases; do not merge them.

`looks_like_latex` (MR-100) asks "did a remote agent submit a .tex paper as a *markdown* review?" It
gates a REJECTION OF A CREATE, so a false positive refuses a legitimate markdown doc. It stays
narrow: preamble or a `.tex` source_path, nothing more. It only runs when latex mode is enabled and
the caller did NOT pass `kind` explicitly; an explicit `kind="markdown"` is always honored (the
escape hatch for prose that legitimately quotes LaTeX).

`is_tex_source` (#188) asks the reverse: "could this body compile as paper.tex at all?" It gates a
REJECTION OF A WRITE to a review that is ALREADY kind=latex, so a false positive refuses to save a
user's work — the costlier error. It is therefore deliberately WIDER than a preamble test: it also
accepts `\\input`/`\\include`, because `compiler._prepare_job` copies attached assets into the job
dir, so `\\input{preamble}` plus a `preamble.tex` asset is a preamble-less body that really does
compile. Erring toward acceptance there merely preserves today's behavior.

Both share the fence exclusion: a markdown doc quoting `\\documentclass` inside a ``` (or ~~~) fence
must NOT trip either one. Note it does NOT strip inline `code spans`, so prose *about* LaTeX can
still trip `looks_like_latex`; that is a known false positive, tracked separately.

This module is imported by the request layer and by latex_review's write decorator, and is only
*called* under ENABLE_LATEX, so the flag-off import graph is unchanged.
"""
import re

_PREAMBLE_RE = re.compile(r"\\documentclass|\\begin\{document\}")
# `\input foo` (bare, space-delimited) is as valid as `\input{foo}`, hence the [{ ] class.
_INPUT_RE = re.compile(r"\\(?:input|include)\s*[{ ]")
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


def has_preamble(body):
    """True when body carries a document preamble outside any fenced code block."""
    return bool(body and _PREAMBLE_RE.search(_strip_code_fences(body)))


def is_tex_source(body):
    """True when body could compile as paper.tex: a preamble, or an \\input/\\include that can pull
    one in from an attached asset. See the module docstring for why this is wider than has_preamble."""
    return has_preamble(body) or bool(body and _INPUT_RE.search(_strip_code_fences(body)))


def looks_like_latex(source_path, body):
    """True when the create looks like a LaTeX paper submitted as a markdown review."""
    if (source_path or "").strip().lower().endswith(".tex"):
        return True
    return has_preamble(body)


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

    # #188 write guard. is_tex_source accepts everything has_preamble does...
    assert is_tex_source(r"\documentclass{article}") is True
    assert is_tex_source("intro\n\\begin{document}\nbody") is True
    # ...plus the multi-file project that \input's a preamble from an attached asset, which
    # has_preamble alone would reject even though it compiles today.
    assert has_preamble(r"\input{preamble}") is False
    assert is_tex_source(r"\input{preamble}") is True
    assert is_tex_source(r"\include{chapter1}") is True
    assert is_tex_source("\\input preamble\n") is True      # bare form, no braces
    # A markdown body is TeX by neither test — this is the #188 rejection.
    assert is_tex_source("# Reading copy\n\n- a list item\n") is False
    assert is_tex_source("") is False
    assert is_tex_source(None) is False
    # The fence exclusion applies to both, so prose that only QUOTES a preamble is not tex source.
    assert is_tex_source(fenced) is False
    print("latexguard self-check OK")
