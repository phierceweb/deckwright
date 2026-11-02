"""``alt:`` and ``decorative:`` on the figure components: what each refuses, and what reaches the
package and the manifest. A successful corpus build writes both but never reaches a refusal."""

import pytest

import deckwright.components  # noqa: F401 — registers the built-in components
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component

_DECORATIVE = "{http://schemas.microsoft.com/office/drawing/2017/decorative}decorative"


def _icon(ctx_factory, **fields):
    ctx = ctx_factory({"icon": {"name": "target", **fields}})
    get_component("icon")(ctx)
    return ctx, ctx.slide.shapes[-1]._element.nvSpPr.cNvPr


def test_alt_is_written_as_the_shapes_description_and_recorded(ctx_factory):
    ctx, c_nv_pr = _icon(ctx_factory, alt="  A target  ")
    assert c_nv_pr.get("descr") == "A target"
    assert ctx.manifest.slides[-1].shapes[-1].alt == "A target"


def test_decorative_writes_offices_flag_and_no_description(ctx_factory):
    ctx, c_nv_pr = _icon(ctx_factory, decorative=True)
    ext = c_nv_pr.find("{http://schemas.openxmlformats.org/drawingml/2006/main}extLst")[0]
    assert ext.get("uri") == "{C183D7F6-B498-43B3-948B-1728B52AA6E4}"
    assert ext[0].tag == _DECORATIVE
    assert ext[0].get("val") == "1"
    assert c_nv_pr.get("descr") is None
    assert ctx.manifest.slides[-1].shapes[-1].decorative is True


def test_a_figure_given_neither_carries_neither(ctx_factory):
    ctx, c_nv_pr = _icon(ctx_factory)
    assert c_nv_pr.get("descr") is None
    assert len(c_nv_pr) == 0
    record = ctx.manifest.slides[-1].shapes[-1]
    assert (record.alt, record.decorative) == (None, False)


@pytest.mark.parametrize("value", ["", "   ", ["a"], {"a": 1}, True, None])
def test_alt_that_is_not_words_is_refused(ctx_factory, value):
    with pytest.raises(LayoutError, match="'alt' is the text a screen reader reads"):
        _icon(ctx_factory, alt=value)


def test_a_number_is_accepted_as_alt_text(ctx_factory):
    _, c_nv_pr = _icon(ctx_factory, alt=2026)
    assert c_nv_pr.get("descr") == "2026"


def test_a_control_character_in_alt_is_refused_before_lxml_sees_it(ctx_factory):
    with pytest.raises(LayoutError, match=r"control character '\\x01'"):
        _icon(ctx_factory, alt="a\x01b")


def test_a_line_break_in_alt_is_kept(ctx_factory):
    _, c_nv_pr = _icon(ctx_factory, alt="one\ntwo")
    assert c_nv_pr.get("descr") == "one\ntwo"


def test_alt_beside_decorative_is_refused(ctx_factory):
    with pytest.raises(LayoutError, match="contradict each other"):
        _icon(ctx_factory, alt="A target", decorative=True)


def test_decorative_false_beside_alt_is_accepted(ctx_factory):
    _, c_nv_pr = _icon(ctx_factory, alt="A target", decorative=False)
    assert c_nv_pr.get("descr") == "A target"


def test_decorative_that_is_not_a_boolean_is_refused(ctx_factory):
    with pytest.raises(LayoutError, match="'decorative' must be true or false"):
        _icon(ctx_factory, decorative="yes")


def test_a_chart_carries_its_alt_on_the_graphic_frame(ctx_factory):
    ctx = ctx_factory(
        {
            "chart": {
                "kind": "column",
                "alt": "Revenue by quarter",
                "data": [{"category": "Q1", "value": 1}, {"category": "Q2", "value": 2}],
            }
        }
    )
    get_component("chart")(ctx)
    frame = ctx.slide.shapes[-1]
    assert frame.has_chart
    assert frame._element.nvGraphicFramePr.cNvPr.get("descr") == "Revenue by quarter"


def test_a_card_picture_icon_is_decorative_only_beside_words(ctx_factory, tmp_path):
    from PIL import Image

    Image.new("RGB", (8, 8)).save(tmp_path / "mark.png")
    for fields, expected in (({"heading": "Launch"}, True), ({}, False)):
        ctx = ctx_factory({"card": {"icon": str(tmp_path / "mark.png"), **fields}})
        get_component("card")(ctx)
        picture = next(s for s in ctx.slide.shapes if s.shape_type == 13)
        c_nv_pr = picture._element.nvPicPr.cNvPr
        assert c_nv_pr.get("descr") is None, "python-pptx's file name was left as alt text"
        assert (c_nv_pr.find(f".//{_DECORATIVE}") is not None) is expected


def test_a_card_whose_only_content_is_a_picture_takes_alt(ctx_factory, tmp_path):
    from PIL import Image

    Image.new("RGB", (8, 8)).save(tmp_path / "mark.png")
    ctx = ctx_factory({"card": {"icon": str(tmp_path / "mark.png"), "alt": "The company logo"}})
    get_component("card")(ctx)
    picture = next(s for s in ctx.slide.shapes if s.shape_type == 13)
    assert picture._element.nvPicPr.cNvPr.get("descr") == "The company logo"


@pytest.mark.parametrize("value", ["del \x7f here", "cr \r here"])
def test_alt_accepts_every_character_xml_can_hold(ctx_factory, value):
    _, c_nv_pr = _icon(ctx_factory, alt=value)
    assert c_nv_pr.get("descr") == value.strip()


def test_alt_refuses_a_character_xml_cannot_hold(ctx_factory):
    with pytest.raises(LayoutError, match=r"control character '\\x0b'"):
        _icon(ctx_factory, alt="a\x0bb")


def test_alt_on_a_card_with_no_icon_is_refused(ctx_factory):
    ctx = ctx_factory({"card": {"heading": "Launch", "alt": "A rocket"}})
    with pytest.raises(LayoutError, match="describe the card's icon, and it has none"):
        get_component("card")(ctx)
