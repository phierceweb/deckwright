"""`morph-unpaired`: a name a morph slide cannot pair with anything."""

from __future__ import annotations

import json

import pytest

from deckwright.qa.model import Severity
from deckwright.qa.morph import check_morph


@pytest.fixture
def morphing(tmp_path, theme_file):
    """Slide 2 morphs `hero` from slide 1. Slide 3 morphs `solo`, which slide 2 does not have.
    Slide 4 asks to morph and names nothing."""
    from deckwright.compile import build_deck

    def card(name):
        return f"place:\n  - at: {{cols: full}}\n    morph: {name}\n    card: {{heading: H}}\n"

    spec = tmp_path / "m.deck.yaml"
    spec.write_text(
        "theme: testtheme\ntitle: T\nout: out/M.pptx\n"
        f"---\ntitle: One\n{card('hero')}"
        f"---\ntitle: Two\ntransition: morph\n{card('hero')}"
        f"---\ntitle: Three\ntransition: morph\n{card('solo')}"
        "---\ntitle: Four\ntransition: morph\n"
    )
    built = build_deck(spec, theme_path=theme_file)
    return json.loads(built.manifest.read_text())


def test_a_name_with_no_namesake_on_the_slide_before_is_reported(morphing, theme):
    found = check_morph(morphing, theme)
    assert [(f.slide, f.check, f.severity) for f in found] == [
        (3, "morph-unpaired", Severity.WARN),
        (4, "morph-unpaired", Severity.WARN),
    ]
    assert found[0].detail == (
        "'morph: solo' has no namesake on slide 2, where 'hero' no longer appears — if it is "
        "the same shape renamed, Morph fades one out and the other in rather than gliding"
    )
    assert found[1].detail == (
        "the slide asks to morph and names nothing: no placement on it carries 'morph:', so "
        "Morph is given no name to pair"
    )


def test_a_deck_that_never_morphs_reports_nothing(theme):
    data = {"slides": [{"index": 1, "transition": "push", "shapes": [{"name": "m.x.card#1"}]}]}
    assert check_morph(data, theme) == []


def _slide(index, *names, transition="morph"):
    shapes = [{"name": f"m.{name}.card#1"} for name in names]
    return {"index": index, "transition": transition, "shapes": shapes}


def test_a_shape_entering_a_morph_chain_is_not_reported(theme):
    """A shape that first appears on a morph slide must carry its name there to pair with
    the next one; every build-up of a morph sequence did, and each drew a warning."""
    data = {"slides": [_slide(1, "a", transition=None), _slide(2, "a", "b"), _slide(3, "a", "b")]}
    assert check_morph(data, theme) == []


def test_a_shape_entering_on_the_last_slide_of_a_sequence_is_not_reported(theme):
    data = {"slides": [_slide(1, "a", transition=None), _slide(2, "a", "c"), _slide(3, "a")]}
    assert check_morph(data, theme) == []


def test_a_name_that_appears_as_another_disappears_is_reported_as_a_rename(theme):
    data = {"slides": [_slide(1, "hero", "a", transition=None), _slide(2, "Hero", "a")]}
    assert [(f.slide, f.detail) for f in check_morph(data, theme)] == [
        (
            2,
            "'morph: Hero' has no namesake on slide 1, where 'hero' no longer appears — if it "
            "is the same shape renamed, Morph fades one out and the other in rather than gliding",
        )
    ]


def test_a_shape_entering_as_one_of_another_component_leaves_is_not_a_rename(theme):
    leaves = {
        "index": 1,
        "transition": None,
        "shapes": [{"name": "m.a.card#1"}, {"name": "m.link.connector#1"}],
    }
    enters = {
        "index": 2,
        "transition": "morph",
        "shapes": [{"name": "m.a.card#1"}, {"name": "m.strip.table#1"}],
    }
    assert check_morph({"slides": [leaves, enters]}, theme) == []


def test_a_rename_is_reported_though_the_new_name_runs_on_to_the_next_slide(theme):
    """Under `carry: previous` every name runs on, so a rename is never on a sequence's last slide."""
    data = {
        "slides": [
            _slide(1, "hero", "a", transition=None),
            _slide(2, "Hero", "a"),
            _slide(3, "Hero", "a"),
        ]
    }
    assert [f.slide for f in check_morph(data, theme)] == [2]


def test_a_name_carrying_a_hash_is_read_whole(theme):
    """`#` also ends a shape name's counter, so the name is everything before the last one."""
    leaves = {"index": 1, "transition": None, "shapes": [{"name": "m.step#1.card#1"}]}
    enters = {"index": 2, "transition": "morph", "shapes": [{"name": "m.step#2.card#1"}]}
    assert [f.detail.split(" — ")[0] for f in check_morph({"slides": [leaves, enters]}, theme)] == [
        "'morph: step#2' has no namesake on slide 1, where 'step#1' no longer appears"
    ]


def test_a_shape_named_by_its_part_counts_under_its_placements_name(theme):
    leaves = {"index": 1, "transition": None, "shapes": [{"name": "m.grid.table.r1c1"}]}
    enters = {"index": 2, "transition": "morph", "shapes": [{"name": "m.Grid.table.r1c1"}]}
    assert [f.detail.split(" — ")[0] for f in check_morph({"slides": [leaves, enters]}, theme)] == [
        "'morph: Grid' has no namesake on slide 1, where 'grid' no longer appears"
    ]


def test_a_component_the_deck_registers_itself_is_read_by_its_name(theme):
    """`qa` never loads a deck's `extends:` module, so the registry does not know `banner`."""
    leaves = {"index": 1, "transition": None, "shapes": [{"name": "m.hero.banner#1"}]}
    stays = {"index": 2, "transition": "morph", "shapes": [{"name": "m.hero.banner#1"}]}
    renamed = {"index": 3, "transition": "morph", "shapes": [{"name": "m.hero2.banner#1"}]}
    found = check_morph({"slides": [leaves, stays, renamed]}, theme)
    assert [(f.slide, f.detail.split(" — ")[0]) for f in found] == [
        (3, "'morph: hero2' has no namesake on slide 2, where 'hero' no longer appears")
    ]
