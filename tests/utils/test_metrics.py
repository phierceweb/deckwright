"""The baked advance tables against the fonts they were measured from. The drift gate
regenerates each table with the same PIL call that baked it; the floor test holds ``text_em``
to never under-predict. Both skip where the measuring fonts are absent, like the corpus.

Run as a script to print freshly measured dict literals for ``_metrics.py``:

    .venv/bin/python tests/utils/test_metrics.py
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import unicodedata

import pytest

from deckwright.utils import _metrics
from deckwright.utils._cjk import is_cjk
from deckwright.utils._metrics import ARIAL, CALIBRI, CEILING, advance_em, measured, table_for
from deckwright.utils import _metrics_faces
from deckwright.utils._metrics_faces import COURIER, GLYPHS, MONO
from deckwright.utils.text import listing_em, text_em

_LO = pathlib.Path("/Applications/LibreOffice.app/Contents/Resources/fonts/truetype")
_FONTS = pathlib.Path("/System/Library/Fonts")
_SYS = _FONTS / "Supplemental"

_SOURCES = {
    "CALIBRI": (_LO / "Carlito-Regular.ttf", _LO / "Carlito-Bold.ttf"),
    "ARIAL": (_LO / "LiberationSans-Regular.ttf", _LO / "LiberationSans-Bold.ttf"),
}
_CEILING_EXTRA = (_SYS / "Verdana.ttf", _SYS / "Verdana Bold.ttf", _LO / "DejaVuSans.ttf")
_ALL = tuple(p for pair in _SOURCES.values() for p in pair) + _CEILING_EXTRA
# Outside ``_ALL``: a monospace advance would widen every narrow glyph in CEILING.
_MONO = (_LO / "LiberationMono-Regular.ttf", _LO / "LiberationMono-Bold.ttf")

fonts_present = pytest.mark.skipif(
    not all(p.is_file() for p in _ALL + _MONO),
    reason="the measuring fonts (LibreOffice bundle + Verdana) are not present",
)

# Google Fonts' OFL files, fetched by hand into a cache outside the repo; see docs/utils.md.
_FACES_DIR = pathlib.Path.home() / ".cache" / "deckwright" / "metric-fonts"
# ``(file, instance)``: a variable font names the instance to measure, a static one None.
_FACE_SOURCES = {
    "POPPINS": (("poppins/Poppins-Regular.ttf", None), ("poppins/Poppins-Bold.ttf", None)),
    "OPEN_SANS": (
        ("opensans/OpenSans[wdth,wght].ttf", "Regular"),
        ("opensans/OpenSans[wdth,wght].ttf", "Bold"),
    ),
    "MONTSERRAT": (
        ("montserrat/Montserrat[wght].ttf", "Regular"),
        ("montserrat/Montserrat[wght].ttf", "Bold"),
    ),
    "AMATIC": (("amaticsc/AmaticSC-Regular.ttf", None), ("amaticsc/AmaticSC-Bold.ttf", None)),
    "SNIGLET": (("sniglet/Sniglet-Regular.ttf", None), ("sniglet/Sniglet-ExtraBold.ttf", None)),
    "BEBAS_NEUE": (("bebasneue/BebasNeue-Regular.ttf", None),),
    "BARLOW_SEMI_CONDENSED": (
        ("barlowsemicondensed/BarlowSemiCondensed-Regular.ttf", None),
        ("barlowsemicondensed/BarlowSemiCondensed-Bold.ttf", None),
    ),
}

faces_present = pytest.mark.skipif(
    not all((_FACES_DIR / f).is_file() for cuts in _FACE_SOURCES.values() for f, _ in cuts),
    reason=f"the brand-face measuring fonts are not in {_FACES_DIR}",
)


def _font(path, instance=None):
    from PIL import ImageFont

    font = ImageFont.truetype(str(path), 1000)
    if instance is not None:
        font.set_variation_by_name(instance)
    return font


def _measured(paths) -> dict[str, float]:
    """A table exactly as ``_metrics.py`` bakes one: per-glyph max across ``paths``.

    Each entry is a path, or a ``(path, instance)`` pair for a variable font.
    """
    fonts = [_font(*p) if isinstance(p, tuple) else _font(p) for p in paths]
    return {ch: round(max(f.getlength(ch) / 1000 for f in fonts), 4) for ch in GLYPHS}


def _face_paths(name: str):
    return tuple((_FACES_DIR / f, instance) for f, instance in _FACE_SOURCES[name])


# --- the drift gate ---------------------------------------------------------


@fonts_present
@pytest.mark.parametrize("name", ["CALIBRI", "ARIAL", "CEILING"])
def test_the_baked_table_matches_the_fonts_it_was_measured_from(name):
    baked = getattr(_metrics, name)
    fresh = _measured(_ALL if name == "CEILING" else _SOURCES[name])
    assert set(baked) == set(fresh)
    off = {ch: (baked[ch], fresh[ch]) for ch in fresh if abs(baked[ch] - fresh[ch]) > 1e-3}
    assert off == {}


@fonts_present
def test_the_baked_courier_table_matches_liberation_mono():
    fresh = _measured(_MONO)
    off = {ch: (COURIER[ch], fresh[ch]) for ch in fresh if abs(COURIER[ch] - fresh[ch]) > 1e-3}
    assert off == {}


# ``(file, index)``: the cuts whose shared repertoire a monospaced table charges one column.
_COURIER_CUTS = (
    (_LO / "LiberationMono-Regular.ttf", 0),
    (_LO / "LiberationMono-Bold.ttf", 0),
    (_SYS / "Courier New.ttf", 0),
    (_SYS / "Courier New Bold.ttf", 0),
)
_MONO_CUTS = _COURIER_CUTS + (
    (_FONTS / "SFNSMono.ttf", 0),
    (_FONTS / "Menlo.ttc", 0),
    (_FONTS / "Menlo.ttc", 1),
    (_LO / "DejaVuSansMono.ttf", 0),
    (_LO / "DejaVuSansMono-Bold.ttf", 0),
)


def _charset(path, index) -> set[int]:
    """The code points fontconfig reads in one cut."""
    argv = ["fc-query", "-i", str(index), "--format=%{charset}", str(path)]
    points: set[int] = set()
    for token in subprocess.run(argv, capture_output=True, text=True, check=True).stdout.split():
        lo, _, hi = token.partition("-")
        points.update(range(int(lo, 16), int(hi or lo, 16) + 1))
    return points


# A face with no table of its own is relied on for Latin only: Basic, Latin-1 and Extended-A.
_LATIN_END = 0x180


def _repertoire(cuts, *, below: int = 0x110000) -> str:
    """The characters beyond ``GLYPHS``, and under ``below``, that every cut carries and draws
    one column wide."""
    from PIL import ImageFont

    fonts = [ImageFont.truetype(str(path), 1000, index=index) for path, index in cuts]

    def counts(ch: str) -> bool:
        category = unicodedata.category(ch)
        return (
            0xA0 <= ord(ch) < below
            and ch not in GLYPHS
            and not is_cjk(ch)
            and not unicodedata.combining(ch)
            and (category[0] in "LNPS" or category == "Zs")
            and unicodedata.east_asian_width(ch) not in ("W", "F")
            and all(abs(f.getlength(ch) - f.getlength("0")) <= 0.5 for f in fonts)
        )

    shared = set.intersection(*(_charset(path, index) for path, index in cuts))
    return "".join(ch for ch in map(chr, sorted(shared)) if counts(ch))


def _spans(chars: str) -> str:
    spans: list[list[int]] = []
    for code in map(ord, chars):
        if spans and code == spans[-1][1] + 1:
            spans[-1][1] = code
        else:
            spans.append([code, code])
    return " ".join(f"{lo:x}-{hi:x}" if lo != hi else f"{lo:x}" for lo, hi in spans)


def _cuts_present(cuts):
    return pytest.mark.skipif(
        shutil.which("fc-query") is None or not all(path.is_file() for path, _ in cuts),
        reason="fc-query or a measured monospace cut is not present",
    )


@pytest.mark.parametrize(
    "table,cuts,below",
    [
        pytest.param(
            COURIER, _COURIER_CUTS, 0x110000, id="courier", marks=_cuts_present(_COURIER_CUTS)
        ),
        pytest.param(MONO, _MONO_CUTS, _LATIN_END, id="mono", marks=_cuts_present(_MONO_CUTS)),
    ],
)
def test_a_monospaced_table_covers_what_every_cut_draws_one_column_wide(table, cuts, below):
    beyond = "".join(ch for ch in table if ch not in GLYPHS)
    assert _spans(beyond) == _spans(_repertoire(cuts, below=below))


def test_an_unmeasured_mono_face_charges_a_letter_beyond_latin_its_class_widest():
    """Such a face may draw ``Ж`` and ``λ`` from another face, so each is charged the widest
    capital or lowercase measured; ``é`` it can be relied on to carry in one column."""
    assert listing_em("Жλé", "Menlo") == pytest.approx(1.1284 + 1.0581 + 0.6182)


@faces_present
@pytest.mark.parametrize("name", list(_FACE_SOURCES))
def test_a_baked_brand_face_matches_the_fonts_it_was_measured_from(name):
    baked = getattr(_metrics_faces, name)
    fresh = _measured(_face_paths(name))
    assert list(baked) == list(fresh)
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
    ("Courier New", _LO / "LiberationMono-Bold.ttf"),
]


@fonts_present
@pytest.mark.parametrize("face,heaviest", _HEAVIEST, ids=["calibri", "arial", "ceiling", "courier"])
@pytest.mark.parametrize("string", _STRINGS)
def test_text_em_never_under_predicts_the_real_rendered_width(face, heaviest, string):
    from PIL import ImageFont

    real = ImageFont.truetype(str(heaviest), 1000).getlength(string) / 1000
    assert text_em(string, face) >= real


# What a listing carries beyond ASCII: a file tree, an arrow, accents, Greek and Cyrillic,
# and the spaces a number is grouped or aligned with.
_LISTING_STRINGS = (
    "├── src/app/main.py",
    "│   └── café → λ ≤ Ж",
    "x = 1  # naïve ±0.5",
    "n = 1 234 567  # total",
)
# ``(face, file, index)``: the Bold of a collection where it has one. No table covers these.
_UNMEASURED_MONO = [
    ("Menlo", _FONTS / "Menlo.ttc", 1),
    ("SF Mono", _FONTS / "SFNSMono.ttf", 0),
    ("DejaVu Sans Mono", _LO / "DejaVuSansMono-Bold.ttf", 0),
    ("Andale Mono", _SYS / "Andale Mono.ttf", 0),
    ("PT Mono", _SYS / "PTMono.ttc", 1),
]


@pytest.mark.parametrize(
    "face,path,index",
    [
        pytest.param(
            *row, id=row[0], marks=pytest.mark.skipif(not row[1].is_file(), reason="absent")
        )
        for row in _UNMEASURED_MONO
    ],
)
@pytest.mark.parametrize("string", _STRINGS + _LISTING_STRINGS)
def test_an_unmeasured_mono_face_is_never_under_charged(face, path, index, string):
    from PIL import ImageFont

    real = ImageFont.truetype(str(path), 1000, index=index).getlength(string) / 1000
    assert listing_em(string, face) >= real


@fonts_present
@pytest.mark.parametrize(
    "heaviest", [_MONO[1], _SYS / "Courier New Bold.ttf"], ids=lambda p: p.stem
)
@pytest.mark.parametrize("string", _LISTING_STRINGS)
def test_a_courier_listing_is_never_under_charged(heaviest, string):
    from PIL import ImageFont

    real = ImageFont.truetype(str(heaviest), 1000).getlength(string) / 1000
    assert listing_em(string, "Courier New") >= real


_HEAVIEST_FACES = [
    ("Poppins", "poppins/Poppins-Bold.ttf", None),
    ("Open Sans", "opensans/OpenSans[wdth,wght].ttf", "Bold"),
    ("Montserrat", "montserrat/Montserrat[wght].ttf", "Bold"),
    ("Amatic", "amaticsc/AmaticSC-Bold.ttf", None),
    ("Sniglet", "sniglet/Sniglet-ExtraBold.ttf", None),
    ("Bebas Neue", "bebasneue/BebasNeue-Regular.ttf", None),
    ("Barlow Semi Condensed", "barlowsemicondensed/BarlowSemiCondensed-Bold.ttf", None),
]


@faces_present
@pytest.mark.parametrize("face,heaviest,instance", _HEAVIEST_FACES, ids=lambda v: str(v))
@pytest.mark.parametrize("string", _STRINGS)
def test_a_brand_face_never_under_predicts_its_heaviest_cut(face, heaviest, instance, string):
    real = _font(_FACES_DIR / heaviest, instance).getlength(string) / 1000
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


def test_an_unmeasured_face_setting_a_listing_routes_to_the_monospace_table():
    assert table_for("Menlo") is CEILING
    assert table_for("Menlo", mono=True) is MONO
    assert table_for("Source Code Pro Black", mono=True) is MONO
    assert table_for("Courier New", mono=True) is COURIER
    assert set(MONO.values()) == {0.6182}


def test_a_listing_face_named_like_a_proportional_family_routes_to_the_monospace_table():
    """ "Helvetica Monospaced" carries "helvetica": Arial's table, which no listing may use."""
    assert table_for("Helvetica Monospaced") is ARIAL
    assert table_for("Helvetica Monospaced", mono=True) is MONO
    assert measured("Helvetica Monospaced")
    assert not measured("Helvetica Monospaced", mono=True)
    assert measured("Courier New", mono=True)


