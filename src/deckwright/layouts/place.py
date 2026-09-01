"""Resolve an ``at:`` mapping to a rectangle, and guard the placements it produces.

``cols`` spans the column grid, ``rows`` spans the theme's row grid over the area being
resolved against, and ``box`` takes fractions of the whole canvas. ``Grid`` comes
from ``theme.scale``, not the ``deckwright.theme`` package: ``theme.load`` imports this
module, so the package namespace is half-initialised here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence

from deckwright.errors import LayoutError, ThemeError
from deckwright.theme.model import Rect
from deckwright.theme.scale import Grid, Scale
from deckwright.utils.poly import poly_hits_box, poly_x_span
from deckwright.utils.spans import Share, divides, resolve as resolve_span

if TYPE_CHECKING:  # layouts.chrome imports this module, so the name stays annotation-only
    from deckwright.layouts.chrome import ChromeBand

AT_KEYS = ("cols", "rows", "box")
# Inches. Half a rendered point, so a shared edge reads as a touch, not a collision.
_EPS = 0.007
# Fraction of canvas height between the chrome stack and the content band.
_CHROME_GAP = 0.04


@dataclass(frozen=True)
class Reserved:
    """A canvas region placements must stay out of, as a polygon in canvas fractions.

    A polygon rather than a rectangle because a corner wedge is a triangle: a
    bounding box would forbid the usable space above its diagonal.
    """

    name: str
    poly: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if len(self.poly) < 3:
            raise ThemeError(f"reserved region {self.name!r} needs at least 3 points")
        if any(len(p) != 2 for p in self.poly):
            raise ThemeError(f"reserved region {self.name!r} needs x, y points")
        xs, ys = [p[0] for p in self.poly], [p[1] for p in self.poly]
        if max(xs) - min(xs) <= 0 or max(ys) - min(ys) <= 0:
            raise ThemeError(f"reserved region {self.name!r} encloses no area")

    def rect(self, scale: Scale) -> Rect:
        """The region's bounding box, in inches."""
        xs, ys = [p[0] for p in self.poly], [p[1] for p in self.poly]
        left, top = scale.x(min(xs)), scale.y(min(ys))
        return Rect(left, top, scale.x(max(xs)) - left, scale.y(max(ys)) - top)

    def hits(self, rect: Rect, *, scale: Scale) -> bool:
        """True when ``rect`` (inches) touches the region itself, not just its box."""
        return poly_hits_box(self._inches(scale), rect.left, rect.top, rect.width, rect.height)

    def x_span(self, *, scale: Scale, top: float, bottom: float) -> tuple[float, float] | None:
        """Leftmost and rightmost inch the region reaches between two y values."""
        return poly_x_span(self._inches(scale), top, bottom)

    def _inches(self, scale: Scale) -> tuple[tuple[float, float], ...]:
        return tuple((scale.x(x), scale.y(y)) for x, y in self.poly)


def content_rect(
    *, grid: Grid, chrome: Sequence[ChromeBand] = (), reserved: Sequence[Reserved] = ()
) -> Rect:
    """The band placements may occupy: inside the margins, below ``body_top`` and
    below the stacked chrome, less every reserved region that spans it edge to edge.

    Only stacked chrome counts — a line placed with an ``at:`` may sit over the body. A
    corner wedge spans neither axis and is enforced per placement in
    :func:`clear_reserved`. See ``docs/placement.md``.
    """
    left, right = grid.left, grid.right_edge
    top, bottom = grid.body_top, grid.slide_h - grid.bottom
    stacked = [band for band in chrome if band.stacked]
    if stacked:
        stack = max(band.rect.bottom for band in stacked)
        top = max(top, stack + grid.scale.y(_CHROME_GAP))
        if top >= bottom:
            raise LayoutError(
                f"the chrome stack reaches {stack:.2f}in, leaving no content area above "
                f"the {bottom:.2f}in bottom margin — shorten the "
                f"{', '.join(sorted(band.name for band in stacked))} or set a smaller rung"
            )
    for region in reserved:
        r = region.rect(grid.scale)
        if (
            r.right <= left + _EPS
            or r.left >= right - _EPS
            or r.bottom <= top + _EPS
            or r.top >= bottom - _EPS
        ):
            continue
        spans_w = r.left <= left + _EPS and r.right >= right - _EPS
        spans_h = r.top <= top + _EPS and r.bottom >= bottom - _EPS
        if spans_w and spans_h:
            raise ThemeError(f"reserved region {region.name!r} covers the whole content area")
        if spans_w:
            top, bottom = (r.bottom, bottom) if r.top < top + _EPS else (top, r.top)
        elif spans_h:
            left, right = (r.right, right) if r.left <= left + _EPS else (left, r.left)
        if right - left <= 0 or bottom - top <= 0:
            raise ThemeError(f"reserved region {region.name!r} leaves no content area")
    return Rect(left, top, right - left, bottom - top)


