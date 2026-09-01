"""`placement-fit`: a shape that escapes the rect its placement was given. The check itself is
driven against every real template by `tests/test_templates.py`; only the refusals live here."""

import pathlib

import pytest

from deckwright.compile.record import owns
from deckwright.qa.geometry import check_placement_fit
from deckwright.qa.model import Severity
from deckwright.theme.chartstyle import ChartStyle
from deckwright.theme import Grid, Scale
from deckwright.theme.defaults import DEFAULT_PAIRS, DEFAULT_ROLES
from deckwright.theme.model import Theme, TypeStyle
from deckwright.theme.palette import build_palette

SCALE = Scale(13.333, 7.5)
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
CHART = ChartStyle()
THEME = Theme(
    name="t",
    template=pathlib.Path("x.pptx"),
    drop_template_slides=False,
    palette=build_palette(DEFAULT_ROLES, pairs=DEFAULT_PAIRS),
    scale=SCALE,
    face="Calibri",
    mono="Consolas",
    ramp={"body": TypeStyle(13.5 / 7.5, SCALE)},
    min_pt=10.5,
    grid=GRID,
    line_weight=2.25,
    chart=CHART,
    reserve=(),
)

RECT = (1.0, 1.0, 4.0, 3.0)
INSIDE = (1.5, 1.5, 1.0, 1.0)
ESCAPES = (1.5, 1.5, 4.0, 1.0)  # right edge 5.5 against the rect's 5.0


def _box(values):
    return dict(zip("xywh", values, strict=True))


def _manifest(shapes, placements):
    return {
        "deck": "d.pptx",
        "slides": [{"index": 1, "background": "page", "placements": placements, "shapes": shapes}],
    }


def _placement(origin="s1.p1.card", component="card", box=RECT):
    return {"origin": origin, "component": component, "box": _box(box)}


def _shape(box, *, name="s1.p1.card#1", shape_id=2, **extra):
    return {"shape_id": shape_id, "name": name, "box": _box(box), **extra}


def test_a_shape_past_its_placement_is_an_error():
    found = check_placement_fit(_manifest([_shape(ESCAPES)], [_placement()]), THEME)
    assert len(found) == 1
    assert found[0].check == "placement-fit"
    assert found[0].severity is Severity.ERROR
    assert found[0].shape == "s1.p1.card#1"
    assert "0.50in past" in found[0].detail


def test_a_shape_inside_its_placement_is_not():
    assert check_placement_fit(_manifest([_shape(INSIDE)], [_placement()]), THEME) == []


@pytest.mark.parametrize(
    "axis,box",
    [
        ("left", (0.5, 1.5, 1.0, 1.0)),
        ("top", (1.5, 0.5, 1.0, 1.0)),
        ("bottom", (1.5, 1.5, 1.0, 3.0)),
    ],
)
def test_every_edge_is_measured_not_only_the_right(axis, box):
    found = check_placement_fit(_manifest([_shape(box)], [_placement()]), THEME)
    assert len(found) == 1, f"{axis} overrun went unreported"


# --- the four exemptions, each a branch a successful build never reaches -------------


def test_a_declared_bleed_is_exempt():
    assert (
        check_placement_fit(_manifest([_shape(ESCAPES, bleed=True)], [_placement()]), THEME) == []
    )


def test_a_plate_is_exempt():
    """The compiler paints a contrast surface wider than the text it carries."""
    assert (
        check_placement_fit(_manifest([_shape(ESCAPES, plate=True)], [_placement()]), THEME) == []
    )


def test_a_connector_is_exempt():
    """A connector draws *between* two other placements, never inside its own rect."""
    assert (
        check_placement_fit(
            _manifest(
                [_shape(ESCAPES, name="s1.p1.connector#1")],
                [_placement(origin="s1.p1.connector", component="connector")],
            ),
            THEME,
        )
        == []
    )


def test_a_shape_no_placement_owns_is_exempt():
    """Chrome and the background are recorded under an origin that never had a rect."""
    assert (
        check_placement_fit(
            _manifest([_shape(ESCAPES, name="s1.chrome.title")], [_placement()]), THEME
        )
        == []
    )


def test_a_degenerate_box_is_skipped():
    """`rule` records a zero-extent box sitting on an edge of its own rect."""
    assert (
        check_placement_fit(
            _manifest(
                [_shape((1.0, 1.0, 4.0, 0.0), name="s1.p1.rule#1")],
                [_placement(origin="s1.p1.rule", component="rule")],
            ),
            THEME,
        )
        == []
    )


def test_an_origin_recorded_twice_reports_nothing_for_either():
    """A name collision is `shape-name`'s finding; guessing a rect would invent a second."""
    assert (
        check_placement_fit(
            _manifest(
                [_shape(ESCAPES)], [_placement(box=RECT), _placement(box=(0.0, 0.0, 13.0, 7.0))]
            ),
            THEME,
        )
        == []
    )


# --- attribution ---------------------------------------------------------------------


def test_a_shorter_origin_does_not_claim_a_longer_ones_shape():
    """`s1.p1.card` must not own `s1.p10.card#1`, or the wrong rect is measured against: `p1` is
    given a rect the shape fits and `p10` one it does not."""
    found = check_placement_fit(
        _manifest(
            [_shape(ESCAPES, name="s1.p10.card#1")],
            [
                _placement(origin="s1.p1.card", box=(0.0, 0.0, 13.0, 7.0)),
                _placement(origin="s1.p10.card", box=RECT),
            ],
        ),
        THEME,
    )
    assert len(found) == 1
    assert found[0].shape == "s1.p10.card#1"


@pytest.mark.parametrize(
    "origin,name,expected",
    [
        ("s1.p1.card", "s1.p1.card", True),
        ("s1.p1.card", "s1.p1.card#1", True),
        ("s1.p1.card", "s1.p1.card.title", True),
        ("s1.p1.card", "s1.p10.card#1", False),
        ("s1.p1.card", "s1.p1.cards#1", False),
    ],
)
def test_owns_requires_the_separator(origin, name, expected):
    assert owns(origin, name) is expected
