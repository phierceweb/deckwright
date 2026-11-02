"""Point-in-polygon and polygon/box intersection, in whatever units the caller uses."""

from __future__ import annotations

Point = tuple[float, float]
Poly = tuple[Point, ...]


def segments_cross(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """True when segment p1p2 touches or crosses segment p3p4."""

    def orient(a: Point, b: Point, c: Point) -> int:
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return (v > 0) - (v < 0)

    def on_span(a: Point, b: Point, c: Point) -> bool:
        return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(
            a[1], b[1]
        )

    o1, o2 = orient(p1, p2, p3), orient(p1, p2, p4)
    o3, o4 = orient(p3, p4, p1), orient(p3, p4, p2)
    if o1 != o2 and o3 != o4:
        return True
    return (
        (o1 == 0 and on_span(p1, p2, p3))
        or (o2 == 0 and on_span(p1, p2, p4))
        or (o3 == 0 and on_span(p3, p4, p1))
        or (o4 == 0 and on_span(p3, p4, p2))
    )


def point_in_poly(poly: Poly, x: float, y: float) -> bool:
    """Ray-casting point-in-polygon test."""
    inside = False
    j = len(poly) - 1
    for i, (xi, yi) in enumerate(poly):
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def poly_hits_box(poly: Poly, left: float, top: float, width: float, height: float) -> bool:
    """True when an axis-aligned box overlaps the polygon.

    Vertex containment alone is insufficient: two rectangles can cross in a ``+``
    with no vertex of either inside the other, so edges are tested too.
    """
    right, bottom = left + width, top + height
    corners = ((left, top), (right, top), (right, bottom), (left, bottom))
    if any(point_in_poly(poly, x, y) for x, y in corners):
        return True
    if any(left <= x <= right and top <= y <= bottom for x, y in poly):
        return True
    box_edges = [(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    poly_edges = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]
    return any(segments_cross(a, b, c, d) for a, b in box_edges for c, d in poly_edges)


def poly_x_span(poly: Poly, top: float, bottom: float) -> tuple[float, float] | None:
    """Leftmost and rightmost x the polygon occupies between ``top`` and ``bottom``.

    ``None`` when it does not reach into that horizontal band at all. Vertices
    inside the band plus every crossing of its two edges — a diagonal reaches
    furthest out at exactly one of those points.
    """
    xs = [x for x, y in poly if top <= y <= bottom]
    for i, (x1, y1) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        if y1 == y2:
            continue
        for edge_y in (top, bottom):
            if min(y1, y2) <= edge_y <= max(y1, y2):
                xs.append(x1 + (x2 - x1) * (edge_y - y1) / (y2 - y1))
    return (min(xs), max(xs)) if xs else None
