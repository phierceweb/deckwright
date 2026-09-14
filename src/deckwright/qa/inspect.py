"""Shape inventory for a built deck — plain data for the hand-edit workflow."""

from __future__ import annotations

from pathlib import Path
from dataclasses import asdict
from typing import Any

from deckwright.compile.record import Box
from deckwright.errors import SpecError
from deckwright.utils.deck import open_presentation
from deckwright.utils.mce import resolved_shapes


def inspect_deck(deck: str | Path) -> list[dict[str, Any]]:
    """List every slide's shapes with ids, names and boxes, in inches.

    Args:
        deck: Path to a ``.pptx`` file.

    Returns:
        One dict per slide: ``{"index": int, "layout": str, "shapes": [...]}``,
        each shape a ``{"shape_id": int, "name": str, "box": {"x", "y", "w", "h"}}``.

    Raises:
        SpecError: ``deck`` is not a readable ``.pptx``.
    """
    prs = open_presentation(deck, what="deck", error=SpecError)
    slides: list[dict[str, Any]] = []
    for index, slide in enumerate(prs.slides, start=1):
        shapes = [
            {
                "shape_id": shape.shape_id,
                "name": shape.name,
                "box": asdict(Box.from_emu(shape.left, shape.top, shape.width, shape.height)),
            }
            for shape in resolved_shapes(slide.shapes)
        ]
        slides.append({"index": index, "layout": slide.slide_layout.name, "shapes": shapes})
    return slides
