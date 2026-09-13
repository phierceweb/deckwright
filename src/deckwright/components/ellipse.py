"""A disc: a badge, a dot or a step number.

The diameter comes from the placement's short side. ``align``/``anchor`` move the disc
inside its placement rather than moving type — the shape *is* the content here.
"""

from __future__ import annotations

from pptx.util import Inches

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, component
from deckwright.layouts.registry import Disc, SlideCtx
from deckwright.utils.shapes import ALIGN, ANCHOR, para
from deckwright.utils.text import LINE_HEIGHT, estimate_caveat, wrapped_lines

from deckwright.components._shape import (
    anchored,
    fraction,
    known_fields,
    oval,
    pair_named,
    shadow,
    visible_edge,
)

_FIELDS = ("pair", "label", "rung", "size", "shadow")
_PAIR_DEFAULT = "accent-1"
_RUNG_DEFAULT = "caption"
# A label sits inside a circle, so its measure is the inscribed square's side, not
# the diameter.
_INSCRIBED = 0.7071


@component("ellipse")
def ellipse(ctx: SlideCtx) -> BodyResult:
    """Draw a disc in the background of a declared pair, with an optional label on it."""
    known_fields(ctx, _FIELDS)
    pair = pair_named(ctx, _PAIR_DEFAULT)
    rect = ctx.body_rect
    size = fraction(
        ctx, "size", default=1.0, what="the diameter as a fraction of the placement's short side"
    )
    diameter = min(rect.width, rect.height) * size
    disc = anchored(rect, diameter, diameter, align=ctx.align, anchor=ctx.anchor)
    shape = oval(ctx, disc, ctx.rgb(pair.bg), line=visible_edge(ctx, pair))
    label = None if ctx.body.get("label") is None else str(ctx.body["label"])
    if label:
        _label(ctx, shape, label, diameter=diameter, ink=pair.fg)
    shadow(ctx, shape)
    style = ctx.style(str(ctx.body.get("rung", _RUNG_DEFAULT)))
    ctx.manifest.record(
        shape,
        text=label,
        font_pt=style.size if label else None,
        fg=pair.fg if label else None,
        bg=pair.bg,
        fill=pair.bg if str(ctx.body.get("pair", _PAIR_DEFAULT)) != "surface" else None,
        ground=ctx.behind(disc, ink=pair.bg),
    )
    ctx.painted.append((disc, Disc(pair.bg)))
    return BodyResult(groups=[[(shape.shape_id, "surface")]], height=diameter)


def _label(ctx: SlideCtx, shape, text: str, *, diameter: float, ink: str) -> None:
    """Centre a label in the disc, refusing a disc the label does not fit inside."""
    style = ctx.style(str(ctx.body.get("rung", _RUNG_DEFAULT)))
    measure = diameter * _INSCRIBED
    line_h = style.size * LINE_HEIGHT / 72
    if (
        line_h > measure
        or wrapped_lines(text, width_in=measure, size_pt=style.size, face=ctx.theme.font_for(style))
        > 1
    ):
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'ellipse'): the label {text!r} needs "
            f"more than the {measure:.2f}in across the middle of a {diameter:.2f}in disc "
            f"at {style.size:.1f}pt — grow the placement, raise 'size', or name a "
            f"smaller 'rung'{estimate_caveat(ctx.theme.font_for(style))}"
        )
    tf = shape.text_frame
    tf.word_wrap = False
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0)
    tf.vertical_anchor = ANCHOR["middle"]
    para(
        tf,
        text,
        style.size,
        ctx.rgb(ink),
        bold=style.bold,
        italic=style.italic,
        align=ALIGN["center"],
        first=True,
        space_after=0,
        font=ctx.theme.font_for(style),
    )
