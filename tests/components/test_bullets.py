import dataclasses

import pytest

import deckwright.components  # noqa: F401 — registers the built-in components
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component
from deckwright.theme import Scale
from deckwright.theme.defaults import DEFAULT_PALETTE
from deckwright.utils.color import AA_LARGE, AA_NORMAL, contrast_ratio
from deckwright.utils.shapes import ALIGN, ANCHOR

TALL = Scale(26.666, 15.0)


def _texts(slide):
    return [s.text_frame.text for s in slide.shapes if s.has_text_frame]


def _tall(theme):
    """The fixture theme on twice the canvas — every rung and margin follows the scale."""
    return dataclasses.replace(
        theme,
        scale=TALL,
        grid=dataclasses.replace(theme.grid, scale=TALL),
        ramp={role: dataclasses.replace(style, scale=TALL) for role, style in theme.ramp.items()},
    )


def test_items_are_rendered_as_bullets(ctx_factory):
    ctx = ctx_factory({"bullets": {"items": ["alpha", "beta"]}})
    get_component("bullets")(ctx)
    joined = "\n".join(_texts(ctx.slide))
    assert "alpha" in joined and "beta" in joined
    assert "•" in joined


def test_an_optional_heading_is_rendered(ctx_factory):
    ctx = ctx_factory({"bullets": {"heading": "What it is", "items": ["a"]}})
    get_component("bullets")(ctx)
    assert "What it is" in "\n".join(_texts(ctx.slide))


def test_the_reported_height_carries_the_heading_band(ctx_factory):
    """A heading pushes the bullets down, and the reported height has to include that band —
    both decks draw the same bullets, so only the offset differs."""
    items = {"items": ["alpha", "beta"]}
    plain = get_component("bullets")(ctx_factory({"bullets": items}))
    headed = get_component("bullets")(ctx_factory({"bullets": {**items, "heading": "H"}}))
    # _HEADING_H, plus the 0.1in the component leaves under it.
    assert headed.height - plain.height == pytest.approx(0.42 + 0.1, abs=0.001)


def test_a_heading_whose_accent_cannot_be_read_on_the_page_takes_the_pages_ink(ctx_factory):
    """An accent below the large-text bar on the page must not paint the heading."""
    ctx = ctx_factory({"bullets": {"heading": "H", "items": ["a"]}})
    accent = ctx.theme.palette.role("accent-1")
    assert contrast_ratio(accent, ctx.theme.palette.pair("page").bg) < AA_LARGE
    get_component("bullets")(ctx)
    written = [r for r in ctx.manifest.slides[0].shapes if r.text == "H"][0]
    assert written.fg == ctx.theme.palette.pair("page").fg


def test_a_heading_whose_accent_cannot_be_read_on_a_dark_slide_takes_that_slides_ink(
    ctx_factory, theme
):
    themed = dataclasses.replace(theme, palette=DEFAULT_PALETTE)
    ctx = ctx_factory(
        {"bullets": {"heading": "H", "items": ["a"]}}, background="inverse", theme_override=themed
    )
    assert (
        contrast_ratio(DEFAULT_PALETTE.role("accent-1"), DEFAULT_PALETTE.pair("inverse").bg)
        < AA_NORMAL
    )
    get_component("bullets")(ctx)
    written = [r for r in ctx.manifest.slides[0].shapes if r.text == "H"][0]
    assert written.fg == DEFAULT_PALETTE.pair("inverse").fg
    assert written.bg == DEFAULT_PALETTE.pair("inverse").bg


def test_a_heading_keeps_an_accent_that_does_read_on_a_dark_slide(ctx_factory):
    ctx = ctx_factory({"bullets": {"heading": "H", "items": ["a"]}}, background="inverse")
    get_component("bullets")(ctx)
    written = [r for r in ctx.manifest.slides[0].shapes if r.text == "H"][0]
    assert written.fg == ctx.theme.palette.role("accent-1")


def test_items_is_required(ctx_factory):
    ctx = ctx_factory({"bullets": {}})
    with pytest.raises(LayoutError, match=r"slide 1 .*'items'"):
        get_component("bullets")(ctx)


def test_bullets_is_registered():
    from deckwright.layouts.components import registered_components

    assert "bullets" in registered_components()


def test_a_single_column_returns_one_reveal_group(ctx_factory):
    ctx = ctx_factory({"bullets": {"items": ["a", "b"]}})
    assert len(get_component("bullets")(ctx).groups) == 1


