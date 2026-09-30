"""A deckwright deck's placements, read back whole from the names its shapes carry.

Each shape the build drew is named for the placement that drew it, so the shapes of one
placement can be gathered and redrafted as that component — a card as a card, a chart as
a chart with its data — where a stranger's deck gives only its words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from pptx.enum.dml import MSO_COLOR_TYPE, MSO_FILL
from pptx.enum.shapes import MSO_SHAPE_TYPE

from deckwright.components.bullets import MARKER
from deckwright.spec._chartback import chart_block
from deckwright.spec._figures import Picture, picture
from deckwright.spec._motionback import read_animate, read_reveals, read_transition
from deckwright.spec._origin import Origin, origin_of
from deckwright.spec._tree import (
    MAX_GROUP_DEPTH,
    flat,
    is_picture,
    linked_text,
    members,
    shape_type,
    table_grid,
)

Box = tuple[float, float, float, float]  # x, y, w, h as fractions of the canvas

_AUTO = re.compile(r"p\d+")
_PAIRED = ("card", "panel")
_CITE = "— "


@dataclass(frozen=True)
class Recovered:
    """A placement read back: its component's mapping, where it sat, and what it is called."""

    component: str
    body: dict[str, Any]
    box: Box
    key: str  # the placement's id, its pN, or its morph name
    id: str | None = None
    morph: str | None = None
    reveals: str | None = None
    note: str | None = None
    words: tuple[str, ...] = ()
    media: tuple[tuple[str, bytes], ...] = ()  # a picture's file, by the name ``body`` gives it
    painted: tuple[str, str | None] | None = None  # a plate's fill and its words' ink, as hex


@dataclass(frozen=True)
class Recovery:
    """A slide's placements read back, the shapes they account for, and the slide's motion."""

    placed: tuple[Recovered, ...] = ()
    notes: tuple[str, ...] = ()
    claimed: frozenset[Any] = frozenset()
    animate: str | None = None
    transition: str | None = None


def recover(slide, *, index: int, canvas: tuple[int, int], boxes: dict[str, Box]) -> Recovery:
    """The placements ``slide``'s named shapes came from; nothing for a stranger's slide.

    ``boxes`` maps a placement's origin to the rectangle its manifest recorded. Without one,
    a placement's box is the union of its shapes'.
    """
    groups: dict[str, list[Any]] = {}
    origins: dict[str, Origin] = {}
    for shape in _built(slide.shapes):
        found = origin_of(str(shape.name))
        if found is not None:
            groups.setdefault(found.token, []).append(shape)
            origins.setdefault(found.token, found)
    if not groups:
        return Recovery()
    placed: list[Recovered] = []
    notes: list[str] = []
    claimed: set[Any] = set()
    for token, shapes in groups.items():
        if len({str(s.name) for s in shapes}) < len(shapes):
            continue  # a copy kept its original's name: two placements, left to the words walk
        origin = origins[token]
        name = f"slide{index}-{_safe(origin.placement)}"
        if origin.component == "image":
            body, note, words, media = _image(shapes, name=name)
        else:
            (body, note, words), media = _body(origin.component, shapes), ()
            if body is None and not words:
                body, _, words, media = _image(shapes, name=name)
                note = (
                    f"drafted as an image: a {origin.component} placement's source is not in "
                    "the file, only its picture"
                )
        if body is None:
            continue  # left to the words walk, which names it and keeps its alt text
        if note:
            notes.append(f"{token}: {note}")
        claimed.update(shape._element for shape in shapes)
        placed.append(
            Recovered(
                component=next(iter(body)),
                body=body,
                box=boxes.get(token) or _union(shapes, canvas),
                key=origin.placement,
                id=_id(origin, position=len(placed) + 1),
                morph=origin.placement if origin.morph else None,
                words=words,
                media=media,
                painted=_painted(shapes) if origin.component in _PAIRED else None,
            )
        )
    wanted, unsaid = read_reveals(slide, keys={item.key for item in placed})
    tokens = {origin.placement: token for token, origin in origins.items()}
    notes += [f"{tokens[key]}: {why}" for key, why in unsaid]
    return Recovery(
        placed=tuple(_revealed(item, wanted) for item in placed),
        notes=tuple(notes),
        claimed=frozenset(claimed),
        animate=read_animate(slide),
        transition=read_transition(slide),
    )


def _revealed(item: Recovered, wanted: dict[str, str]) -> Recovered:
    """``item`` with its ``reveals:``, and the id a trigger must be named by."""
    if item.key in wanted.values() and item.id is None:
        item = replace(item, id=item.key)
    if item.key in wanted:
        item = replace(item, reveals=wanted[item.key])
    return item


def _built(shapes, depth: int = 0):
    """Every shape in tree order — the build's own — with a group's children in its place."""
    built, _ = members(shapes)
    for shape in built:
        if shape_type(shape) is MSO_SHAPE_TYPE.GROUP and depth < MAX_GROUP_DEPTH:
            yield from _built(shape.shapes, depth + 1)
        else:
            yield shape


def _id(origin: Origin, *, position: int) -> str | None:
    """The ``id:`` that keeps the placement's shapes named as they were: an author's own id,
    or a ``pN`` the draft's order would no longer give it."""
    if origin.morph:
        return None
    if not _AUTO.fullmatch(origin.placement) or origin.placement != f"p{position}":
        return origin.placement
    return None


