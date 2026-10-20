"""Per-character advance tables, in ems, baked from real font files (``docs/utils.md``).

Each table is a per-character ``max`` over its family's Regular and Bold cuts, so no
caller passes a bold flag; ``CEILING`` is the max across Carlito, Liberation Sans,
Verdana and DejaVu Sans, not across the brand faces in ``_metrics_faces``.
Each is packed as one string of advances in ``GLYPHS`` order; regenerate them with
``.venv/bin/python tests/utils/test_metrics.py``.
"""

from __future__ import annotations

from functools import lru_cache

from deckwright.utils._cjk import CJK_EM, is_cjk
from deckwright.utils._metrics_faces import (
    AMATIC,
    BARLOW_SEMI_CONDENSED,
    BEBAS_NEUE,
    COURIER,
    MONO,
    MONTSERRAT,
    OPEN_SANS,
    POPPINS,
    SNIGLET,
    _packed,
)

CALIBRI = _packed(
    "0.2261 0.3257 0.4385 0.498 0.5068 0.729 0.7046 0.2334 0.3115 0.3115 0.498 0.498 0.2578 0.3062 0.2671 0.4297 0.5068 0.5068 0.5068 0.5068 0.5068 0.5068 0.5068 0.5068 0.5068 0.5068 0.2759 0.2759 0.498 0.498 0.498 0.4634 0.8984 0.606 0.5605 0.5332 0.6304 0.4883 0.4595 0.6372 0.6309 0.2666 0.3311 0.5469 0.4229 0.874 0.6587 0.6763 0.5322 0.686 0.563 0.4727 0.4951 0.6528 0.5913 0.9062 0.5508 0.5195 0.478 0.3247 0.4297 0.3247 0.498 0.498 0.3003 0.4937 0.5366 0.4229 0.5366 0.5034 0.3164 0.4741 0.5366 0.2456 0.2554 0.48 0.2456 0.8135 0.5366 0.5376 0.5366 0.5366 0.3555 0.3989 0.3467 0.5366 0.4731 0.7451 0.4595 0.4736 0.3975 0.3438 0.4751 0.3438 0.498 0.2578 0.2578 0.4351 0.4351 0.498 0.9053 0.7114 0.5068 0.5068 0.3423 0.498 0.498"
)
"""Carlito Regular+Bold — what Calibri renders as everywhere this project renders."""

ARIAL = _packed(
    "0.2778 0.333 0.4741 0.5562 0.5562 0.8892 0.7222 0.2378 0.333 0.333 0.3892 0.584 0.2778 0.333 0.2778 0.2778 0.5562 0.5562 0.5562 0.5562 0.5562 0.5562 0.5562 0.5562 0.5562 0.5562 0.333 0.333 0.584 0.584 0.584 0.6108 1.0151 0.7222 0.7222 0.7222 0.7222 0.667 0.6108 0.7778 0.7222 0.2778 0.5562 0.7222 0.6108 0.833 0.7222 0.7778 0.667 0.7778 0.7222 0.667 0.6108 0.7222 0.667 0.9438 0.667 0.667 0.6108 0.333 0.2778 0.333 0.584 0.5562 0.333 0.5562 0.6108 0.5562 0.6108 0.5562 0.333 0.6108 0.6108 0.2778 0.2778 0.5562 0.2778 0.8892 0.6108 0.6108 0.6108 0.6108 0.3892 0.5562 0.333 0.6108 0.5562 0.7778 0.5562 0.5562 0.5 0.3892 0.2798 0.3892 0.584 0.2778 0.2778 0.5 0.5 0.5562 1 1 0.5562 0.5562 0.3999 0.584 0.35"
)
"""LiberationSans Regular+Bold — metric clone of Arial, and what Helvetica falls to."""

