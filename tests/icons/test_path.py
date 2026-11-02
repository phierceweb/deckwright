"""SVG path data to DrawingML. A mirrored arc, a dropped relative offset or an off-by-one
bézier all produce a deck that builds and passes, so the expectations here are literal numbers."""

from __future__ import annotations

import math

import pytest

from deckwright.errors import SpecError
from deckwright.icons.path import UNITS, parse, to_drawingml

SQUARE = (0.0, 0.0, 100.0, 100.0)


def points(d: str, view=SQUARE):
    """Every emitted point as (x, y) integers, in the order drawn."""
    import re

    xml = to_drawingml(parse(d), view=view)
    return [(int(x), int(y)) for x, y in re.findall(r'x="(-?\d+)" y="(-?\d+)"', xml)]


def tags(d: str):
    import re

    return re.findall(r"<a:(\w+)[/>]", to_drawingml(parse(d), view=SQUARE))


# --- the command vocabulary --------------------------------------------------


def test_a_line_lands_where_the_view_scales_it():
    """Half of a 100-unit view is half of the unit grid."""
    assert points("M 0 0 L 50 100") == [(0, 0), (UNITS // 2, UNITS)]


def test_a_relative_command_is_an_offset_from_the_pen():
    """'l 50 50' from (25,25) ends at (75,75) — reading it as absolute lands at (50,50)."""
    assert points("M 25 25 l 50 50")[-1] == (75_000, 75_000)


def test_a_repeated_argument_set_repeats_the_command():
    assert points("M 0 0 L 10 0 20 0") == [(0, 0), (10_000, 0), (20_000, 0)]


def test_a_second_moveto_pair_draws_a_line_not_a_jump():
    """Per the SVG grammar, extra pairs after an M are implicit L, not more M."""
    assert tags("M 0 0 10 10") == ["moveTo", "lnTo"]


def test_horizontal_and_vertical_keep_the_other_axis():
    assert points("M 10 20 H 60 V 70") == [(10_000, 20_000), (60_000, 20_000), (60_000, 70_000)]


def test_a_close_emits_a_close_and_returns_the_pen_to_the_subpath_start():
    """'Z' then a relative move is measured from the start point, not the last point."""
    assert tags("M 10 10 L 90 90 Z l 10 0")[-1] == "lnTo"
    assert points("M 10 10 L 90 90 Z l 10 0")[-1] == (20_000, 10_000)


def test_a_quadratic_is_raised_to_a_cubic_at_two_thirds():
    """Q(0,0)(60,0)(60,60) has cubic controls at 2/3 of the way to the quadratic's."""
    got = points("M 0 0 Q 60 0 60 60")
    assert got[1] == (40_000, 0)  # p0 + 2/3 (ctrl - p0)
    assert got[2] == (60_000, 20_000)  # p1 + 2/3 (ctrl - p1)
    assert got[3] == (60_000, 60_000)


def test_a_smooth_cubic_reflects_the_previous_control_through_the_pen():
    """S's first control is the mirror of C's last: (40,10) about (50,50) is (60,90)."""
    assert points("M 0 0 C 10 10 40 10 50 50 S 90 90 100 50")[4] == (60_000, 90_000)


def test_a_smooth_cubic_with_no_curve_before_it_starts_at_the_pen():
    assert points("M 30 30 S 90 90 100 50")[1] == (30_000, 30_000)


# --- arcs --------------------------------------------------------------------


def test_a_quarter_arc_ends_where_it_was_told_to():
    """The endpoint is given, so it must survive the centre-parameter round trip."""
    assert points("M 50 0 A 50 50 0 0 1 100 50")[-1] == (100_000, 50_000)


def test_the_sweep_flag_decides_which_way_round_the_arc_goes():
    """A semicircle on the same two endpoints: sweep 1 over the top, 0 under. Asserted as a side
    of the chord, so one handled direction cannot pass by producing the same arc twice."""
    half = UNITS / 2
    over = points("M 0 50 A 50 50 0 0 1 100 50")
    under = points("M 0 50 A 50 50 0 0 0 100 50")
    assert max(y for _, y in over) <= half + 1, over
    assert min(y for _, y in under) >= half - 1, under
    # Top to bottom is the pair needing the negative-sweep correction: without it this arc
    # bulges right instead of left, and every left/right semicircle above still passes.
    left = points("M 50 0 A 50 50 0 0 0 50 100")
    assert min(x for x, _ in left) <= 1, left
    assert max(x for x, _ in left) <= half + 1, left


def test_a_full_circle_of_two_arcs_stays_on_its_radius():
    """Every emitted point of a circle sits within a unit of the drawn radius."""
    got = points("M 50 0 A 50 50 0 1 0 50 100 A 50 50 0 1 0 50 0")
    half = UNITS / 2
    radii = [math.hypot(x - half, y - half) for x, y in got]
    # Bézier controls sit outside the circle; the on-curve points are every third.
    on_curve = radii[0::3]
    assert all(abs(r - half) < 60 for r in on_curve), sorted(on_curve)[:3]


def test_an_arc_of_zero_radius_degenerates_to_a_line():
    assert points("M 0 0 A 0 0 0 0 1 40 40")[-1] == (40_000, 40_000)


def test_radii_too_small_to_reach_the_endpoint_are_scaled_up():
    """The spec says grow them rather than give up; the endpoint must still be hit."""
    assert points("M 0 0 A 1 1 0 0 1 80 0")[-1] == (80_000, 0)


# --- the view ----------------------------------------------------------------


def test_a_tall_view_is_fitted_and_centred_not_stretched():
    """A 50x100 drawing keeps its proportions, so its width is inset either side."""
    got = points("M 0 0 L 50 100", view=(0.0, 0.0, 50.0, 100.0))
    assert got == [(25_000, 0), (75_000, UNITS)]


def test_the_views_origin_is_subtracted():
    """Material Symbols ships 0 -960 960 960; ignoring the origin draws off the shape."""
    assert points("M 0 -960 L 960 0", view=(0.0, -960.0, 960.0, 960.0)) == [(0, 0), (UNITS, UNITS)]


# --- what is rejected --------------------------------------------------------


def test_data_that_starts_with_a_number_is_rejected():
    with pytest.raises(SpecError, match="starts with a number"):
        parse("10 10 L 20 20")


def test_an_unknown_command_is_rejected():
    with pytest.raises(SpecError, match="unknown svg path command 'B'"):
        parse("M 0 0 B 1 2")


def test_a_command_missing_arguments_is_rejected():
    with pytest.raises(SpecError, match="wants 6 numbers, got 4"):
        parse("M 0 0 C 1 2 3 4")


def test_a_view_with_no_extent_is_rejected():
    with pytest.raises(SpecError, match="positive width and height"):
        to_drawingml(parse("M 0 0"), view=(0.0, 0.0, 0.0, 10.0))
