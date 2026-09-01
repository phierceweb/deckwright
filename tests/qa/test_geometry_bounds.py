import pathlib

from deckwright.qa.geometry import check_bounds, check_reserved
from deckwright.qa.model import Severity
from deckwright.theme.chartstyle import ChartStyle
from deckwright.theme import Grid, Scale
from deckwright.theme.defaults import DEFAULT_PAIRS, DEFAULT_ROLES
from deckwright.layouts.place import Reserved
from deckwright.theme.model import Theme, TypeStyle
from deckwright.theme.palette import build_palette

SCALE = Scale(13.333, 7.5)
PALETTE = build_palette(DEFAULT_ROLES, pairs=DEFAULT_PAIRS)
GRID = Grid(
    scale=SCALE,
    top_frac=0.30 / 7.5,
    right_frac=0.61 / 13.333,
    bottom_frac=0.5 / 7.5,
    left_frac=0.62 / 13.333,
    columns=12,
    rows=12,
    gutter_frac=0.18 / 13.333,
    body_top_frac=1.7 / 7.5,
)
WEDGE = Reserved(name="logo-wedge", poly=((1.0, 0.7227), (1.0, 1.0), (0.825, 1.0)))
CHART = ChartStyle()


def _theme(zones=(WEDGE,)):
    return Theme(
        name="t",
        template=pathlib.Path("x.pptx"),
        drop_template_slides=False,
        palette=PALETTE,
        scale=SCALE,
        face="Calibri",
        mono="Consolas",
        ramp={"body": TypeStyle(13.5 / 7.5, SCALE)},
        min_pt=10.5,
        grid=GRID,
        line_weight=2.25,
        chart=CHART,
        reserve=zones,
    )


def _manifest(*shapes, index=1):
    return {
        "deck": "d.pptx",
        "slide_w": 13.333,
        "slide_h": 7.5,
        "slides": [{"index": index, "background": "page", "shapes": list(shapes)}],
    }


def _shape(box, *, shape_id=2, name="Box", text="t", rendered="native"):
    return {
        "shape_id": shape_id,
        "name": name,
        "box": dict(zip("xywh", box, strict=True)),
        "text": text,
        "lines": [],
        "font_pt": None,
        "fg": None,
        "bg": None,
        "rendered": rendered,
    }


def test_a_shape_inside_the_slide_is_clean():
    assert check_bounds(_manifest(_shape([1.0, 1.0, 3.0, 1.0])), _theme()) == []


def test_a_shape_off_the_right_edge_is_an_error():
    findings = check_bounds(_manifest(_shape([12.0, 1.0, 3.0, 1.0])), _theme())
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert findings[0].check == "bounds"
    assert findings[0].slide == 1


def test_a_shape_off_the_bottom_is_an_error():
    assert len(check_bounds(_manifest(_shape([1.0, 7.0, 2.0, 1.0])), _theme())) == 1


def test_a_negative_origin_is_an_error():
    assert len(check_bounds(_manifest(_shape([-0.5, 1.0, 2.0, 1.0])), _theme())) == 1


def test_a_full_bleed_background_is_exempt():
    """The exemption has to be what makes this pass, and a box of exactly the canvas is inside
    bounds anyway. This one overshoots every edge past the 0.01in edge tolerance while staying
    inside the 0.02in full-bleed one."""
    overshooting = _shape([-0.015, -0.015, 13.36, 7.53])
    assert check_bounds(_manifest(overshooting), _theme()) == []


def test_duplicate_records_with_different_typography_still_report_once():
    # Mirrors the Critical fix: geometry stays deduped by shape+box even though the
    # two records disagree on font_pt — one box, one bounds finding.
    first = _shape([12.0, 1.0, 3.0, 1.0], shape_id=9)
    first["font_pt"] = 13.5
    second = dict(first, font_pt=5.0)
    assert len(check_bounds(_manifest(first, second), _theme())) == 1


def test_the_finding_carries_the_offending_box():
    findings = check_bounds(_manifest(_shape([12.0, 1.0, 3.0, 1.0])), _theme())
    assert findings[0].box == (12.0, 1.0, 3.0, 1.0)


# --- reserved regions -------------------------------------------------------------


def test_a_shape_clear_of_the_wedge_is_clean():
    assert check_reserved(_manifest(_shape([0.62, 1.7, 6.0, 3.0])), _theme()) == []


def test_a_shape_intruding_on_the_wedge_is_an_error():
    findings = check_reserved(_manifest(_shape([12.5, 6.9, 0.8, 0.4])), _theme())
    assert len(findings) == 1
    assert findings[0].check == "reserved"
    assert "logo-wedge" in findings[0].detail


def test_a_full_bleed_background_is_exempt_from_zones():
    assert check_reserved(_manifest(_shape([0.0, 0.0, 13.333, 7.5])), _theme()) == []


def test_duplicate_records_intruding_report_once():
    dup = _shape([12.5, 6.9, 0.8, 0.4])
    assert len(check_reserved(_manifest(dup, dict(dup)), _theme())) == 1


def test_every_zone_is_checked_on_every_slide():
    intruder = _shape([12.5, 6.9, 0.8, 0.4])
    manifest = _manifest(intruder)
    manifest["slides"].append(dict(manifest["slides"][0], index=2))
    findings = check_reserved(manifest, _theme())
    assert [f.slide for f in findings] == [1, 2]


# --- full-bleed origin validation -----------------------------------------------


def test_a_full_slide_sized_box_mispositioned_is_an_error():
    findings = check_bounds(_manifest(_shape([5.0, 5.0, 13.333, 7.5])), _theme())
    assert len(findings) == 1
    assert findings[0].check == "bounds"


def test_a_full_slide_sized_box_mispositioned_is_an_error_for_zones():
    findings = check_reserved(_manifest(_shape([5.0, 5.0, 13.333, 7.5])), _theme())
    assert len(findings) == 1
    assert findings[0].check == "reserved"


def test_a_shape_in_two_reserved_regions_is_reported_once():
    """One finding per shape: a second region is more noise, not more information."""
    footer = Reserved(name="footer", poly=((0.0, 0.88), (1.0, 0.88), (1.0, 1.0), (0.0, 1.0)))
    # Sits inside the wedge and inside the footer band at once.
    manifest = _manifest(_shape([11.6, 6.9, 1.2, 0.4]))
    findings = check_reserved(manifest, _theme(zones=(WEDGE, footer)))
    assert len(findings) == 1
    assert "logo-wedge" in findings[0].detail  # the first region declared


# --- a bleed is an instruction, not an accident -------------------------------


def _bleeding(box, **kw):
    return {**_shape(box, **kw), "bleed": True}


def test_a_shape_the_author_declared_as_bleeding_is_not_a_bounds_error():
    """`bleed: true` says off-canvas is the point. Reporting it trains people to
    ignore the check — a bleed-heavy deck could never produce a clean run."""
    assert check_bounds(_manifest(_bleeding([11.0, 1.0, 4.0, 2.0])), _theme()) == []


def test_a_shape_that_leaves_the_canvas_without_saying_so_is_still_an_error():
    """The exemption must be the declaration, not the geometry, or it exempts everything."""
    findings = check_bounds(_manifest(_shape([11.0, 1.0, 4.0, 2.0])), _theme())
    assert len(findings) == 1 and findings[0].severity is Severity.ERROR
