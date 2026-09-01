"""Text helpers: near-match suggestions, and how tall a string wraps."""

from __future__ import annotations

from collections.abc import Iterable
from difflib import get_close_matches
from math import ceil

from deckwright.utils._metrics import (  # noqa: F401 — re-exported; _metrics is private
    MEASURED_FAMILIES,
    advance_em,
    measured,
    table_for,
)

LINE_HEIGHT = 1.2
"""Single-spaced line advance as a multiple of nominal point size, in the faces we set."""

_CUTOFF = 0.6

# Per-character summation cannot see kerning, hinting, or a renderer's own spacing;
# one margin over the summed width covers all three.
_MARGIN = 1.04


def closest_match(name: str, options: Iterable[str]) -> str | None:
    """The single closest match to ``name`` among ``options``, or ``None``."""
    matches = get_close_matches(name, list(options), n=1, cutoff=_CUTOFF)
    return matches[0] if matches else None


def text_em(text: str, face: str | None = None) -> float:
    """Width of ``text`` in ems when set in ``face``, held ``_MARGIN`` wide.

    ``face`` routes to that family's measured advances (bold folded in); ``None`` or
    a face with no table gets the ceiling across every measured face.
    """
    table = table_for(face)
    return _MARGIN * sum(advance_em(ch, table) for ch in text)


def wrapped_lines(text: str, *, width_in: float, size_pt: float, face: str | None = None) -> int:
    """How many lines ``text`` occupies when wrapped to ``width_in`` at ``size_pt``.

    ``_MARGIN`` errs wide by design, so a box is never sized a line short of its text.
    """
    if width_in <= 0 or size_pt <= 0:
        return 1
    capacity = width_in * 72 / size_pt
    space = _MARGIN * advance_em(" ", table_for(face))
    lines, used = 1, 0.0
    for word in text.split():
        width = text_em(word, face)
        need = width if used == 0.0 else used + space + width
        if need <= capacity:
            used = need
            continue
        if used > 0.0:
            lines += 1
        rows = max(1, ceil(width / capacity))
        lines += rows - 1
        used = width - (rows - 1) * capacity
    return lines
