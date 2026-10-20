"""A deckwright placement's fields, read back from the shapes its component drew."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deckwright.components.bullets import MARKER
from deckwright.spec._chartback import chart_block
from deckwright.spec._glyphback import glyph_name
from deckwright.spec._tree import flat, linked_text, table_grid

_CITE = "— "


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
