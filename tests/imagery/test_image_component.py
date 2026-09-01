"""What the ``image`` component refuses, and the geometry a mask forces on it: a build reaches
the squaring but never reads it back, and a circle drawn on an oblong is an oval."""

from __future__ import annotations

import pytest
from pptx.util import Inches

import deckwright.components  # noqa: F401 — registers the built-in components
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component


def _draw(ctx):
    get_component("image")(ctx)
    return list(ctx.slide.shapes)


def test_a_circle_mask_squares_the_placement(ctx_factory, white_wide):
    """A 16:9 placement masked to an ellipse would draw an oval, so the box is squared."""
    ctx = ctx_factory({"image": {"src": str(white_wide), "mask": "circle"}})
    picture = _draw(ctx)[0]
    assert picture.width == picture.height


def test_an_unmasked_picture_keeps_the_whole_placement(ctx_factory, white_wide):
    """The contrast with the test above: nothing else squares a placement."""
    ctx = ctx_factory({"image": {"src": str(white_wide)}})
    picture = _draw(ctx)[0]
    assert picture.width > picture.height


def test_a_circle_mask_refuses_a_contain_fit(ctx_factory, white_wide):
    """``contain`` re-oblongs the squared box to the source's aspect — an oval again."""
    ctx = ctx_factory({"image": {"src": str(white_wide), "mask": "circle", "fit": "contain"}})
    with pytest.raises(LayoutError, match="circle mask needs 'fit: cover'"):
        _draw(ctx)


def test_a_rounded_mask_accepts_a_contain_fit(ctx_factory, black_tall):
    """The refusal is specific to circles: a rounded rectangle of any aspect is fine."""
    ctx = ctx_factory({"image": {"src": str(black_tall), "mask": "rounded", "fit": "contain"}})
    assert _draw(ctx)


def test_a_radius_beyond_a_half_is_refused(ctx_factory, white_wide):
    ctx = ctx_factory({"image": {"src": str(white_wide), "mask": "rounded", "radius": 0.75}})
    with pytest.raises(LayoutError, match="fraction of the picture's short side"):
        _draw(ctx)


def test_a_missing_src_is_refused(ctx_factory):
    with pytest.raises(LayoutError, match="'src' must name an image file"):
        _draw(ctx_factory({"image": {"mask": "circle"}}))


def test_an_unknown_field_names_the_known_ones(ctx_factory, white_wide):
    ctx = ctx_factory({"image": {"src": str(white_wide), "opacity": 0.5}})
    with pytest.raises(LayoutError, match="unknown field 'opacity'"):
        _draw(ctx)


def test_an_over_line_without_text_is_refused(ctx_factory, white_wide):
    ctx = ctx_factory({"image": {"src": str(white_wide), "over": [{"rung": "title"}]}})
    with pytest.raises(LayoutError, match="every 'over' line needs a 'text'"):
        _draw(ctx)


def test_an_over_line_with_an_unknown_key_names_the_known_ones(ctx_factory, white_wide):
    ctx = ctx_factory(
        {"image": {"src": str(white_wide), "over": [{"text": "Hi", "colour": "red"}]}}
    )
    with pytest.raises(LayoutError, match="has no key 'colour'"):
        _draw(ctx)


def test_a_crop_that_is_not_an_aspect_is_refused(ctx_factory, white_wide):
    ctx = ctx_factory({"image": {"src": str(white_wide), "crop": "widescreen"}})
    with pytest.raises(LayoutError, match="write it as '16:9'"):
        _draw(ctx)


def test_an_inset_wider_than_the_picture_is_refused(ctx_factory, white_wide):
    """Silently clamping would stack the text outside the picture it belongs to."""
    ctx = ctx_factory({"image": {"src": str(white_wide), "inset": 0.9, "over": [{"text": "Hi"}]}})
    with pytest.raises(LayoutError, match="leaves the text no width"):
        _draw(ctx)


def test_text_over_a_white_photograph_gets_a_scrim_nobody_asked_for(ctx_factory, white_wide):
    """The failure the component exists to prevent: white ink straight onto white."""
    ctx = ctx_factory(
        {"image": {"src": str(white_wide), "over": [{"text": "Unreadable without one"}]}}
    )
    shapes = _draw(ctx)
    assert len(shapes) == 3, "expected picture, scrim, textbox"
    scrim = shapes[1]
    assert scrim.width == Inches(ctx.body_rect.width)