def test_the_courier_family_routes_to_its_own_table_not_arials():
    """ "Liberation Mono" carries "liberation", Arial's clone's family name."""
    assert table_for("Courier New") is COURIER
    assert table_for("Liberation Mono") is COURIER
    assert table_for("Cousine") is COURIER


@pytest.mark.parametrize(
    "face,name",
    [
        ("Poppins", "POPPINS"),
        ("Open Sans", "OPEN_SANS"),
        ("Montserrat-Bold", "MONTSERRAT"),
        ("Amatic", "AMATIC"),
        ("Amatic SC", "AMATIC"),
        ("Sniglet", "SNIGLET"),
        ("Bebas Neue", "BEBAS_NEUE"),
        ("Barlow Semi Condensed Light", "BARLOW_SEMI_CONDENSED"),
    ],
)
def test_a_face_a_bundled_theme_names_routes_to_its_own_table(face, name):
    """The names are the ones the brand themes actually carry."""
    assert table_for(face) is getattr(_metrics_faces, name)


def test_plain_barlow_is_not_its_semi_condensed_cut():
    assert table_for("Barlow") is CEILING


def test_an_unmeasured_face_and_none_route_to_the_ceiling():
    assert table_for(None) is CEILING
    assert table_for("Aptos") is CEILING
    assert table_for("Verdana") is CEILING


