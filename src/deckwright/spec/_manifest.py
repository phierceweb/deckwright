"""What the manifest beside a deck says that the file cannot."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from deckwright.spec._recover import Box
from deckwright.spec._snapshot import Kept, kept_placements
from deckwright.spec.matching import drawn, matched_slides, recorded
from deckwright.utils.provenance import find_manifest, read_manifest

_T = TypeVar("_T")


@dataclass(frozen=True)
class Built:
    """What the manifest beside a deck says that the file cannot: each placement's rectangle,
    each slide's section, and the theme it was built with. Keyed by where each slide now sits
    in the deck, from 1."""

    boxes: dict[int, dict[str, Box]] = field(default_factory=dict)
    sections: dict[int, str] = field(default_factory=dict)
    presets: dict[int, str] = field(default_factory=dict)  # each slide's `chrome:` preset
    bleeds: dict[int, frozenset[str]] = field(default_factory=dict)  # origins that bleed
    theme: str | None = None
    kept: dict[int, dict[str, Kept]] = field(default_factory=dict)  # by slide, then origin


def from_manifest(deck: Path, prs) -> Built:
    """``Built`` from the manifest that describes ``deck``, found beside it or by its build
    id; a copy with no manifest is read from its shapes alone."""
    identifier = str(prs.core_properties.identifier or "")
    found = find_manifest(deck, identifier)
    if found is None:
        return Built()
    try:
        data = read_manifest(found, records=False)
        width, height = float(data["canvas"]["w"]), float(data["canvas"]["h"])
        if not (0 < width < math.inf and 0 < height < math.inf):
            return Built()
        slides = data.get("slides") or []
        boxes = {
            slide["index"]: {
                str(p["origin"]): (
                    p["box"]["x"] / width,
                    p["box"]["y"] / height,
                    p["box"]["w"] / width,
                    p["box"]["h"] / height,
                )
                for p in slide.get("placements") or []
            }
            for slide in slides
        }
        sections = {s["index"]: str(s["section"]) for s in slides if s.get("section")}
        presets = {s["index"]: str(s["chrome"]) for s in slides if s.get("chrome")}
        bleeds = {
            s["index"]: frozenset(
                str(p["origin"]) for p in s.get("placements") or [] if p.get("bleed")
            )
            for s in slides
        }
    except (ValueError, KeyError, TypeError):  # SpecError among them
        return Built()
    deck_slides = [drawn(slide) for slide in prs.slides]
    matched = matched_slides(deck_slides, {s["index"]: recorded(s.get("shapes")) for s in slides})
    return Built(
        boxes=_moved(boxes, matched),
        sections=_moved(sections, matched),
        presets=_moved(presets, matched),
        bleeds=_moved(bleeds, matched),
        theme=str(data["theme"]) if data.get("theme") else None,
        kept=kept_placements(found, data, identifier, matched),
    )


def _moved(by_index: dict[int, _T], matched: dict[int, int]) -> dict[int, _T]:
    return {position: by_index[index] for position, index in matched.items() if index in by_index}