def test_two_columns_return_one_group_each(ctx_factory):
    ctx = ctx_factory({"bullets": {"columns": 2, "items": ["a", "b", "c", "d"]}})
    assert len(get_component("bullets")(ctx).groups) == 2


def test_every_returned_id_is_a_real_shape_on_the_slide(ctx_factory):
    ctx = ctx_factory({"bullets": {"items": ["a"]}})
    groups = get_component("bullets")(ctx).groups
    ids = {s.shape_id for s in ctx.slide.shapes}
    assert all(spid in ids for group in groups for spid in group)


def test_content_stays_inside_the_body_rect(ctx_factory):
    ctx = ctx_factory({"bullets": {"items": ["a", "b", "c"]}})
    get_component("bullets")(ctx)
    rect = ctx.body_rect
    for shape in ctx.slide.shapes:
        assert shape.left / 914400 >= rect.left - 0.01
        assert (shape.left + shape.width) / 914400 <= rect.right + 0.01
        assert shape.top / 914400 >= rect.top - 0.01
        assert (shape.top + shape.height) / 914400 <= rect.bottom + 0.01


def test_shapes_are_recorded_in_the_manifest(ctx_factory):
    ctx = ctx_factory({"bullets": {"items": ["alpha"]}})
    get_component("bullets")(ctx)
    texts = ctx.manifest.slides[0].texts()
    assert texts, "nothing was recorded at all, so the search below proves nothing"
    assert any("alpha" in t for t in texts)


def test_recorded_lines_match_the_drawn_paragraphs(ctx_factory):
    ctx = ctx_factory({"bullets": {"heading": "H", "items": ["alpha", "beta"]}})
    get_component("bullets")(ctx)
    by_id = {s.shape_id: s for s in ctx.slide.shapes}
    recorded = [r for r in ctx.manifest.slides[0].shapes if r.lines]
    # One row per bullet is what qa's overflow check diffs against the render;
    # collapsing the column into a single joined string would defeat it.
    assert [r.lines for r in recorded] == [["•  alpha", "•  beta"]]
    for record in recorded:
        drawn = [p.text for p in by_id[record.shape_id].text_frame.paragraphs]
        assert drawn == record.lines


def test_an_uneven_split_still_fills_every_column(ctx_factory):
    ctx = ctx_factory({"bullets": {"columns": 3, "items": ["a", "b", "c", "d"]}})
    assert len(get_component("bullets")(ctx).groups) == 3


def test_more_columns_than_items_clamps_to_the_item_count(ctx_factory):
    ctx = ctx_factory({"bullets": {"columns": 5, "items": ["a", "b"]}})
    assert len(get_component("bullets")(ctx).groups) == 2


def test_a_heading_does_not_misalign_the_first_column(ctx_factory):
    ctx = ctx_factory({"bullets": {"columns": 2, "heading": "H", "items": ["a", "b", "c", "d"]}})
    groups = get_component("bullets")(ctx).groups
    ids = {i for g in groups for i in g}
    bullet_tops = {
        s.top
        for s in ctx.slide.shapes
        if s.shape_id in ids and s.has_text_frame and "•" in s.text_frame.text
    }
    assert len(bullet_tops) == 1


def test_the_reported_height_tracks_the_content_not_the_rect(ctx_factory):
    """``0 < h <= body_rect.height`` is true by construction: the frame is drawn at the
    rect's full height. Two lengths, so the number has to move with the content."""
    three = get_component("bullets")(ctx_factory({"bullets": {"items": ["a", "b", "c"]}}))
    six = get_component("bullets")(ctx_factory({"bullets": {"items": list("abcdef")}}))
    rect = ctx_factory({"bullets": {"items": ["a"]}}).body_rect
    assert 0 < three.height < six.height < rect.height


def test_too_many_bullets_for_the_column_height_raises(ctx_factory):
    items = [f"Item {i}" for i in range(20)]
    ctx = ctx_factory({"bullets": {"items": items}})
    with pytest.raises(LayoutError, match=r"slide 1.*bullets in the longest column need"):
        get_component("bullets")(ctx)


def test_a_non_numeric_columns_raises_a_layout_error(ctx_factory):
    ctx = ctx_factory({"bullets": {"columns": "two", "items": ["a", "b"]}})
    with pytest.raises(LayoutError, match=r"slide 1 .*'columns'.*got 'two'"):
        get_component("bullets")(ctx)


def test_the_placements_align_reaches_every_paragraph(ctx_factory):
    ctx = ctx_factory({"bullets": {"heading": "H", "items": ["a", "b"]}})
    ctx.align = "center"
    get_component("bullets")(ctx)
    written = [
        p for s in ctx.slide.shapes if s.has_text_frame for p in s.text_frame.paragraphs if p.runs
    ]
    assert {p.alignment for p in written} == {ALIGN["center"]}


