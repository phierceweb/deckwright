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
        "'morph: solo' has no namesake on slide 2, so Morph has nothing of that name to pair it with"
    )
    assert found[1].detail == (
        "the slide asks to morph and names nothing: no placement on it carries 'morph:', so "
        "Morph is given no name to pair"
    )


def test_a_deck_that_never_morphs_reports_nothing(theme):
    data = {"slides": [{"index": 1, "transition": "push", "shapes": [{"name": "m.x.card#1"}]}]}
    assert check_morph(data, theme) == []
