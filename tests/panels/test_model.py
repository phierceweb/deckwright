import dataclasses

import pytest

from deckwright.errors import LayoutError
from deckwright.panels.model import Panel, Region


def test_regions_are_named():
    panel = Panel(
        html="<b>x</b>",
        width=700,
        regions=(Region("a", 0, 0, 700, 100), Region("b", 0, 100, 700, 100)),
    )
    assert panel.region_names() == ("a", "b")


def test_a_panel_may_have_no_regions():
    assert Panel(html="<b>x</b>", width=700).region_names() == ()


def test_duplicate_region_names_are_rejected():
    with pytest.raises(LayoutError, match="duplicate region"):
        Panel(html="x", width=700, regions=(Region("a", 0, 0, 10, 10), Region("a", 0, 10, 10, 10)))


def test_a_zero_width_panel_is_rejected():
    with pytest.raises(LayoutError, match="width"):
        Panel(html="x", width=0)


def test_a_region_with_no_area_is_rejected():
    with pytest.raises(LayoutError, match="area"):
        Region("a", 0, 0, 0, 10)


@pytest.mark.parametrize("name", ["../evil", "a/b", "a\\b", ".."])
def test_a_region_name_that_is_not_filesystem_safe_is_rejected(name):
    with pytest.raises(LayoutError, match="filesystem-safe"):
        Region(name, 0, 0, 10, 10)


def test_panel_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Panel(html="x", width=700).width = 800


def test_region_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Region("a", 0, 0, 10, 10).width = 20
