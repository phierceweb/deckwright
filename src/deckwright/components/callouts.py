"""A mark beside a heading and a line of body copy, one row per item.

The marker is an accent dot unless the item names an ``icon:``, in which case
it is that glyph — the rail is the same either way, so a list can mix them.
"""

from __future__ import annotations

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, RevealItem, component
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.model import Rect
from deckwright.utils.shapes import ANCHOR, rrect, textbox

from deckwright.components._shape import known_fields, known_item_fields
from deckwright.components.card import copy_height
from deckwright.components._shared import (
    HEAD_SPACE_AFTER_PT,
    LINE_HEIGHT,
    body,
    head,
    mark_side,
    place_mark,
    require_list,
)

_DOT = 0.17
_TEXT_INDENT = 0.42
# Leading between rows, in body line-heights. Short lists drift apart if leftover room
# is shared out without a ceiling; past it the block sits at the top of the rect.
_MAX_LEAD = 1.6 * LINE_HEIGHT


def _min_row(ctx: SlideCtx) -> float:
    """A row is never shorter than one heading line plus its space-after."""
    return (LINE_HEIGHT * ctx.style("head").size + HEAD_SPACE_AFTER_PT) / 72


# Matches the band `bullets` reserves, so the two read alike in a split.
_HEADING_H = 0.42

_FIELDS = ("items", "heading")
_ITEM_FIELDS = frozenset({"head", "body", "icon"})


@component("callouts")
def callouts(ctx: SlideCtx) -> BodyResult:
    """One dot-plus-text row per item; one reveal group each.

    Text is set flush against the dot rail, so ``align`` is refused: centred or
    right-set copy would drift away from the marker it belongs to.
    """
    if ctx.align != "left":
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'callouts'): align {ctx.align!r} would "
            f"pull each row's text away from its dot; 'callouts' sets text flush to the "
            f"dot rail"
        )
    known_fields(ctx, _FIELDS)
    items = require_list(ctx, "items")
    rect = ctx.body_rect
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or "head" not in item:
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'callouts'): item {index} needs a 'head'"
            )
        known_item_fields(ctx, item, _ITEM_FIELDS, index=index)

    heading = str(ctx.body.get("heading", "")) or None
    rect = _below_heading(ctx, rect, heading)

    # Each row is as deep as its own copy at its own measure: a dot and a glyph indent
    # differently, so equal lanes would let a long body run into the row beneath it.
    indents = [mark_side(ctx) + ctx.grid.gutter if i.get("icon") else _TEXT_INDENT for i in items]
    heights = [
        max(
            copy_height(
                ctx, width=rect.width - indent, heading=str(i["head"]), copy=str(i.get("body", ""))
            ),
            _min_row(ctx),
        )
        for i, indent in zip(items, indents, strict=True)
    ]
    needed = sum(heights)
    if needed > rect.height:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'callouts'): {len(items)} items need "
            f"{needed:.2f}in of height but the body rect is only {rect.height:.2f}in "
            f"— split the slide or shorten the copy"
        )
    slack = rect.height - needed
    lead = (
        min(slack / (len(items) - 1), _MAX_LEAD * ctx.style("body").size / 72)
        if len(items) > 1
        else 0.0
    )
    groups: list[list[RevealItem]] = []
    if heading is not None:
        groups.append([_heading(ctx, heading, rect.top - _HEADING_H)])
    top = rect.top

    for index, item in enumerate(items):
        indent, frame_h = indents[index], heights[index]
        if item.get("icon"):
            side = mark_side(ctx)
            marker = place_mark(ctx, str(item["icon"]), Rect(rect.left, top, side, side))
            indent = side + ctx.grid.gutter
        else:
            dot = rrect(
                ctx.slide,
                rect.left,
                top + 0.06,
                _DOT,
                _DOT,
                ctx.color("accent-1"),
                radius=0.5,
            )
            ctx.manifest.record(dot)
            marker = dot.shape_id
            indent = _TEXT_INDENT

        tf = textbox(
            ctx.slide,
            rect.left + indent,
            top,
            rect.width - indent,
            frame_h,
            anchor=ANCHOR["top"],
        )
        head(ctx, tf, str(item["head"]), first=True)
        if item.get("body"):
            body(ctx, tf, str(item["body"]))
        ctx.manifest.record(
            tf._parent,
            lines=[str(item["head"])] + ([str(item["body"])] if item.get("body") else []),
            font_pt=ctx.style("head").size,
            line_pt=[ctx.style("head").size]
            + ([ctx.style("body").size] if item.get("body") else []),
            # Two paragraph colours (head ink, body muted); record the head's —
            # it's the dominant, larger-and-bolder run, matching the font_pt above.
            fg=ctx.pair.fg,
            bg=ctx.pair.bg,
        )
        groups.append([marker, tf._parent.shape_id])
        top += frame_h + lead

    return BodyResult(groups=groups, height=needed + lead * (len(items) - 1))


def _below_heading(ctx: SlideCtx, rect: Rect, heading: str | None) -> Rect:
    """The rows' rect, with a band taken off the top when a heading is set."""
    if heading is None:
        return rect
    if rect.height <= _HEADING_H:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'callouts'): a 'heading' needs "
            f"{_HEADING_H:.2f}in and the placement is only {rect.height:.2f}in tall"
        )
    return Rect(rect.left, rect.top + _HEADING_H, rect.width, rect.height - _HEADING_H)


def _heading(ctx: SlideCtx, text: str, top: float) -> int:
    frame = textbox(ctx.slide, ctx.body_rect.left, top, ctx.body_rect.width, _HEADING_H)
    head(ctx, frame, text, first=True)
    ctx.manifest.record(frame._parent, text=text)
    return frame._parent.shape_id
