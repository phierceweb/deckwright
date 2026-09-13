"""A column of bulleted items under an optional heading."""

from __future__ import annotations

from typing import Any

from pptx.util import Inches

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, RevealItem, component
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.model import Rect
from deckwright.utils.shapes import para, textbox
from deckwright.utils.text import text_em

from deckwright.components._shape import known_fields
from deckwright.components._shared import (
    BULLET_SPACE_AFTER_PT,
    LINE_HEIGHT,
    coerce_int,
    require_list,
)

# Floor for the heading band; a larger type ramp takes its own line height, or the
# heading is drawn through the first bullet.
_HEADING_H = 0.42
_HEADING_GAP = 0.1


_FIELDS = ("items", "columns", "heading")


@component("bullets")
def bullets(ctx: SlideCtx) -> BodyResult:
    """Render ``items`` as bullets, split across ``columns``; one reveal group per bullet in one column, per column in several.

    The overflow guard assumes single-line bullets; a long wrapping bullet can still
    overflow past the body rect, which only a later render-based check can measure.
    """
    known_fields(ctx, _FIELDS)
    items = [_line(ctx, i, n) for n, i in enumerate(require_list(ctx, "items"), start=1)]
    columns = max(1, min(coerce_int(ctx, "columns", ctx.body.get("columns"), 1), len(items)))
    heading = ctx.body.get("heading")
    rect = ctx.body_rect
    heading_h = max(_HEADING_H, ctx.style("head").size * LINE_HEIGHT / 72)

    gutter = ctx.grid.gutter
    col_w = (rect.width - gutter * (columns - 1)) / columns
    # One shared top for every column, so a heading over the first cannot push its
    # own bullets out of line with the rest.
    bullets_top = rect.top + (heading_h + _HEADING_GAP if heading else 0.0)
    sizes = [(len(items) + columns - 1 - i) // columns for i in range(columns)]

    per_line = (ctx.style("body").size * LINE_HEIGHT + BULLET_SPACE_AFTER_PT) / 72
    available = rect.bottom - bullets_top
    needed = max(sizes) * per_line
    if needed > available:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'bullets'): {max(sizes)} bullets in the "
            f"longest column need {needed:.2f}in but only {available:.2f}in is available "
            f"— split the slide, add a column, or shorten the list"
        )

    groups: list[list[RevealItem]] = []
    start = 0
    for index, size in enumerate(sizes):
        chunk = items[start : start + size]
        start += size
        x = rect.left + index * (col_w + gutter)
        ids: list[RevealItem] = []
        if heading and index == 0:
            tf = textbox(ctx.slide, x, rect.top, col_w, heading_h)
            style = ctx.style("head")
            ink, paper = ctx.accent_at(Rect(x, rect.top, col_w, heading_h), size_pt=style.size)
            para(
                tf,
                str(heading),
                style.size,
                ctx.rgb(ink),
                bold=True,
                align=ctx.text_align(),
                first=True,
                space_after=0,
                font=ctx.theme.font_for(style),
            )
            ctx.manifest.record(tf._parent, text=str(heading), font_pt=style.size, fg=ink, bg=paper)
            ids.append((tf._parent.shape_id, "text"))
        tf = textbox(
            ctx.slide, x, bullets_top, col_w, rect.bottom - bullets_top, anchor=ctx.text_anchor()
        )
        style = ctx.style("body")
        face = ctx.theme.font_for(style)
        ink, paper = ctx.text_ink(
            Rect(x, bullets_top, col_w, rect.bottom - bullets_top), size_pt=style.size
        )
        # A hanging indent, or a wrapped line starts left of its own first line — under
        # the dot instead of under the text.
        hang = Inches(text_em("•  ", face) * style.size / 72)
        for i, item in enumerate(chunk):
            line = para(
                tf,
                f"•  {item}",
                style.size,
                ctx.rgb(ink),
                align=ctx.text_align(),
                first=(i == 0),
                space_after=BULLET_SPACE_AFTER_PT,
                font=face,
            )
            pPr = line._p.get_or_add_pPr()
            pPr.set("marL", str(int(hang)))
            pPr.set("indent", str(-int(hang)))
        ctx.manifest.record(
            tf._parent,
            lines=[f"•  {item}" for item in chunk],
            font_pt=style.size,
            fg=ink,
            bg=paper,
        )
        if columns == 1:
            # One text box would be one click; its paragraphs are the beats a list stages.
            spid = tf._parent.shape_id
            groups.append([*ids, (spid, "text", 0)])
            groups.extend([[(spid, "text", i)] for i in range(1, len(chunk))])
            continue
        ids.append((tf._parent.shape_id, "text"))
        groups.append(ids)

    return BodyResult(groups=groups, height=needed + (bullets_top - rect.top))


def _line(ctx: SlideCtx, value: Any, position: int) -> str:
    """One bullet's text, refusing anything that would render as a repr.

    A YAML flow mapping breaks on an unquoted comma or colon, so `- {a: b, c: d}`
    where a string was meant arrives here as a dict. `str()` would set the literal
    `{'a': 'b'}` on the slide and report nothing.
    """
    if isinstance(value, (dict, list)):
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'bullets'): item {position} is a "
            f"{type(value).__name__}, not a line of text — a bullet holding a comma or "
            f"a colon needs quoting, or YAML reads it as a mapping"
        )
    return str(value)
