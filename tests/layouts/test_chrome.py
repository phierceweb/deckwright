import pytest

from deckwright.errors import LayoutError
from deckwright.layouts.chrome import CHROME_ORDER, ChromeField, chrome_bands, chrome_field
from deckwright.layouts.place import content_rect
from deckwright.theme.scale import Grid, Scale
from deckwright.utils.text import LINE_HEIGHT

SCALE = Scale(slide_w=13.333, slide_h=7.5)
GRID = Grid(
    scale=SCALE,
    left_frac=0.0465,
    right_frac=0.0458,
    top_frac=0.0400,
    bottom_frac=0.0667,
    columns=12,
    rows=12,
    gutter_frac=0.0135,
    body_top_frac=0.2267,
)


# --- chrome: the default stack ---------------------------------------------


def test_the_chrome_order_is_kicker_title_subtitle():
    assert CHROME_ORDER == ("kicker", "title", "subtitle")


def bands(lines, **fields):
    """Place chrome, keyed by field name for the assertions."""
    placed = chrome_bands(lines, fields=fields, grid=GRID)
    return {band.name: band for band in placed}


def test_chrome_bands_start_at_the_top_margin_and_span_the_content_width():
    out = bands({"kicker": ("K", 14), "title": ("T", 32)})
    assert (out["kicker"].rect.left, out["kicker"].rect.top) == pytest.approx((GRID.left, GRID.top))
    assert out["title"].rect.width == pytest.approx(GRID.content_w)


def test_each_chrome_band_stacks_below_the_one_before_it():
    out = bands({"kicker": ("K", 14), "title": ("T", 32), "subtitle": ("S", 15)})
    assert out["title"].rect.top == pytest.approx(out["kicker"].rect.bottom)
    assert out["subtitle"].rect.top == pytest.approx(out["title"].rect.bottom)


def test_the_kicker_sits_above_the_title_however_the_fields_were_written():
    out = bands({"subtitle": ("S", 15), "title": ("T", 32), "kicker": ("K", 14)})
    assert out["kicker"].rect.top < out["title"].rect.top < out["subtitle"].rect.top


def test_an_absent_chrome_field_gets_no_band():
    assert set(bands({"title": ("T", 32)})) == {"title"}


def test_a_title_only_slide_starts_its_title_at_the_top_margin():
    assert bands({"title": ("T", 32)})["title"].rect.top == pytest.approx(GRID.top)


def test_a_chrome_band_scales_with_its_type_size():
    small = bands({"title": ("T", 16)})["title"].rect
    big = bands({"title": ("T", 32)})["title"].rect
    assert big.height == pytest.approx(2 * small.height)


def test_an_unknown_chrome_field_is_rejected():
    with pytest.raises(LayoutError, match="unknown chrome field 'eyebrow'"):
        chrome_bands({"eyebrow": ("E", 14)}, fields={}, grid=GRID)


def test_short_chrome_leaves_the_band_starting_at_body_top():
    placed = chrome_bands({"kicker": ("K", 14), "title": ("T", 32)}, fields={}, grid=GRID)
    assert content_rect(grid=GRID, chrome=placed).top == pytest.approx(GRID.body_top)


def test_tall_chrome_pushes_the_band_below_body_top():
    placed = chrome_bands({"title": ("T", 96)}, fields={}, grid=GRID)
    r = content_rect(grid=GRID, chrome=placed)
    assert r.top > GRID.body_top
    assert r.top > placed[0].rect.bottom


# --- chrome: composed ------------------------------------------------------


def test_a_chrome_field_given_a_box_lands_exactly_there():
    field = ChromeField(at={"box": (0.1, 0.63, 0.5, 0.14)})
    rect = bands({"title": ("T", 60)}, title=field)["title"].rect
    assert (rect.left, rect.top, rect.width, rect.height) == pytest.approx(
        (13.333 * 0.10, 7.5 * 0.63, 13.333 * 0.50, 7.5 * 0.14)
    )


