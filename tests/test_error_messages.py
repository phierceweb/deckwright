"""Every error message must survive the console it is printed on: `pf_core.cli.run_cli` prints
through a rich `Console`, so an unescaped `[x, y]` is *dropped* on its way to the terminal and
`[/]` raises `MarkupError` from inside the error handler. `theme/load.py`'s `{x, y}` is the house
form."""

from __future__ import annotations

import ast
import io
import pathlib
import re

import pytest
from rich.console import Console

SRC = pathlib.Path(__file__).resolve().parents[1] / "src/deckwright"
_BRACKETED = re.compile(r"\[[^\[\]\n]{1,60}\]")


def _survives(fragment: str) -> bool:
    """True when rich prints `fragment` unchanged rather than eating or rejecting it."""
    console = Console(file=io.StringIO(), width=400, no_color=True)
    try:
        console.print(f"x{fragment}x")
    except Exception:
        return False  # MarkupError — it takes the handler down
    return fragment in console.file.getvalue()


def _message_literals() -> list[tuple[str, str]]:
    """Every literal string inside a `raise`, with where it came from. Literals only: an
    interpolated `{value!r}` is runtime data this cannot see, and a repr carries quotes or digits
    anyway."""
    out = []
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            for sub in ast.walk(node.exc):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    out.append((f"{path.relative_to(SRC.parent.parent)}:{node.lineno}", sub.value))
    return out


def test_no_error_message_is_eaten_by_the_console_it_prints_on():
    literals = _message_literals()
    assert literals, "no raise messages found at all — the sweep is looking at nothing"
    mangled = [
        (where, frag)
        for where, text in literals
        for frag in _BRACKETED.findall(text)
        if not _survives(frag)
    ]
    assert mangled == [], (
        "these fragments never reach the terminal; reword without square brackets:\n"
        + "\n".join(f"  {frag!r} at {where}" for where, frag in mangled)
    )


@pytest.mark.parametrize(
    "fragment,survives",
    [
        ("[x, y]", False),  # the real case: a bare word-comma-word reads as a style
        ("[bold]", False),
        ("[0.5, 0.5]", True),  # digit-led, so rich passes it through
        ("['x', 'y']", True),  # a repr's quotes are not a style name
        ("{x, y}", True),  # the house form
    ],
)
def test_the_sweep_can_tell_the_two_apart(fragment, survives):
    """The negative control. Without it a `_survives` that always returned True would
    leave the gate above green over any message at all."""
    assert _survives(fragment) is survives