def resolve_at(at: dict, *, grid: Grid, area: Rect, where: str) -> Rect:
    """Resolve one placement's ``at:`` mapping to a rectangle in inches."""
    if not isinstance(at, dict):
        raise LayoutError(
            f"{where}: 'at' must be a mapping with 'cols' or 'box', got {type(at).__name__}"
        )
    unknown = sorted(set(at) - set(AT_KEYS))
    if unknown:
        raise LayoutError(
            f"{where}: unknown 'at' key {unknown[0]!r}; known keys: {', '.join(AT_KEYS)}"
        )
    if "box" in at:
        if "cols" in at or "rows" in at:
            raise LayoutError(f"{where}: 'box' cannot be combined with 'cols' or 'rows'")
        x, y, w, h = at["box"]
        scale = grid.scale
        return Rect(scale.x(x), scale.y(y), scale.x(w), scale.y(h))
    if not at:
        # Only a bleeding placement reaches here with nothing: it is drawn off the
        # canvas, so the canvas is the rect it is handed.
        return Rect(0.0, 0.0, grid.slide_w, grid.slide_h)
    if "cols" not in at:
        raise LayoutError(f"{where}: 'at' needs 'cols' or 'box'")
    left, width = _col_span(at["cols"], grid=grid, where=where)
    top, height = _row_span(at.get("rows"), area=area, grid=grid, where=where)
    return Rect(left, top, width, height)


def clear_reserved(rect: Rect, *, reserved: Sequence[Reserved], grid: Grid, where: str) -> Rect:
    """Narrow a grid-derived rect horizontally until it clears every reserved region.

    Only the rect's own vertical extent counts, so a placement bounded by ``rows:``
    above a corner wedge keeps the full content width. A region reaching in from
    both sides raises: there is nowhere to step aside to.
    """
    left, right = rect.left, rect.right
    for region in reserved:
        # Inset by the touch epsilon on both axes, so a region whose edge merely meets
        # the rect's does not count as reaching into it.
        span = region.x_span(scale=grid.scale, top=rect.top + _EPS, bottom=rect.bottom - _EPS)
        if span is None:
            continue
        lo, hi = span
        if hi <= left + _EPS or lo >= right - _EPS:
            continue
        if lo <= left + _EPS and hi >= right - _EPS:
            raise LayoutError(
                f"{where}: reserved region {region.name!r} leaves no room at {_fmt(rect)}"
            )
        if lo <= left + _EPS:
            left = hi + grid.gutter
        else:
            right = lo - grid.gutter
        if right - left <= 0:
            raise LayoutError(
                f"{where}: reserved region {region.name!r} leaves no room at {_fmt(rect)}"
            )
    return Rect(left, rect.top, right - left, rect.height)


@dataclass(frozen=True)
class Placed:
    """One resolved placement, labelled for the error messages."""

    where: str
    rect: Rect
    bleed: bool = False
    exact: bool = False  # written as a box:, so measured against the canvas


