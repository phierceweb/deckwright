import types

import pytest
from pptx import Presentation

from deckwright.errors import ThemeError
from deckwright.theme.clrscheme import parse_color_scheme, parse_font_scheme, read_theme_xml

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _theme_xml(*, colors: str, fonts: str = "") -> bytes:
    fonts = fonts or (
        '<a:majorFont><a:latin typeface="Georgia"/></a:majorFont>'
        '<a:minorFont><a:latin typeface="Verdana"/></a:minorFont>'
    )
    return (
        f'<a:theme xmlns:a="{_A}" name="T"><a:themeElements>'
        f'<a:clrScheme name="S">{colors}</a:clrScheme>'
        f'<a:fontScheme name="F">{fonts}</a:fontScheme>'
        f"</a:themeElements></a:theme>"
    ).encode()


def test_reads_srgb_slots():
    xml = _theme_xml(colors='<a:accent1><a:srgbClr val="27b94c"/></a:accent1>')
    assert parse_color_scheme(xml) == {"accent1": "27B94C"}


def test_reads_sysclr_slots_via_lastclr():
    xml = _theme_xml(colors='<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>')
    assert parse_color_scheme(xml) == {"dk1": "000000"}


def test_missing_clrscheme_raises_theme_error():
    xml = f'<a:theme xmlns:a="{_A}" name="T"><a:themeElements/></a:theme>'.encode()
    with pytest.raises(ThemeError, match="no clrScheme"):
        parse_color_scheme(xml)


def test_reads_font_scheme():
    assert parse_font_scheme(_theme_xml(colors="")) == ("Georgia", "Verdana")


def test_a_font_scheme_without_a_usable_latin_typeface_is_rejected():
    """Both halves of the guard: the element absent, and present but empty. Without it
    the deck is set in an empty face name, or the parse dies on an AttributeError."""
    absent = _theme_xml(
        colors="",
        fonts='<a:majorFont/><a:minorFont><a:latin typeface="Verdana"/></a:minorFont>',
    )
    with pytest.raises(ThemeError, match="no major latin typeface"):
        parse_font_scheme(absent)

    blank = _theme_xml(
        colors="",
        fonts=(
            '<a:majorFont><a:latin typeface="Georgia"/></a:majorFont>'
            '<a:minorFont><a:latin typeface=""/></a:minorFont>'
        ),
    )
    with pytest.raises(ThemeError, match="no minor latin typeface"):
        parse_font_scheme(blank)


def test_the_scheme_is_read_from_the_master_it_is_handed(synthetic_template):
    prs = Presentation(str(synthetic_template))
    scheme = parse_color_scheme(read_theme_xml(prs.slide_masters[0]))
    # The stock Office theme defines all twelve slots.
    assert {"dk1", "lt1", "dk2", "lt2", "hlink", "folHlink"} <= set(scheme)
    assert all(len(v) == 6 for v in scheme.values())


def test_a_master_with_no_theme_part_is_rejected():
    class _Part:
        def part_related_by(self, reltype):
            raise KeyError(reltype)

    with pytest.raises(ThemeError, match="no theme part"):
        read_theme_xml(types.SimpleNamespace(part=_Part()))
