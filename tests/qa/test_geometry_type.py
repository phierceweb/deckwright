from deckwright.qa.geometry import check_contrast, check_type_sizes
from deckwright.qa.model import Severity
from tests.qa.test_geometry_bounds import _manifest, _shape, _theme


# --- type sizes -------------------------------------------------------------


def test_type_at_the_minimum_is_clean():
    shape = _shape([1.0, 1.0, 2.0, 1.0])
    shape["font_pt"] = 10.5
    assert check_type_sizes(_manifest(shape), _theme()) == []


def test_type_below_the_minimum_is_a_warning():
    shape = _shape([1.0, 1.0, 2.0, 1.0])
    shape["font_pt"] = 9.0
    findings = check_type_sizes(_manifest(shape), _theme())
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARN
    assert findings[0].check == "min-font"
    assert "9" in findings[0].detail and "10.5" in findings[0].detail


def test_a_record_without_a_font_size_is_skipped():
    assert check_type_sizes(_manifest(_shape([1.0, 1.0, 2.0, 1.0])), _theme()) == []


# --- contrast ---------------------------------------------------------------


def _coloured(fg, bg, font_pt=13.5):
    shape = _shape([1.0, 1.0, 2.0, 1.0])
    shape.update(fg=fg, bg=bg, font_pt=font_pt)
    return shape


def test_aubergine_on_white_is_clean():
    assert check_contrast(_manifest(_coloured("2D0937", "FFFFFF")), _theme()) == []


def test_a_pair_no_backdrop_could_save_is_an_error():
    """CCCCCC on FFFFFF is 1.61:1 — below the 3:1 floor, so nothing really painted behind
    the text redeems it. The build no longer refuses this, which makes the severity here
    the thing that stops it reaching anyone."""
    findings = check_contrast(_manifest(_coloured("CCCCCC", "FFFFFF")), _theme())
    assert len(findings) == 1
    assert findings[0].check == "contrast"
    assert findings[0].severity is Severity.ERROR


def test_a_marginal_shortfall_only_warns():
    """8A8A8A on FFFFFF is 3.45:1 — short of AA, but the manifest records the pair a
    component asked for and the real backdrop may be darker."""
    findings = check_contrast(_manifest(_coloured("8A8A8A", "FFFFFF")), _theme())
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARN


def test_large_type_uses_the_looser_threshold():
    # ratio ~3.1: fails the 4.5 normal bar, passes the 3.0 large-text bar
    assert check_contrast(_manifest(_coloured("949494", "FFFFFF", font_pt=24)), _theme()) == []
    assert len(check_contrast(_manifest(_coloured("949494", "FFFFFF", font_pt=12)), _theme())) == 1


def test_a_record_missing_either_colour_is_skipped():
    assert check_contrast(_manifest(_coloured(None, "FFFFFF")), _theme()) == []
    assert check_contrast(_manifest(_coloured("000000", None)), _theme()) == []


def test_an_image_rendered_record_is_skipped():
    shape = _coloured("CCCCCC", "FFFFFF")
    shape["rendered"] = "image"
    assert check_contrast(_manifest(shape), _theme()) == []


# --- typography checks must see every paragraph record, not just the first --------
# A textbox records one row per paragraph; shape+box dedupe must not hide the second.


def test_a_defect_on_the_second_record_of_a_shape_is_still_caught_by_min_font():
    clean = _shape([1.0, 1.0, 2.0, 1.0], shape_id=9)
    clean["font_pt"] = 13.5
    defective = dict(clean, font_pt=5.0)
    findings = check_type_sizes(_manifest(clean, defective), _theme())
    assert len(findings) == 1
    assert findings[0].detail.startswith("5")


def test_a_defect_on_the_second_record_of_a_shape_is_still_caught_by_contrast():
    clean = _coloured("2D0937", "FFFFFF")
    clean["shape_id"] = 9
    defective = dict(clean, fg="F2F2F2")
    findings = check_contrast(_manifest(clean, defective), _theme())
    assert len(findings) == 1
    assert findings[0].detail.startswith("F2F2F2")
