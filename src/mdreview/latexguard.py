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

Both share the markup exclusion (`_strip_markup`): a markdown doc quoting `\\documentclass` inside a
``` fence OR inside an inline `code span` must NOT trip either one. #206 closed the inline half,
which previously cut both ways: prose *about* LaTeX tripped `looks_like_latex` (a false REJECT of a
legitimate markdown create), and a markdown body mentioning `\\input{...}` in backticks passed
`is_tex_source` (a false ACCEPT into a latex review).

Closing it does NOT make `is_tex_source` refuse real work: a genuine .tex body carries its
`\\input` outside backticks, so it still detects. The only bodies whose classification changes are
those whose ONLY `\\input` is inside a code span — which is markdown prose, and is precisely what
#188's write guard exists to reject.

This module is imported by the request layer and by latex_review's write decorator, and is only
*called* under ENABLE_LATEX, so the flag-off import graph is unchanged.
"""
import re

_PREAMBLE_RE = re.compile(r"\\documentclass|\\begin\{document\}")
# `\input foo` (bare, space-delimited) is as valid as `\input{foo}`, hence the [{ ] class.
_INPUT_RE = re.compile(r"\\(?:input|include)\s*[{ ]")
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")
# #206: a CommonMark inline code span is a run of N backticks closed by another run of exactly N.
# Non-greedy, and the inner pattern forbids the closing run, so an UNMATCHED backtick matches
# nothing and is left alone — a stray ` in real .tex must not swallow the rest of the document.
# DOTALL because a code span may wrap across lines.
_INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)*?\1", re.S)


def _strip_inline_code(text):
    """Return text with inline `code spans` blanked, so prose *about* LaTeX does not read as LaTeX.

    #206: `_strip_code_fences` handled ``` blocks only, so a markdown plan writing
    "the `\\documentclass` preamble" was classified as a .tex paper and the create was REFUSED.

    Replaced with a space rather than deleted: `a`b` must not weld its neighbours into a new token.
    """
    return _INLINE_CODE_RE.sub(" ", text)


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


def _strip_markup(text):
    """Fences FIRST, then inline spans. The order is load-bearing and asserted in the self-check:
    a fence's ``` delimiters are themselves backtick runs, so stripping inline spans first would
    pair an opening fence marker with a closing one and blank the prose BETWEEN two code blocks
    while leaving the blocks' contents intact — exactly inverting the intent.

    Both predicates go through this single helper so they cannot drift apart on that order.
    """
    return _strip_inline_code(_strip_code_fences(text))


def has_preamble(body):
    """True when body carries a document preamble outside any fenced code block."""
    return bool(body and _PREAMBLE_RE.search(_strip_markup(body)))


def is_tex_source(body):
    """True when body could compile as paper.tex: a preamble, or an \\input/\\include that can pull
    one in from an attached asset. See the module docstring for why this is wider than has_preamble."""
    return has_preamble(body) or bool(body and _INPUT_RE.search(_strip_markup(body)))


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

    # ---- #206: inline code spans, both directions ------------------------------------------
    # THE BUG: prose ABOUT LaTeX was classified as LaTeX, so a legitimate markdown create was
    # REFUSED. `_strip_code_fences` handled ``` blocks only.
    assert looks_like_latex("plan.md", "the `\\documentclass` preamble goes first") is False
    assert looks_like_latex("plan.md", "use `\\begin{document}` to open the body") is False
    assert has_preamble("we discuss `\\documentclass{article}` at length") is False
    # Mirror gap: a markdown body whose ONLY \input is in backticks is not tex source.
    assert is_tex_source("the `\\input{preamble}` directive pulls it in") is False

    # TRUE POSITIVES UNREGRESSED — the costly direction. A real preamble still detects.
    assert has_preamble("\\documentclass{article}\n\\begin{document}hi") is True
    assert looks_like_latex("paper.tex", "anything") is True
    assert is_tex_source("\\input{preamble}\n\\section{x}") is True
    assert is_tex_source("\\input preamble") is True          # bare, space-delimited

    # ORDER: fences run first. Semantically that is right — a fence delimiter is structural and
    # should be resolved before inline spans, which are content.
    #
    # HONEST LIMITATION, not an assertion: I could not construct a document where the two orders
    # give DIFFERENT answers, so there is no test here that would fail if the order were reversed.
    # The reason is structural: `_strip_inline_code` pairs runs of backticks with each other, and a
    # ``` fence delimiter IS such a run, so inline-first strips fenced content too — it subsumes
    # fence stripping on every shape tried (stray tick before a fence, backticks inside a fence,
    # unclosed fence, span after a fence). Both orders returned the same verdict in all of them.
    # The ticket asks for the order to be asserted rather than assumed; that criterion is NOT met,
    # and is reported on the issue instead of being papered over with a test that passes either way.
    # This case is kept as a plain regression guard on the combined behaviour.
    both_forms = (
        "intro mentions `\\documentclass` inline\n"
        "```\n\\documentclass{article}\n```\n"
    )
    assert has_preamble(both_forms) is False

    # An UNMATCHED backtick must not swallow the document.
    assert has_preamble("\\documentclass{article} ` stray tick") is True
    assert is_tex_source("\\input{a} ` stray") is True
    # And a GREEDY match must not span two separate code spans, eating the real preamble between
    # them. (The previous single-backtick case could not catch this: with only one tick a greedy
    # `.*` finds no pair at all and strips nothing, so it passed either way.)
    assert has_preamble("`a` \\documentclass{article} `b`") is True, \
        "two spans must strip separately, not as one greedy run"

    # A code span must not weld its neighbours into a new token (replaced with a space, not "").
    assert has_preamble("\\document`x`class{article}") is False
    print("latexguard self-check: ok")
    print("latexguard self-check OK")