def test_a_boxed_chrome_line_is_not_stacked_so_it_leaves_the_content_band_alone():
    field = ChromeField(at={"box": (0.1, 0.63, 0.5, 0.14)})
    placed = chrome_bands({"title": ("T", 60)}, fields={"title": field}, grid=GRID)
    assert placed[0].stacked is False
    assert content_rect(grid=GRID, chrome=placed).top == pytest.approx(GRID.body_top)


def test_a_column_chrome_line_takes_the_columns_measure_at_the_top_margin():
    field = ChromeField(at={"cols": (7, 12)})
    rect = bands({"title": ("T", 32)}, title=field)["title"].rect
    assert (rect.left, rect.top) == pytest.approx((GRID.col_x(7), GRID.top))
    assert rect.width == pytest.approx(GRID.span_w(5))


def test_a_narrower_measure_wraps_a_title_the_content_width_would_not():
    wide = bands({"title": (WRAPS, 31.2)})["title"].rect
    narrow = bands({"title": (WRAPS, 31.2)}, title=ChromeField(at={"cols": (0, 4)}))["title"].rect
    assert narrow.height > wide.height


def test_rows_on_a_chrome_line_divide_the_whole_canvas_not_the_content_band():
    field = ChromeField(at={"cols": (0, 12), "rows": (6, 8)})
    rect = bands({"title": ("T", 32)}, title=field)["title"].rect
    assert rect.top == pytest.approx(GRID.slide_h * 6 / 12)
    assert rect.height == pytest.approx(GRID.slide_h * 2 / 12)


def test_a_placed_line_leaves_its_stacked_siblings_stacking_from_the_top_margin():
    out = bands(
        {"kicker": ("K", 14), "title": ("T", 32), "subtitle": ("S", 15)},
        title=ChromeField(at={"box": (0.5, 0.5, 0.4, 0.1)}),
    )
    assert out["kicker"].rect.top == pytest.approx(GRID.top)
    assert out["subtitle"].rect.top == pytest.approx(out["kicker"].rect.bottom)


def test_a_chrome_box_outside_the_canvas_names_the_fractions_it_should_have_been():
    with pytest.raises(LayoutError, match=r"box .* leaves the canvas"):
        chrome_field(
            {"at": {"box": {"x": "62%", "y": "60%", "w": "1130%", "h": "125%"}}}, name="title"
        )


def test_the_canvas_bound_tolerates_float_dust_and_nothing_an_author_could_see():
    """Brackets the slack from both sides: a billionth past the edge is float residue
    and inside, a thousandth is an overhang. The wildly-out case above tests neither."""
    dust = chrome_field(
        {"at": {"box": {"x": "50%", "y": "0%", "w": f"{50 + 1e-7}%", "h": "10%"}}}, name="title"
    )
    assert dust.at["box"] == pytest.approx((0.5, 0.0, 0.5 + 1e-9, 0.1))

    with pytest.raises(LayoutError, match=r"box .* leaves the canvas"):
        chrome_field(
            {"at": {"box": {"x": "50%", "y": "0%", "w": "50.1%", "h": "10%"}}}, name="title"
        )


def test_a_stacked_line_cannot_anchor_because_it_has_no_frame_of_its_own():
    with pytest.raises(LayoutError, match="a stacked line shares the stack's frame"):
        chrome_bands(
            {"title": ("T", 32)}, fields={"title": ChromeField(anchor="bottom")}, grid=GRID
        )


def test_a_slide_override_replaces_only_the_keys_it_sets():
    themed = ChromeField(at={"box": (0, 0.05, 1, 0.14)}, align="center")
    merged = themed.merge(ChromeField(align="right"))
    assert merged.align == "right"
    assert merged.at == themed.at