def test_the_placements_anchor_reaches_the_bullet_frame(ctx_factory):
    ctx = ctx_factory({"bullets": {"items": ["a"]}})
    ctx.anchor = "middle"
    get_component("bullets")(ctx)
    frame = next(s for s in ctx.slide.shapes if s.has_text_frame)
    assert frame.text_frame.vertical_anchor == ANCHOR["middle"]


def _boxes(slide):
    return [(s.left, s.top, s.width, s.height) for s in slide.shapes if s.has_text_frame]


def test_a_heading_is_drawn_once_and_the_bullets_start_below_it(ctx_factory):
    """Drawn per column it repeats; drawn without an offset it sits on the bullets."""
    ctx = ctx_factory({"bullets": {"heading": "H", "columns": 2, "items": ["a", "b", "c", "d"]}})
    get_component("bullets")(ctx)
    headings = [s for s in ctx.slide.shapes if s.has_text_frame and s.text_frame.text == "H"]
    assert len(headings) == 1
    head_bottom = headings[0].top + headings[0].height
    bullet_tops = [s.top for s in ctx.slide.shapes if s.has_text_frame and "•" in s.text_frame.text]
    assert bullet_tops and min(bullet_tops) >= head_bottom


def test_a_tall_canvas_gives_the_heading_its_own_line_height(ctx_factory, theme):
    """Double the canvas and the head rung's line outgrows the 0.42in band, setting the
    heading's words outside their box and over the first bullet."""
    ctx = ctx_factory(
        {"bullets": {"heading": "H", "items": ["alpha", "beta"]}}, theme_override=_tall(theme)
    )
    get_component("bullets")(ctx)
    _LINE_HEIGHT = 1.2
    line_h = ctx.style("head").size * _LINE_HEIGHT / 72
    assert line_h > 0.42, "the tall canvas has to clear the floor or this proves nothing"
    heading = next(s for s in ctx.slide.shapes if s.has_text_frame and s.text_frame.text == "H")
    assert heading.height / 914400 == pytest.approx(line_h, abs=0.001)
    bullet_top = min(
        s.top for s in ctx.slide.shapes if s.has_text_frame and "•" in s.text_frame.text
    )
    assert bullet_top >= heading.top + heading.height


def test_the_heading_animates_in_with_the_column_it_titles(ctx_factory):
    ctx = ctx_factory({"bullets": {"heading": "H", "items": ["a", "b"]}})
    result = get_component("bullets")(ctx)
    heading_id = next(
        s.shape_id for s in ctx.slide.shapes if s.has_text_frame and s.text_frame.text == "H"
    )
    assert heading_id in result.groups[0]


def test_an_uneven_split_gives_the_remainder_to_the_leftmost_columns(ctx_factory):
    """Four across three: over-allocating the early columns empties the last one, and
    the slice clamps so a two-column case cannot show it."""
    ctx = ctx_factory({"bullets": {"columns": 3, "items": ["a", "b", "c", "d"]}})
    get_component("bullets")(ctx)
    columns = [
        s.text_frame.text for s in ctx.slide.shapes if s.has_text_frame and "•" in s.text_frame.text
    ]
    assert [c.count("•") for c in columns] == [2, 1, 1]


def test_a_bullet_that_yaml_read_as_a_mapping_is_rejected(ctx_factory):
    """An unquoted comma turns `- One thing, then another` into a mapping. Rendering
    its repr onto the slide is the silent-wrong-output this spec exists to refuse."""
    from deckwright.errors import LayoutError

    ctx = ctx_factory({"bullets": {"items": [{"One thing": "then another"}]}})
    with pytest.raises(LayoutError, match="item 1 is a dict, not a line of text"):
        get_component("bullets")(ctx)


def test_the_rejection_names_which_item_it_was(ctx_factory):
    from deckwright.errors import LayoutError

    ctx = ctx_factory({"bullets": {"items": ["fine", "also fine", {"bad": "one"}]}})
    with pytest.raises(LayoutError, match="item 3 is a dict"):
        get_component("bullets")(ctx)


def test_a_number_is_still_accepted_as_a_bullet(ctx_factory):
    """Only containers are refused — a bare figure is a legitimate line."""
    ctx = ctx_factory({"bullets": {"items": [2027, "and a word"]}})
    get_component("bullets")(ctx)
    assert "2027" in "\n".join(s.text_frame.text for s in ctx.slide.shapes if s.has_text_frame)
