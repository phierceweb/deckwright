"""A column of bulleted items under an optional heading."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar

from pptx.util import Inches

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, RevealItem, component
from deckwright.layouts.registry import SlideCtx
from deckwright.spec._scalars import has_text
from deckwright.theme.model import Rect
from deckwright.utils.shapes import para, textbox
from deckwright.utils.text import estimate_caveat, text_em, wrapped_lines

from deckwright.components._shape import known_fields
from deckwright.components._shared import (
    BULLET_SPACE_AFTER_PT,
    LINE_HEIGHT,
    coerce_int,
    require_list,
)

MARKER = "•  "
"""What each bullet is set behind, as run text."""

# Floor for the heading band; a larger type ramp takes its own line height, or the
# heading is drawn through the first bullet.
_HEADING_H = 0.42
_HEADING_GAP = 0.1


_FIELDS = ("items", "columns", "heading")

_T = TypeVar("_T")


def split(items: Sequence[_T], columns: int) -> list[list[_T]]:
    """``items`` across ``columns`` in order, the remainder one each to the leftmost."""
    out: list[list[_T]] = []
    start = 0
    for i in range(columns):
        size = (len(items) + columns - 1 - i) // columns
        out.append(list(items[start : start + size]))
        start += size
    return out


def column_width(width_in: float, columns: int, gutter: float) -> float:
    """One column's width when ``width_in`` is split ``columns`` ways."""
    return (width_in - gutter * (columns - 1)) / columns


def hang(size_pt: float, face: str | None) -> float:
    """How far a bullet's text sits in from its marker, in inches."""
    return text_em(MARKER, face) * size_pt / 72


def item_lines(item: str, *, width_in: float, size_pt: float, face: str | None) -> int:
    """Lines one bullet sets on in a column ``width_in`` wide, beside its marker."""
    return wrapped_lines(item, width_in=width_in - hang(size_pt, face), size_pt=size_pt, face=face)


def stack_height(lines: Sequence[int], *, size_pt: float) -> float:
    """Inches a column takes whose bullets set on ``lines``, the space after each included."""
    return sum(n * size_pt * LINE_HEIGHT + BULLET_SPACE_AFTER_PT for n in lines) / 72


@component("bullets")
def bullets(ctx: SlideCtx) -> BodyResult:
    """Render ``items`` as bullets, split across ``columns``; one reveal group per bullet in one column, per column in several.

    Each item is measured wrapped to its column, so a list that would run past the body
    rect is refused rather than drawn.
    """
    known_fields(ctx, _FIELDS)
    items = [_line(ctx, i, n) for n, i in enumerate(require_list(ctx, "items"), start=1)]
    columns = max(1, min(coerce_int(ctx, "columns", ctx.body.get("columns"), 1), len(items)))
    heading = str(ctx.body["heading"]) if has_text(ctx.body.get("heading")) else None
    rect = ctx.body_rect
    heading_h = max(_HEADING_H, ctx.style("head").size * LINE_HEIGHT / 72)

    gutter = ctx.grid.gutter
    col_w = column_width(rect.width, columns, gutter)
    # One shared top for every column, so a heading over the first cannot push its
    # own bullets out of line with the rest.
    bullets_top = rect.top + (heading_h + _HEADING_GAP if heading else 0.0)
    style = ctx.style("body")
    face = ctx.theme.font_for(style)
    chunks = split(items, columns)
    lines = [
        [item_lines(item, width_in=col_w, size_pt=style.size, face=face) for item in chunk]
        for chunk in chunks
    ]
    heights = [stack_height(counts, size_pt=style.size) for counts in lines]
    needed = max(heights)
    available = rect.bottom - bullets_top
    if needed > available:
        tallest = heights.index(needed)
        _refuse(
            ctx,
            count=len(chunks[tallest]),
            lines=sum(lines[tallest]),
            needed=needed,
            available=available,
            face=face,
        )

    groups: list[list[RevealItem]] = []
    for index, chunk in enumerate(chunks):
        x = rect.left + index * (col_w + gutter)
        ids: list[RevealItem] = []
        if heading and index == 0:
            tf = textbox(ctx.slide, x, rect.top, col_w, heading_h)
            head = ctx.style("head")
            ink, paper = ctx.accent_at(Rect(x, rect.top, col_w, heading_h), size_pt=head.size)
            para(
                tf,
                str(heading),
                head.size,
                ctx.rgb(ink),
                bold=True,
                align=ctx.text_align(),
                first=True,
                space_after=0,
                font=ctx.theme.font_for(head),
            )
            ctx.manifest.record(tf._parent, text=str(heading), font_pt=head.size, fg=ink, bg=paper)
            ids.append((tf._parent.shape_id, "text"))
        tf = textbox(
            ctx.slide, x, bullets_top, col_w, rect.bottom - bullets_top, anchor=ctx.text_anchor()
        )
        ink, paper = ctx.text_ink(
            Rect(x, bullets_top, col_w, rect.bottom - bullets_top), size_pt=style.size
        )
        # A hanging indent, or a wrapped line starts left of its own first line — under
        # the dot instead of under the text.
        indent = Inches(hang(style.size, face))
        for i, item in enumerate(chunk):
            line = para(
                tf,
                f"{MARKER}{item}",
                style.size,
                ctx.rgb(ink),
                align=ctx.text_align(),
                first=(i == 0),
                space_after=BULLET_SPACE_AFTER_PT,
                font=face,
            )
            pPr = line._p.get_or_add_pPr()
            pPr.set("marL", str(int(indent)))
            pPr.set("indent", str(-int(indent)))
        ctx.manifest.record(
            tf._parent,
            lines=[f"{MARKER}{item}" for item in chunk],
            font_pt=style.size,
            line_pt=[style.size] * len(chunk),
            space_after_pt=[BULLET_SPACE_AFTER_PT] * len(chunk),
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


def _refuse(
    ctx: SlideCtx, *, count: int, lines: int, needed: float, available: float, face: str
) -> None:
    where = f"slide {ctx.spec.index} (component 'bullets')"
    if lines == count:
        raise LayoutError(
            f"{where}: {count} bullets in the longest column need {needed:.2f}in but only "
            f"{available:.2f}in is available — split the slide, add a column, or shorten "
            f"the list"
        )
    raise LayoutError(
        f"{where}: {count} bullets wrap to {lines} lines in the tallest column and need "
        f"{needed:.2f}in but only {available:.2f}in is available — split the slide, "
        f"shorten the longest items, or give the placement more room{estimate_caveat(face)}"
    )


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
