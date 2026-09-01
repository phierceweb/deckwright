import pytest

from deckwright.errors import LayoutError, ThemeError
from deckwright.layouts.place import (
    Placed,
    Reserved,
    check_placements,
    clear_reserved,
    content_rect,
    resolve_at,
)
from deckwright.theme.model import Rect
from deckwright.utils.spans import Share
from deckwright.theme.scale import Grid, Scale

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
# Built by hand, not by content_rect: the at: tests must not depend on how the
# content band was derived.
AREA = Rect(GRID.left, GRID.body_top, GRID.content_w, 5.30)


def at(**kw):
    return resolve_at(kw, grid=GRID, area=AREA, where="slide 1 placement 1 (chart)")


def test_a_column_span_starts_at_its_first_column():
    assert at(cols=[0, 6]).left == pytest.approx(GRID.col_x(0))


def test_a_column_span_is_as_wide_as_the_columns_it_covers():
    assert at(cols=[0, 6]).width == pytest.approx(GRID.span_w(6))


def test_a_full_span_fills_the_content_width():
    assert at(cols=[0, 12]).width == pytest.approx(GRID.content_w)


def test_a_span_without_rows_fills_the_content_band_vertically():
    r = at(cols=[0, 6])
    assert (r.top, r.height) == pytest.approx((AREA.top, AREA.height))


def test_two_halves_of_the_grid_do_not_overlap():
    left, right = at(cols=[0, 6]), at(cols=[6, 12])
    assert right.left >= left.right


def test_a_span_running_past_the_last_column_is_rejected():
    with pytest.raises(LayoutError, match=r"cols \[0, 13\] out of range"):
        at(cols=[0, 13])


def test_a_span_that_ends_where_it_starts_is_rejected():
    with pytest.raises(LayoutError, match="out of range"):
        at(cols=[4, 4])


def test_an_at_naming_neither_cols_nor_box_is_rejected():
    with pytest.raises(LayoutError, match="needs 'cols' or 'box'"):
        at(rows=[0, 6])


# --- rows ------------------------------------------------------------------


def test_a_row_span_takes_a_share_of_the_twelve_row_content_band():
    r = at(cols=[0, 12], rows=[0, 6])
    assert (r.top, r.height) == pytest.approx((AREA.top, AREA.height / 2))


def test_rows_divide_the_content_band_not_the_canvas():
    """A row band never reaches above body_top or below the bottom margin."""
    r = at(cols=[0, 12], rows=[0, 12])
    assert (r.top, r.bottom) == pytest.approx((AREA.top, AREA.bottom))


def test_a_row_past_the_last_row_is_rejected():
    with pytest.raises(LayoutError, match=r"rows \[6, 13\] out of range"):
        at(cols=[0, 12], rows=[6, 13])


def test_an_inverted_row_span_is_rejected():
    with pytest.raises(LayoutError, match="out of range"):
        at(cols=[0, 12], rows=[8, 2])


# --- box -------------------------------------------------------------------


def test_a_box_is_read_as_fractions_of_the_canvas():
    r = at(box=[0.5, 0.25, 0.25, 0.5])
    assert (r.left, r.top, r.width, r.height) == pytest.approx(
        (13.333 * 0.5, 7.5 * 0.25, 13.333 * 0.25, 7.5 * 0.5)
    )


def test_the_same_box_scales_with_the_canvas():
    huge = Scale(slide_w=26.666, slide_h=15.0)
    grid = Grid(
        scale=huge,
        left_frac=0.0465,
        right_frac=0.0458,
        top_frac=0.0400,
        bottom_frac=0.0667,
        columns=12,
        rows=12,
        gutter_frac=0.0135,
        body_top_frac=0.2267,
    )
    r = resolve_at({"box": (0.5, 0.25, 0.25, 0.5)}, grid=grid, area=AREA, where="w")
    assert (r.left, r.width) == pytest.approx((13.333, 6.6665))


def test_a_box_cannot_be_combined_with_cols():
    with pytest.raises(LayoutError, match="'box' cannot be combined"):
        at(box=[0, 0, 1, 1], cols=[0, 6])


