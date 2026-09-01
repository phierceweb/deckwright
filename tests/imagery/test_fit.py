"""What a fit refuses, and how a contain fit answers "what is behind this text?" — the
letterbox band has no photograph to sample, and a caller that gets one is being lied to."""

from __future__ import annotations

import pytest

from deckwright.errors import LayoutError
from deckwright.imagery.fit import fit_image, parse_aspect, square
from deckwright.theme.model import Rect


def test_an_aspect_written_with_a_colon_is_width_over_height():
    assert parse_aspect("16:9", where="w") == pytest.approx(16 / 9)


def test_an_aspect_can_be_a_bare_number():
    assert parse_aspect(1.5, where="w") == 1.5


def test_a_word_is_not_an_aspect():
    with pytest.raises(LayoutError, match="write it as '16:9' or 1.78"):
        parse_aspect("widescreen", where="w")


def test_an_aspect_over_zero_height_is_refused():
    with pytest.raises(LayoutError, match="write it as '16:9' or 1.78"):
        parse_aspect("16:0", where="w")


def test_a_negative_aspect_is_refused():
    with pytest.raises(LayoutError, match="aspect must be positive"):
        parse_aspect(-1.78, where="w")


def test_an_unknown_fit_names_the_ones_that_exist():
    with pytest.raises(LayoutError, match="expected one of cover, contain"):
        fit_image(source_aspect=1.5, box=Rect(0, 0, 4, 3), fit="fill")


def test_a_source_with_no_area_is_refused():
    with pytest.raises(LayoutError, match="source image aspect must be positive"):
        fit_image(source_aspect=0.0, box=Rect(0, 0, 4, 3))


def test_an_unknown_align_names_the_ones_that_exist():
    with pytest.raises(LayoutError, match="expected one of left, center, right"):
        square(Rect(0, 0, 4, 3), align="middle")


def test_an_unknown_anchor_names_the_ones_that_exist():
    with pytest.raises(LayoutError, match="expected one of top, middle, bottom"):
        square(Rect(0, 0, 4, 3), anchor="center")


def test_the_letterbox_band_of_a_contain_fit_has_no_photograph_behind_it():
    """A 2:1 source contained in a 4x4 box leaves bands top and bottom that are paint."""
    fit = fit_image(source_aspect=2.0, box=Rect(0, 0, 4, 4), fit="contain")
    assert fit.dest == Rect(0.0, 1.0, 4.0, 2.0)
    assert fit.window_under(Rect(0.0, 0.0, 4.0, 0.5)) is None


def test_a_rect_inside_a_contain_fit_reports_the_source_fractions_it_covers():
    """The placement is offset from the origin, so an answer that ignores it is wrong."""
    fit = fit_image(source_aspect=2.0, box=Rect(2, 1, 4, 4), fit="contain")
    assert fit.dest == Rect(2.0, 2.0, 4.0, 2.0)
    assert fit.window_under(Rect(2.0, 2.0, 2.0, 1.0)) == (0.0, 0.0, 0.5, 0.5)


def test_a_cover_fit_trims_the_source_rather_than_shrinking_the_box():
    """A 2:1 source covering a square box loses a quarter off each side."""
    fit = fit_image(source_aspect=2.0, box=Rect(0, 0, 3, 3))
    assert fit.dest == Rect(0, 0, 3, 3)
    assert fit.trim == (0.25, 0.0, 0.25, 0.0)


def test_a_crop_is_taken_before_the_box_gets_a_say():
    """A 1:2 portrait cropped to 1:1 then covering a 1:1 box loses only the crop."""
    fit = fit_image(source_aspect=0.5, box=Rect(0, 0, 3, 3), crop=1.0)
    assert fit.trim == (0.0, 0.25, 0.0, 0.25)
