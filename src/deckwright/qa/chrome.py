"""Chrome is drawn last, over every placement: a line or its plate that lands on one hides it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deckwright.compile.record import box_of, owns
from deckwright.errors import SpecError
from deckwright.layouts.chrome import ChromeBand, ChromeField
from deckwright.layouts.chrome_ink import reaches
from deckwright.qa.model import Finding, Severity
from deckwright.qa.walk import all_shapes, slides
from deckwright.theme.model import Rect, Theme
from deckwright.utils.deck import open_presentation
from deckwright.utils.text import LINE_HEIGHT, wrapped_lines

# Placements a chrome line is meant to sit on: a colour field, a photograph it reverses out of.
_BACKDROPS = frozenset({"panel", "image"})
# Shared edges and anti-aliasing are not an overlap.
_SLACK_IN = 0.02
_ANCHORS = {"t": "top", "ctr": "middle", "b": "bottom"}
_ALIGNS = {"l": "left", "ctr": "center", "r": "right"}


def check_chrome_overlap(
    manifest: dict[str, Any], theme: Theme, *, deck: Path | None = None
) -> list[Finding]:
    """A finding per chrome line whose words can land on a placement it was not put there
    to sit on, and per chrome plate that covers any placement at all.

    A line is measured where its words can land, as the build tries its ink — ``deck``
    supplies each boxed line's anchor and alignment, which the manifest does not record.
    """
    findings: list[Finding] = []
    frames = _frames(deck)
    for slide in slides(manifest):
        index = int(slide.get("index", 0))
        chrome = f"s{index}.chrome"
        shapes = all_shapes(slide)
        plates = [
            (str(s["name"])[len(chrome) + 1 :].split(".")[0], box)
            for s in shapes
            if s.get("plate") and owns(chrome, str(s.get("name") or "")) and (box := box_of(s))
        ]
        lines = _lines(shapes, chrome, theme, frames.get(index, {}))
        if not lines and not plates:
            continue
        for placement in slide.get("placements") or []:
            origin, box = str(placement.get("origin") or ""), box_of(placement)
            if box is None:
                continue
            what = f"{origin} ({placement.get('component')})"
            for field, plate in plates:
                if _overlaps(plate, box):
                    findings.append(
                        Finding(
                            slide=index,
                            check="chrome-plate",
                            severity=Severity.WARN,
                            detail=(
                                f"chrome {field!r} needed a plate of the slide's paper, which "
                                f"covers part of {what}; move the placement clear of the line, "
                                f"or name an ink that reads where it lands"
                            ),
                        )
                    )
            if placement.get("component") in _BACKDROPS or _bleeds(origin, shapes):
                continue
            for field, reach in lines.items():
                if _overlaps((reach.left, reach.top, reach.width, reach.height), box):
                    findings.append(
                        Finding(
                            slide=index,
                            check="chrome-overlap",
                            severity=Severity.WARN,
                            detail=(
                                f"chrome {field!r} can be drawn over {what}; give the "
                                f"placement rows below the line, or move the line with "
                                f"chrome: at:"
                            ),
                        )
                    )
    return findings


def _lines(
    shapes: list[dict[str, Any]], chrome: str, theme: Theme, frames: dict[str, Any]
) -> dict[str, Rect]:
    """Where each chrome line's words can land. Lines recorded with one box share a stacked
    frame; a line alone in its box sits at that frame's anchor."""
    boxes: dict[tuple, list[dict[str, Any]]] = {}
    for shape in shapes:
        name, box = str(shape.get("name") or ""), box_of(shape)
        if box and shape.get("text") and not shape.get("plate") and owns(chrome, name):
            boxes.setdefault(box, []).append(shape)
    bands: list[ChromeBand] = []
    faces: dict[str, str | None] = {}
    for (x, y, w, h), records in boxes.items():
        stacked = len(records) > 1
        shared = frames.get(chrome) if stacked else None
        for i, record in enumerate(records):
            field = str(record["name"])[len(chrome) + 1 :] or "chrome"
            size = float(record.get("font_pt") or 0.0) or theme.style("body").size
            faces[field] = theme.font_for(theme.style(field)) if field in theme.ramp else None
            frame = shared if stacked else frames.get(str(record["name"]))
            anchor, align = _set(frame, paragraph=i if stacked else 0)
            depth = (
                wrapped_lines(str(record["text"]), width_in=w, size_pt=size, face=faces[field])
                * size
                * LINE_HEIGHT
                / 72
            )
            bands.append(
                ChromeBand(
                    field,
                    str(record["text"]),
                    size,
                    Rect(x, y, w, depth if stacked else h),
                    ChromeField(align=align, anchor=anchor),
                    stacked,
                )
            )
            if stacked:
                y += depth
    return reaches(tuple(bands), faces)


def _frames(deck: Path | None) -> dict[int, dict[str, Any]]:
    """Each slide's chrome shapes by name, from the saved deck; nothing without one."""
    if deck is None:
        return {}
    try:
        prs = open_presentation(deck, what="deck", error=SpecError)
    except SpecError:
        return {}  # an unreadable package is `package`'s finding, not this one's
    return {
        index: {s.name: s for s in slide.shapes if ".chrome" in (s.name or "")}
        for index, slide in enumerate(prs.slides, start=1)
    }


def _set(frame: Any, *, paragraph: int) -> tuple[str | None, str | None]:
    """A frame's vertical anchor and one paragraph's alignment, as chrome field values."""
    if frame is None or not frame.has_text_frame:
        return None, None
    anchor = _ANCHORS.get(frame.text_frame._txBody.bodyPr.get("anchor", ""))
    paragraphs = frame.text_frame.paragraphs
    p = paragraphs[min(paragraph, len(paragraphs) - 1)]._p
    return anchor, _ALIGNS.get(p.pPr.get("algn", "") if p.pPr is not None else "")


def _bleeds(origin: str, shapes: list[dict[str, Any]]) -> bool:
    return any(s.get("bleed") and owns(origin, str(s.get("name") or "")) for s in shapes)


def _overlaps(a: tuple, b: tuple) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    across = min(ax + aw, bx + bw) - max(ax, bx)
    down = min(ay + ah, by + bh) - max(ay, by)
    return across > _SLACK_IN and down > _SLACK_IN
