"""The spec a build kept beside its deck, read for the fields the file does not carry.

A placement takes its component and fields from that spec only while the deck still holds
the shapes and words the build drew for it. Whatever else the file states and `extract`
reads — the timing, alt text, a plate's colour — still comes from the file, and wins.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pw_foundation.exceptions import FlowException

from deckwright.components.card import names_file
from deckwright.paths import SCRATCH
from deckwright.spec._origin import counted, token_of
from deckwright.spec._scalars import SpecLoader
from deckwright.utils.a11y import described, is_file_name
from deckwright.utils.provenance import BUILD_PREFIX

FROM_SPEC = "fields the file does not show come from the spec it was built from"

# A field naming a file beside the spec, which a draft written anywhere else cannot reach.
_ON_DISK = {"card": "icon", "document": "source", "image": "src"}
# What the file states even where it was not read back as this component: the colour of a
# plate or a glyph, which the draft resolves to a pair or role, and a figure's alt text.
_STATED = {
    "card": ("pair", "alt", "decorative"),
    "panel": ("pair",),
    "icon": ("ink", "alt", "decorative"),
    "image": ("alt", "decorative"),
    "equation": ("alt", "decorative"),
}
# Fields holding words: once the file's words are the build's, the spec's way of writing them
# stands, a spanned header cell, a total row and a nested item included.
_WORDS = {
    "bullets": ("heading", "items"),
    "card": ("heading", "body"),
    "prose": ("paragraphs", "cite"),
    "table": ("header", "rows", "total"),
}
_CELL = re.compile(r"r(\d+)c(\d+)")
_SLIDE = re.compile(r"s(\d+)\.")
_HASHED = 16  # hex digits of a build's spec_hash, as compile.build._digest cuts it
_LARGEST = 16 * 1024 * 1024  # bytes; no spec a build kept comes near it


@dataclass(frozen=True)
class Kept:
    """A placement as the spec wrote it, and each shape's words as the build drew them."""

    component: str
    fields: dict[str, Any]
    texts: dict[str, str] = field(default_factory=dict)
    id: str | None = None
    align: str = "left"
    anchor: str = "top"
    bleed: bool = False


def kept_placements(
    manifest: Path, data: dict[str, Any], identifier: str, names: list[list[str]]
) -> dict[int, dict[str, Kept]]:
    """Each slide's placements by the origin their shapes are named for, read from the spec
    the build kept beside ``manifest``, for a deck whose slides hold shapes named ``names``.

    Empty unless ``identifier`` is that build's id, and the kept spec is a file that still
    hashes to the manifest's ``spec_hash``, names no ``extends:`` module and parses. A slide is
    left out unless it holds a shape named for it and none named for another.
    """
    from deckwright.spec.parse import parse_deck_text

    if identifier != f"{BUILD_PREFIX}{data.get('build_id')}":
        return {}
    kept = manifest.parent / SCRATCH / f"{manifest.name.removesuffix('.manifest.json')}.deck.yaml"
    recorded = str(data.get("spec_hash") or "")
    try:
        if not kept.is_file() or kept.stat().st_size > _LARGEST:  # a pipe would hold the read
            return {}
        raw = kept.read_bytes()
    except OSError:
        return {}
    if hashlib.sha256(raw).hexdigest()[:_HASHED] != recorded:
        return {}
    try:
        text = raw.decode("utf-8")
        if _extends(text):
            return {}
        spec = parse_deck_text(text, source=kept)
    except (FlowException, UnicodeDecodeError, yaml.YAMLError, RecursionError):
        return {}
    try:
        drawn = {int(s["index"]): _words(s.get("shapes") or []) for s in data.get("slides") or []}
    except (AttributeError, TypeError):
        return {}
    out: dict[int, dict[str, Kept]] = {}
    for slide in spec.slides:
        if slide.index > len(names) or not _in_place(names[slide.index - 1], slide.index):
            continue
        for position, placement in enumerate(slide.place, start=1):
            token = token_of(slide.index, position, placement)
            texts = _texts(drawn.get(slide.index, {}), token)
            out.setdefault(slide.index, {})[token] = Kept(
                placement.component,
                dict(placement.body),
                texts,
                placement.id,
                placement.align,
                placement.anchor,
                placement.bleed,
            )
    return out


def _in_place(names: list[str], index: int) -> bool:
    """Whether a slide holds a shape the build named for slide ``index`` and none named for
    another; a morph name carries no slide, so it shows nothing."""
    numbered = [int(found[1]) for found in map(_SLIDE.match, names) if found]
    return bool(numbered) and all(number == index for number in numbered)


