"""The theme's own column grid, and the regions a placement may not enter.

Both are read from the live theme: the columns every `at:` resolves against, and the
polygons `conform` derives from a brand template's artwork. A deck showing what an
onboarded template reserves therefore shows what the compiler will actually enforce.
"""

from __future__ import annotations

from pptx.util import Inches

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, RevealItem, component
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.model import Rect
from deckwright.utils.shapes import para, rect as fill_rect, textbox

from deckwright.components._shape import choice, flag, known_fields

_FIELDS = ("show", "reserve", "caption")
_SHOW = ("columns", "rows", "both")
# Fractions of the placement: how much of it the bars occupy, and the caption beneath.
_BARS_FRACTION = 0.62
_CAPTION_H_RUNG = 0.08
# Between the bars and the caption; counted in the height so the two agree.
_CAPTION_GAP = 0.18
# Absorbs the rounding between a column's right edge and the rect's own.
_EDGE_SLACK = 0.005


@component("grid")
def grid(ctx: SlideCtx) -> BodyResult:
    """Draw the grid as bars, overlay any reserved region, and label the measurements."""
    known_fields(ctx, _FIELDS)
    show = choice(ctx, "show", _SHOW, default="columns")
    overlay = flag(ctx, "reserve") if "reserve" in ctx.body else True
    theme_grid = ctx.grid
    rect = ctx.body_rect
    caption_h = ctx.theme.scale.y(_CAPTION_H_RUNG)
    bars_h = max(rect.height * _BARS_FRACTION, 0.0)
    if bars_h <= 0:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'grid'): the placement is "
            f"{rect.height:.2f}in tall, too short to draw a grid in"
        )

    groups: list[list[RevealItem]] = []
    bars: list[RevealItem] = []
    line = ctx.theme.palette.role("line")
    drawn = 0
    if show in ("columns", "both"):
        for index in range(theme_grid.columns):
            left = theme_grid.col_x(index)
            # A placement a reserved region narrowed holds fewer columns than the theme has.
            if left + theme_grid.col_w > rect.left + rect.width + _EDGE_SLACK:
                break
            bar = fill_rect(ctx.slide, left, rect.top, theme_grid.col_w, bars_h, ctx.color("line"))
            ctx.manifest.record(bar)
            ctx.painted.append((Rect(left, rect.top, theme_grid.col_w, bars_h), line))
            bars.append((bar.shape_id, "surface"))
            drawn += 1
    if show in ("rows", "both"):
        rows = ctx.theme.grid.rows
        row_h = bars_h / rows
        for index in range(rows):
            band = Rect(rect.left, rect.top + index * row_h, rect.width, max(row_h - 0.02, 0.01))
            bar = fill_rect(
                ctx.slide, band.left, band.top, band.width, band.height, ctx.color("line")
            )
            ctx.manifest.record(bar)
            ctx.painted.append((band, line))
            bars.append((bar.shape_id, "surface"))
    groups.append(bars)

    reserved = ctx.theme.reserve if overlay else ()
    for region in reserved:
        patch = _polygon(ctx, region)
        # A picture of the region, drawn inside it on purpose.
        ctx.manifest.record(patch, text=region.name, annotation=True)
        groups.append([(patch.shape_id, "surface")])

    text = str(ctx.body.get("caption", "")) or _measurements(ctx, theme_grid, reserved, drawn=drawn)
    frame = textbox(
        ctx.slide, rect.left, rect.top + bars_h + _CAPTION_GAP, ctx.grid.span_w(9), caption_h
    )
    size = ctx.style("caption").size
    ink, paper = ctx.text_ink(
        Rect(rect.left, rect.top + bars_h + _CAPTION_GAP, ctx.grid.span_w(9), caption_h),
        size_pt=size,
        muted=True,
    )
    para(
        frame,
        text,
        size,
        ctx.rgb(ink),
        first=True,
        space_after=0,
        font=ctx.theme.mono,
    )
    ctx.manifest.record(frame._parent, text=text, font_pt=size, fg=ink, bg=paper)
    groups.append([(frame._parent.shape_id, "text")])
    return BodyResult(groups=groups, height=bars_h + _CAPTION_GAP + caption_h)


def _polygon(ctx: SlideCtx, region):
    """The region drawn as its real polygon.

    A bounding box would forbid the usable space above a corner wedge's diagonal.
    """
    scale = ctx.theme.scale
    points = [(Inches(scale.x(x)), Inches(scale.y(y))) for x, y in region.poly]
    builder = ctx.slide.shapes.build_freeform(points[0][0], points[0][1], scale=1.0)
    builder.add_line_segments(points[1:], close=True)
    shape = builder.convert_to_shape()
    shape.fill.solid()
    shape.fill.fore_color.rgb = ctx.color("accent-1")
    shape.fill.transparency = 0.55
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def _measurements(ctx: SlideCtx, theme_grid, reserved, *, drawn: int) -> str:
    """What the theme actually holds, so the label cannot drift from the drawing."""
    parts = [
        f'{theme_grid.columns} columns · {theme_grid.col_w:.3f}" wide '
        f'· {theme_grid.gutter:.3f}" gutter'
    ]
    if drawn and drawn < theme_grid.columns:
        # Never let the picture be quietly partial.
        parts.append(f"{drawn} fit this placement")
    if reserved:
        parts.append("reserved: " + ", ".join(r.name for r in reserved))
    return "   ".join(parts)
