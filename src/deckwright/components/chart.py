"""Render a chart body as a real OOXML chart."""

from __future__ import annotations

from deckwright.errors import LayoutError
from deckwright.charts.record import record_chart_text
from deckwright.charts._kinds import _BUILDABLE_BY_CATEGORY
from deckwright.charts.model import ChartSpec
from deckwright.charts.native import add_native_chart
from deckwright.layouts.components import BodyResult, component
from deckwright.layouts.registry import SlideCtx
from deckwright.motion import add_chart_build

from deckwright.components._shape import figure_text
from deckwright.components._shared import require_default_align
from deckwright.utils.a11y import describe

_EMU_PER_INCH = 914400

# Slide-level animate -> add_chart_build's 'by'. Any other component asking for
# these is rejected by layouts/compose.py instead.
_CHART_ANIMATIONS = {"by_category": "category", "by_series": "series"}


@component("chart")
def chart(ctx: SlideCtx) -> BodyResult:
    """Place ``ctx.body`` (the slide's ``chart:`` mapping) as a native chart.

    Native charts embed real text a PDF extractor can read, so they're
    recorded ``rendered="native"``.
    """
    require_default_align(ctx)
    spec = ChartSpec.from_body(ctx, ctx.body)
    alt, decorative = figure_text(ctx)
    rect = ctx.body_rect
    animate = ctx.spec.animate

    frame = add_native_chart(ctx, spec, rect)
    describe(frame, alt=alt, decorative=decorative)
    ctx.manifest.record(frame, rendered="native")
    record_chart_text(ctx, frame, spec)
    height = frame.height / _EMU_PER_INCH
    if animate in _CHART_ANIMATIONS:
        by = _CHART_ANIMATIONS[animate]
        if by == "category" and spec.type not in _BUILDABLE_BY_CATEGORY:
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'chart'): a {spec.type!r} chart "
                f"cannot build by category — its categories are vertices of one "
                f"outline, not separate marks, so the build would be a click per "
                f"category with nothing to show. Use 'animate: together', or a kind "
                f"that builds: {', '.join(sorted(_BUILDABLE_BY_CATEGORY))}"
            )
        parts = len(spec.series) if by == "series" else len(spec.categories)
        add_chart_build(
            ctx.slide, frame.shape_id, by=by, parts=parts, kind=ctx.theme.motion.roles["datum"]
        )
        ctx.manifest.record_animation(
            "chart_build", [[frame.shape_id]], clicks=parts + 1 if parts >= 1 else 1
        )
        return BodyResult(groups=[], height=height)
    return BodyResult(groups=[[(frame.shape_id, "datum")]], height=height)
