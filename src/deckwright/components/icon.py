"""A vector mark, drawn as native geometry and painted from the palette."""

from __future__ import annotations

from deckwright.components._shape import anchored, figure_text, fraction, known_fields
from deckwright.components._shared import mark_colour
from deckwright.icons.draw import place_icon
from deckwright.layouts.components import BodyResult, component
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.model import Rect
from deckwright.utils.a11y import describe

_FIELDS = ("name", "alt", "decorative", "size", "ink")
_SIZE_DEFAULT = 1.0


@component("icon")
def icon(ctx: SlideCtx) -> BodyResult:
    """Draw the named glyph in the placement, painted so it reads on what is behind it."""
    known_fields(ctx, _FIELDS)
    alt, decorative = figure_text(ctx)
    name = str(ctx.body.get("name") or "").strip()
    if not name:
        raise _missing(ctx)
    rect = ctx.body_rect
    size = fraction(
        ctx,
        "size",
        default=_SIZE_DEFAULT,
        what="the glyph's side as a fraction of the placement's short side",
    )
    side = min(rect.width, rect.height) * size
    box = anchored(rect, side, side, align=ctx.align, anchor=ctx.anchor)
    fill = ink_for(ctx, box)
    shape = place_icon(ctx.slide, name, box, fill=fill, theme=ctx.theme)
    describe(shape, alt=alt, decorative=decorative)
    ctx.manifest.record(shape, fg=fill, bg=ctx.behind(box, ink=fill))
    return BodyResult(groups=[[(shape.shape_id, "figure")]], height=side)


def ink_for(ctx: SlideCtx, box: Rect) -> str:
    """The colour a glyph is painted: the role asked for, or one that reads where it lands."""
    named = ctx.body.get("ink")
    if named is not None:
        return ctx.theme.palette.role(str(named))
    return mark_colour(ctx, box)


def _missing(ctx: SlideCtx):
    from deckwright.errors import SpecError
    from deckwright.icons.load import available

    return SpecError(
        f"slide {ctx.spec.index} (component 'icon'): needs a 'name:' saying which glyph "
        f"to draw — one of {len(available()):,} names, catalogued in docs/glyphs.md"
    )
