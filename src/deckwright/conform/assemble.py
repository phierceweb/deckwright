"""Turn exercises into a deck spec — shared by the conformance run and the demo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from deckwright.conform.media import photographs


def assets(work: Path) -> dict[str, Path]:
    """The files exercises name by placeholder, generated into ``work``.

    Named absolutely: ``document`` and ``image`` resolve against the process directory,
    not the spec's.
    """
    notes = (work / "NOTES.md").resolve()
    notes.write_text("# A heading\n\nA paragraph of body copy.\n", encoding="utf-8")
    return {"notes": notes, **photographs(work)}


def fill(text: str, assets: dict[str, Path]) -> str:
    """Substitute ``{name}`` placeholders with the absolute paths of the run's assets."""
    for name, path in assets.items():
        text = text.replace("{" + name + "}", str(path))
    return text


def spec(slides: list[dict[str, Any]], *, theme: str, out: str) -> str:
    """A deck spec: the deck document, then one document per slide."""
    head = yaml.safe_dump({"theme": theme, "out": out}, sort_keys=False)
    return head + "".join("---\n" + yaml.safe_dump(s, sort_keys=False) for s in slides)
