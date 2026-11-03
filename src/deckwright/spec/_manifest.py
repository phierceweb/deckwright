"""What the manifest beside a deck says that the file cannot."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from deckwright.spec._origin import counted
from deckwright.spec._recover import Box
from deckwright.spec._snapshot import Kept, kept_placements
from deckwright.spec._tree import Unreadable, leaves, slide_box
from deckwright.utils.provenance import find_manifest, read_manifest

_NUMBERED = re.compile(r"s(\d+)\.")
_T = TypeVar("_T")
_EMU_PER_INCH = 914400
_NEAR = 0.01  # inches: the manifest records a box to the thousandth
_NOWHERE = (math.nan,) * 4  # a box that matches none
Drawn = dict[str, tuple[tuple[float, ...], str]]  # each shape's box, in inches, and words


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
        data = read_manifest(found)
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
    drawn = [_drawn(slide) for slide in prs.slides]
    matched = matched_slides(drawn, {s["index"]: _recorded(s.get("shapes")) for s in slides})
    return Built(
        boxes=_moved(boxes, matched),
        sections=_moved(sections, matched),
        presets=_moved(presets, matched),
        bleeds=_moved(bleeds, matched),
        theme=str(data["theme"]) if data.get("theme") else None,
        kept=kept_placements(found, data, identifier, matched),
    )


def matched_slides(deck: list[Drawn], built: dict[int, Drawn | None]) -> dict[int, int]:
    """Each deck slide's position, from 1, and the build slide it answers to, by the rules
    ``docs/cli.md`` gives under ``extract``.

    ``deck`` holds each slide's shapes by name with their boxes in inches and their words, in
    deck order; ``built`` the same for each build slide by index, None where its records are
    unreadable.
    """
    numbers = [_numbers(shapes) for shapes in deck]
    out: dict[int, int] = {}
    for position, numbered in enumerate(numbers, start=1):
        if len(numbered) == 1:
            (index,) = numbered
            if index in built and index not in out.values():
                out[position] = index
    for position, shapes in enumerate(deck, start=1):
        recorded = built.get(position)
        if numbers[position - 1] or recorded is None or _numbers(recorded):
            continue
        morphs = _morphs(recorded)
        if _same(_morphs(shapes), morphs) if morphs else not shapes:
            out[position] = position
    return out


def _numbers(shapes: Drawn) -> set[int]:
    return {int(found[1]) for found in map(_NUMBERED.match, shapes) if found}


def _morphs(shapes: Drawn) -> Drawn:
    """The morph placements' shapes, by a name counted ``#k``: a table's cells are recorded as
    parts of its one shape."""
    return {
        name: shape for name, shape in shapes.items() if name.startswith("m.") and counted(name)[1]
    }


def _same(drawn: Drawn, recorded: Drawn) -> bool:
    """Whether two sets of shapes carry the same names, each drawn where the other is and
    holding the same words."""
    return drawn.keys() == recorded.keys() and all(
        drawn[name][1] == recorded[name][1]
        and all(abs(a - b) <= _NEAR for a, b in zip(drawn[name][0], recorded[name][0], strict=True))
        for name in drawn
    )


def _drawn(slide) -> Drawn:
    """A deck slide's shapes, through groups and markup compatibility, by name."""
    out: Drawn = {}
    for shape in leaves(slide.shapes):
        if isinstance(shape, Unreadable):
            continue
        box = slide_box(shape)
        words = _flat(shape.text_frame.text) if shape.has_text_frame else ""
        out[str(shape.name)] = (tuple(v / _EMU_PER_INCH for v in box) if box else _NOWHERE, words)
    return out


def _recorded(records: Any) -> Drawn | None:
    """A build slide's shape records by name, None when they cannot be read as records; a
    slide the build drew nothing on records none."""
    if records is None:
        return {}
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        return None
    out: Drawn = {}
    for record in records:
        box = record.get("box")
        try:
            where = tuple(float(box[key]) for key in "xywh")
        except (KeyError, TypeError, ValueError):
            where = _NOWHERE
        out[str(record.get("name", ""))] = (where, _flat(str(record.get("text") or "")))
    return out


def _flat(text: str) -> str:
    return " ".join(text.split())


def _moved(by_index: dict[int, _T], matched: dict[int, int]) -> dict[int, _T]:
    return {position: by_index[index] for position, index in matched.items() if index in by_index}
