"""`carry: previous`: a morph slide names only what changes."""

from __future__ import annotations

from pathlib import Path

import pytest

from deckwright.errors import SpecError
from deckwright.spec.parse import parse_deck_text

_HEAD = "theme: base\ntitle: T\nout: out/C.pptx\n---\n"
_FIRST = (
    "title: One\nplace:\n"
    "  - {at: {cols: left-third}, morph: a, card: {heading: A}}\n"
    "  - {at: {cols: mid-third}, morph: b, card: {heading: B}}\n"
    "  - {at: {cols: right-third}, card: {heading: Not carried}}\n"
    "---\n"
)


def _slides(text):
    return parse_deck_text(_HEAD + text, source=Path("c.deck.yaml")).slides


def test_carry_copies_the_named_placements_and_replaces_one_in_its_place():
    (_, second) = _slides(
        _FIRST + "title: Two\ntransition: morph\ncarry: previous\nplace:\n"
        "  - {at: {cols: full}, morph: a, card: {heading: A, body: grown}}\n"
        "  - {at: {cols: left-half}, morph: c, card: {heading: C}}\n"
    )
    assert [(p.morph, p.body.get("body")) for p in second.place] == [
        ("a", "grown"),
        ("b", None),
        ("c", None),
    ]


def test_drop_leaves_a_carried_placement_behind():
    (_, second) = _slides(_FIRST + "title: Two\ncarry: previous\ndrop: [b]\n")
    assert [p.morph for p in second.place] == ["a"]


def test_a_name_dropped_and_placed_again_keeps_the_placement_the_author_wrote():
    (_, second) = _slides(
        _FIRST + "title: Two\ncarry: previous\ndrop: [a]\nplace:\n"
        "  - {at: {cols: full}, morph: a, card: {heading: A again}}\n"
    )
    assert [(p.morph, p.body.get("heading")) for p in second.place] == [
        ("b", "B"),
        ("a", "A again"),
    ]


def test_carry_chains_through_the_slide_before_as_it_was_carried():
    (_, _, third) = _slides(
        _FIRST + "title: Two\ncarry: previous\ndrop: [b]\n---\ntitle: Three\ncarry: previous\n"
    )
    assert [p.morph for p in third.place] == ["a"]


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("title: One\ncarry: previous\n", "there is no slide before"),
        (
            "title: One\nplace:\n  - {at: {cols: full}, card: {heading: H}}\n---\n"
            "title: Two\ncarry: previous\n",
            "it names none",
        ),
        (
            _FIRST + "title: Two\ncarry: previous\ndrop: [z]\n",
            "'drop' names 'z', which is not carried; carried: a, b",
        ),
        (_FIRST + "title: Two\ndrop: [a]\n", "nothing is carried"),
        (
            _FIRST + "title: Two\ncarry: previous\nplace:\n"
            "  - {at: {cols: left-half}, morph: a, card: {heading: First a}}\n"
            "  - {at: {cols: right-half}, morph: a, card: {heading: Second a}}\n",
            "placement 2: 'morph: a' is already placement 1",
        ),
        (_FIRST + "title: Two\ncarry: next\n", "'carry' takes only previous"),
        (
            "title: One\nplace:\n  - {at: {cols: full}, id: x, morph: a, card: {heading: A}}\n---\n"
            "title: Two\ncarry: previous\nplace:\n  - {at: {cols: full}, id: x, card: {heading: B}}\n",
            "share the id 'x'",
        ),
    ],
)
def test_a_carry_that_cannot_be_made_is_refused_by_name(text, match):
    with pytest.raises(SpecError, match=match):
        _slides(text)


def test_a_carried_placement_is_on_screen_on_arrival_whatever_either_slide_builds():
    """A copy kept the slide before's `animate: none` onto a slide that does not build, which
    is refused, and the flag could not be dropped from where it was written."""
    first = (
        "title: One\nanimate: one_at_a_time\nplace:\n"
        "  - {at: {cols: left-half}, morph: a, animate: none, card: {heading: A}}\n"
        "  - {at: {cols: right-half}, card: {heading: B}}\n---\n"
    )
    (_, still) = _slides(first + "title: Two\ncarry: previous\n")
    assert [(p.morph, p.still) for p in still.place] == [("a", False)]
    (_, building) = _slides(
        first + "title: Two\nanimate: one_at_a_time\ncarry: previous\nplace:\n"
        "  - {at: {cols: right-half}, card: {heading: New}}\n"
    )
    assert [(p.morph, p.still) for p in building.place] == [("a", True), (None, False)]


def test_a_carried_copy_is_not_hidden_again_behind_its_trigger():
    """The answer a click revealed on the slide before is on screen when the next lands."""
    (_, second) = _slides(
        "title: One\nplace:\n"
        "  - {at: {cols: left-half}, id: q, morph: q, card: {heading: Question}}\n"
        "  - {at: {cols: right-half}, morph: a, reveals: q, card: {heading: Answer}}\n"
        "---\ntitle: Two\ntransition: morph\ncarry: previous\nanimate: one_at_a_time\n"
    )
    assert [(p.morph, p.reveals) for p in second.place] == [("q", None), ("a", None)]
