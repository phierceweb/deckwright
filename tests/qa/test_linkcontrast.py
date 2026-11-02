"""`link-contrast`: the colour Keynote draws a link in, against the ground it lands on."""

from __future__ import annotations

import json

import pytest

from deckwright.qa.linkcontrast import check_link_contrast
from deckwright.qa.model import Severity


@pytest.fixture
def linked(tmp_path, theme_file):
    """One linked line on an inverse slide and one on the page; the template's link colour is
    Office's own 0000FF."""
    from deckwright.compile import build_deck

    spec = tmp_path / "l.deck.yaml"
    body = (
        "place:\n  - at: {cols: full}\n    prose:\n      paragraphs:\n"
        "        - 'See [the docs](https://example.com) for more.'\n"
    )
    spec.write_text(
        "theme: testtheme\ntitle: T\nout: out/L.pptx\n"
        f"---\ntitle: Dark\nbackground: inverse\n{body}"
        f"---\ntitle: Light\n{body}"
        "---\ntitle: No link\nplace:\n  - at: {cols: full}\n    prose: {paragraphs: [Plain words.]}\n"
    )
    built = build_deck(spec, theme_path=theme_file)
    return built.deck, json.loads(built.manifest.read_text())


def test_a_link_on_a_ground_the_templates_link_colour_fails_on_is_reported(linked):
    """Blue on black is 2.4:1. On the white page it is 8.6:1 and says nothing."""
    found = check_link_contrast(*linked)
    assert [(f.slide, f.check, f.severity, f.shape) for f in found] == [
        (1, "link-contrast", Severity.WARN, "s1.p1.prose#1")
    ]
    assert found[0].detail.startswith(
        "Keynote draws links in the template's hlink colour 0000FF, 2.4:1 on this shape's "
        "ground 000000"
    )


def test_an_unreadable_deck_is_not_this_checks_finding(tmp_path):
    bad = tmp_path / "bad.pptx"
    bad.write_bytes(b"not a zip")
    assert check_link_contrast(bad, {"slides": []}) == []


def test_a_shape_the_manifest_records_no_ground_for_is_passed_over(linked):
    deck, data = linked
    for slide in data["slides"]:
        for shape in slide["shapes"]:
            shape.pop("bg", None)
    assert check_link_contrast(deck, data) == []
