"""Office Math as an `equation:` writes it: one element per node kind."""

from __future__ import annotations

import re

import pytest

from deckwright.components._omml import omml
from deckwright.components._tex import parse


def _bare(tex: str) -> str:
    """The maths inside `m:oMath`, without the run properties every run carries."""
    xml = omml(parse(tex, where="t"), size_pt=24, ink="1A1D21")
    inner = re.search(r"<m:oMath>(.*)</m:oMath>", xml).group(1)
    return re.sub(r"<a:rPr\b.*?</a:rPr>", "", inner)


def _r(text: str) -> str:
    return f"<m:r><m:t>{text}</m:t></m:r>"


@pytest.mark.parametrize(
    "tex, xml",
    [
        ("x", _r("x")),
        ("x = 2y", _r("x=2y")),
        ("a < b", _r("a&lt;b")),
        ("x^2", f"<m:sSup><m:e>{_r('x')}</m:e><m:sup>{_r('2')}</m:sup></m:sSup>"),
        ("x_i", f"<m:sSub><m:e>{_r('x')}</m:e><m:sub>{_r('i')}</m:sub></m:sSub>"),
        (
            "x_i^2",
            f"<m:sSubSup><m:e>{_r('x')}</m:e><m:sub>{_r('i')}</m:sub>"
            f"<m:sup>{_r('2')}</m:sup></m:sSubSup>",
        ),
        (r"\frac{a}{b}", f"<m:f><m:num>{_r('a')}</m:num><m:den>{_r('b')}</m:den></m:f>"),
        (
            r"\sqrt{x}",
            f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>{_r("x")}</m:e></m:rad>',
        ),
        (r"\sqrt[3]{x}", f"<m:rad><m:deg>{_r('3')}</m:deg><m:e>{_r('x')}</m:e></m:rad>"),
        (
            r"\sum_{i=1}^{n} i",
            '<m:nary><m:naryPr><m:chr m:val="∑"/><m:limLoc m:val="undOvr"/></m:naryPr>'
            f"<m:sub>{_r('i=1')}</m:sub><m:sup>{_r('n')}</m:sup><m:e>{_r('i')}</m:e></m:nary>",
        ),
        (
            r"\int_0^1 x",
            '<m:nary><m:naryPr><m:chr m:val="∫"/><m:limLoc m:val="subSup"/></m:naryPr>'
            f"<m:sub>{_r('0')}</m:sub><m:sup>{_r('1')}</m:sup><m:e>{_r('x')}</m:e></m:nary>",
        ),
        (
            r"\prod x",
            '<m:nary><m:naryPr><m:chr m:val="∏"/><m:limLoc m:val="undOvr"/>'
            '<m:subHide m:val="1"/><m:supHide m:val="1"/></m:naryPr>'
            f"<m:sub/><m:sup/><m:e>{_r('x')}</m:e></m:nary>",
        ),
        (
            r"\lim_{x \to 0} f",
            '<m:func><m:fName><m:limLow><m:e><m:r><m:rPr><m:sty m:val="p"/></m:rPr>'
            f"<m:t>lim</m:t></m:r></m:e><m:lim>{_r('x→0')}</m:lim></m:limLow></m:fName>"
            f"<m:e>{_r('f')}</m:e></m:func>",
        ),
        (
            r"\left( a \right.",
            '<m:d><m:dPr><m:begChr m:val="("/><m:endChr m:val=""/></m:dPr>'
            f"<m:e>{_r('a')}</m:e></m:d>",
        ),
        (
            r"\text{if } x",
            '<m:r><m:rPr><m:nor/></m:rPr><m:t xml:space="preserve">if </m:t></m:r>' + _r("x"),
        ),
    ],
)
def test_each_node_is_written_as_its_office_math_element(tex, xml):
    assert _bare(tex) == xml


def test_the_quadratic_formula_is_the_maths_the_probe_carried():
    """The kit's equation probe held this, written by hand; the writer has to agree with it."""
    assert _bare(r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}") == (
        "<m:r><m:t>x=</m:t></m:r>"
        "<m:f><m:num><m:r><m:t>−b±</m:t></m:r>"
        '<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>'
        "<m:sSup><m:e><m:r><m:t>b</m:t></m:r></m:e><m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup>"
        "<m:r><m:t>−4ac</m:t></m:r></m:e></m:rad></m:num>"
        "<m:den><m:r><m:t>2a</m:t></m:r></m:den></m:f>"
    )


def test_every_run_carries_the_size_ink_and_face_powerpoint_sets_maths_in():
    """PowerPoint keeps DrawingML run properties where Word keeps its own; without them the
    maths takes the text box's default ink, which on a dark slide is the slide."""
    xml = omml(parse("x", where="t"), size_pt=24, ink="FFFFFF")
    assert (
        '<m:r><a:rPr sz="2400"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>'
        '<a:latin typeface="Cambria Math"/></a:rPr><m:t>x</m:t></m:r>'
    ) in xml


@pytest.mark.parametrize("align, jc", [("left", "left"), ("center", "center"), ("right", "right")])
def test_the_equation_is_justified_as_its_placement_aligns(align, jc):
    xml = omml(parse("x", where="t"), size_pt=24, ink="000000", align=align)
    assert f'<m:oMathParaPr><m:jc m:val="{jc}"/></m:oMathParaPr>' in xml


def test_the_maths_sits_in_the_extension_element_powerpoint_reads():
    xml = omml(parse("x", where="t"), size_pt=24, ink="000000")
    assert xml.startswith(
        '<a14:m xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main" '
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><m:oMathPara>'
    )
    assert xml.endswith("</m:oMath></m:oMathPara></a14:m>")


def test_a_styled_run_keeps_office_maths_properties_ahead_of_drawingmls():
    """`CT_R` reads `m:rPr` first, then the slot where PowerPoint keeps `a:rPr`."""
    xml = omml(parse(r"\text{if }", where="t"), size_pt=24, ink="000000")
    assert (
        '<m:r><m:rPr><m:nor/></m:rPr><a:rPr sz="2400"><a:solidFill><a:srgbClr val="000000"/>'
        '</a:solidFill><a:latin typeface="Cambria Math"/></a:rPr>'
        '<m:t xml:space="preserve">if </m:t></m:r>'
    ) in xml
