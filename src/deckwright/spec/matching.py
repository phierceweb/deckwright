"""Which slide of its build a deck's slide is, read off the shapes it carries.

A shape name survives an edit, so it is the join between deck and manifest. ``extract`` matches
slides with ``matched_slides``, by the rules ``docs/cli.md`` gives under ``extract``; ``diff``
reads the same evidence in ``compile/_slides.py``, by its own.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from pptx.oxml.ns import qn

from deckwright.spec._origin import counted
from deckwright.spec._tree import Unreadable, leaves, slide_box

_NUMBERED = re.compile(r"s(\d+)\.")
_EMU_PER_INCH = 914400
_NEAR = 0.01  # inches: the manifest records a box to the thousandth
_NOWHERE = (math.nan,) * 4  # a box that matches none
Drawn = dict[str, tuple[tuple[float, ...], str]]  # each shape's box, in inches, and words
_FILLS = frozenset(
    qn(f"a:{tag}") for tag in ("solidFill", "gradFill", "blipFill", "pattFill", "grpFill")
)


def placed(slide) -> list[tuple[Any, tuple[int, int, int, int] | None]]:
    """A deck slide's leaf shapes, through groups and markup compatibility, each with its box
    in slide space, EMU; None where it reports no geometry."""
    return [
        (shape, slide_box(shape))
        for shape in leaves(slide.shapes)
        if not isinstance(shape, Unreadable)
    ]


def unplaced(shape) -> bool:
    """A layout placeholder nobody filled: a `p:sp` with no words and nothing of its own that
    paints it — no fill, no outline with a fill, no shape style that references a fill or line.
    Filled with a picture it is a `p:pic`, with a table or chart a `p:graphicFrame`."""
    element = shape._element
    if element.tag != qn("p:sp") or not shape.is_placeholder:
        return False
    if shape.has_text_frame and shape.text_frame.text.strip():
        return False
    return not _painted(element)


def _painted(element) -> bool:
    properties = element.find(qn("p:spPr"))
    for child in properties if properties is not None else ():
        if child.tag in _FILLS or (
            child.tag == qn("a:ln") and any(fill.tag in _FILLS for fill in child)
        ):
            return True
    style = element.find(qn("p:style"))
    return style is not None and any(
        ref.get("idx", "0") != "0"
        for ref in (style.find(qn("a:fillRef")), style.find(qn("a:lnRef")))
        if ref is not None
    )


def drawn(slide, *, unfilled: bool = True) -> Drawn:
    """A deck slide's shapes by name, with their boxes in inches and their words; without
    ``unfilled``, leaving out the layout placeholders nobody filled."""
    out: Drawn = {}
    for shape, box in placed(slide):
        if not unfilled and unplaced(shape):
            continue
        words = _flat(shape.text_frame.text) if shape.has_text_frame else ""
        out[str(shape.name)] = (tuple(v / _EMU_PER_INCH for v in box) if box else _NOWHERE, words)
    return out


def recorded(records: Any) -> Drawn | None:
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


def matched_slides(deck: list[Drawn], built: dict[int, Drawn | None]) -> dict[int, int]:
    """Each deck slide's position, from 1, and the build slide it answers to, by the rules
    ``docs/cli.md`` gives under ``extract``.

    ``deck`` holds each slide's shapes by name with their boxes in inches and their words, in
    deck order; ``built`` the same for each build slide by index, None where its records are
    unreadable.
    """
    found = [numbers(shapes) for shapes in deck]
    out: dict[int, int] = {}
    for position, numbered in enumerate(found, start=1):
        if len(numbered) == 1:
            (index,) = numbered
            if index in built and index not in out.values():
                out[position] = index
    for position, shapes in enumerate(deck, start=1):
        record = built.get(position)
        if found[position - 1] or record is None or numbers(record):
            continue
        held = morphs(record)
        if same(morphs(shapes), held) if held else not shapes:
            out[position] = position
    return out


def numbers(shapes: Drawn) -> set[int]:
    """The slide numbers the shapes are named for."""
    return set(tally(shapes))


def tally(shapes: Drawn) -> Counter[int]:
    """How many of the shapes are named for each slide number."""
    return Counter(int(match[1]) for match in map(_NUMBERED.match, shapes) if match)


def morphs(shapes: Drawn) -> Drawn:
    """The morph placements' shapes, by a name counted ``#k``: a table's cells are recorded as
    parts of its one shape."""
    return {
        name: shape for name, shape in shapes.items() if name.startswith("m.") and counted(name)[1]
    }


def same(drawn: Drawn, recorded: Drawn, *, words: bool = True) -> bool:
    """Whether two sets of shapes carry the same names, each drawn where the other is and, with
    ``words``, holding the same words."""
    return drawn.keys() == recorded.keys() and all(
        (not words or drawn[name][1] == recorded[name][1])
        and all(abs(a - b) <= _NEAR for a, b in zip(drawn[name][0], recorded[name][0], strict=True))
        for name in drawn
    )


def _flat(text: str) -> str:
    return " ".join(text.split())
