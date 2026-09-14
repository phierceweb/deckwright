"""`[words](address)` as components write it: the runs, their ink, and the manifest row."""

import pytest

import deckwright.components  # noqa: F401 — registers the built-in components
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _runs(ctx):
    return [
        r
        for s in ctx.slide.shapes
        if s.has_text_frame
        for p in s.text_frame.paragraphs
        for r in p.runs
    ]


def test_a_link_is_its_own_underlined_run_in_the_lines_own_ink(ctx_factory):
    ctx = ctx_factory({"prose": {"paragraphs": ["Read [the guide](https://example.com/g) first"]}})
    get_component("prose")(ctx)
    runs = _runs(ctx)
    assert [r.text for r in runs] == ["Read ", "the guide", " first"]
    link = runs[1]
    assert link.hyperlink.address == "https://example.com/g"
    assert link.font.underline is True
    assert runs[0].font.underline is None
    assert link.font.color.rgb == runs[0].font.color.rgb
    ext = link._r.rPr.find(f"{_A}hlinkClick").find(f"{_A}extLst")[0]
    assert ext.get("uri") == "{A12FA001-AC4F-418D-AE19-62706E023703}"
    assert ext[0].get("val") == "tx"


def test_the_manifest_records_the_words_shown_and_the_address(ctx_factory):
    ctx = ctx_factory({"prose": {"paragraphs": ["Read [the guide](https://example.com/g) first"]}})
    get_component("prose")(ctx)
    record = next(r for r in ctx.manifest.slides[-1].shapes if r.links)
    assert record.text == "Read the guide first"
    assert record.links == ["https://example.com/g"]


def test_a_code_listing_shows_link_markup_as_written(ctx_factory):
    ctx = ctx_factory({"code": {"lines": ["See [docs](https://example.com)"]}})
    get_component("code")(ctx)
    runs = _runs(ctx)
    assert [r.text for r in runs] == ["See [docs](https://example.com)"]
    assert runs[0].hyperlink.address is None
    record = ctx.manifest.slides[-1].shapes[-1]
    assert record.lines == ["See [docs](https://example.com)"]
    assert record.links == []


def test_a_link_that_is_not_a_web_address_is_refused_where_it_is_drawn(ctx_factory):
    """A deck-local component's text never passes the spec's own check, so the writer refuses."""
    ctx = ctx_factory({"prose": {"paragraphs": ["[run](file:///etc/passwd)"]}})
    with pytest.raises(
        LayoutError,
        match="the link \\[run\\]\\(file:///etc/passwd\\): 'file:///etc/passwd' is not a web address",
    ):
        get_component("prose")(ctx)