def test_a_heavier_than_bold_cut_routes_to_the_ceiling_not_its_family():
    assert table_for("Arial Black") is CEILING


# --- characters outside the measured set ------------------------------------


def test_a_character_never_measured_is_charged_its_class_ceiling():
    """Literals from the CEILING table: '%' (widest glyph), 'W' (widest upper),
    'm' (widest lower), and the ceiling space. CJK has its own em-square charge."""
    assert advance_em("★", CALIBRI) == 1.272
    assert advance_em("É", CALIBRI) == 1.1284
    assert advance_em("é", CALIBRI) == 1.0581
    assert advance_em("\u00a0", CALIBRI) == 0.3516


if __name__ == "__main__":
    for name in ("CALIBRI", "ARIAL", "CEILING"):
        print(f"{name} = {_measured(_ALL if name == 'CEILING' else _SOURCES[name])}\n")
    for name, paths in (("COURIER", _MONO),) + tuple((n, _face_paths(n)) for n in _FACE_SOURCES):
        packed = " ".join(f"{v:g}" for v in _measured(paths).values())
        print(f'{name} = _packed("{packed}")\n')
    for name, cuts, below in (
        ("COURIER", _COURIER_CUTS, 0x110000),
        ("MONO", _MONO_CUTS, _LATIN_END),
    ):
        print(f'{name} beyond GLYPHS = _spans("{_spans(_repertoire(cuts, below=below))}")\n')
