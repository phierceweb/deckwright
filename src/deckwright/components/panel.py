"""A filled block, sized by its placement and coloured by a declared palette pair.

It carries no text of its own — a chrome line naming the same ``pair:`` supplies that,
and reads on it by construction.
"""

from __future__ import annotations

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, component
from deckwright.layouts.registry import SlideCtx
from deckwright.utils.color import contrast_ratio
from deckwright.utils.shapes import rect as fill_rect, rrect

from deckwright.components._shape import known_fields
from deckwright.components._shared import require_default_align

_FIELDS = ("pair", "radius")
_PAIR_DEFAULT = "surface"
_MAX_RADIUS = 0.5
# Below this ratio against the slide's own paper the fill is invisible, so the block
# is given the theme's rule colour as an edge instead of vanishing.
_MIN_EDGE_RATIO = 1.2


@component("panel")
def panel(ctx: SlideCtx) -> BodyResult:
    """Paint the placement's rectangle in the background of a declared pair."""
    require_default_align(ctx)
    known_fields(ctx, _FIELDS)
    name = str(ctx.body.get("pair", _PAIR_DEFAULT))
    pair = ctx.theme.palette.pair(name)
    radius = _radius(ctx)
    rect = ctx.body_rect
    edge = None if contrast_ratio(pair.bg, ctx.pair.bg) >= _MIN_EDGE_RATIO else ctx.color("line")
    fill = ctx.rgb(pair.bg)
    shape = (
        rrect(
            ctx.slide, rect.left, rect.top, rect.width, rect.height, fill, line=edge, radius=radius
        )
        if radius
        else fill_rect(ctx.slide, rect.left, rect.top, rect.width, rect.height, fill, line=edge)
    )
    ctx.manifest.record(shape)
    # Chrome drawn over this panel reads its fill, not the slide's surface.
    ctx.panels.append((rect, pair.bg))
    return BodyResult(groups=[[shape.shape_id]], height=rect.height)


def _radius(ctx: SlideCtx) -> float:
    raw = ctx.body.get("radius", 0.0)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'panel'): 'radius' must be a number, got {raw!r}"
        ) from None
    if not 0.0 <= value <= _MAX_RADIUS:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'panel'): 'radius' is a fraction of the "
            f"block's short side, 0..{_MAX_RADIUS} ({_MAX_RADIUS} is a stadium); "
            f"got {value}"
        )
    return value
