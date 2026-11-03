"""A deckwright placement's fields, read back from the shapes its component drew."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from pptx.oxml.ns import qn

from deckwright.components.bullets import MARKER
from deckwright.components.table import TABLE_DEFAULTS
from deckwright.spec._chartback import chart_block
from deckwright.spec._glyphback import glyph_name
from deckwright.spec._tree import flat, linked_text, table_grid
from deckwright.utils.shapes import ALIGN, ANCHOR

_CITE = "— "
_ALIGNED = {value: name for name, value in ALIGN.items()}
_ANCHORED = {value: name for name, value in ANCHOR.items()}


def component_body(
    component: str, shapes: list[Any], icons: tuple[Path, ...]
) -> tuple[dict[str, Any] | None, str | None, tuple[str, ...]]:
    """The component's mapping, a note on what did not come back, and its words."""
    texts = [s for s in shapes if s.has_text_frame and text_lines(s)]
    if component == "card":
        return _card(shapes, texts, icons)
    if component == "bullets":
        return _bullets(texts)
    if component == "prose" and len(texts) == 1:
        lines = text_lines(texts[0])
        body: dict[str, Any] = {"paragraphs": list(lines)}
        if len(lines) > 1 and lines[-1].startswith(_CITE):
            body = {"paragraphs": list(lines[:-1]), "cite": lines[-1][len(_CITE) :]}
        return {"prose": body}, None, lines
    if component == "table" and shapes[0].has_table:
        grid = table_grid(shapes[0])
        if len(grid) > 1:
            head, *rows = grid
            table: dict[str, Any] = {"header": list(head), "rows": [list(r) for r in rows]}
            columns = [int(c.width) for c in shapes[0].table.columns]
            if max(columns) - min(columns) > sum(columns) / 100:
                table["widths"] = [round(c / sum(columns), 3) for c in columns]
            table.update(_table_look(shapes[0].table))
            return {"table": table}, None, ()
    if component == "chart" and shapes[0].has_chart:
        block, why = chart_block(shapes[0])
        if block is None:
            return None, f"not converted: {why}", ()
        return {"chart": block}, None, ()
    if component == "rule":
        wide = shapes[0].width >= shapes[0].height
        return {"rule": {} if wide else {"orient": "vertical"}}, None, ()
    if component == "panel" and not texts:
        return {"panel": {}}, None, ()
    words = tuple(line.removeprefix(MARKER) for shape in texts for line in text_lines(shape))
    if not words:
        return None, f"not converted: a {component} placement, which holds no words", ()
    return (
        {"bullets": {"items": list(words)}},
        f"drafted as bullets: a {component} placement's fields are not in the file, only its words",
        words,
    )


def _table_look(table) -> dict[str, Any]:
    """A table's column alignment, cell anchoring and rules as the file draws them, defaults
    included so a hand edit back to one still says so; a column holding no words reads as
    None."""
    rows = [list(row.cells) for row in table.rows]
    own = [cell for row in rows for cell in row if not cell.is_spanned]
    look: dict[str, Any] = {
        "valign": _most((_ANCHORED.get(cell.vertical_anchor, "top") for cell in own), "top"),
        "rules": _rules_drawn(rows),
    }
    look["align"] = [_column_align(rows, col) for col in range(len(rows[0]))]
    return look


def table_unset(table: dict[str, Any], align: str) -> dict[str, Any]:
    """A table's fields less those at the value it takes unwritten; a column whose alignment
    read as None is set as the placement is."""
    out = {k: v for k, v in table.items() if k not in TABLE_DEFAULTS or v != TABLE_DEFAULTS[k]}
    if isinstance(out.get("align"), list):
        out["align"] = [align if entry is None else entry for entry in out["align"]]
        if all(entry == align for entry in out["align"]):
            del out["align"]
    return out


def _column_align(rows: list[list[Any]], col: int) -> str | None:
    """The alignment most of a column's own, non-empty cells carry; None with no words."""
    cells = [row[col] for row in rows if not row[col].is_spanned and flat(row[col].text)]
    return _most((_ALIGNED.get(c.text_frame.paragraphs[0].alignment, "left") for c in cells), None)


def _most(values, default: str | None) -> str | None:
    counted = Counter(values).most_common(1)
    return counted[0][0] if counted else default


def _rules_drawn(rows: list[list[Any]]) -> str:
    """Which of ``RULES`` the table's own cell borders draw."""
    if any(_ruled(cell, "lnR") for row in rows for cell in row):
        return "grid"
    below = {r for r, row in enumerate(rows) if any(_ruled(cell, "lnB") for cell in row)}
    if not below and not any(_ruled(cell, "lnT") for row in rows for cell in row):
        return "none"
    return "header" if below == {0} and len(rows) >= 3 else "rows"


def _ruled(cell, edge: str) -> bool:
    """Whether a cell's ``edge`` carries a line: an edge holding no fill draws none."""
    tcPr = cell._tc.tcPr
    line = tcPr.find(qn(f"a:{edge}")) if tcPr is not None else None
    return line is not None and line.find(qn("a:noFill")) is None


def _card(
    shapes: list[Any], texts: list[Any], icons: tuple[Path, ...]
) -> tuple[dict[str, Any] | None, str | None, tuple[str, ...]]:
    lines = tuple(line for shape in texts for line in text_lines(shape))
    body: dict[str, Any] = {}
    if len(lines) >= 2:
        body = {"heading": lines[0], "body": " ".join(lines[1:])}
    elif lines:
        run = texts[0].text_frame.paragraphs[0].runs
        body = {"heading" if run and run[0].font.bold else "body": lines[0]}
    marks = [s for s in shapes[1:] if s not in texts]
    named = glyph_name(marks[0], icons) if len(marks) == 1 else None
    if named is not None:
        body["icon"] = named
    note = "its icon is not in the file by name, so it is left out" if marks and not named else None
    return {"card": body}, note, lines


def _bullets(texts: list[Any]) -> tuple[dict[str, Any] | None, str | None, tuple[str, ...]]:
    heading = [s for s in texts if not text_lines(s)[0].startswith(MARKER)]
    columns = [s for s in texts if text_lines(s)[0].startswith(MARKER)]
    items = [line.removeprefix(MARKER) for shape in columns for line in text_lines(shape)]
    if not items:
        return None, "not converted: a bullets placement with no items", ()
    body: dict[str, Any] = {}
    if heading:
        body["heading"] = text_lines(heading[0])[0]
    if len(columns) > 1:
        body["columns"] = len(columns)
    body["items"] = items
    words = ((body["heading"],) if "heading" in body else ()) + tuple(items)
    return {"bullets": body}, None, words


def text_lines(shape) -> tuple[str, ...]:
    return tuple(
        line for line in (flat(linked_text(p)) for p in shape.text_frame.paragraphs) if line
    )