def _extends(text: str) -> bool:
    """Whether a spec names an ``extends:`` module, which parsing it would import and run."""
    config = next(yaml.load_all(text, Loader=SpecLoader), None)
    return isinstance(config, dict) and bool(config.get("extends"))


@dataclass(frozen=True)
class Supplied:
    """A placement's body and note, and the fields of its own the file does not carry."""

    body: dict[str, Any] | None
    note: str | None
    id: str | None = None
    align: str = "left"
    anchor: str = "top"
    bleed: bool = False


def supply(
    kept: Kept | None,
    body: dict[str, Any] | None,
    shapes: list[Any],
    *,
    note: str | None,
    morph: bool,
    bled: bool,
) -> Supplied:
    """What ``kept`` gives a placement the file read as ``body`` with ``note``: nothing unless
    its ``shapes`` are still the build's, holding the build's words."""
    merged = _merged(kept, body, shapes) if kept and _unchanged(shapes, kept.texts) else None
    if kept is None or merged is None:
        return Supplied(body, note)
    named = kept.id if morph else None
    if merged[0] != body:
        body, note = merged
    elif note is None and (
        named or (kept.align, kept.anchor) != ("left", "top") or (kept.bleed and not bled)
    ):
        note = FROM_SPEC
    return Supplied(body, note, named, kept.align, kept.anchor, kept.bleed)


def _unchanged(shapes: list[Any], texts: dict[str, str]) -> bool:
    """Whether ``shapes`` are the ones the build drew for a placement, holding its words."""
    names = {str(shape.name) for shape in shapes}
    drawn = {name for name in texts if counted(name)[1]}
    if not drawn <= names or not names <= texts.keys():
        return False
    for shape in shapes:
        name = str(shape.name)
        if shape.has_table:
            if _cells(shape) != _recorded_cells(texts, counted(name)[0]):
                return False
            continue
        if not shape.has_text_frame:
            continue
        was = texts.get(name, "")
        if _flat(shape.text_frame.text) != _flat(was):
            return False
    return True


def _merged(
    kept: Kept, body: dict[str, Any] | None, shapes: list[Any]
) -> tuple[dict[str, Any], str] | None:
    """``kept``'s component and fields under every field the file states besides its words,
    and the note that says so: ``body``'s fields when the file was read as the same
    component, and ``_STATED``.

    None when the spec names a file that ``body`` does not supply and the component cannot
    go without it.
    """
    stated = dict(body[kept.component]) if body and kept.component in body else {}
    for key in _WORDS.get(kept.component, ()):
        stated.pop(key, None)
    fields = dict(kept.fields)
    note = FROM_SPEC
    for key in _STATED.get(kept.component, ()):
        fields.pop(key, None)
    if "alt" in _STATED.get(kept.component, ()):
        fields.update(_description(shapes))
    on_disk = _ON_DISK.get(kept.component)
    if on_disk in fields and on_disk not in stated and names_file(str(fields[on_disk])):
        if kept.component != "card":
            return None
        # A card's alt text describes its icon, so it goes with it.
        for key in (on_disk, "alt", "decorative"):
            fields.pop(key, None)
        note += f"; its {on_disk} is a file beside that spec, so it is left out"
    fields.update(stated)
    return {kept.component: fields}, note


def _description(shapes: list[Any]) -> dict[str, Any]:
    """The alt text or decorative mark on the placement's figure, as fields."""
    for shape in shapes:
        alt, decorative = described(shape)
        if decorative:
            return {"decorative": True}
        if alt and not is_file_name(alt):
            return {"alt": alt}
    return {}


def _words(records: list[dict[str, Any]]) -> dict[str, str]:
    """Each shape record's name and the words it holds."""
    return {str(r.get("name", "")): str(r.get("text") or "") for r in records}


def _texts(drawn: dict[str, str], token: str) -> dict[str, str]:
    """The records the placement's shapes answer for."""
    return {n: words for n, words in drawn.items() if n.startswith((f"{token}#", f"{token}."))}


def _cells(frame) -> dict[tuple[int, int], str]:
    """A table's non-empty cells by row and column, counted from 1 as the build names them."""
    return {
        (r, c): _flat(cell.text)
        for r, row in enumerate(frame.table.rows, start=1)
        for c, cell in enumerate(row.cells, start=1)
        if _flat(cell.text)
    }


def _recorded_cells(texts: dict[str, str], head: str) -> dict[tuple[int, int], str]:
    """The cells the build recorded under ``head``, as :func:`_cells` reads a table."""
    out = {}
    for name, text in texts.items():
        found = _CELL.fullmatch(name.removeprefix(f"{head}.")) if name.startswith(head) else None
        if found and _flat(text):
            out[(int(found[1]), int(found[2]))] = _flat(text)
    return out


def _flat(text: str) -> str:
    return " ".join(text.split())
