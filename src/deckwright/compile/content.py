"""Render a build manifest as the deck's words.

Derived, never authoritative: regenerate it, do not edit it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterator

from pf_core.utils.io import atomic_write_text

_CHROME_ORDER = ("kicker", "title", "subtitle")
# Components that hold no words and are not worth naming: the slide's own paint, a
# divider, a line between two placements.
_UNSPOKEN = ("bg", "rule", "connector")
_CELL = re.compile(r"^r(\d+)c(\d+)$")


def split_name(name: str) -> tuple[str, str | None]:
    """A shape name as ``(origin, part)`` — ``s2.p1.table.r1c1`` is that table's ``r1c1``."""
    if "#" in name:
        return name.split("#", 1)[0], None
    origin, _, part = name.rpartition(".")
    return (origin, part) if origin else (name, None)


def render_content(manifest: dict[str, Any]) -> str:
    """The deck's content as markdown, slide by slide, in order."""
    deck = Path(str(manifest.get("deck") or "deck")).stem
    slides = manifest.get("slides") or []
    facts = [f"{len(slides)} slide(s)"]
    for key, label in (("theme", "theme"), ("build_id", "build")):
        if manifest.get(key):
            facts.append(f"{label} `{manifest[key]}`")
    lines = [
        f"# {deck}",
        "",
        " · ".join(facts),
        "",
        "Derived from the build manifest. Regenerate it rather than edit it.",
        "",
    ]
    for slide in slides:
        lines.extend(_slide(slide))
    return "\n".join(lines).rstrip() + "\n"


def write_content(manifest: dict[str, Any], path: str | Path) -> Path:
    """Write the content view beside the deck; returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, render_content(manifest))
    return path


def _slide(slide: dict[str, Any]) -> Iterator[str]:
    head = f"## Slide {slide.get('index')}"
    if slide.get("section"):
        head += f" · {slide['section']}"
    yield from ("---", "", head, "")
    chrome, tables, body = _sort(slide.get("shapes") or [])
    for field in _CHROME_ORDER:
        if field in chrome:
            yield from _chrome_line(field, chrome[field])
    for origin, shapes in body:
        if origin in tables:
            yield from _table(tables.pop(origin))
        else:
            yield from _block(origin, shapes)
    if slide.get("notes"):
        yield from (f"> {line}" for line in str(slide["notes"]).strip().splitlines())
        yield ""


def _sort(shapes: list[dict[str, Any]]):
    """Split a slide's records into chrome, table grids, and body blocks in draw order."""
    chrome: dict[str, dict[str, Any]] = {}
    tables: dict[str, dict[tuple[int, int], str]] = {}
    body: list[tuple[str, list[dict[str, Any]]]] = []
    for shape in shapes:
        origin, part = split_name(str(shape.get("name") or ""))
        if origin.endswith(".chrome") and part:
            chrome[part] = shape
            continue
        cell = _CELL.match(part or "")
        if cell:
            grid = tables.setdefault(origin, {})
            grid[(int(cell.group(1)), int(cell.group(2)))] = _one_line(shape)
        if body and body[-1][0] == origin:
            body[-1][1].append(shape)
        else:
            body.append((origin, [shape]))
    return chrome, tables, body


def _chrome_line(field: str, shape: dict[str, Any]) -> Iterator[str]:
    text = _one_line(shape)
    if not text:
        return
    yield {"kicker": f"**{text}**", "title": f"### {text}"}.get(field, text)
    yield ""


def _block(origin: str, shapes: list[dict[str, Any]]) -> Iterator[str]:
    """One placement's words, under the origin that drew them."""
    written: list[str] = []
    for shape in shapes:
        rendered = shape.get("rendered", "native")
        if rendered == "picture":
            written.append("*(picture)*")
            continue
        lines = shape.get("lines") or ([shape["text"]] if shape.get("text") else [])
        note = " *(rendered as an image)*" if rendered == "image" else ""
        written.extend(f"{_bullet(line)}{note}" for line in lines)
    component = origin.rpartition(".")[2]
    if not written:
        # A chart or a picture holds no text, and a slide that is one would otherwise
        # read as empty.
        if component in _UNSPOKEN:
            return
        written = [f"*({component})*"]
    yield f"`{origin}`"
    yield ""
    yield from written
    yield ""


def _table(grid: dict[tuple[int, int], str]) -> Iterator[str]:
    """A recorded cell grid as a markdown table, its first row the header."""
    rows = max(r for r, _ in grid)
    cols = max(c for _, c in grid)
    for row in range(1, rows + 1):
        yield "| " + " | ".join(grid.get((row, col), "") for col in range(1, cols + 1)) + " |"
        if row == 1:
            yield "|" + "---|" * cols
    yield ""


def _one_line(shape: dict[str, Any]) -> str:
    lines = shape.get("lines") or []
    return str(lines[0] if lines else (shape.get("text") or "")).strip()


def _bullet(line: str) -> str:
    """A recorded bullet already carries its mark; give markdown one it understands."""
    text = str(line)
    return f"- {text.lstrip('•').strip()}" if text.lstrip().startswith("•") else text
