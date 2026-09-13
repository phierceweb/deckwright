"""Paragraph writers and coercion helpers shared by the built-in components."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from deckwright.errors import LayoutError
from deckwright.icons.draw import place_icon
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.model import Rect
from deckwright.utils.color import AA_LARGE, contrast_ratio
from deckwright.utils.shapes import para
from deckwright.utils.text import LINE_HEIGHT  # noqa: F401 — re-exported for components

HEAD_SPACE_AFTER_PT = 3
BULLET_SPACE_AFTER_PT = 8


def _part(ctx: SlideCtx) -> str:
    """The primitive a composite is inside, when it is not what the author wrote."""
    return f" ({ctx.part})" if ctx.part else ""


def subcontext(
    ctx: SlideCtx,
    name: str,
    fields: dict[str, Any],
    rect: Rect,
    *,
    align: str | None = None,
    anchor: str | None = None,
    placements: dict[str, Rect] | None = None,
) -> SlideCtx:
    """A context for calling one component from inside another.

    The slide's mutable state is the same object here, so a plate drawn through this seam
    is still what the outer slide's contrast check measures text against.
    """
    return replace(
        ctx,
        # The author wrote the outer component; `name` is the primitive it reaches for,
        # so it rides along as context rather than being reported as their key.
        part=name,
        body=fields,
        rect=rect,
        align=ctx.align if align is None else align,
        anchor=ctx.anchor if anchor is None else anchor,
        placements=ctx.placements if placements is None else placements,
    )


def box_of(shape) -> Rect:
    """A shape's frame in inches."""
    return Rect(*(v / 914400 for v in (shape.left, shape.top, shape.width, shape.height)))


def head(ctx: SlideCtx, tf, text: str, *, first: bool) -> tuple[str, str]:
    """Write a body heading paragraph in the theme's ``head`` style; return its ink and ground."""
    style = ctx.style("head")
    ink, paper = ctx.text_ink(box_of(tf._parent), size_pt=style.size)
    para(
        tf,
        text,
        style.size,
        ctx.rgb(ink),
        bold=style.bold,
        align=ctx.text_align(),
        first=first,
        space_after=HEAD_SPACE_AFTER_PT,
        font=ctx.theme.font_for(style),
    )
    return ink, paper


def body(ctx: SlideCtx, tf, text: str, *, first: bool = False) -> tuple[str, str]:
    """Write a body paragraph in the theme's ``body`` style; return its ink and ground."""
    style = ctx.style("body")
    ink, paper = ctx.text_ink(box_of(tf._parent), size_pt=style.size, muted=True)
    para(
        tf,
        text,
        style.size,
        ctx.rgb(ink),
        align=ctx.text_align(),
        first=first,
        space_after=0,
        font=ctx.theme.font_for(style),
    )
    return ink, paper


def require_default_align(ctx: SlideCtx) -> None:
    """Reject ``align``/``anchor`` on a component that sets no text of its own.

    Silently ignoring them would leave an author staring at a slide that did not
    move, with nothing to read that says why.
    """
    for key, value, default in (("align", ctx.align, "left"), ("anchor", ctx.anchor, "top")):
        if value != default:
            raise LayoutError(
                f"slide {ctx.spec.index} (component {ctx.component!r}{_part(ctx)}): {key} "
                f"{value!r} has nothing to act on — {ctx.component!r} sets no text of "
                f"its own; drop the {key}"
            )


def require_list(ctx: SlideCtx, key: str) -> list:
    """Fetch a required list from the component's mapping, or fail naming the slide."""
    value = ctx.body.get(key)
    if not isinstance(value, list) or not value:
        raise LayoutError(
            f"slide {ctx.spec.index} (component {ctx.component!r}{_part(ctx)}): "
            f"{key!r} must be a non-empty list"
        )
    return value


def coerce_int(ctx: SlideCtx, key: str, value: Any, default: int) -> int:
    """Coerce a component field to ``int``; ``None`` (absent or blank) falls back to ``default``.

    Raises ``LayoutError`` naming the slide, the component and the value, so no bare
    ``ValueError``/``TypeError`` escapes the project's error hierarchy.
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as e:
        raise LayoutError(
            f"slide {ctx.spec.index} (component {ctx.component!r}{_part(ctx)}): "
            f"field {key!r} must be an int, got {value!r}"
        ) from e


def mark_colour(ctx: SlideCtx, box: Rect) -> str:
    """The colour a non-text mark is painted where it lands.

    Every accent is tried in order against WCAG 1.4.11's 3:1, not only the first, then the
    surface's own ink. Where nothing reads across the box the mark gets the same last
    resort a chrome line does: a plate of the slide's own paper.
    """
    palette = ctx.theme.palette
    for name in palette.accents:
        colour = palette.role(name)
        if contrast_ratio(colour, ctx.behind(box, ink=colour)) >= AA_LARGE:
            return colour
    ink, paper = ctx.ink_at(box, preferred=ctx.pair.fg)
    if contrast_ratio(ink, paper) >= AA_LARGE:
        return ink
    plate = ctx.plate(box, within=ctx.body_rect)
    for name in palette.accents:
        colour = palette.role(name)
        if contrast_ratio(colour, plate) >= AA_LARGE:
            return colour
    return ctx.pair.fg


def place_mark(ctx: SlideCtx, name: str, box: Rect) -> int:
    """Draw the glyph ``name`` filling ``box``, painted so it reads there.

    Returns:
        The new shape's id, for the caller's reveal group.
    """
    fill = mark_colour(ctx, box)
    shape = place_icon(ctx.slide, name, box, fill=fill, theme=ctx.theme)
    ctx.manifest.record(shape, fg=fill, bg=ctx.behind(box, ink=fill))
    return shape.shape_id


def mark_side(ctx: SlideCtx, lines: float = 1.0) -> float:
    """A mark's side in inches: ``lines`` heading line-heights.

    Off the type ramp rather than a fixed measure, so a mark keeps its relationship
    to the words beside it on any canvas.
    """
    return ctx.style("head").size * LINE_HEIGHT / 72 * lines
