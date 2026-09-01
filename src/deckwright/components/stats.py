"""A row of big-number tiles, each with an optional mark, and a caption beneath."""

from __future__ import annotations

from pptx.util import Inches

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, RevealItem, component
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.model import Rect
from deckwright.utils.shapes import ANCHOR, para, rrect, textbox

from deckwright.components._shape import known_fields, known_item_fields
from deckwright.components._shared import (
    coerce_int,
    mark_side,
    place_mark,
    require_list,
)

# Fractions of canvas height, so a tile keeps its proportions on any slide size.
_TILE_H_RUNG = 0.20
_CAPTION_H_RUNG = 0.08
_CAPTION_GAP_RUNG = 0.0133
_MAX_COLUMNS = 4
# The tile's own padding, in inches.
_MARGIN_X = 0.18
_MARGIN_TOP = 0.14


_FIELDS = ("items", "columns", "caption")
_ITEM_FIELDS = frozenset({"value", "label", "icon"})


@component("stats")
def stats(ctx: SlideCtx) -> BodyResult:
    """One tile per item, laid out across the body rect; one reveal group each."""
    known_fields(ctx, _FIELDS)
    items = require_list(ctx, "items")
    rect = ctx.body_rect
    columns = min(coerce_int(ctx, "columns", ctx.body.get("columns"), len(items)), _MAX_COLUMNS)
    columns = max(1, columns)
    gutter = ctx.grid.gutter
    tile_h = ctx.theme.scale.y(_TILE_H_RUNG)
    caption_h = ctx.theme.scale.y(_CAPTION_H_RUNG)
    caption_gap = ctx.theme.scale.y(_CAPTION_GAP_RUNG)
    # A tile carrying a mark is that much taller: the glyph sits above the number
    # rather than beside it, so sizing the tile by the type alone crops one or other.
    marked = any(isinstance(i, dict) and i.get("icon") for i in items)
    mark = mark_side(ctx) if marked else 0.0
    tile_h += mark
    rows = -(-len(items) // columns)
    extent = (rows - 1) * (tile_h + gutter) + tile_h
    if ctx.body.get("caption"):
        extent = rows * (tile_h + gutter) + caption_gap + caption_h
    if extent > rect.height:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'stats'): {len(items)} items in "
            f"{columns} columns need {extent:.2f}in of height but the body rect is "
            f"only {rect.height:.2f}in — split the slide or reduce the items"
        )
    tile_w = (rect.width - gutter * (columns - 1)) / columns
    value_style, label_style = ctx.style("stat"), ctx.style("caption")
    # The tile is its own surface: the ink has to read on the tile, not on the slide.
    fill = ctx.theme.palette.role("line")
    value_ink = ctx.accent_on(fill, size_pt=value_style.size)
    label_ink = ctx.ink_on(fill)
    groups: list[list[RevealItem]] = []

    for index, item in enumerate(items):
        if not isinstance(item, dict) or "value" not in item:
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'stats'): item {index + 1} needs a 'value'"
            )
        known_item_fields(ctx, item, _ITEM_FIELDS, index=index + 1)
        row, col = divmod(index, columns)
        x = rect.left + col * (tile_w + gutter)
        y = rect.top + row * (tile_h + gutter)
        tile = rrect(ctx.slide, x, y, tile_w, tile_h, ctx.rgb(fill), radius=0.06)
        shapes = [tile.shape_id]
        # Painted after the tile, so the mark sits on it rather than under it.
        if item.get("icon"):
            ctx.panels.append((Rect(x, y, tile_w, tile_h), fill))
            shapes.append(
                place_mark(ctx, str(item["icon"]), Rect(x + _MARGIN_X, y + _MARGIN_TOP, mark, mark))
            )
        tf = tile.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(_MARGIN_X)
        tf.margin_top = Inches(_MARGIN_TOP + mark)
        tf.vertical_anchor = ANCHOR["top"]
        para(
            tf,
            str(item["value"]),
            value_style.size,
            ctx.rgb(value_ink),
            bold=True,
            align=ctx.text_align(),
            first=True,
            space_after=0,
            font=ctx.theme.font_for(value_style),
        )
        if item.get("label"):
            para(
                tf,
                str(item["label"]),
                label_style.size,
                ctx.rgb(label_ink),
                align=ctx.text_align(),
                space_after=0,
                font=ctx.theme.font_for(label_style),
            )
        ctx.manifest.record(
            tile,
            lines=[str(item["value"])] + ([str(item["label"])] if item.get("label") else []),
            font_pt=value_style.size,
            line_pt=[value_style.size] + ([label_style.size] if item.get("label") else []),
            # Dominant colour is the value's (it matches font_pt); bg is the tile's own
            # fill, not the page background — that's what the text sits on.
            fg=value_ink,
            bg=fill,
        )
        groups.append(shapes)

    caption = ctx.body.get("caption")
    if caption and groups:
        y = rect.top + rows * (tile_h + gutter) + caption_gap
        tf = textbox(ctx.slide, rect.left, y, rect.width, caption_h)
        caption_style = ctx.style("body")
        para(
            tf,
            str(caption),
            caption_style.size,
            ctx.dim(),
            italic=True,
            align=ctx.text_align(),
            first=True,
            space_after=0,
            font=ctx.theme.font_for(caption_style),
        )
        ctx.manifest.record(tf._parent, text=str(caption), fg=str(ctx.dim()), bg=ctx.pair.bg)
        groups[-1].append(tf._parent.shape_id)

    return BodyResult(groups=groups, height=extent)
