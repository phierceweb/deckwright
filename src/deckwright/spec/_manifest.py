"""What the manifest beside a deck says that the file cannot."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from deckwright.spec._recover import Box
from deckwright.utils.provenance import find_manifest


@dataclass(frozen=True)
class Built:
    """What the manifest beside a deck says that the file cannot: each placement's rectangle,
    each slide's section, and the theme it was built with."""

    boxes: dict[int, dict[str, Box]] = field(default_factory=dict)
    sections: dict[int, str] = field(default_factory=dict)
    presets: dict[int, str] = field(default_factory=dict)  # each slide's `chrome:` preset
    bleeds: dict[int, frozenset[str]] = field(default_factory=dict)  # origins that bleed
    theme: str | None = None


def from_manifest(deck: Path, prs) -> Built:
    """``Built`` from the manifest that describes ``deck``, found beside it or by its build
    id; a copy with no manifest is read from its shapes alone."""
    found = find_manifest(deck, str(prs.core_properties.identifier or ""))
    if found is None:
        return Built()
    try:
        data = json.loads(found.read_text(encoding="utf-8"))
        width, height = float(data["canvas"]["w"]), float(data["canvas"]["h"])
        slides = data.get("slides") or []
        return Built(
            boxes={
                int(slide["index"]): {
                    str(p["origin"]): (
                        p["box"]["x"] / width,
                        p["box"]["y"] / height,
                        p["box"]["w"] / width,
                        p["box"]["h"] / height,
                    )
                    for p in slide.get("placements") or []
                }
                for slide in slides
            },
            sections={int(s["index"]): str(s["section"]) for s in slides if s.get("section")},
            presets={int(s["index"]): str(s["chrome"]) for s in slides if s.get("chrome")},
            bleeds={
                int(s["index"]): frozenset(
                    str(p["origin"]) for p in s.get("placements") or [] if p.get("bleed")
                )
                for s in slides
            },
            theme=str(data["theme"]) if data.get("theme") else None,
        )
    except (OSError, ValueError, KeyError, TypeError):
        return Built()
