"""A deckwright shape's name, read back into the placement that drew it."""

from __future__ import annotations

import pytest

import deckwright.components  # noqa: F401 — registers the built-ins
from deckwright.spec._origin import Origin, origin_of


@pytest.mark.parametrize(
    "name, origin",
    [
        ("s7.hero.card#2", Origin(slide=7, placement="hero", component="card", part="2")),
        ("s3.p2.table.r1c1", Origin(slide=3, placement="p2", component="table", part="r1c1")),
        ("s11.p1.chart.labels", Origin(slide=11, placement="p1", component="chart", part="labels")),
        ("m.figure.panel#1", Origin(slide=None, placement="figure", component="panel", part="1")),
        ("s2.a.b.card#1", Origin(slide=2, placement="a.b", component="card", part="1")),
        ("s4.p1.bullets#3", Origin(slide=4, placement="p1", component="bullets", part="3")),
        ("s1.x.card.bullets#1", Origin(slide=1, placement="x.card", component="bullets", part="1")),
    ],
)
def test_a_placements_shape_names_its_slide_placement_component_and_part(name, origin):
    assert origin_of(name) == origin


@pytest.mark.parametrize(
    "name",
    ["TextBox 4", "s1.chrome.title", "s1.chrome", "s2.bg#1", "s1.p1.nothing#1", "m.x", "Title 1"],
)
def test_chrome_a_background_and_foreign_names_are_no_placement(name):
    assert origin_of(name) is None


def test_a_morph_origin_is_marked_as_one():
    found = origin_of("m.figure.card#2")
    assert found is not None and found.morph and found.token == "m.figure.card"
    assert origin_of("s2.p1.card#1").token == "s2.p1.card"