def test_a_field_overriding_nothing_is_left_alone():
    themed = ChromeField(at={"cols": (6, 12)}, align="center", rung="hero")
    assert themed.merge(None) is themed
    assert themed.merge(ChromeField()) == themed


def test_a_chrome_field_defaults_to_left_aligned_and_top_anchored():
    assert (ChromeField().alignment, ChromeField().anchoring) == ("left", "top")


def test_an_unknown_chrome_key_lists_the_ones_that_exist():
    with pytest.raises(LayoutError, match=r"unknown key 'colour'; known keys: at, align"):
        chrome_field({"colour": "red"}, name="title")


def test_a_chrome_anchor_outside_the_vocabulary_is_rejected():
    with pytest.raises(LayoutError, match="anchor must be one of top, middle, bottom"):
        chrome_field({"anchor": "baseline"}, name="title")


# --- chrome that wraps -----------------------------------------------------

WRAPS = "Retrieval-augmented generation cut our support ticket backlog in half"
SUBTITLE = "Q3 results across all four regions"


def test_a_title_that_wraps_gets_a_band_as_tall_as_the_lines_it_takes():
    one = bands({"title": ("Short title", 31.2)})["title"].rect
    two = bands({"title": (WRAPS, 31.2)})["title"].rect
    assert two.height == pytest.approx(2 * one.height)


def test_a_wrapping_title_pushes_the_subtitle_down_by_the_line_it_gained():
    one = bands({"title": ("Short title", 31.2), "subtitle": (SUBTITLE, 15.6)})
    two = bands({"title": (WRAPS, 31.2), "subtitle": (SUBTITLE, 15.6)})
    assert two["subtitle"].rect.top - one["subtitle"].rect.top == pytest.approx(
        31.2 * LINE_HEIGHT / 72
    )


def test_the_further_a_title_wraps_the_lower_the_subtitle_sits():
    tops = [
        bands(
            {
                "kicker": ("Section two", 14),
                "title": (WRAPS * n, 31.2),
                "subtitle": (SUBTITLE, 15.6),
            }
        )["subtitle"].rect.top
        for n in (1, 2, 3)
    ]
    assert tops[0] < tops[1] < tops[2]


def test_a_wrapping_title_pushes_the_content_band_down():
    short = chrome_bands(
        {"kicker": ("K", 14), "title": ("Short title", 31.2), "subtitle": (SUBTITLE, 15.6)},
        fields={},
        grid=GRID,
    )
    wrapped = chrome_bands(
        {"kicker": ("K", 14), "title": (WRAPS, 31.2), "subtitle": (SUBTITLE, 15.6)},
        fields={},
        grid=GRID,
    )
    assert content_rect(grid=GRID, chrome=wrapped).top > content_rect(grid=GRID, chrome=short).top


def test_a_chrome_stack_that_fills_the_slide_is_rejected():
    placed = chrome_bands({"title": (WRAPS * 6, 96)}, fields={}, grid=GRID)
    with pytest.raises(LayoutError, match="leaving no content area"):
        content_rect(grid=GRID, chrome=placed)


def test_a_chrome_field_given_a_bare_size_is_rejected():
    with pytest.raises(LayoutError, match=r"needs a \(text, type size\) pair"):
        chrome_bands({"title": 32}, fields={}, grid=GRID)


def test_a_chrome_field_given_a_non_numeric_size_is_rejected():
    with pytest.raises(LayoutError, match="needs a numeric type size"):
        chrome_bands({"title": ("T", "big")}, fields={}, grid=GRID)


def test_a_chrome_field_given_a_zero_size_is_rejected():
    with pytest.raises(LayoutError, match="needs a positive type size"):
        chrome_bands({"title": ("T", 0)}, fields={}, grid=GRID)


