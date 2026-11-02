"""A divider line, spanning its placement and positioned by the placement's own keys.

The weight is a multiple of the theme's line weight, so a hairline stays a hairline on a
canvas of any size.
"""

from __future__ import annotations

from pptx.enum.shapes import MSO_CONNECTOR

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, component
from deckwright.layouts.registry import SlideCtx

from deckwright.components._shape import choice, known_fields, line_shape

_FIELDS = ("orient", "color", "weight")
_ORIENTS = ("horizontal", "vertical")
_COLOR_DEFAULT = "line"


@component("rule")
def rule(ctx: SlideCtx) -> BodyResult:
    """Draw a rule across the placement, along the axis ``orient`` names."""
    known_fields(ctx, _FIELDS)
    orient = choice(ctx, "orient", _ORIENTS, default="horizontal")
    rect = ctx.body_rect
    if orient == "horizontal":
        _refuse(ctx, "align", ctx.align, "left", orient=orient, spans="width")
        y = {"top": rect.top, "middle": rect.top + rect.height / 2, "bottom": rect.bottom}[
            ctx.anchor
        ]
        start, end = (rect.left, y), (rect.right, y)
    else:
        _refuse(ctx, "anchor", ctx.anchor, "top", orient=orient, spans="height")
        x = {"left": rect.left, "center": rect.left + rect.width / 2, "right": rect.right}[
            ctx.align
        ]
        start, end = (x, rect.top), (x, rect.bottom)

    line = line_shape(ctx, MSO_CONNECTOR.STRAIGHT, start, end, default_role=_COLOR_DEFAULT)
    ctx.manifest.record(line)
    return BodyResult(groups=[[(line.shape_id, "line")]], height=0.0)


def _refuse(ctx: SlideCtx, key: str, value: str, default: str, *, orient: str, spans: str) -> None:
    """A rule spans one axis outright, so the key that would move it along that axis
    has nothing to act on."""
    if value == default:
        return
    other = "anchor" if key == "align" else "align"
    raise LayoutError(
        f"slide {ctx.spec.index} (component 'rule'): {key} {value!r} has nothing to act "
        f"on — a {orient} rule spans its placement's whole {spans}; use {other} to move "
        f"it across, or narrow the placement"
    )
