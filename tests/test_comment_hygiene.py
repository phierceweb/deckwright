"""A count in a comment is the one fact that rots on a commit touching nothing near it.

Percentages and arithmetic are allowed — `50% shade of FF8040 is 7F4020` is checkable and
does not drift. What rots is an inventory: a count of repo things, or a byte size nobody
will re-measure. If a number is worth stating, either the code holds it as a constant or
`docs/` holds it where a gate already checks it.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

_ROT = re.compile(
    r"""(?<![\w.])(
      \d{1,3},\d{3}                                   # 4,001 · 1,389
    | \d+(\.\d+)?\s?(MB|KB|GB|MiB|KiB|GiB)\b           # 716 KB · 0.9 GB
    | \d+\s+(templates?|exercises?|glyphs?|components?
            |slides?|tests?|commits?|freeforms?|names?)\b
    | \b(eleven|twelve|thirteen|fourteen|eighteen|thousand)\s+
      (templates?|exercises?|glyphs?|components?|slides?|tests?|files?|names?)\b
)""",
    re.X | re.I,
)


def _sources() -> list[pathlib.Path]:
    """Every module this gate reads — except itself.

    This file has to quote the shapes it rejects in order to explain them, so it is the
    one place they may appear. Nothing else is exempt, and nothing else should be.
    """
    return sorted(
        p
        for p in list((ROOT / "src").rglob("*.py")) + list((ROOT / "tests").rglob("*.py"))
        if "__pycache__" not in p.parts and p.name != pathlib.Path(__file__).name
    )


def _prose(path: pathlib.Path) -> list[tuple[int, str]]:
    """Every comment and docstring line, with its line number. Code and strings excluded."""
    text = path.read_text()
    out = [
        (i, line.strip())
        for i, line in enumerate(text.splitlines(), 1)
        if line.strip().startswith("#")
    ]
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                out += [(getattr(node, "lineno", 1), line.strip()) for line in doc.splitlines()]
    return out


def test_there_is_prose_to_check():
    """Without this the parametrization could silently collect nothing."""
    assert sum(len(_prose(p)) for p in _sources()) > 500


@pytest.mark.parametrize("path", _sources(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_comment_states_a_count_that_will_go_stale(path):
    found = [f"line {n}: {line}" for n, line in _prose(path) if _ROT.search(line)]
    assert found == [], (
        f"{path.relative_to(ROOT)} states a count nothing keeps true:\n  "
        + "\n  ".join(found)
        + "\n\nSay what the number means instead ('thousands of names', 'the whole "
        "registry'), or put it where a gate checks it."
    )
