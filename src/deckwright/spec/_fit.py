"""Fit harvested words to a theme's grid: how many rows each placement needs, how
many bullets a band holds, and what spills when the slide asks for more."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from deckwright.components._shared import BULLET_SPACE_AFTER_PT
from deckwright.components._tablegeom import heights
from deckwright.components._tablespec import Cell, Placed, Row
from deckwright.components.table import _PAD_Y_EM as TABLE_PAD_Y_EM
from deckwright.layouts.chrome import CHROME_ORDER, chrome_bands
from deckwright.layouts.place import content_rect
from deckwright.theme.model import Rect, Theme
from deckwright.utils.text import LINE_HEIGHT

if TYPE_CHECKING:
    from deckwright.spec.extract import SlideContent, _Lines, _Table

# A band of one row is thinner than a single line of type, so nothing is given less.
ROWS_PER_PLACEMENT = 2
# Past three, a column is narrower than the words in it.
MAX_BULLET_COLUMNS = 3


@dataclass(frozen=True)
class Item:
    """One placement's component mapping, and the grid rows it needs to draw in."""

    body: dict
    rows: int


def _bullets(lines: _Lines) -> dict:
    return {"bullets": {"items": list(lines)}}


def _as_table(grid: _Table) -> dict:
    return {"table": {"header": list(grid[0]), "rows": [list(row) for row in grid[1:]]}}


def _split(slide: SlideContent) -> tuple[list[_Lines], list[_Table]]:
    """The slide's blocks and its tables — a one-row grid has no body rows, so it
    becomes another block rather than a table the compiler refuses."""
    blocks = list(slide.blocks)
    tables: list[_Table] = []
    for grid in slide.tables:
        if len(grid) > 1:
            tables.append(grid)
        elif grid:
            blocks.append(grid[0])
    return blocks, tables


def _table_rows(grid: _Table, *, theme: Theme, band: Rect) -> int:
    """Grid rows the table needs — the compiler's own height arithmetic, run early."""
    style = theme.style("body")
    columns_in = [band.width / len(grid[0])] * len(grid[0])
    rows = [Row(tuple(Cell(text=text) for text in line)) for line in grid]
    placed = [
        Placed(cell, index, column)
        for index, row in enumerate(rows)
        for column, cell in enumerate(row.cells)
    ]
    extent = sum(
        heights(
            rows,
            placed,
            columns_in,
            size_pt=style.size,
            pad_x=theme.grid.gutter,
            pad_y=style.size * TABLE_PAD_Y_EM / 72,
            face=theme.font_for(style),
        )
    )
    return math.ceil(extent / (band.height / theme.grid.rows))


def fit(slide: SlideContent, *, theme: Theme, band: Rect) -> tuple[list[Item], _Lines]:
    """The placements the theme's grid can band, and the words that did not fit."""
    blocks, tables = _split(slide)
    sized = [
        (grid, max(ROWS_PER_PLACEMENT, _table_rows(grid, theme=theme, band=band)))
        for grid in tables
    ]
    items = [Item(_bullets(block), ROWS_PER_PLACEMENT) for block in blocks]
    items += [Item(_as_table(grid), need) for grid, need in sized]
    if sum(item.rows for item in items) <= theme.grid.rows:
        return items, ()

    lines = tuple(line for block in blocks for line in block)
    kept = [Item(_bullets(lines), ROWS_PER_PLACEMENT)] if lines else []
    left = theme.grid.rows - sum(item.rows for item in kept)
    for index, (grid, need) in enumerate(sized):
        if need > left:
            return kept, tuple(" | ".join(row) for g, _ in sized[index:] for row in g)
        kept.append(Item(_as_table(grid), need))
        left -= need
    return kept, ()


def content_band(slide: SlideContent, theme: Theme) -> Rect:
    """The band this slide's placements may occupy — its own chrome pushes it down."""
    lines: dict[str, tuple[str, float]] = {}
    faces: dict[str, str] = {}
    for name in CHROME_ORDER:
        text = getattr(slide, name)
        if text:
            style = theme.style(name)
            lines[name] = (str(text), style.size)
            faces[name] = theme.font_for(style)
    bands = chrome_bands(lines, fields={}, grid=theme.grid, faces=faces) if lines else ()
    return content_rect(grid=theme.grid, chrome=bands, reserved=theme.reserve)


def bullet_budget(theme: Theme, band: Rect) -> int:
    """Bullets the content band holds — the compiler refuses a slide asking for more."""
    per_line = (theme.style("body").size * LINE_HEIGHT + BULLET_SPACE_AFTER_PT) / 72
    return max(1, int(band.height / per_line))


def column_up(place: list[dict], *, budget: int, rows: int) -> _Lines:
    """A list longer than its band takes a second column, then a third; past that its
    tail spills."""
    spilled: list[str] = []
    for entry in place:
        bullets = entry.get("bullets")
        if bullets is None:
            continue
        span = entry["at"].get("rows")
        share = budget * (span["to"] - span["from"]) // rows if span else budget
        fits = max(1, share)
        items = bullets["items"]
        columns = min(MAX_BULLET_COLUMNS, -(-len(items) // fits))
        held = fits * columns
        spilled += items[held:]
        kept: dict = {"items": items[:held]}
        entry["bullets"] = {"columns": columns, **kept} if columns > 1 else kept
    return tuple(spilled)


def band(place: list[dict], demands: list[int], *, rows: int) -> None:
    """Rows for each placement in proportion to what it holds: two placements both
    filling the content band overlap, which the compiler refuses."""
    if len(place) < 2:
        return
    total, taken, start = sum(demands), 0, 0
    for entry, need in zip(place, demands, strict=True):
        taken += need
        end = rows * taken // total
        entry["at"]["rows"] = {"from": start, "to": end}
        start = end
