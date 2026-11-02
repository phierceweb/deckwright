"""`chrome-overlap` and `chrome-plate`: chrome is drawn over every placement, so landing on
one hides it, and nothing at build time compares the two."""

from __future__ import annotations

import json

import pytest

from deckwright.compile import build_deck
from deckwright.qa.chrome import check_chrome_overlap
from tests.qa.test_geometry_bounds import _shape, _theme


def _slide(*shapes, placements=()):
    return {
        "slides": [
            {
                "index": 1,
                "shapes": list(shapes),
                "placements": [
                    {"origin": o, "component": c, "box": dict(zip("xywh", b, strict=True))}
                    for o, c, b in placements
                ],
            }
        ]
    }


_TITLE = _shape(
    [0.8, 0.4, 11.7, 1.0],
    name="s1.chrome.title",
    text="A title long enough to wrap onto a second line across the whole of this measure",
)
_TITLE["font_pt"] = 34.0
_CARD = ("s1.p1.card", "card", [0.8, 1.2, 4.0, 2.0])


def test_a_title_drawn_over_a_card_is_reported():
    found = check_chrome_overlap(_slide(_TITLE, placements=[_CARD]), _theme())
    assert [(f.check, f.detail) for f in found] == [
        (
            "chrome-overlap",
            "chrome 'title' can be drawn over s1.p1.card (card); give the placement rows "
            "below the line, or move the line with chrome: at:",
        )
    ]


def test_a_shape_in_a_tall_boxs_empty_lower_part_is_clean():
    """A one-line title in a box a fifth of the slide deep sits at the box's top; the rule
    under it was reported though no word can reach it."""
    title = _shape([0.55, 2.59, 8.5, 1.13], name="s1.chrome.title", text="Chaining")
    title["font_pt"] = 40.0
    rule = ("s1.p1.rule", "rule", [0.55, 3.43, 2.0, 0.11])
    assert check_chrome_overlap(_slide(title, placements=[rule]), _theme()) == []


def test_a_title_on_a_panel_or_a_bleeding_placement_is_meant_to_be_there():
    bled = _shape([0.0, 0.0, 6.0, 7.5], name="s1.p2.ellipse#1")
    bled["bleed"] = True
    placements = [
        ("s1.p1.panel", "panel", [0.0, 0.0, 6.0, 7.5]),
        ("s1.p2.ellipse", "ellipse", [0.0, 0.0, 6.0, 7.5]),
    ]
    assert check_chrome_overlap(_slide(_TITLE, bled, placements=placements), _theme()) == []


def test_a_title_clear_of_the_body_is_clean():
    card = ("s1.p1.card", "card", [0.8, 1.5, 4.0, 2.0])
    assert check_chrome_overlap(_slide(_TITLE, placements=[card]), _theme()) == []


def test_a_chrome_plate_over_any_placement_is_reported():
    plate = _shape([0.6, 1.0, 7.3, 1.2], name="s1.chrome.subtitle.plate")
    plate["plate"] = True
    panel = ("s1.p1.panel", "panel", [0.0, 0.9, 5.0, 0.4])
    found = check_chrome_overlap(_slide(plate, placements=[panel]), _theme())
    assert [f.check for f in found] == ["chrome-plate"]
    assert "chrome 'subtitle'" in found[0].detail and "s1.p1.panel (panel)" in found[0].detail


def test_a_title_printed_through_a_row_of_cards_is_reported_from_a_real_build(tmp_path):
    spec = tmp_path / "o.deck.yaml"
    spec.write_text(
        "theme: base\ntitle: T\nout: out/O.pptx\n---\n"
        "title: Same facts as sloppy, and now Jordan knows what to change\n"
        "chrome:\n  title: {at: {cols: {from: 0, to: 10}, rows: {from: 10, to: 12}}}\n"
        "place:\n- at: {rows: {from: 0, to: 12}}\n  split:\n"
        "  - card: {heading: Situation}\n  - card: {heading: Behaviour}\n"
        "  - card: {heading: Impact}\n"
    )
    data = json.loads(build_deck(spec).manifest.read_text())
    found = check_chrome_overlap(data, _theme())
    assert {f.detail.split(" can be drawn over ")[1].split(";")[0] for f in found} == {
        "s1.p1.card (card)",
        "s1.p2.card (card)",
        "s1.p3.card (card)",
    }


@pytest.mark.parametrize(("top", "reported"), [("50%", False), ("68%", True)])
def test_a_line_anchored_middle_is_measured_where_its_words_sit(tmp_path, top, reported):
    """A one-line subtitle in the slide's lower half, anchored middle, sits about 5.6in down:
    a card over the box's top edge is clear of it, and one over its middle is not."""
    spec = tmp_path / "m.deck.yaml"
    spec.write_text(
        "theme: base\ntitle: T\nout: out/M.pptx\n---\n"
        "title: T\nsubtitle: The claim\n"
        "chrome:\n  subtitle: {at: {box: {x: 6%, y: 50%, w: 88%, h: 50%}}, anchor: middle}\n"
        f"place:\n- {{at: {{box: {{x: 6%, y: {top}, w: 40%, h: 12%}}}}, card: {{heading: H}}}}\n"
    )
    built = build_deck(spec)
    found = check_chrome_overlap(json.loads(built.manifest.read_text()), _theme(), deck=built.deck)
    assert [f.detail.split(" can be drawn")[0] for f in found] == (
        ["chrome 'subtitle'"] if reported else []
    )
