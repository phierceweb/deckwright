"""Which manifest describes a deck: the one beside it, else the one recording its build id."""

from __future__ import annotations

import json
from pathlib import Path

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
            recorded = json.loads(candidate.read_text(encoding="utf-8")).get("build_id")
        except (OSError, json.JSONDecodeError):
            continue
        if recorded == ident[len(BUILD_PREFIX) :]:
            return candidate
    return None