def _body(
    component: str, shapes: list[Any]
) -> tuple[dict[str, Any] | None, str | None, tuple[str, ...]]:
    """The component's mapping, a note on what did not come back, and its words."""
    texts = [s for s in shapes if s.has_text_frame and _lines(s)]
    if component == "card":
        return _card(shapes, texts)
    if component == "bullets":
        return _bullets(texts)
    if component == "prose" and len(texts) == 1:
        lines = _lines(texts[0])
        body: dict[str, Any] = {"paragraphs": list(lines)}
        if len(lines) > 1 and lines[-1].startswith(_CITE):
            body = {"paragraphs": list(lines[:-1]), "cite": lines[-1][len(_CITE) :]}
        return {"prose": body}, None, lines
    if component == "table" and shapes[0].has_table:
        grid = table_grid(shapes[0])
        if len(grid) > 1:
            head, *rows = grid
            return {"table": {"header": list(head), "rows": [list(r) for r in rows]}}, None, ()
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
    words = tuple(line.removeprefix(MARKER) for shape in texts for line in _lines(shape))
    if not words:
        return None, f"not converted: a {component} placement, which holds no words", ()
    return (
        {"bullets": {"items": list(words)}},
        f"drafted as bullets: a {component} placement's fields are not in the file, only its words",
        words,
    )


def _image(
    shapes: list[Any], *, name: str
) -> tuple[dict[str, Any] | None, str | None, tuple[str, ...], tuple[tuple[str, bytes], ...]]:
    """An image placement's picture, as the file the draft will write beside it, and the
    lines set over it."""
    found = next((s for s in shapes if is_picture(s)), None)
    got = picture(found, name=name) if found is not None else None
    if not isinstance(got, Picture):
        return None, None, (), ()
    body = got.image()
    texts = [s for s in shapes if s.has_text_frame and _lines(s)]
    over = tuple(line for shape in texts for line in _lines(shape))
    if over:
        body["over"] = list(over)
    scrim = any(s is not found and s not in texts for s in shapes)
    note = " and ".join(
        (["its lines come back at the default rung"] if over else [])
        + (["its scrim is solved afresh"] if scrim else [])
    )
    return {"image": body}, note or None, over, ((got.name, got.blob),)


def _painted(shapes: list[Any]) -> tuple[str, str | None] | None:
    """The plate's solid fill, and the ink of the first run on it that names a colour."""
    plate = next((s for s in shapes if shape_type(s) is MSO_SHAPE_TYPE.AUTO_SHAPE), None)
    if plate is None or plate.fill.type != MSO_FILL.SOLID:
        return None
    runs = (
        run
        for shape in shapes
        if shape.has_text_frame
        for paragraph in shape.text_frame.paragraphs
        for run in paragraph.runs
    )
    ink = next(
        (str(r.font.color.rgb) for r in runs if r.font.color.type == MSO_COLOR_TYPE.RGB), None
    )
    return str(plate.fill.fore_color.rgb), ink


def _safe(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", key).strip("-") or "image"


def _card(
    shapes: list[Any], texts: list[Any]
) -> tuple[dict[str, Any] | None, str | None, tuple[str, ...]]:
    lines = tuple(line for shape in texts for line in _lines(shape))
    body: dict[str, Any] = {}
    if len(lines) >= 2:
        body = {"heading": lines[0], "body": " ".join(lines[1:])}
    elif lines:
        run = texts[0].text_frame.paragraphs[0].runs
        body = {"heading" if run and run[0].font.bold else "body": lines[0]}
    marks = [s for s in shapes[1:] if s not in texts]
    note = "its icon is not in the file by name, so it is left out" if marks else None
    return {"card": body}, note, lines


def _bullets(texts: list[Any]) -> tuple[dict[str, Any] | None, str | None, tuple[str, ...]]:
    heading = [s for s in texts if not _lines(s)[0].startswith(MARKER)]
    columns = [s for s in texts if _lines(s)[0].startswith(MARKER)]
    items = [line.removeprefix(MARKER) for shape in columns for line in _lines(shape)]
    if not items:
        return None, "not converted: a bullets placement with no items", ()
    body: dict[str, Any] = {}
    if heading:
        body["heading"] = _lines(heading[0])[0]
    if len(columns) > 1:
        body["columns"] = len(columns)
    body["items"] = items
    words = ((body["heading"],) if "heading" in body else ()) + tuple(items)
    return {"bullets": body}, None, words


def _lines(shape) -> tuple[str, ...]:
    return tuple(
        line for line in (flat(linked_text(p)) for p in shape.text_frame.paragraphs) if line
    )


def _union(shapes: list[Any], canvas: tuple[int, int]) -> Box:
    width, height = canvas
    edges = [
        (s.left, s.top, s.left + s.width, s.top + s.height)
        for s in shapes
        if None not in (s.left, s.top, s.width, s.height)
    ]
    left = min(e[0] for e in edges)
    top = min(e[1] for e in edges)
    return (
        left / width,
        top / height,
        (max(e[2] for e in edges) - left) / width,
        (max(e[3] for e in edges) - top) / height,
    )