def check_placements(
    placed: Sequence[Placed], *, area: Rect, grid: Grid, reserved: Sequence[Reserved] = ()
) -> None:
    """Reject placements that leave their bounds, hit a reserved region, or overlap
    one another. A placement declaring ``bleed`` is exempt from all three.

    Bounds depend on how the placement was written: ``cols``/``rows`` is measured against
    the content band it was carved out of, ``box`` against the whole canvas.
    """
    canvas = Rect(0.0, 0.0, grid.slide_w, grid.slide_h)
    for item in placed:
        if item.bleed:
            continue
        rect = item.rect
        bounds = canvas if item.exact else area
        if (
            rect.left < bounds.left - _EPS
            or rect.top < bounds.top - _EPS
            or rect.right > bounds.right + _EPS
            or rect.bottom > bounds.bottom + _EPS
        ):
            raise LayoutError(
                f"{item.where}: {_fmt(rect)} falls outside the "
                f"{'canvas' if item.exact else 'content area'} {_fmt(bounds)}"
            )
        for region in reserved:
            # Inset so a rect merely flush against a region's edge is a touch.
            if region.hits(rect.inset(_EPS, _EPS), scale=grid.scale):
                raise LayoutError(f"{item.where}: overlaps the reserved region {region.name!r}")
    for i, a in enumerate(placed):
        for b in placed[i + 1 :]:
            if a.bleed or b.bleed:
                continue
            if _overlaps(a.rect, b.rect):
                raise LayoutError(f"{a.where} overlaps {b.where}")


def _overlaps(a: Rect, b: Rect) -> bool:
    return (
        a.left < b.right - _EPS
        and b.left < a.right - _EPS
        and a.top < b.bottom - _EPS
        and b.top < a.bottom - _EPS
    )


def _fmt(r: Rect) -> str:
    return f"[{r.left:.2f}, {r.top:.2f}, {r.width:.2f}, {r.height:.2f}]in"


def _col_span(value: Any, *, grid: Grid, where: str) -> tuple[float, float]:
    if isinstance(value, Share):
        return _share(value, grid=grid, where=where)
    start, end = _indices(value, "cols", grid.columns, where=where)
    if not 0 <= start < end <= grid.columns:
        raise LayoutError(
            f"{where}: cols [{start}, {end}] out of range — a span runs "
            f"0..{grid.columns} with start < end"
        )
    return grid.col_x(start), grid.span_w(end - start)


def _row_span(value: Any, *, area: Rect, grid: Grid, where: str) -> tuple[float, float]:
    if value is None:
        return area.top, area.height
    start, end = _indices(value, "rows", grid.rows, where=where)
    if not 0 <= start < end <= grid.rows:
        raise LayoutError(
            f"{where}: rows [{start}, {end}] out of range — the content band has "
            f"{grid.rows} rows and a span runs 0..{grid.rows} with start < end"
        )
    row_h = area.height / grid.rows
    return area.top + start * row_h, (end - start) * row_h


def _share(share: Share, *, grid: Grid, where: str) -> tuple[float, float]:
    """One ``split:`` child's slice of its band.

    Whole-column bands give shares that *are* column spans; anything else — five across a
    twelve-column grid — divides the band's inches evenly.
    """
    start, end = _indices(share.band, "cols", grid.columns, where=where)
    columns = end - start
    if columns % share.total == 0:
        step = columns // share.total
        return (grid.col_x(start + share.index * step), grid.span_w(share.span * step))
    left, width = grid.col_x(start), grid.span_w(columns)
    slice_w = (width - grid.gutter * (share.total - 1)) / share.total
    if slice_w <= 0:
        raise LayoutError(
            f"{where}: {share.total} shares leave no width in a {columns}-column band"
        )
    return (
        left + share.index * (slice_w + grid.gutter),
        slice_w * share.span + grid.gutter * (share.span - 1),
    )


def _indices(value: Any, key: str, divisor: int, *, where: str) -> tuple[int, int]:
    """A validated span as indices — a named fraction resolved against this grid."""
    if isinstance(value, str):
        if not divides(value, divisor, key=key):
            raise LayoutError(
                f"{where}: {key} {value!r} does not divide this theme's {divisor} "
                f"{key} evenly — say the span outright with {{from:, to:}}"
            )
        return resolve_span(value, divisor, key=key)
    return int(value[0]), int(value[1])
