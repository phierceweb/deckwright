"""`text-fit`: the recorded words against the box the shape declared. `bounds` asks whether the
box is on the slide; nothing asked whether the text fits inside it."""

from deckwright.qa.geometry import check_text_fit
from deckwright.qa.model import Severity
from tests.qa.test_geometry_bounds import _manifest, _shape, _theme

_LONG = (
    "a run of words considerably longer than a third of an inch of height can hold "
    "at body size, which is precisely the defect bounds reports clean on"
)


def _fitted(lines, *, height, font_pt=14.0, width=6.0, line_pt=None):
    shape = _shape([1.0, 1.0, width, height])
    shape.update(lines=lines, font_pt=font_pt)
    if line_pt is not None:
        shape["line_pt"] = line_pt
    return shape


def test_one_line_inside_its_box_is_clean():
    assert check_text_fit(_manifest(_fitted(["short"], height=0.4)), _theme()) == []


def test_text_past_its_own_box_is_a_warning():
    findings = check_text_fit(_manifest(_fitted([_LONG], height=0.3)), _theme())
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARN
    assert findings[0].check == "text-fit"
    assert "0.30in" in findings[0].detail


def test_a_mixed_shape_is_measured_at_each_line_own_size():
    """A heading over its body, 18pt then 13.5pt, genuinely fitting. Measuring both at 18pt — all
    a single `font_pt` allows — invents a defect, which is what `line_pt` exists to remove."""
    shape = _fitted(["Heading", _LONG], height=0.9, font_pt=18.0, line_pt=[18.0, 13.5])
    assert check_text_fit(_manifest(shape), _theme()) == []


def test_a_mixed_shape_that_genuinely_overflows_is_flagged():
    """The case the check could not see at all before: a real multi-paragraph overflow."""
    shape = _fitted(["Heading", _LONG], height=0.4, font_pt=18.0, line_pt=[18.0, 13.5])
    findings = check_text_fit(_manifest(shape), _theme())
    assert len(findings) == 1 and findings[0].check == "text-fit"


def test_a_multi_line_record_without_sizes_is_skipped_not_guessed_at():
    """No `line_pt`, so the shape is unmeasurable: skipped rather than measured at the dominant
    size, which would over-report."""
    shape = _fitted(["Heading", _LONG], height=0.8, font_pt=18.0)
    assert check_text_fit(_manifest(shape), _theme()) == []


def test_a_rasterized_panel_is_skipped():
    """Its text is set by a browser, not by us, so our metrics say nothing about it."""
    shape = _fitted([_LONG], height=0.3)
    shape["rendered"] = "image"
    assert check_text_fit(_manifest(shape), _theme()) == []


def test_a_hair_over_is_arithmetic_not_a_defect():
    """Boxes are rounded and the wrap estimate carries its own margin."""
    one_line = 14.0 * 1.2 / 72
    assert check_text_fit(_manifest(_fitted(["short"], height=one_line - 0.03)), _theme()) == []
