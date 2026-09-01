"""The baked advance tables against the fonts they were measured from. The drift gate
regenerates each table with the same PIL call that baked it; the floor test holds ``text_em``
to never under-predict. Both skip where the measuring fonts are absent, like the corpus.

Run as a script to print freshly measured dict literals for ``_metrics.py``:

    .venv/bin/python tests/utils/test_metrics.py
"""

from __future__ import annotations

import pathlib

import pytest

from deckwright.utils import _metrics
from deckwright.utils._metrics import ARIAL, CALIBRI, CEILING, advance_em, table_for
from deckwright.utils.text import text_em

_LO = pathlib.Path("/Applications/LibreOffice.app/Contents/Resources/fonts/truetype")
_SYS = pathlib.Path("/System/Library/Fonts/Supplemental")

_SOURCES = {
    "CALIBRI": (_LO / "Carlito-Regular.ttf", _LO / "Carlito-Bold.ttf"),
    "ARIAL": (_LO / "LiberationSans-Regular.ttf", _LO / "LiberationSans-Bold.ttf"),
}
_CEILING_EXTRA = (_SYS / "Verdana.ttf", _SYS / "Verdana Bold.ttf", _LO / "DejaVuSans.ttf")
_ALL = tuple(p for pair in _SOURCES.values() for p in pair) + _CEILING_EXTRA

fonts_present = pytest.mark.skipif(
    not all(p.is_file() for p in _ALL),
    reason="the measuring fonts (LibreOffice bundle + Verdana) are not present",
)

_GLYPHS = [chr(c) for c in range(32, 127)] + list("’‘“”–—…€£°×•")


def _measured(paths: tuple[pathlib.Path, ...]) -> dict[str, float]:
    """A table exactly as ``_metrics.py`` bakes one: per-glyph max across ``paths``."""
    from PIL import ImageFont

    fonts = [ImageFont.truetype(str(p), 1000) for p in paths]
    return {ch: round(max(f.getlength(ch) / 1000 for f in fonts), 4) for ch in _GLYPHS}


# --- the drift gate ---------------------------------------------------------


@fonts_present
@pytest.mark.parametrize("name", ["CALIBRI", "ARIAL", "CEILING"])
def test_the_baked_table_matches_the_fonts_it_was_measured_from(name):
    baked = getattr(_metrics, name)
    fresh = _measured(_ALL if name == "CEILING" else _SOURCES[name])
    assert set(baked) == set(fresh)
    off = {ch: (baked[ch], fresh[ch]) for ch in fresh if abs(baked[ch] - fresh[ch]) > 1e-3}
    assert off == {}


# --- the floor: never under-predict the heaviest cut ------------------------

_STRINGS = (
    "a",
    "I",
    "Q3",
    "revenue",
    "extraordinarily",
    "Miscommunication",
    "ALL-CAPS HEADLINE",
    "TOTAL COST OF OWNERSHIP",
    "What we shipped, and why it mattered",
    "12,847 units (+38% YoY) — $4.2M ARR",
    "l'Hôpital's rule",
    '(punctuation; [brackets] {braces} "quotes"!?)',
    "https://example.com/a/very/long/path?query=string&flag=1",
    "supercalifragilisticexpialidocious",
    "WWW MMM @@@ %%%",
    "illiterate illusionists jilt frilly lilies",
    "The quick brown fox jumps over the lazy dog",
    "Retrieval-augmented generation cut our support ticket backlog in half",
    "Weighing efficiency, extensibility and margin, the committee ultimately "
    "recommended consolidating nineteen regional vendors into three strategic "
    "partnerships, a decision projected to save four million dollars annually "
    "while reducing onboarding friction for every downstream engineering team "
    "and simplifying quarterly procurement reviews across all divisions",
    "€1,000 × 12 = £10,400…",
    "kerning AVATAR To Ve Wo Ya",
)

_HEAVIEST = [
    ("Calibri", _LO / "Carlito-Bold.ttf"),
    ("Arial", _LO / "LiberationSans-Bold.ttf"),
    (None, _SYS / "Verdana Bold.ttf"),
]


@fonts_present
@pytest.mark.parametrize("face,heaviest", _HEAVIEST, ids=["calibri", "arial", "ceiling"])
@pytest.mark.parametrize("string", _STRINGS)
def test_text_em_never_under_predicts_the_real_rendered_width(face, heaviest, string):
    from PIL import ImageFont

    real = ImageFont.truetype(str(heaviest), 1000).getlength(string) / 1000
    assert text_em(string, face) >= real


# --- face routing -----------------------------------------------------------


def test_the_calibri_family_routes_to_its_own_table():
    assert table_for("Calibri") is CALIBRI
    assert table_for("Carlito") is CALIBRI
    assert table_for("Calibri Light") is CALIBRI


def test_the_arial_family_routes_to_its_own_table():
    assert table_for("Arial") is ARIAL
    assert table_for("Helvetica Neue") is ARIAL
    assert table_for("Liberation Sans") is ARIAL


def test_an_unmeasured_face_and_none_route_to_the_ceiling():
    assert table_for(None) is CEILING
    assert table_for("Aptos") is CEILING
    assert table_for("Verdana") is CEILING


def test_a_heavier_than_bold_cut_routes_to_the_ceiling_not_its_family():
    assert table_for("Arial Black") is CEILING


# --- characters outside the measured set ------------------------------------


def test_a_character_never_measured_is_charged_its_class_ceiling():
    """Literals from the CEILING table: '%' (widest glyph), 'W' (widest upper),
    'm' (widest lower), and the ceiling space."""
    assert advance_em("中", CALIBRI) == 1.272
    assert advance_em("É", CALIBRI) == 1.1284
    assert advance_em("é", CALIBRI) == 1.0581
    assert advance_em("\u00a0", CALIBRI) == 0.3516


if __name__ == "__main__":
    for name in ("CALIBRI", "ARIAL", "CEILING"):
        print(f"{name} = {_measured(_ALL if name == 'CEILING' else _SOURCES[name])}\n")
