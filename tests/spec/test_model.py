import dataclasses

import pytest

from deckwright.spec.model import Background, Placement, SlideSpec


def test_a_slide_defaults_to_the_page_background():
    assert SlideSpec(index=1).background == Background(kind="page")


def test_every_chrome_field_is_absent_by_default():
    slide = SlideSpec(index=1)
    assert (slide.title, slide.kicker, slide.subtitle, slide.notes) == (None, None, None, None)


def test_a_slide_starts_with_no_placements():
    assert SlideSpec(index=1).place == ()


def test_a_placement_carries_its_component_and_its_mapping():
    placement = Placement(at={"cols": (0, 6)}, component="bullets", body={"items": ["a"]})
    assert placement.component == "bullets"
    assert placement.body == {"items": ["a"]}


def test_a_placement_is_anonymous_and_does_not_bleed_by_default():
    placement = Placement(at={"cols": (0, 6)}, component="bullets")
    assert placement.id is None and placement.bleed is False


def test_an_image_background_keeps_the_image_beside_the_kind():
    assert Background(kind="image", image="cover.png").image == "cover.png"


def test_the_page_background_selects_the_page_pair():
    assert Background().pair == "page"


def test_an_image_background_selects_the_inverse_pair():
    assert Background(kind="image", image="cover.png").pair == "inverse"


def test_a_slide_spec_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        SlideSpec(index=1).title = "no"
