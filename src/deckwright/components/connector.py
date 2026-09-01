"""A line joining two placements, or two points on the canvas.

The line attaches to the facing edge of each end, so moving a placement moves the join.
It draws *between* rectangles rather than inside its own, so its placement needs
``bleed: true`` whenever the line crosses the space the two ends occupy.
"""

from __future__ import annotations

from math import hypot

from pptx.enum.shapes import MSO_CONNECTOR
from pptx.util import Inches, Pt

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, component
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.model import Rect

from deckwright.components._shape import (
    ARROWS,
    arrow,
    canvas_point,
    choice,
    known_fields,
    line_shape,
)
from deckwright.components._shared import require_default_align

_FIELDS = ("from", "to", "kind", "color", "weight", "arrow")
_KINDS = {
    "straight": MSO_CONNECTOR.STRAIGHT,
    "elbow": MSO_CONNECTOR.ELBOW,
    "curved": MSO_CONNECTOR.CURVE,
}
_COLOR_DEFAULT = "accent-1"
# Inches. Two ends this close describe no direction, and PowerPoint routes an elbow
# between them unpredictably.
_MIN_RUN = 0.02

Endpoint = Rect | tuple[float, float]
Point = tuple[float, float]
Attached = tuple[Point, str | None]


@component("connector")
def connector(ctx: SlideCtx) -> BodyResult:
    """Join ``from`` to ``to`` with a straight, elbowed or curved line."""
    require_default_align(ctx)
    known_fields(ctx, _FIELDS)
    kind = choice(ctx, "kind", tuple(_KINDS), default="straight")
    (start, start_axis), (end, end_axis) = _run(ctx)
    if kind == "elbow":
        # Routed here, not by the renderer: LibreOffice re-routes a free elbow with its
        # own heuristic, which can run the last leg flush along the target's edge with
        # the arrowhead pointing beside the card instead of into it.
        line = _elbow(ctx, start, end, start_axis=start_axis, end_axis=end_axis)
    else:
        line = line_shape(ctx, _KINDS[kind], start, end, default_role=_COLOR_DEFAULT)
    arrow(line, choice(ctx, "arrow", ARROWS, default="none"))
    ctx.manifest.record(line)
    return BodyResult(groups=[[(line.shape_id, "line")]], height=0.0)


def _elbow(
    ctx: SlideCtx, start: Point, end: Point, *, start_axis: str | None, end_axis: str | None
):
    """An open polyline through explicit bends, entering each edge square-on."""
    from deckwright.components._shape import stroke, weight_pt

    points = _route(start, end, start_axis, end_axis)
    builder = ctx.slide.shapes.build_freeform(Inches(points[0][0]), Inches(points[0][1]), scale=1.0)
    builder.add_line_segments([(Inches(x), Inches(y)) for x, y in points[1:]], close=False)
    shape = builder.convert_to_shape()
    shape.fill.background()
    shape.line.color.rgb = stroke(ctx, _COLOR_DEFAULT)
    shape.line.width = Pt(weight_pt(ctx))
    shape.shadow.inherit = False
    return shape


def _route(start: Point, end: Point, start_axis: str | None, end_axis: str | None) -> list[Point]:
    (sx, sy), (ex, ey) = start, end
    if start_axis is None:
        start_axis = "h" if abs(ex - sx) >= abs(ey - sy) else "v"
    if end_axis is None:
        end_axis = "h" if abs(ex - sx) >= abs(ey - sy) else "v"
    if start_axis == "h" and end_axis == "h":
        mid = (sx + ex) / 2
        raw = [(sx, sy), (mid, sy), (mid, ey), (ex, ey)]
    elif start_axis == "v" and end_axis == "v":
        mid = (sy + ey) / 2
        raw = [(sx, sy), (sx, mid), (ex, mid), (ex, ey)]
    elif start_axis == "h":
        raw = [(sx, sy), (ex, sy), (ex, ey)]
    else:
        raw = [(sx, sy), (sx, ey), (ex, ey)]
    points = [raw[0]]
    for pt in raw[1:]:
        if pt != points[-1]:
            points.append(pt)
    return points


def _run(ctx: SlideCtx) -> tuple[Attached, Attached]:
    """The two points the line runs between, in inches, each with the axis of the edge
    it attached to — ``None`` where the end is a bare point and has no edge."""
    tail, head = _endpoint(ctx, "from"), _endpoint(ctx, "to")
    start, start_axis = _attach(tail, _centre(head))
    end, end_axis = _attach(head, _centre(tail))
    if hypot(end[0] - start[0], end[1] - start[1]) < _MIN_RUN:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'connector'): 'from' and 'to' resolve to "
            f"the same point on the canvas, so the line has no direction"
        )
    return (start, start_axis), (end, end_axis)


def _endpoint(ctx: SlideCtx, key: str) -> Endpoint:
    """One end: the rectangle a placement id names, or a point on the canvas."""
    value = ctx.body.get(key)
    if value is None:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'connector'): {key!r} is required — "
            f"give it a placement id, or two numbers, x then y, as fractions of the "
            f"canvas"
        )
    if isinstance(value, str):
        rect = ctx.placements.get(value)
        if rect is None:
            known = ", ".join(sorted(ctx.placements)) or "no placement on this slide has one"
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'connector'): {key!r} names the "
                f"placement id {value!r}, which this slide does not declare; ids "
                f"here: {known}"
            )
        return rect
    return canvas_point(ctx, value, key=key)


def _centre(end: Endpoint) -> Point:
    if isinstance(end, Rect):
        return end.left + end.width / 2, end.top + end.height / 2
    return end


def _attach(end: Endpoint, target: Point) -> Attached:
    """Where the line meets a rectangle: the edge midpoint nearest the other end, and
    the axis that edge runs off."""
    if not isinstance(end, Rect):
        return end, None
    x, y = _centre(end)
    edges = (
        ((end.right, y), "h"),
        ((end.left, y), "h"),
        ((x, end.bottom), "v"),
        ((x, end.top), "v"),
    )
    return min(edges, key=lambda e: hypot(e[0][0] - target[0], e[0][1] - target[1]))
