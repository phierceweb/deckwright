"""`rhythm`: the run test, counted from the manifest. INFO only."""

from __future__ import annotations

from deckwright.qa.model import Severity
from deckwright.qa.rhythm import check_rhythm
from tests.qa.test_geometry_bounds import _theme


def _box(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


def _slide(index, *placed, title=(0.8, 0.4, 11.7, 0.6), background="page", clicks=0):
    shapes, placements = [], []
    for n, (component, box) in enumerate(placed, start=1):
        origin = f"s{index}.p{n}.{component}"
        placements.append({"origin": origin, "component": component, "box": _box(*box)})
        shapes.append({"name": f"{origin}#1", "box": _box(*box)})
    if title is not None:
        shapes.append({"name": f"s{index}.chrome.title", "box": _box(*title)})
    animations = [{"kind": "click_sequence", "clicks": clicks}] if clicks else []
    return {
        "index": index,
        "background": background,
        "shapes": shapes,
        "placements": placements,
        "animations": animations,
    }


def _deck(*slides):
    return {"canvas": {"w": 13.333, "h": 7.5}, "slides": list(slides)}


_CARD = ("card", (0.8, 1.6, 11.7, 3.0))
_CHART = ("chart", (0.8, 1.6, 11.7, 4.0))
_BAND = ("callouts", (0.8, 5.6, 11.7, 1.0))


def _checks(findings):
    return [(f.check, f.slide, f.severity) for f in findings]


def test_four_slides_of_one_look_are_one_run_and_three_are_not():
    four = check_rhythm(_deck(*(_slide(i, _CARD) for i in range(1, 5))), _theme())
    assert [f.detail for f in four if "in a row on" in f.detail] == [
        "slides 1–4: 4 in a row on page, plates, the title at the top — the run test reads "
        "them as one treatment"
    ]
    three = check_rhythm(_deck(*(_slide(i, _CARD) for i in range(1, 4))), _theme())
    assert not [f for f in three if "in a row on" in f.detail]


def test_a_change_of_ground_mass_or_title_breaks_the_run():
    slides = [
        _slide(1, _CARD),
        _slide(2, _CARD, background="inverse"),
        _slide(3, _CHART),
        _slide(4, _CARD, title=(0.8, 1.6, 3.7, 1.0)),
    ]
    assert not [f for f in check_rhythm(_deck(*slides), _theme()) if "in a row on" in f.detail]


def test_slides_closing_on_a_band_under_the_body_are_counted():
    slides = [_slide(i, _CARD, _BAND) for i in range(1, 4)] + [_slide(4, _CHART)]
    (band,) = [f for f in check_rhythm(_deck(*slides), _theme()) if "band under" in f.detail]
    assert band.detail.startswith("3 slides end on a band under the body (1, 2, 3)")


def test_a_title_that_never_moves_is_reported_and_one_that_does_breaks_it():
    still = [_slide(i, _CARD if i % 2 else _CHART) for i in range(1, 9)]
    assert [f for f in check_rhythm(_deck(*still), _theme()) if "never varies" in f.detail]
    moved = still[:-1] + [_slide(8, _CHART, title=(0.8, 1.6, 3.7, 1.0))]
    assert not [f for f in check_rhythm(_deck(*moved), _theme()) if "never varies" in f.detail]


def test_four_slides_that_each_build_one_group_per_click_are_reported():
    slides = [_slide(i, _CARD if i % 2 else _CHART, clicks=3) for i in range(1, 5)]
    (built,) = [f for f in check_rhythm(_deck(*slides), _theme()) if "per click" in f.detail]
    assert built.detail.startswith("slides 1–4: 4 in a row reveal one group per click")


def test_every_rhythm_finding_is_info():
    slides = [_slide(i, _CARD, _BAND, clicks=3) for i in range(1, 9)]
    found = check_rhythm(_deck(*slides), _theme())
    assert found and {f.severity for f in found} == {Severity.INFO}
