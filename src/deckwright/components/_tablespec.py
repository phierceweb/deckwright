"""The shape of a table before anything is drawn: cells, spans, and where they land.

A ``down:`` cell makes placement a pass rather than a sum: the row beneath it is written
with fewer cells, so the rule is "every column accounted for, once" rather than "the cells
add up to the width".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deckwright.errors import LayoutError
from deckwright.layouts.registry import SlideCtx
from deckwright.utils.shapes import ALIGNS, ANCHORS

CELL_KEYS = ("text", "across", "down", "align", "valign", "emphasis", "pair")


@dataclass(frozen=True)
class Cell:
    """One cell: its words, how far it reaches, and how it is set."""

    text: str
    across: int = 1  # columns this cell covers, itself included
    down: int = 1  # rows this cell covers, itself included
    align: str | None = None  # overrides the column's alignment
    valign: str | None = None  # overrides the table's vertical alignment
    emphasis: bool = False  # set apart: the theme's heading weight
    pair: str | None = None  # a palette pair painted behind this cell alone


@dataclass(frozen=True)
class Row:
    """One row of cells, and whether it is set apart from the rows above it."""

    cells: tuple[Cell, ...]
    kind: str = "body"  # head | body | total

    @property
    def span(self) -> int:
        return sum(c.across for c in self.cells)


@dataclass(frozen=True)
class Placed:
    """A cell and the grid position it was given, top-left first."""

    cell: Cell
    row: int
    col: int

    @property
    def last_row(self) -> int:
        return self.row + self.cell.down - 1

    @property
    def last_col(self) -> int:
        return self.col + self.cell.across - 1


def read_rows(ctx: SlideCtx) -> tuple[list[Row], int, list[Placed]]:
    """Every row in drawing order, how many columns wide, and where each cell lands.

    The column count comes from the header, else the first body row: neither can inherit
    a column from above, so both are a plain sum.

    Raises:
        LayoutError: a row is not a list, is empty, does not account for every
            column, or holds a cell that overlaps one reaching down from above.
    """
    head = _row(ctx, ctx.body.get("header"), kind="head", where="header")
    body = _body(ctx)
    total = _row(ctx, ctx.body.get("total"), kind="total", where="total")

    columns = head.span if head is not None else body[0].span
    if columns == 0:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'table'): the first row fixes the "
            f"table's width, so it cannot be the empty row that a 'down:' cell above "
            f"leaves behind — give the table a 'header:', or start it with real cells"
        )
    rows = [*([head] if head is not None else []), *body, *([total] if total is not None else [])]
    return rows, columns, _place(ctx, rows, columns)


def _place(ctx: SlideCtx, rows: list[Row], columns: int) -> list[Placed]:
    """Walk the grid left to right, top to bottom, giving every cell its position.

    A column already covered from above is stepped over, so the author writes only the
    cells that are theirs.
    """
    taken: set[tuple[int, int]] = set()
    placed: list[Placed] = []
    for index, row in enumerate(rows):
        inherited = sum(1 for c in range(columns) if (index, c) in taken)
        covers = inherited + row.span
        if row.span == 0 and inherited == columns:
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'table'): "
                f"{_name(row, rows, index)} has no cells of its own — every one of its "
                f"columns is covered by a 'down:' cell above, so the row is height and "
                f"nothing else. Drop it, and drop a row from the 'down:' that reached "
                f"into it: the table you meant is the same table without either"
            )
        if covers != columns:
            advice = _advice(covers > columns, inherited)
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'table'): "
                f"{_name(row, rows, index)} covers {covers} column(s) but the table is "
                f"{columns} wide — a table is rectangular, so {advice}"
            )
        column = 0
        for number, cell in enumerate(row.cells, start=1):
            while (index, column) in taken:
                column += 1
            _claim(
                ctx,
                taken,
                cell,
                at=(index, column),
                columns=columns,
                rows=rows,
                row=row,
                number=number,
            )
            placed.append(Placed(cell=cell, row=index, col=column))
            column += cell.across
    return placed


def _advice(over: bool, inherited: int) -> str:
    """What to try, which depends on which way the row is wrong and why.

    An over-long row with nothing reaching into it is nearly always one cell holding an
    unquoted comma, which YAML has already split in two before the table sees it.
    """
    if not over:
        return "add a cell, or widen one with 'across:'"
    if inherited:
        return (
            "this row has a cell too many — a column a 'down:' cell above already "
            "covers is not written again"
        )
    return (
        "this row has a cell too many — a cell holding an unquoted comma is read "
        "by YAML as two, so quote it"
    )


def _claim(
    ctx: SlideCtx,
    taken: set[tuple[int, int]],
    cell: Cell,
    *,
    at: tuple[int, int],
    columns: int,
    rows: list[Row],
    row: Row,
    number: int,
) -> None:
    """Mark every square one cell covers, refusing a reach that collides or runs off."""
    index, column = at
    where = f"{_name(row, rows, index)} cell {number}"
    if index + cell.down > len(rows):
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'table'): {where} sets 'down' to "
            f"{cell.down}, reaching past the last of the table's {len(rows)} row(s) — "
            f"count the header and total rows, which are rows of the table too"
        )
    squares = [
        (r, c) for r in range(index, index + cell.down) for c in range(column, column + cell.across)
    ]
    if column + cell.across > columns or any(s in taken for s in squares):
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'table'): {where} reaches across a "
            f"column that a 'down:' cell above already covers — cells cannot overlap"
        )
    taken.update(squares)


def _name(row: Row, rows: list[Row], index: int) -> str:
    if row.kind != "body":
        return {"head": "the header", "total": "the total row"}[row.kind]
    body_before = sum(1 for r in rows[:index] if r.kind == "body")
    return f"row {body_before + 1}"


def _body(ctx: SlideCtx) -> list[Row]:
    value = ctx.body.get("rows")
    if not isinstance(value, list) or not value:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'table'): 'rows' must be a non-empty list"
        )
    # `[]` parses so that a row left with nothing to say gets the message explaining
    # why that table has no shape, rather than "must be a non-empty list of cells".
    return [
        _require(ctx, r, kind="body", where=f"row {i}", empty_ok=True)
        for i, r in enumerate(value, start=1)
    ]


def _row(ctx: SlideCtx, value: Any, *, kind: str, where: str) -> Row | None:
    if value is None:
        return None
    return _require(ctx, value, kind=kind, where=where)


def _require(ctx: SlideCtx, value: Any, *, kind: str, where: str, empty_ok: bool = False) -> Row:
    if not isinstance(value, list) or (not value and not empty_ok):
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'table'): {where} must be a non-empty "
            f"list of cells, got {value!r}"
        )
    return Row(
        tuple(_cell(ctx, v, where=f"{where} cell {i}") for i, v in enumerate(value, start=1)),
        kind=kind,
    )


def _cell(ctx: SlideCtx, value: Any, *, where: str) -> Cell:
    """One cell, from a scalar or a mapping."""
    if value is None:
        return Cell(text="")
    if not isinstance(value, dict):
        if isinstance(value, list):
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'table'): {where} is a list, not a "
                f"cell — a row holding a comma needs quoting, or YAML reads it as one"
            )
        return Cell(text=str(value))

    unknown = sorted(set(value) - set(CELL_KEYS))
    if unknown:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'table'): {where} has no key "
            f"{unknown[0]!r}; a cell reads: {', '.join(CELL_KEYS)}"
        )
    return Cell(
        text="" if value.get("text") is None else str(value["text"]),
        across=_reach(ctx, value.get("across", 1), key="across", axis="columns", where=where),
        down=_reach(ctx, value.get("down", 1), key="down", axis="rows", where=where),
        align=_word(ctx, value.get("align"), key="align", known=ALIGNS, where=where),
        valign=_word(ctx, value.get("valign"), key="valign", known=ANCHORS, where=where),
        emphasis=bool(value.get("emphasis", False)),
        pair=None if value.get("pair") is None else str(value["pair"]),
    )


def _reach(ctx: SlideCtx, value: Any, *, key: str, axis: str, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'table'): {where} sets {key!r} to "
            f"{value!r} — it is how many {axis} the cell covers, itself included, "
            f"so it is a whole number from 1"
        )
    return value


def _word(ctx: SlideCtx, value: Any, *, key: str, known: tuple[str, ...], where: str) -> str | None:
    if value is None:
        return None
    if str(value) not in known:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'table'): {where} sets {key} "
            f"{value!r}; known: {', '.join(known)}"
        )
    return str(value)
