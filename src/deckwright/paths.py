"""What an output directory is allowed to look like, and whose checkout this is.

A built deck's directory shows the deck, its manifest and its render, and nothing else:
every generated intermediate goes one level down, under the dot-prefixed scratch name.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

SCRATCH = ".build"
"""Generated inputs and intermediates, inside whatever directory produced them."""

RENDER = "render"
"""Rasterized slides, the PDF behind them, and the QA report — made to be looked at."""


def render_dir(pptx: str | Path) -> Path:
    """Where one deck's renders go: ``render/<stem>/`` beside it.

    Per deck, not shared: a version series in one directory otherwise overwrites the
    previous deck's ``slide-N.jpg`` while its own PDF sits deck-named beside them —
    stale images that read as current.
    """
    deck = Path(pptx)
    return deck.parent / RENDER / deck.stem


def scratch(outdir: str | Path) -> Path:
    """The scratch directory for ``outdir``, created."""
    path = Path(outdir) / SCRATCH
    path.mkdir(parents=True, exist_ok=True)
    return path


def in_checkout() -> bool:
    """Whether the working directory is deckwright's *own* source checkout.

    A bare ``pyproject.toml`` is any Python project, so testing for one made deckwright
    treat a user's repo as its own and write into it.
    """
    pyproject = Path("pyproject.toml")
    if not pyproject.is_file():
        return False
    try:
        with pyproject.open("rb") as fh:
            return tomllib.load(fh).get("project", {}).get("name") == "deckwright"
    except (OSError, tomllib.TOMLDecodeError):
        return False
