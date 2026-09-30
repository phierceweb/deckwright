"""Fit harvested words to a theme's grid: how many rows each placement needs, how
many bullets a band holds, and what spills when the slide asks for more."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from deckwright.components._tablegeom import heights
from deckwright.components._tablespec import Cell, Placed, Row
from deckwright.components.bullets import column_width, item_lines, split, stack_height
from deckwright.components.table import _PAD_Y_EM as TABLE_PAD_Y_EM
from deckwright.errors import SpecError
from deckwright.layouts.chrome import CHROME_ORDER, chrome_bands
from deckwright.layouts.place import clear_reserved, content_rect, resolve_at
from deckwright.theme.model import Rect, Theme
from deckwright.utils.spans import parse_span
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
    chart_rows = max(ROWS_PER_PLACEMENT, theme.grid.rows // 2)
    figures = (
        [(Item(_as_table(grid), need), _table_lines(grid)) for grid, need in sized]
        + [(Item({"chart": c}, chart_rows), (_chart_line(c),)) for c in slide.charts]
        + [(Item({"image": p.image()}, chart_rows), (_picture_line(p),)) for p in slide.pictures]
    )
    items = [Item(_bullets(block), ROWS_PER_PLACEMENT) for block in blocks]
    items += [Item({"card": body}, ROWS_PER_PLACEMENT) for body in slide.cards]
    items += [item for item, _ in figures]
    if sum(item.rows for item in items) <= theme.grid.rows:
        return items, ()

    lines = tuple(line for block in blocks for line in block) + _card_lines(slide)
    kept = [Item(_bullets(lines), ROWS_PER_PLACEMENT)] if lines else []
    left = theme.grid.rows - sum(item.rows for item in kept)
    for index, (item, _) in enumerate(figures):
        if item.rows > left:
            return kept, tuple(line for _, named in figures[index:] for line in named)
        kept.append(item)
        left -= item.rows
    return kept, ()


def lay_out(slide: SlideContent, *, theme: Theme, area: Rect) -> tuple[list[dict], _Lines]:
    """The slide's placements banded down ``area``, and what did not fit. Words come first:
    pictures that would push more of them off the slide are named instead."""
    place, spilled, pushed = _banded(slide, theme=theme, area=area)
    if pushed and slide.pictures:
        bare, left, fewer = _banded(replace(slide, pictures=()), theme=theme, area=area)
        if len(fewer) < len(pushed):
            return bare, left + fewer + tuple(_picture_line(p) for p in slide.pictures)
    return place, spilled + pushed


def _banded(slide: SlideContent, *, theme: Theme, area: Rect) -> tuple[list[dict], _Lines, _Lines]:
    """Placements, the figures with no room, and the lines no column could hold."""
    items, spilled = fit(slide, theme=theme, band=area)
    place = [{"at": {"cols": "full"}, **item.body} for item in items]
    band(place, [item.rows for item in items], rows=theme.grid.rows)
    return place, spilled, column_up(place, theme=theme, band=area)


def loose(slide: SlideContent) -> _Lines:
    """Everything harvested from ``slide``, each as the line a comment can hold."""
    return (
        tuple(line for block in slide.blocks for line in block)
        + tuple(line for grid in slide.tables for line in _table_lines(grid))
        + _card_lines(slide)
        + tuple(_chart_line(c) for c in slide.charts)
        + tuple(_picture_line(p) for p in slide.pictures)
    )


def _table_lines(grid) -> _Lines:
    return tuple(" | ".join(row) for row in grid)


def _card_lines(slide: SlideContent) -> _Lines:
    return tuple(line for body in slide.cards for line in body.values())


def _picture_line(found) -> str:
    return f"a picture — {found.name}" + (f": {found.alt}" if found.alt else "")


def _chart_line(block: dict) -> str:
    """A chart that found no room, as the one line a comment can hold."""
    rows = block["data"]
    shown = ", ".join(
        f"{r['category']}: {r['value'] if 'value' in r else r['values']}" for r in rows
    )
    return f"a {block['kind']} chart — {shown}"


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


def column_up(place: list[dict], *, theme: Theme, band: Rect) -> _Lines:
    """A list taller than its band takes a second column, then a third; past that its
    tail spills, and a placement holding nothing is dropped."""
    spilled: list[str] = []
    for entry in list(place):
        bullets = entry.get("bullets")
        if bullets is None:
            continue
        rect = _rect(entry["at"], theme=theme, band=band)
        if "heading" in bullets:
            head = theme.style("head")
            rect = Rect(rect.left, rect.top, rect.width, rect.height - head.size * LINE_HEIGHT / 72)
        items = bullets["items"]
        columns, held = _held(items, theme=theme, rect=rect, first=int(bullets.get("columns", 1)))
        spilled += items[held:]
        if not held:
            place.remove(entry)
            continue
        kept = {k: v for k, v in bullets.items() if k not in ("columns", "items")}
        kept["items"] = items[:held]
        entry["bullets"] = {"columns": columns, **kept} if columns > 1 else kept
    return tuple(spilled)


def _rect(at: dict, *, theme: Theme, band: Rect) -> Rect:
    """Where a drafted placement lands: a box in canvas percents, or grid spans in the band."""
    if "box" in at:
        box = at["box"]
        slide_w, slide_h = theme.scale.slide_w, theme.scale.slide_h
        return Rect(
            *(
                float(str(box[k]).rstrip("%")) / 100 * size
                for k, size in (("x", slide_w), ("y", slide_h), ("w", slide_w), ("h", slide_h))
            )
        )
    spans = {k: parse_span(v, k, where="draft", error=SpecError) for k, v in at.items()}
    rect = resolve_at(spans, grid=theme.grid, area=band, where="draft")
    return clear_reserved(rect, reserved=theme.reserve, grid=theme.grid, where="draft")


def _held(items: list[str], *, theme: Theme, rect: Rect, first: int = 1) -> tuple[int, int]:
    """The fewest columns from ``first`` up holding the most of ``items``, and how many that
    is — each item wrapped to its column as the compiler measures it, so more columns can
    hold fewer. A list read back from a deck starts at the columns it was set in."""
    style = theme.style("body")
    face = theme.font_for(style)
    at: dict[int, list[int]] = {}

    def fits(count: int, columns: int) -> bool:
        columns = min(columns, count)
        if columns not in at:
            width = column_width(rect.width, columns, theme.grid.gutter)
            at[columns] = [
                item_lines(item, width_in=width, size_pt=style.size, face=face) for item in items
            ]
        return all(
            stack_height(chunk, size_pt=style.size) <= rect.height
            for chunk in split(at[columns][:count], columns)
        )

    best, best_columns = 0, 1
    for columns in range(max(1, first), MAX_BULLET_COLUMNS + 1):
        held = len(items)
        while held and not fits(held, columns):
            held -= 1
        if held > best:
            best, best_columns = held, min(columns, held)
        if held == len(items):
            break
    return best_columns, best


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
