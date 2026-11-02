"""`fill-ground`: a shape filled to stand off what is behind it, and all but vanishing into it."""

from __future__ import annotations

import pytest

import deckwright.components  # noqa: F401 — registers the built-ins
from deckwright.layouts.components import get_component
from deckwright.qa.fills import check_fill_ground
from deckwright.qa.model import Severity
from deckwright.theme.model import Rect
from tests.qa.test_geometry_bounds import _manifest, _shape, _theme


def _filled(fill, ground):
    shape = _shape([1.0, 1.0, 2.0, 1.0])
    shape.update(fill=fill, ground=ground)
    return shape


@pytest.mark.parametrize(("fill", "ground"), [("242E3D", "242E3D"), ("44546A", "3282BE")])
def test_a_fill_within_three_to_one_of_its_ground_is_a_warning(fill, ground):
    findings = check_fill_ground(_manifest(_filled(fill, ground)), _theme())
    assert [(f.check, f.severity) for f in findings] == [("fill-ground", Severity.WARN)]
    assert fill in findings[0].detail and ground in findings[0].detail


def test_a_fill_that_stands_off_its_ground_is_clean():
    assert check_fill_ground(_manifest(_filled("000000", "824BB0")), _theme()) == []


def test_a_record_with_no_fill_is_not_judged():
    assert check_fill_ground(_manifest(_shape([1.0, 1.0, 2.0, 1.0])), _theme()) == []


def test_an_inverse_panel_records_its_fill_and_the_ground_it_was_laid_on(ctx_factory):
    ctx = ctx_factory({"panel": {"pair": "inverse"}})
    ctx.painted.append((Rect(0.0, 0.0, 13.333, 7.5), "2D0937"))
    get_component("panel")(ctx)
    [panel] = ctx.manifest.slides[0].shapes
    assert (panel.fill, panel.ground) == ("2D0937", "2D0937")


def test_a_surface_panel_is_a_recess_and_records_no_fill_to_judge(ctx_factory):
    get_component("panel")(ctx := ctx_factory({"panel": {"pair": "surface"}}))
    [panel] = ctx.manifest.slides[0].shapes
    assert panel.fill is None


def test_a_saturated_accent_on_a_pale_page_stands_off_by_colour_though_not_by_luminance():
    """Yellow on white is 1.47:1, and plainly visible: luminance alone cannot say it vanishes."""
    assert check_fill_ground(_manifest(_filled("FFD000", "FFFFFF")), _theme()) == []
