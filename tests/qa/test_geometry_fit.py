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


def test_a_recorded_line_is_measured_as_written_even_when_it_reads_as_a_link():
    """A code listing records its markup literally; measured as a link it would fit."""
    line = "See [docs](https://example.com/reference/manual/chapter-one/section-two/the-long-page)"
    findings = check_text_fit(_manifest(_fitted([line], height=0.3, width=2.0)), _theme())
    assert [f.check for f in findings] == ["text-fit"]


def _spaced(*, height):
    """Three 14pt lines, 0.70in, with 8pt after each paragraph."""
    shape = _fitted(["one", "two", "three"], height=height, line_pt=[14.0] * 3)
    shape["space_after_pt"] = [8.0] * 3
    return shape


def test_the_space_between_paragraphs_counts_toward_the_height_they_need():
    """0.70in of lines fits 0.80in; the two gaps between them take it to 0.92in."""
    findings = check_text_fit(_manifest(_spaced(height=0.8)), _theme())
    assert [f.check for f in findings] == ["text-fit"]
    assert "needs 0.92in" in findings[0].detail


def test_the_space_after_the_last_paragraph_is_not_counted():
    """It sets no ink: 0.92in fits a 0.90in box inside the slack, where 1.03in would not."""
    assert check_text_fit(_manifest(_spaced(height=0.9)), _theme()) == []


# Two lines a bullet across the base theme's full 11.73in column at 16pt.
_BULLET = (
    "A point long enough that it cannot sit on one line of a column this wide, so the "
    "list has to be measured as it wraps rather than as one line per bullet"
)
_SPEC = (
    "theme: base\ntitle: Fit\nout: fit.pptx\n---\ntitle: A list\nplace:\n"
    "  - at: {cols: full, rows: {from: 0, to: 5}}\n    bullets:\n      items:\n"
    + "".join(f"        - {_BULLET}\n" for _ in range(4))
)


def test_a_wrapping_list_that_overflows_its_column_is_reported_from_a_built_deck(
    tmp_path, monkeypatch
):
    """The deck a single-line bullet count let through: eight lines, 2.13in, fit the
    2.25in column; the three gaps between the bullets take it to 2.47in."""
    import json

    import deckwright.components.bullets as bullets
    from deckwright.compile import build_deck
    from deckwright.theme import load_theme

    monkeypatch.setattr(bullets, "item_lines", lambda item, **_: 1)
    spec = tmp_path / "fit.deck.yaml"
    spec.write_text(_SPEC, encoding="utf-8")
    manifest = json.loads(build_deck(spec).deck.with_suffix(".manifest.json").read_text())
    findings = check_text_fit(manifest, load_theme("base"))
    assert [(f.check, f.shape) for f in findings] == [("text-fit", "s1.p1.bullets#1")]
    assert "needs 2.47in but the shape declares 2.25in" in findings[0].detail


def test_the_build_refuses_the_same_list_before_it_is_drawn(tmp_path):
    import pytest

    from deckwright.compile import build_deck
    from deckwright.errors import LayoutError

    spec = tmp_path / "fit.deck.yaml"
    spec.write_text(_SPEC, encoding="utf-8")
    with pytest.raises(
        LayoutError, match=r"4 bullets wrap to 8 lines in the tallest column and need 2\.58in"
    ):
        build_deck(spec)