CEILING = _packed(
    "0.3516 0.4023 0.5874 0.8672 0.7109 1.272 0.8623 0.332 0.5435 0.5435 0.7109 0.8672 0.3638 0.48 0.3638 0.6895 0.7109 0.7109 0.7109 0.7109 0.7109 0.7109 0.7109 0.7109 0.7109 0.7109 0.4541 0.4541 0.8672 0.8672 0.8672 0.6167 1.0151 0.7764 0.7617 0.7236 0.8301 0.6831 0.6504 0.811 0.8374 0.5459 0.5562 0.771 0.6372 0.9477 0.8467 0.8501 0.7329 0.8501 0.7822 0.7105 0.6816 0.812 0.7637 1.1284 0.7637 0.7368 0.6919 0.5435 0.6895 0.5435 0.8672 0.7109 0.7109 0.668 0.6992 0.5884 0.6992 0.6641 0.4224 0.6992 0.7124 0.3418 0.4028 0.6709 0.3418 1.0581 0.7124 0.6865 0.6992 0.6992 0.4971 0.5933 0.4556 0.7124 0.6499 0.9795 0.669 0.6509 0.5967 0.7109 0.5435 0.7109 0.8672 0.332 0.332 0.5874 0.5874 0.7109 1 1.0488 0.7109 0.7109 0.5874 0.8672 0.7109"
)
"""Per-character max across every measured face (the two above plus Verdana and DejaVu)."""

# A character no table carries is charged its class's widest measured glyph, so a
# glyph outside the measured set is never under-counted. CJK is measured on its em square.
_FALLBACK_SPACE = CEILING[" "]
_FALLBACK_UPPER = max(v for k, v in CEILING.items() if k.isupper())
_FALLBACK_LOWER = max(v for k, v in CEILING.items() if k.islower())
_FALLBACK_ANY = max(CEILING.values())

_CALIBRI_FACES = ("calibri", "carlito")
# Ahead of Arial's, which "liberation" alone would claim Liberation Mono for.
_COURIER_FACES = ("courier", "liberation mono", "cousine")
_ARIAL_FACES = ("arial", "helvetica", "liberation")
# Plain "Barlow" is wider than its semi-condensed cut, so only the cut itself matches.
_FACE_TABLES = (
    (("poppins",), POPPINS),
    (("open sans", "opensans"), OPEN_SANS),
    (("montserrat",), MONTSERRAT),
    (("amatic",), AMATIC),
    (("sniglet",), SNIGLET),
    (("bebas",), BEBAS_NEUE),
    (("barlow semi condensed", "barlowsemicondensed"), BARLOW_SEMI_CONDENSED),
)
# Wider than the Bold the family tables fold in, so they get the ceiling instead.
_HEAVY = ("black", "heavy")


def advance_em(ch: str, table: dict[str, float]) -> float:
    """The advance of ``ch`` in ems, over-counted when ``ch`` was never measured."""
    got = table.get(ch)
    if got is not None:
        return got
    if is_cjk(ch):
        return CJK_EM
    if ch.isspace():
        return _FALLBACK_SPACE
    if ch.isupper():
        return _FALLBACK_UPPER
    if ch.islower():
        return _FALLBACK_LOWER
    return _FALLBACK_ANY


MEASURED_FAMILIES = (
    "Calibri / Carlito",
    "Arial / Helvetica / Liberation",
    "Courier New / Liberation Mono / Cousine",
    "Poppins",
    "Open Sans",
    "Montserrat",
    "Amatic",
    "Sniglet",
    "Bebas Neue",
    "Barlow Semi Condensed",
)
"""The families with their own advance tables. Anything else gets ``CEILING``."""


def measured(face: str | None, *, mono: bool = False) -> bool:
    """Whether ``face`` has its own advances, or is laid out against a fallback table."""
    table = table_for(face, mono=mono)
    return table is not CEILING and table is not MONO


def table_for(face: str | None, *, mono: bool = False) -> dict[str, float]:
    """The advance table for ``face``: its family's, or ``CEILING`` when unmeasured. With
    ``mono``, a face whose family has no monospaced table gets ``MONO``."""
    table = _routed(face)
    return MONO if mono and table is not COURIER else table


@lru_cache(maxsize=None)
def _routed(face: str | None) -> dict[str, float]:
    lowered = (face or "").lower()
    if any(cut in lowered for cut in _HEAVY):
        return CEILING
    if any(family in lowered for family in _CALIBRI_FACES):
        return CALIBRI
    if any(family in lowered for family in _COURIER_FACES):
        return COURIER
    if any(family in lowered for family in _ARIAL_FACES):
        return ARIAL
    for names, table in _FACE_TABLES:
        if any(name in lowered for name in names):
            return table
    return CEILING