# --- malformed at ----------------------------------------------------------


def test_an_unknown_at_key_is_rejected_by_name():
    with pytest.raises(LayoutError, match="unknown 'at' key 'col'"):
        at(col=[0, 6])


def test_a_scalar_at_is_rejected():
    with pytest.raises(LayoutError, match="'at' must be a mapping"):
        resolve_at("left", grid=GRID, area=AREA, where="w")


# --- reserved regions ------------------------------------------------------


def band(name, x, y, w, h):
    return Reserved(name=name, poly=((x, y), (x + w, y), (x + w, y + h), (x, y + h)))


LEFT_RAIL = band("rail", 0.0, 0.0, 0.10, 1.0)
FOOTER = band("footer", 0.0, 0.92, 1.0, 0.08)
BANNER = band("banner", 0.0, 0.0, 1.0, 0.30)
WEDGE = Reserved(name="logo-wedge", poly=((1.0, 0.7227), (1.0, 1.0), (0.8250, 1.0)))


def test_without_reservations_the_band_runs_from_body_top_to_the_bottom_margin():
    r = content_rect(grid=GRID)
    assert (r.left, r.top, r.width) == pytest.approx((GRID.left, GRID.body_top, GRID.content_w))
    assert r.bottom == pytest.approx(GRID.slide_h - GRID.bottom)


def test_a_left_rail_moves_the_content_band_right():
    assert content_rect(grid=GRID, reserved=(LEFT_RAIL,)).left == pytest.approx(13.333 * 0.10)


def test_a_footer_band_lifts_the_content_bottom():
    assert content_rect(grid=GRID, reserved=(FOOTER,)).bottom == pytest.approx(7.5 * 0.92)


def test_a_top_banner_pushes_the_content_down():
    assert content_rect(grid=GRID, reserved=(BANNER,)).top == pytest.approx(7.5 * 0.30)


def test_rails_on_opposite_edges_both_apply():
    right_rail = band("right-rail", 0.90, 0.0, 0.10, 1.0)
    r = content_rect(grid=GRID, reserved=(LEFT_RAIL, right_rail))
    assert (r.left, r.right) == pytest.approx((13.333 * 0.10, 13.333 * 0.90))


def test_a_corner_wedge_leaves_the_content_band_whole():
    r = content_rect(grid=GRID, reserved=(WEDGE,))
    assert (r.left, r.width) == pytest.approx((GRID.left, GRID.content_w))


def test_a_region_clear_of_the_content_band_changes_nothing():
    bleed = band("bleed", 0.0, 0.0, 0.03, 1.0)
    assert content_rect(grid=GRID, reserved=(bleed,)).left == pytest.approx(GRID.left)


def test_a_region_covering_the_whole_band_is_rejected():
    with pytest.raises(ThemeError, match="covers the whole content area"):
        content_rect(grid=GRID, reserved=(band("everything", 0.0, 0.0, 1.0, 1.0),))


def test_a_region_of_fewer_than_three_points_is_rejected():
    with pytest.raises(ThemeError, match="at least 3 points"):
        Reserved(name="degenerate", poly=((0.0, 0.0), (1.0, 1.0)))


def test_a_zero_height_region_is_rejected():
    with pytest.raises(ThemeError, match="encloses no area"):
        Reserved(name="hairline", poly=((0.0, 0.5), (1.0, 0.5), (0.5, 0.5)))


def test_a_region_point_that_is_not_an_x_y_pair_is_rejected():
    with pytest.raises(ThemeError, match="needs x, y points"):
        Reserved(name="lopsided", poly=((0.0, 0.0), (1.0,), (1.0, 1.0)))


def test_a_wedge_is_hit_only_where_the_polygon_actually_reaches():
    scale = GRID.scale
    assert WEDGE.hits(Rect(11.5, 6.5, 1.5, 0.8), scale=scale) is True
    # Inside the wedge's bounding box but above its diagonal: a bounding-box
    # implementation calls this a hit.
    assert WEDGE.hits(Rect(11.2, 5.5, 0.6, 0.4), scale=scale) is False


