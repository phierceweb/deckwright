"""Name a drawn icon by its outline.

deckwright writes every glyph's path on one unit grid (``icons.draw.place_glyph``), so a
glyph draws the same ``a:path`` at any size and in any colour, and a PowerPoint save keeps
it. The path's commands and points are the glyph's fingerprint.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

from lxml import etree
from pptx.oxml.ns import qn

from deckwright.icons.load import glyphs
from deckwright.icons.path import UNITS
from deckwright.icons.shapes import SHAPES
from deckwright.utils.xml import fromstring as parse_xml

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_PATH = f"{qn('p:spPr')}/{qn('a:custGeom')}/{qn('a:pathLst')}/{qn('a:path')}"

Print = tuple[Any, ...]


def glyph_name(shape: Any, dirs: tuple[Path, ...] = ()) -> str | None:
    """The name of the glyph ``shape`` draws, looked up in ``dirs`` and the shipped set, or
    ``None`` for a shape that is no glyph a name reaches."""
    path = shape._element.find(_PATH)
    if path is None or len(path.getparent()) != 1:
        return None
    return _index(dirs).get(_print(path))


def _print(path: Any) -> Print:
    return (
        path.get("w"),
        path.get("h"),
        tuple(
            (
                etree.QName(command).localname,
                tuple(sorted(command.attrib.items())),
                tuple((pt.get("x"), pt.get("y")) for pt in command.iter(f"{{{_A}}}pt")),
            )
            for command in path
        ),
    )


@functools.cache
def _index(dirs: tuple[Path, ...]) -> dict[Print, str]:
    """Each fingerprint's name. ``glyphs`` yields a directory's before the shipped set's, and
    each alphabetically, so the first name kept is the one ``load`` reaches first among
    aliases that draw alike. A plain shape draws as a preset, not a path."""
    found: dict[Print, str] = {}
    for glyph in glyphs(dirs):
        if glyph.name not in SHAPES:
            path = parse_xml(
                f'<a:path xmlns:a="{_A}" w="{UNITS}" h="{UNITS}">{glyph.drawingml()}</a:path>'.encode()
            )
            found.setdefault(_print(path), glyph.name)
    return found
