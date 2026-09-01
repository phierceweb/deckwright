"""How wide every column is, how deep every row is, and how the two are validated.

A merged cell measures across the padding it swallowed; a cell reaching down is satisfied
by the rows it covers together rather than by any one of them.
"""

from __future__ import annotations

from deckwright.errors import LayoutError
from deckwright.layouts.registry import SlideCtx
from deckwright.utils.shapes import ALIGNS
from deckwright.utils.text import LINE_HEIGHT, wrapped_lines

from deckwright.components._tablespec import Placed, Row


def aligns(ctx: SlideCtx, columns: int) -> list[str]:
    """Each column's horizontal alignment — ``align:``, else the placement's own."""
    value = ctx.body.get("align")
    if value is None:
        return [ctx.align] * columns
    if not isinstance(value, list) or len(value) != columns:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'table'): 'align' is one entry per "
            f"column, so it needs {columns}; got {value!r}"
        )
    for entry in value:
        if str(entry) not in ALIGNS:
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'table'): 'align' entries must be "
                f"one of {', '.join(ALIGNS)}, got {entry!r}"
            )
    return [str(entry) for entry in value]


def widths(ctx: SlideCtx, columns: int, *, total: float) -> list[float]:
    """Column widths in inches — ``widths:`` as relative weights, else an even split."""
    value = ctx.body.get("widths")
    if value is None:
        return [total / columns] * columns
    if not isinstance(value, list) or len(value) != columns:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'table'): 'widths' is one entry per "
            f"column, so it needs {columns}; got {value!r}"
        )
    weights: list[float] = []
    for entry in value:
        try:
            weight = float(entry)
        except (TypeError, ValueError):
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'table'): 'widths' entries must be "
                f"positive numbers, got {entry!r}"
            ) from None
        if weight <= 0:
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'table'): 'widths' entries must be "
                f"positive numbers, got {entry!r}"
            )
        weights.append(weight)
    share = sum(weights)
    return [total * weight / share for weight in weights]


def heights(
    rows: list[Row],
    placed: list[Placed],
    columns_in: list[float],
    *,
    size_pt: float,
    pad_x: float,
    pad_y: float,
    limit: float | None = None,
    face: str | None = None,
) -> list[float]:
    """How deep each row must be, in inches.

    A spanning cell's shortfall is shared evenly across the rows it covers, so a two-row
    label is not paid for entirely by its first row. That is not minimal, so when it
    overruns the room available :func:`_tight` is used instead.
    """
    needs = {
        id(p): _needs(p, columns_in, size_pt=size_pt, pad_x=pad_x, pad_y=pad_y, face=face)
        for p in placed
    }
    roomy = _even(rows, placed, needs, floor=_depth(1, size_pt, pad_y))
    if limit is None or sum(roomy) <= limit:
        return roomy
    return _tight(rows, placed, needs, floor=_depth(1, size_pt, pad_y))


def _even(
    rows: list[Row], placed: list[Placed], needs: dict[int, float], *, floor: float
) -> list[float]:
    """Every row sized by its own cells, then each span's shortfall shared across it."""
    depths = [floor] * len(rows)
    for one in (p for p in placed if p.cell.down == 1):
        depths[one.row] = max(depths[one.row], needs[id(one)])
    for tall in (p for p in placed if p.cell.down > 1):
        have = sum(depths[tall.row : tall.row + tall.cell.down])
        if needs[id(tall)] > have:
            share = (needs[id(tall)] - have) / tall.cell.down
            for index in range(tall.row, tall.row + tall.cell.down):
                depths[index] += share
    return depths


def _tight(
    rows: list[Row], placed: list[Placed], needs: dict[int, float], *, floor: float
) -> list[float]:
    """The shallowest table that still holds every cell.

    Claims are taken in order of where they *end* and paid off in their last row, which
    leaves the depth where later claims can still reach it.
    """
    depths = [floor] * len(rows)
    for spot in sorted(placed, key=lambda p: (p.last_row, p.cell.down)):
        have = sum(depths[spot.row : spot.row + spot.cell.down])
        if needs[id(spot)] > have:
            depths[spot.last_row] += needs[id(spot)] - have
    return depths


def _needs(
    placed: Placed,
    columns_in: list[float],
    *,
    size_pt: float,
    pad_x: float,
    pad_y: float,
    face: str | None = None,
) -> float:
    if not placed.cell.text:
        return _depth(1, size_pt, pad_y)
    lines = wrapped_lines(
        placed.cell.text,
        size_pt=size_pt,
        width_in=measure(columns_in, placed.col, placed.cell.across, pad_x),
        face=face,
    )
    return _depth(lines, size_pt, pad_y)


def _depth(lines: int, size_pt: float, pad_y: float) -> float:
    return lines * size_pt * LINE_HEIGHT / 72 + 2 * pad_y


def measure(columns_in: list[float], start: int, count: int, pad_x: float) -> float:
    """The width text has inside a cell of ``count`` columns.

    One pair of margins for the whole span, so the padding between merged columns becomes
    measure and a spanning cell holds more than its columns did separately.
    """
    return max(sum(columns_in[start : start + count]) - 2 * pad_x, 0.01)