def test_three_column_chrome_lines_stack_instead_of_landing_on_each_other():
    """A measure narrowed to clear a template's artwork is still a stack, not a pile."""
    field = ChromeField(at={"cols": (5, 12)})
    out = bands(
        {"kicker": ("K", 14), "title": ("T", 32), "subtitle": ("S", 15)},
        kicker=field,
        title=field,
        subtitle=field,
    )
    assert out["kicker"].rect.top == pytest.approx(GRID.top)
    assert out["title"].rect.top == pytest.approx(out["kicker"].rect.bottom)
    assert out["subtitle"].rect.top == pytest.approx(out["title"].rect.bottom)
    assert all(band.rect.left == pytest.approx(GRID.col_x(5)) for band in out.values())


def test_a_column_chrome_line_still_pushes_the_content_band_down():
    """It sits in the stack, so a placement below it must clear it like any other."""
    placed = chrome_bands(
        {"title": (WRAPS, 31.2)}, fields={"title": ChromeField(at={"cols": (5, 12)})}, grid=GRID
    )
    assert content_rect(grid=GRID, chrome=placed).top > GRID.body_top


def test_a_chrome_box_too_short_for_its_text_names_the_slide(theme):
    """The most-met build error names its slide like every other."""
    lines = {"title": ("A title long enough that it certainly wraps to two lines", 40.0)}
    fields = {
        "title": chrome_field(
            {"at": {"box": {"x": "6%", "y": "20%", "w": "60%", "h": "8%"}}}, name="title"
        )
    }
    with pytest.raises(LayoutError, match=r"^slide 7: chrome field 'title' wraps to"):
        chrome_bands(lines, fields=fields, grid=theme.grid, slide=7)


def _title_field(h):
    return chrome_field({"at": {"box": {"x": "6%", "y": "20%", "w": "60%", "h": h}}}, name="title")


def test_an_auto_height_box_takes_the_depth_its_text_wraps_to(theme):
    """A hand-measured `h:` is tuned against one title at one rung; re-shuffling content
    changes the title."""
    short = chrome_bands(
        {"title": ("Short", 40.0)}, fields={"title": _title_field("auto")}, grid=theme.grid
    )
    long = chrome_bands(
        {"title": ("A title long enough that it certainly wraps to several lines", 40.0)},
        fields={"title": _title_field("auto")},
        grid=theme.grid,
    )
    assert long[0].rect.height > short[0].rect.height


def test_an_auto_height_box_never_refuses_its_own_text(theme):
    """The declared-height branch raises when the text outgrows the box; `auto` has no
    declared height to outgrow."""
    bands = chrome_bands(
        {"title": ("A title long enough that it certainly wraps to several lines", 40.0)},
        fields={"title": _title_field("auto")},
        grid=theme.grid,
        slide=1,
    )
    assert bands[0].rect.height > 0


def test_a_declared_height_still_refuses_text_that_outgrows_it(theme):
    """`auto` is opt-in; a number keeps meaning exactly what it did."""
    with pytest.raises(LayoutError, match="wraps to"):
        chrome_bands(
            {"title": ("A title long enough that it certainly wraps to several lines", 40.0)},
            fields={"title": _title_field("8%")},
            grid=theme.grid,
        )


def test_an_auto_height_box_keeps_the_top_it_was_given(theme):
    """Only the depth is content-sized; x, y and w are still the author's."""
    bands = chrome_bands(
        {"title": ("Short", 40.0)}, fields={"title": _title_field("auto")}, grid=theme.grid
    )
    assert bands[0].rect.top == pytest.approx(0.20 * theme.grid.slide_h)


def test_a_chrome_refusal_on_an_unmeasured_face_says_the_estimate_errs_wide(theme):
    lines = {"title": ("A title long enough that it certainly wraps to two lines", 40.0)}
    fields = {"title": _title_field("8%")}
    with pytest.raises(LayoutError, match=r"'Segoe UI' has no width table"):
        chrome_bands(lines, fields=fields, grid=theme.grid, slide=7, faces={"title": "Segoe UI"})
