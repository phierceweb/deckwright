import pytest
from pptx.enum.dml import MSO_FILL

import deckwright.components  # noqa: F401 — registers the built-in components
from deckwright.errors import LayoutError, ThemeError
from deckwright.layouts.components import get_component
from deckwright.utils.color import contrast_ratio


def _panel(ctx):
    get_component("panel")(ctx)
    return ctx.slide.shapes[0]


def test_the_block_is_filled_with_the_background_of_the_pair_it_names(ctx_factory):
    ctx = ctx_factory({"panel": {"pair": "accent-3"}})
    shape = _panel(ctx)
    assert str(shape.fill.fore_color.rgb) == ctx.theme.palette.pair("accent-3").bg


def test_the_block_fills_the_rectangle_its_placement_resolved_to(ctx_factory):
    ctx = ctx_factory({"panel": {}})
    shape = _panel(ctx)
    assert shape.left / 914400 == pytest.approx(ctx.body_rect.left)
    assert shape.width / 914400 == pytest.approx(ctx.body_rect.width)


def test_a_fill_too_close_to_the_paper_to_see_is_given_an_edge(ctx_factory):
    """The surface tint reads as a block on a dark slide and as nothing on white."""
    ctx = ctx_factory({"panel": {"pair": "surface"}})
    assert contrast_ratio(ctx.theme.palette.pair("surface").bg, ctx.pair.bg) < 1.2
    shape = _panel(ctx)
    assert shape.line.fill.type == MSO_FILL.SOLID
    assert str(shape.line.color.rgb) == ctx.theme.palette.role("line")


def test_a_fill_that_stands_out_from_the_paper_is_left_unstroked(ctx_factory):
    ctx = ctx_factory({"panel": {"pair": "accent-3"}})
    assert _panel(ctx).line.fill.type == MSO_FILL.BACKGROUND


def test_a_pair_nothing_readable_sits_on_is_refused_by_name(ctx_factory):
    ctx = ctx_factory({"panel": {"pair": "page-muted-typo"}})
    with pytest.raises(ThemeError, match="no colour pair 'page-muted-typo'"):
        get_component("panel")(ctx)


def test_a_radius_outside_the_fraction_range_is_rejected(ctx_factory):
    ctx = ctx_factory({"panel": {"radius": 2}})
    with pytest.raises(LayoutError, match="'radius' is a fraction of the block"):
        get_component("panel")(ctx)


def test_a_non_numeric_radius_is_rejected(ctx_factory):
    ctx = ctx_factory({"panel": {"radius": "round"}})
    with pytest.raises(LayoutError, match="'radius' must be a number"):
        get_component("panel")(ctx)


def test_an_unknown_field_lists_the_ones_the_block_reads(ctx_factory):
    ctx = ctx_factory({"panel": {"colour": "red"}})
    with pytest.raises(LayoutError, match="known fields: pair, radius"):
        get_component("panel")(ctx)


def test_align_is_refused_because_the_block_sets_no_text(ctx_factory):
    ctx = ctx_factory({"panel": {}})
    ctx.align = "center"
    with pytest.raises(LayoutError, match="align 'center' has nothing to act on"):
        get_component("panel")(ctx)


def test_the_block_is_registered():
    from deckwright.layouts.components import registered_components

    assert "panel" in registered_components()
