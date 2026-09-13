"""`inverse` is chosen against the page a slide really shows, not a presumed light one.

Each scheme below reproduces a shape seen in real templates. Expectations are slot names,
never a contrast computed here.
"""

from __future__ import annotations

import pytest
from pptx import Presentation

from deckwright.conform.derive import _inverse, _inverse_ink, notes


def test_a_light_page_takes_the_brand_dark_over_plain_black():
    """Navy in dk2 beats black in dk1 because it carries the brand's hue."""
    scheme = {"dk1": "000000", "dk2": "0E2841", "lt1": "FFFFFF", "lt2": "E7E6E6"}
    assert _inverse(scheme, page="FFFFFF") == "dk2"


def test_a_dark_page_reverses_out_to_light_not_to_its_own_colour():
    """lt2 *is* the page, so a rule presuming a light page picks it."""
    scheme = {"dk1": "FFFFFF", "dk2": "FFFFFF", "lt1": "FFFFFF", "lt2": "1E2A3A"}
    assert scheme[_inverse(scheme, page="1E2A3A")] == "FFFFFF"


def test_a_dark_page_takes_the_brand_light_over_plain_white():
    """The tinted lt2 beats bare white for the same reason navy beats black."""
    scheme = {"dk1": "000000", "dk2": "1A4A7A", "lt1": "FFFFFF", "lt2": "DDEEF8"}
    assert _inverse(scheme, page="0B1F33") == "lt2"


def test_a_midtone_page_takes_whichever_side_actually_reads():
    """A 3A86C0 page. White is farther in luminance but only black clears AA."""
    scheme = {"dk1": "000000", "dk2": "44546A", "lt1": "FFFFFF", "lt2": "E7E6E6"}
    assert _inverse(scheme, page="3A86C0") == "dk1"


def test_a_hued_slot_that_does_not_read_loses_to_a_plain_one_that_does():
    """The hue preference applies only among slots that already clear AA on the page."""
    scheme = {"dk1": "000000", "dk2": "3A86C0", "lt1": "FFFFFF", "lt2": "E7E6E6"}
    assert _inverse(scheme, page="FFFFFF") == "dk1"


def test_a_dark_page_with_two_plain_lights_takes_the_one_that_reads_strongest():
    """No slot that reads carries hue, so the page itself must rank white over cream."""
    scheme = {"dk1": "000000", "dk2": "1F497D", "lt1": "FFFFFF", "lt2": "EEECE1"}
    assert _inverse(scheme, page="2A2D40") == "lt1"


@pytest.fixture
def stock(tmp_path):
    """A stock Office deck: dk1 000000, dk2 1F497D, lt1 FFFFFF, lt2 EEECE1."""
    path = tmp_path / "Brand.pptx"
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])
    prs.save(str(path))
    return path


def test_the_report_names_the_page_the_theme_wrote_not_the_schemes_lightest(stock):
    """A master that paints its own dark ground overrides the scheme's page slot."""
    report = notes(stock, bind={"page": "1E2A3A", "ink": "lt1", "inverse": "dk2"})
    assert any(line.startswith("page 1E2A3A, ink lt1=FFFFFF") for line in report), report
    assert not any("page lt1=FFFFFF" in line for line in report), report


def test_the_report_names_the_inverse_it_wrote(stock):
    report = notes(stock, bind={"page": "lt1", "ink": "dk1", "inverse": "dk2"})
    assert any("inverse dk2=1F497D" in line for line in report), report


def test_a_dark_ink_slot_other_than_dk1_is_called_out(stock):
    report = notes(stock, bind={"page": "lt1", "ink": "dk2", "inverse": "dk1"})
    assert any("ink came from dk2, not dk1" in line for line in report), report


def test_a_light_ink_on_a_dark_page_is_not_called_a_misplaced_dark(stock):
    """White ink on a dark master is the expected choice, not a surprise about dk1."""
    report = notes(stock, bind={"page": "1E2A3A", "ink": "lt1", "inverse": "dk2"})
    assert not any("not dk1" in line for line in report), report


def test_a_theme_that_binds_no_grounds_is_reported_as_built_in_not_crashed_on(stock):
    """A tuned sidecar may bind only accents, leaving page and ink at the defaults."""
    report = notes(stock, bind={"accent-1": "accent1"})
    assert any(
        line.startswith("page FFFFFF (default), ink 1A1D21 (default) (16.9:1), inverse 12161B")
        for line in report
    ), report


def test_a_theme_that_binds_only_its_page_reports_that_page(stock):
    report = notes(stock, bind={"page": "1E2A3A", "inverse": "lt1"})
    assert any(
        line.startswith("page 1E2A3A, ink 1A1D21 (default) (1.2:1), inverse lt1=FFFFFF (14.5:1")
        for line in report
    ), report


def test_a_light_inverse_is_given_an_ink_that_reads_on_it():
    """A white inverse keeps the default white ink unless one is bound."""
    scheme = {"dk1": "FFFFFF", "dk2": "FFFFFF", "lt1": "FFFFFF", "lt2": "1E2A3A"}
    assert _inverse_ink(scheme, inverse="FFFFFF") == "lt2"


def test_a_dark_inverse_keeps_the_default_ink_and_binds_nothing():
    """Every light-page theme already reads white on its dark inverse; binding one churns it."""
    scheme = {"dk1": "000000", "dk2": "1F497D", "lt1": "FFFFFF", "lt2": "EEECE1"}
    assert _inverse_ink(scheme, inverse="1F497D") is None
