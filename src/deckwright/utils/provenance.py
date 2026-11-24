"""Which manifest describes a deck: the one beside it, else the one recording its build id."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

from deckwright.errors import SpecError

# What a built deck carries in `dc:identifier`, ahead of its build id.
BUILD_PREFIX = "deckwright:"


def find_manifest(deck: Path, identifier: str | None) -> Path | None:
    """The sibling manifest, else the one beside ``deck`` whose build id ``identifier`` names."""
    sibling = deck.with_suffix(".manifest.json")
    if sibling.is_file():
        return sibling
    ident = identifier or ""
    if not ident.startswith(BUILD_PREFIX):
        return None
    for candidate in sorted(deck.parent.glob("*.manifest.json")):
        try:
            recorded = read_manifest(candidate, records=False).get("build_id")
        except SpecError:
            continue
        if recorded == ident[len(BUILD_PREFIX) :]:
            return candidate
    return None


def _number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:  # an integer no float holds
        return False


def _whole(value: Any) -> bool:
    if isinstance(value, int):
        return not isinstance(value, bool)
    return _number(value) and value.is_integer()


def _text(value: Any) -> bool:
    return isinstance(value, str)


def _listed(check: Callable[[Any], bool]) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, list) and all(check(v) for v in value)


def _box(value: Any) -> bool:
    """A keyed box of four numbers. A positional one passes: ``record.box_of`` refuses it."""
    if isinstance(value, list) or value == {}:
        return True
    return isinstance(value, dict) and all(_number(value.get(k)) for k in "xywh")


def _canvas(value: Any) -> bool:
    return isinstance(value, dict) and all(value.get(k) is None or _number(value[k]) for k in "wh")


# What a build writes a field as: the test, and how a refusal names it.
_KINDS: dict[str, tuple[Callable[[Any], bool], str]] = {
    "text": (_text, "text"),
    "number": (_number, "a number"),
    "whole": (_whole, "a whole number"),
    "flag": (lambda v: isinstance(v, bool), "true or false"),
    "texts": (_listed(_text), "a list of text"),
    "numbers": (_listed(_number), "a list of numbers"),
    "steps": (_listed(_listed(_text)), "a list of steps, each a list of shape names"),
    "box": (_box, "a box of four numbers"),
    "canvas": (_canvas, "a slide size"),
}

TOP_FIELDS = {
    "build_id": "text",
    "deckwright": "text",
    "spec": "text",
    "spec_hash": "text",
    "deck_hash": "text",
    "deck": "text",
    "theme": "text",
    "theme_hash": "text",
    "theme_path": "text",
    "compose_layout": "text",
    "canvas": "canvas",
}
SLIDE_FIELDS = {
    "background": "text",
    "section": "text",
    "notes": "text",
    "backdrop": "flag",
    "transition": "text",
    "chrome": "text",
}
# The per-slide lists `qa` and `diff` walk record by record: what one record is called, the
# field that names it, and its fields.
RECORD_FIELDS: dict[str, tuple[str, str | None, dict[str, str]]] = {
    "shapes": (
        "shape",
        "name",
        {
            "shape_id": "whole",
            "name": "text",
            "box": "box",
            "text": "text",
            "lines": "texts",
            "font_pt": "number",
            "line_pt": "numbers",
            "space_after_pt": "numbers",
            "fg": "text",
            "bg": "text",
            "rendered": "text",
            "bleed": "flag",
            "plate": "flag",
            "annotation": "flag",
            "fill": "text",
            "ground": "text",
            "alt": "text",
            "decorative": "flag",
            "goto": "text",
            "links": "texts",
        },
    ),
    "placements": (
        "placement",
        "origin",
        {"origin": "text", "component": "text", "box": "box", "bleed": "flag"},
    ),
    "animations": (
        "animation",
        None,
        {"kind": "text", "clicks": "whole", "steps": "steps", "trigger": "text"},
    ),
}


def read_manifest(path: Path, *, records: bool = True) -> dict[str, Any]:
    """The build manifest at ``path``: a JSON object whose slides, if any, each carry their
    own number and, with ``records``, hold their shapes, placements and animations as lists
    of records, every field of the type a build writes. ``find_manifest`` and ``extract``
    pass ``records=False``: they read past a damaged list.

    Raises:
        SpecError: it cannot be read, is not a JSON object, holds a ``slides`` that is not a
            list of slide records, does not number its slides or numbers two alike, or (with
            ``records``) holds a slide's shapes, placements or animations as something other
            than a list of records, or a field as a value of the wrong type.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise _unreadable(path, f"{type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise _unreadable(path, f"it holds a JSON {type(data).__name__}, not an object")
    if records:
        _typed(path, data, TOP_FIELDS)
    if "slides" not in data:
        return data
    slides = data["slides"]
    if not isinstance(slides, list) or not all(isinstance(s, dict) for s in slides):
        raise _unreadable(path, "'slides' is not a list of slide records")
    seen: set[int] = set()
    for slide in slides:
        index = slide.get("index")
        if isinstance(index, bool) or not isinstance(index, int) or index < 1:
            raise _unreadable(path, f"a slide's index is {index!r}, not a slide number")
        if index in seen:
            raise _unreadable(path, f"two slides are numbered {index}")
        seen.add(index)
        if not records:
            continue
        _typed(path, slide, SLIDE_FIELDS, of=f" of slide {index}")
        for key, (what, namer, fields) in RECORD_FIELDS.items():
            held = slide.get(key)
            if held is None:
                continue
            if not (isinstance(held, list) and all(isinstance(r, dict) for r in held)):
                raise _unreadable(path, f"slide {index}'s {key} is not a list of records")
            for place, record in enumerate(held, start=1):
                name = record.get(namer) if namer else None
                called = _shown(name) if isinstance(name, str) and name else f"record {place}"
                _typed(path, record, fields, of=f" of slide {index}'s {what} {called}")
    return data


def _typed(path: Path, held: dict[str, Any], fields: dict[str, str], *, of: str = "") -> None:
    """Refuse the first of ``fields`` that ``held`` carries as a type no build writes."""
    for field, kind in fields.items():
        value = held.get(field)
        check, wanted = _KINDS[kind]
        if value is not None and not check(value):
            raise _unreadable(path, f"{field}{of} is {_shown(value)}, not {wanted}")


def _shown(value: Any) -> str:
    shown = repr(value)
    return shown if len(shown) <= 40 else f"{shown[:39]}…"


def _unreadable(path: Path, why: str) -> SpecError:
    return SpecError(
        f"{path.name} is not a build manifest deckwright can read ({why}) — build the spec "
        f"again with --out elsewhere and pass the manifest it writes with --manifest"
    )
