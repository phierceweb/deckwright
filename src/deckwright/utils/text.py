"""Text helpers: near-match suggestions, and how tall a string wraps.

A string is measured as it shows, so a ``[words](address)`` link counts its words only.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Iterator
from difflib import get_close_matches
from math import ceil

from deckwright.utils._metrics import (  # noqa: F401 — re-exported; _metrics is private
    MEASURED_FAMILIES,
    advance_em,
    measured,
    table_for,
)
from deckwright.utils._cjk import CJK_EM, HANG, atoms, carries_cjk, is_cjk, is_hangul
from deckwright.utils.links import plain

LINE_HEIGHT = 1.2
"""Single-spaced line advance as a multiple of nominal point size, in the faces we set."""

_CUTOFF = 0.6

# Per-character summation cannot see kerning, hinting, or a renderer's own spacing;
# one margin over the summed width covers all three.
_MARGIN = 1.04

_BREAK_AFTER = frozenset("-‐–—")
_WIDE = ("W", "F")


def closest_match(name: str, options: Iterable[str]) -> str | None:
    """The single closest match to ``name`` among ``options``, or ``None``."""
    matches = get_close_matches(name, list(options), n=1, cutoff=_CUTOFF)
    return matches[0] if matches else None


def text_em(text: str, face: str | None = None, *, links: bool = True) -> float:
    """Width of ``text`` in ems when set in ``face``, held ``_MARGIN`` wide.

    ``face`` routes to that family's measured advances (bold folded in); ``None`` or
    a face with no table gets ``CEILING``. ``links=False`` measures text already shown,
    such as a manifest line, exactly as written.
    """
    return _em(plain(text) if links else text, face)


def _em(shown: str, face: str | None) -> float:
    table = table_for(face)
    return _MARGIN * sum(advance_em(ch, table) for ch in shown)


def wrapped_lines(
    text: str, *, width_in: float, size_pt: float, face: str | None = None, links: bool = True
) -> int:
    """How many lines ``text`` occupies when wrapped to ``width_in`` at ``size_pt``.

    ``_MARGIN`` errs wide by design, so a box is never sized a line short of its text.
    """
    if width_in <= 0 or size_pt <= 0:
        return 1
    shown = plain(text) if links else text
    capacity = width_in * 72 / size_pt
    if carries_cjk(shown):
        return _cjk_lines(shown, capacity=capacity, face=face)
    space = _MARGIN * advance_em(" ", table_for(face))
    lines, used = 1, 0.0
    for word in shown.split():
        width = _em(word, face)
        need = width if used == 0.0 else used + space + width
        if need <= capacity:
            used = need
            continue
        if used > 0.0:
            lines += 1
        # A lone word breaks where its real width does, as `overlong_word` measures it.
        rows = max(1, ceil(width / _MARGIN / capacity))
        lines += rows - 1
        used = width - (rows - 1) * capacity
    return lines


def _cjk_lines(text: str, *, capacity: float, face: str | None) -> int:
    """Lines for text carrying CJK, broken where ``_cjk.atoms`` allows.

    A hanging mark at the end of a full line is drawn past its edge rather than carrying
    the character before it down, so it is not charged against the line.
    """
    space = _MARGIN * advance_em(" ", table_for(face))
    lines, used, gap = 1, 0.0, 0.0
    for atom in atoms(text):
        if atom.isspace() and not is_cjk(atom):
            gap += space if used > 0.0 else 0.0
            continue
        width = _em(atom, face)
        need = used + gap + width if used > 0.0 else width
        hung = need - _MARGIN * CJK_EM if atom[-1] in HANG else need
        if need <= capacity or hung <= capacity:
            used, gap = min(need, capacity), 0.0
            continue
        if used > 0.0:
            lines += 1
        rows = max(1, ceil(width / _MARGIN / capacity))
        lines += rows - 1
        used, gap = width - (rows - 1) * capacity, 0.0
    return lines


def estimate_caveat(*faces: str | None) -> str:
    """The clause a fit refusal ends with when its estimate ran on a face with no table."""
    unmeasured = list(dict.fromkeys(f for f in faces if f and not measured(f)))
    if not unmeasured:
        return ""
    names = ", ".join(repr(f) for f in unmeasured)
    return f" ({names} has no width table, so this estimate errs wide)"


def _unbreakable_runs(text: str) -> Iterator[str]:
    """The runs of ``text`` no line break can fall inside.

    A renderer breaks at a space, after a hyphen or dash, and on either side of a wide or
    CJK character other than hangul, since Korean breaks at spaces. Not after a slash:
    LibreOffice sets a URL broken mid-word. Where a CJK line really breaks, kinsoku
    included, is ``_cjk.atoms``.
    """
    run = ""
    for ch in text:
        if ch.isspace():
            if run:
                yield run
            run = ""
        elif (unicodedata.east_asian_width(ch) in _WIDE or is_cjk(ch)) and not is_hangul(ch):
            if run:
                yield run
            yield ch
            run = ""
        else:
            run += ch
            if ch in _BREAK_AFTER:
                yield run
                run = ""
    if run:
        yield run


def overlong_word(
    text: str, *, width_in: float, size_pt: float, face: str | None = None
) -> tuple[str, float] | None:
    """The first unbreakable run of ``text`` wider than ``width_in``, with the width it needs.

    Nothing can wrap inside one, so a renderer breaks it mid-word. Measured without
    ``_MARGIN``: a sizing allowance would refuse runs that fit.
    """
    table = table_for(face)
    for word in _unbreakable_runs(plain(text)):
        need = sum(advance_em(ch, table) for ch in word) * size_pt / 72
        if need > width_in:
            return word, need
    return None