# --- guards ----------------------------------------------------------------


def test_two_placements_sharing_a_column_are_rejected_naming_both():
    placed = [
        Placed("placement 1 (chart)", at(cols=[0, 7])),
        Placed("placement 2 (bullets)", at(cols=[6, 12])),
    ]
    with pytest.raises(
        LayoutError, match=r"placement 1 \(chart\) overlaps placement 2 \(bullets\)"
    ):
        check_placements(placed, area=AREA, grid=GRID)


def test_side_by_side_placements_are_accepted():
    check_placements(
        [Placed("p1", at(cols=[0, 6])), Placed("p2", at(cols=[6, 12]))], area=AREA, grid=GRID
    )


def test_stacked_row_bands_are_accepted():
    check_placements(
        [Placed("p1", at(cols=[0, 12], rows=[0, 6])), Placed("p2", at(cols=[0, 12], rows=[6, 12]))],
        area=AREA,
        grid=GRID,
    )


def test_a_box_outside_the_content_band_is_rejected():
    with pytest.raises(LayoutError, match="falls outside the content area"):
        check_placements(
            [Placed("placement 1 (chart)", at(box=[0.0, 0.0, 0.5, 0.5]))], area=AREA, grid=GRID
        )


def test_a_bleeding_placement_may_leave_the_content_band():
    check_placements(
        [Placed("placement 1 (image)", at(box=[0.0, 0.0, 1.0, 1.0]), bleed=True)],
        area=AREA,
        grid=GRID,
    )


def test_a_bleeding_placement_may_sit_under_another():
    check_placements(
        [Placed("p1", at(box=[0.0, 0.0, 1.0, 1.0]), bleed=True), Placed("p2", at(cols=[0, 6]))],
        area=AREA,
        grid=GRID,
    )


def test_a_placement_over_a_reserved_region_is_rejected_by_region_name():
    with pytest.raises(LayoutError, match="reserved region 'logo-wedge'"):
        check_placements(
            [Placed("placement 1 (chart)", at(cols=[8, 12]))],
            area=AREA,
            grid=GRID,
            reserved=(WEDGE,),
        )


def test_a_placement_above_a_corner_wedge_is_accepted():
    check_placements(
        [Placed("placement 1 (chart)", at(cols=[8, 12], rows=[0, 6]))],
        area=AREA,
        grid=GRID,
        reserved=(WEDGE,),
    )


# --- clearing a corner wedge ----------------------------------------------


def test_a_full_height_span_is_narrowed_to_clear_a_corner_wedge():
    """The canonical at: {cols: full} must stay usable under a brand logo wedge."""
    full = at(cols=[0, 12])
    cleared = clear_reserved(full, reserved=(WEDGE,), grid=GRID, where="w")
    assert cleared.right < full.right
    assert (cleared.left, cleared.top, cleared.height) == pytest.approx(
        (full.left, full.top, full.height)
    )


def test_the_narrowed_edge_keeps_a_gutter_clear_of_the_wedge():
    cleared = clear_reserved(at(cols=[0, 12]), reserved=(WEDGE,), grid=GRID, where="w")
    assert WEDGE.hits(cleared, scale=GRID.scale) is False
    reach = WEDGE.x_span(scale=GRID.scale, top=cleared.top, bottom=cleared.bottom)
    assert reach[0] - cleared.right == pytest.approx(GRID.gutter, abs=0.01)


def test_a_span_bounded_above_the_wedge_keeps_the_full_content_width():
    short = at(cols=[0, 12], rows=[0, 6])
    assert clear_reserved(short, reserved=(WEDGE,), grid=GRID, where="w") == short


def test_a_region_reaching_in_from_the_left_moves_the_left_edge_right():
    rail = band("rail", 0.0, 0.0, 0.10, 1.0)
    cleared = clear_reserved(at(cols=[0, 12]), reserved=(rail,), grid=GRID, where="w")
    assert cleared.left == pytest.approx(13.333 * 0.10 + GRID.gutter)


