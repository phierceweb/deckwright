import pytest

import deckwright.components  # noqa: F401 — registers the built-in components
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component, registered_components
from deckwright.utils.color import AA_LARGE, contrast_ratio

EMU = 914400


def _rule(ctx):
    get_component("rule")(ctx)
    return ctx.slide.shapes[0]


def _span(shape):
    """The line's start and end in inches, undoing the flips python-pptx normalizes to."""
    return (shape.begin_x / EMU, shape.begin_y / EMU), (shape.end_x / EMU, shape.end_y / EMU)


def test_a_horizontal_rule_runs_the_full_width_of_its_placement(ctx_factory):
    ctx = ctx_factory({"rule": {}})
    (x1, y1), (x2, y2) = _span(_rule(ctx))
    rect = ctx.body_rect
    assert (x1, x2) == pytest.approx((rect.left, rect.right))
    assert y1 == pytest.approx(y2) == pytest.approx(rect.top)


def test_anchor_moves_a_horizontal_rule_down_its_placement(ctx_factory):
    ctx = ctx_factory({"rule": {}})
    ctx.anchor = "middle"
    (_, y1), (_, y2) = _span(_rule(ctx))
    rect = ctx.body_rect
    assert y1 == pytest.approx(y2) == pytest.approx(rect.top + rect.height / 2)


def test_a_bottom_anchored_rule_sits_on_the_placements_bottom_edge(ctx_factory):
    ctx = ctx_factory({"rule": {}})
    ctx.anchor = "bottom"
    (_, y1), _ = _span(_rule(ctx))
    assert y1 == pytest.approx(ctx.body_rect.bottom)


def test_a_vertical_rule_runs_the_full_height_of_its_placement(ctx_factory):
    ctx = ctx_factory({"rule": {"orient": "vertical"}})
    (x1, y1), (x2, y2) = _span(_rule(ctx))
    rect = ctx.body_rect
    assert (y1, y2) == pytest.approx((rect.top, rect.bottom))
    assert x1 == pytest.approx(x2) == pytest.approx(rect.left)


def test_align_moves_a_vertical_rule_across_its_placement(ctx_factory):
    ctx = ctx_factory({"rule": {"orient": "vertical"}})
    ctx.align = "center"
    (x1, _), (x2, _) = _span(_rule(ctx))
    rect = ctx.body_rect
    assert x1 == pytest.approx(x2) == pytest.approx(rect.left + rect.width / 2)


def test_align_on_a_horizontal_rule_is_refused_because_it_already_spans_the_width(
    ctx_factory,
):
    ctx = ctx_factory({"rule": {}})
    ctx.align = "center"
    with pytest.raises(LayoutError, match="a horizontal rule spans its placement's whole width"):
        get_component("rule")(ctx)


def test_anchor_on_a_vertical_rule_is_refused(ctx_factory):
    ctx = ctx_factory({"rule": {"orient": "vertical"}})
    ctx.anchor = "middle"
    with pytest.raises(LayoutError, match="a vertical rule spans its placement's whole height"):
        get_component("rule")(ctx)


def test_the_weight_is_the_themes_line_weight(ctx_factory):
    ctx = ctx_factory({"rule": {}})
    assert _rule(ctx).line.width.pt == pytest.approx(ctx.theme.line_weight)


def test_weight_multiplies_the_themes_line_weight(ctx_factory):
    ctx = ctx_factory({"rule": {"weight": 0.4}})
    assert _rule(ctx).line.width.pt == pytest.approx(ctx.theme.line_weight * 0.4)


def test_a_weight_given_as_a_point_size_is_refused_as_a_multiple(ctx_factory):
    ctx = ctx_factory({"rule": {"weight": 12}})
    with pytest.raises(LayoutError, match="multiple of the theme's line weight"):
        get_component("rule")(ctx)


def test_the_quiet_default_role_gives_way_when_it_cannot_be_seen_on_the_paper(ctx_factory):
    """The theme's rule colour is invisible on a white page, so the rule takes muted."""
    ctx = ctx_factory({"rule": {}})
    palette = ctx.theme.palette
    assert contrast_ratio(palette.role("line"), ctx.pair.bg) < AA_LARGE
    assert str(_rule(ctx).line.color.rgb) == palette.role("muted")


def test_the_named_role_is_kept_when_it_reads_on_the_paper(ctx_factory):
    ctx = ctx_factory({"rule": {}}, background="inverse")
    palette = ctx.theme.palette
    assert contrast_ratio(palette.role("line"), ctx.pair.bg) >= AA_LARGE
    assert str(_rule(ctx).line.color.rgb) == palette.role("line")


def test_a_role_the_author_names_is_used_even_below_the_non_text_minimum(ctx_factory):
    """A brand's own accent as a hairline is a design choice, not a mistake to correct."""
    ctx = ctx_factory({"rule": {"color": "accent-1"}})
    palette = ctx.theme.palette
    assert contrast_ratio(palette.role("accent-1"), ctx.pair.bg) < AA_LARGE
    assert str(_rule(ctx).line.color.rgb) == palette.role("accent-1")


def test_a_named_role_that_cannot_be_seen_on_the_paper_is_refused(ctx_factory):
    ctx = ctx_factory({"rule": {"color": "line"}})
    with pytest.raises(LayoutError, match="cannot be seen; name a role that stands off it"):
        get_component("rule")(ctx)


def test_the_default_rule_reads_on_both_the_page_and_the_inverse_slide(ctx_factory):
    for background in ("page", "inverse"):
        ctx = ctx_factory({"rule": {}}, background=background)
        colour = str(_rule(ctx).line.color.rgb)
        assert contrast_ratio(colour, ctx.pair.bg) >= AA_LARGE, background


def test_an_undeclared_role_is_refused_by_name(ctx_factory):
    from deckwright.errors import ThemeError

    ctx = ctx_factory({"rule": {"color": "accent-9"}})
    with pytest.raises(ThemeError, match="no colour role 'accent-9'"):
        get_component("rule")(ctx)


def test_the_template_effect_a_connector_inherits_is_dropped(ctx_factory):
    """A connector arrives pointing at the template's effect style; a rule is a line."""
    assert "<a:effectLst/>" in _rule(ctx_factory({"rule": {}}))._element.spPr.xml


def test_an_unknown_orientation_lists_the_two(ctx_factory):
    ctx = ctx_factory({"rule": {"orient": "diagonal"}})
    with pytest.raises(LayoutError, match="'orient' must be one of horizontal, vertical"):
        get_component("rule")(ctx)


def test_an_unknown_field_lists_the_ones_the_rule_reads(ctx_factory):
    ctx = ctx_factory({"rule": {"thickness": 2}})
    with pytest.raises(LayoutError, match="known fields: orient, color, weight"):
        get_component("rule")(ctx)


def test_the_rule_is_recorded_for_qa(ctx_factory):
    ctx = ctx_factory({"rule": {}})
    get_component("rule")(ctx)
    record = ctx.manifest.slides[0].shapes[-1]
    assert record.shape_id == ctx.slide.shapes[0].shape_id
    assert record.text is None


def test_the_reveal_group_is_the_line_itself(ctx_factory):
    """A rule reports the ``line`` motion role, not a wire-format effect — the theme
    decides that lines draw themselves."""
    ctx = ctx_factory({"rule": {}})
    result = get_component("rule")(ctx)
    assert result.groups == [[(ctx.slide.shapes[0].shape_id, "line")]]


def test_the_rule_is_registered():
    assert "rule" in registered_components()
