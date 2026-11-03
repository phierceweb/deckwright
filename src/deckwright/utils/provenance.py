"""Which manifest describes a deck: the one beside it, else the one recording its build id."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deckwright.errors import SpecError

# What a built deck carries in `dc:identifier`, ahead of its build id.
BUILD_PREFIX = "deckwright:"


def find_manifest(deck: Path, identifier: str | None) -> Path | None:
    """The sibling manifest, else the one beside ``deck`` whose build id ``identifier`` names."""
    sibling = deck.with_suffix(".manifest.json")
    if sibling.is_file():
        return sibling
    ident = identifier or ""
    if not ident.startswith(BUILD_PREFIX):
        return None
    for candidate in sorted(deck.parent.glob("*.manifest.json")):
        try:
            recorded = read_manifest(candidate).get("build_id")
        except SpecError:
            continue
        if recorded == ident[len(BUILD_PREFIX) :]:
            return candidate
    return None


def read_manifest(path: Path) -> dict[str, Any]:
    """The build manifest at ``path``: a JSON object whose slides, if any, carry their numbers.

    Raises:
        SpecError: it cannot be read, is not a JSON object, or does not number its slides.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise _unreadable(path, f"{type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise _unreadable(path, f"it holds a JSON {type(data).__name__}, not an object")
    if "slides" not in data:
        return data
    slides = data["slides"]
    if not isinstance(slides, list) or not all(isinstance(s, dict) for s in slides):
        raise _unreadable(path, "'slides' is not a list of slide records")
    for slide in slides:
        index = slide.get("index")
        if isinstance(index, bool) or not isinstance(index, int) or index < 1:
            raise _unreadable(path, f"a slide's index is {index!r}, not a slide number")
    return data


def _unreadable(path: Path, why: str) -> SpecError:
    return SpecError(
        f"{path.name} is not a build manifest deckwright can read ({why}) — build the spec "
        f"again with --out elsewhere and pass the manifest it writes with --manifest"
    )