def test_a_region_a_placement_cannot_escape_is_rejected_by_name():
    with pytest.raises(LayoutError, match="reserved region 'curtain' leaves no room"):
        clear_reserved(
            at(cols=[0, 12]),
            reserved=(band("curtain", 0.0, 0.0, 1.0, 1.0),),
            grid=GRID,
            where="slide 1 placement 1 (chart)",
        )


def test_a_region_the_placement_only_touches_along_an_edge_is_not_a_collision():
    """content_rect already cut this band away; the placement flush against the
    cut edge must not then be told there is no room."""
    footer = band("footer", 0.0, 0.9, 1.0, 0.1)
    band_bottom = 7.5 * 0.9
    flush = Rect(GRID.left, AREA.top, GRID.content_w, band_bottom - AREA.top)
    assert clear_reserved(flush, reserved=(footer,), grid=GRID, where="w") == flush
    check_placements([Placed("p1", flush)], area=flush, grid=GRID, reserved=(footer,))


# --- a box: is the escape hatch, so it escapes ---------------------------------


def _box(spec):
    """One placement written as a box:, resolved and marked exact the way compose does."""
    return Placed(
        "boxed", resolve_at({"box": spec}, grid=GRID, area=AREA, where="boxed"), exact=True
    )


def test_a_box_may_sit_above_the_content_band():
    """The doc calls box: the escape hatch. Held to the band it could not reach the
    top fifth of the slide even with the title moved away — which is not an escape."""
    check_placements([_box([0.06, 0.04, 0.5, 0.10])], area=AREA, grid=GRID)


def test_a_box_may_sit_below_the_content_band():
    check_placements([_box([0.06, 0.90, 0.5, 0.08])], area=AREA, grid=GRID)


def test_a_box_may_still_not_leave_the_canvas():
    """Off the slide entirely is what bleed: is for, and it must still be said."""
    with pytest.raises(LayoutError, match="falls outside the canvas"):
        check_placements([_box([0.80, 0.40, 0.50, 0.10])], area=AREA, grid=GRID)


def test_a_column_placement_is_still_held_to_the_content_band():
    """The exemption follows the box:, not every placement — cols must stay in the band."""
    outside = Placed("cols", Rect(GRID.left, 0.2, 3.0, 0.5))
    with pytest.raises(LayoutError, match="falls outside the content area"):
        check_placements([outside], area=AREA, grid=GRID)


# --- split shares ------------------------------------------------------------


def test_a_split_that_divides_the_grid_lands_exactly_where_cols_would():
    """The whole point of the divisible branch: four across a twelve-column band is
    the same geometry a hand-written [0,3][3,6][6,9][9,12] gives, to the bit."""
    shares = [at(cols=Share(band="full", index=k, span=1, total=4)) for k in range(4)]
    spans = [at(cols=(a, b)) for a, b in ((0, 3), (3, 6), (6, 9), (9, 12))]
    assert [(r.left, r.width) for r in shares] == [(r.left, r.width) for r in spans]


def test_a_split_the_grid_cannot_divide_falls_to_an_even_width():
    """Five across twelve columns has no whole-column answer, and is still a row."""
    five = [at(cols=Share(band="full", index=k, span=1, total=5)) for k in range(5)]
    widths = {round(r.width, 9) for r in five}
    assert len(widths) == 1
    assert five[0].left == pytest.approx(GRID.col_x(0))
    assert five[-1].right == pytest.approx(GRID.col_x(0) + GRID.span_w(12))


def test_a_share_spanning_two_covers_both_and_the_gutter_between():
    one = at(cols=Share(band="full", index=0, span=1, total=4))
    two = at(cols=Share(band="full", index=0, span=2, total=4))
    assert two.width == pytest.approx(one.width * 2 + GRID.gutter)


def test_shares_divide_the_band_they_were_given_not_the_whole_width():
    half = at(cols="right-half")
    shares = [at(cols=Share(band="right-half", index=k, span=1, total=2)) for k in range(2)]
    assert shares[0].left == pytest.approx(half.left)
    assert shares[-1].right == pytest.approx(half.right)
