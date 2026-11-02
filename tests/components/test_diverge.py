"""What a successful `diverge` build never reaches: every `raise`, and the invariant the
component exists for — a negative value draws to the *left* of the rule."""

from __future__ import annotations

import pytest

import deckwright.components  # noqa: F401 — registers the built-ins
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component, shape_id

ITEMS = [
    {"label": "Up", "value": 271, "note": "7 to 26"},
    {"label": "Down", "value": -146, "note": "26 to 64"},
]


def _ctx(ctx_factory, **body):
    return ctx_factory({"diverge": {"items": ITEMS, **body}})


def _plain(slide):
    """Shapes carrying no words: the bars and the centre rule. An autoshape has a text frame
    even when empty, so the filter is on the text, not on the frame."""
    return [s for s in slide.shapes if not (s.has_text_frame and s.text_frame.text)]


def _bars(slide):
    """(left, width) of each bar in inches, left to right; the rule is excluded."""
    shapes = _plain(slide)
    rule = max(shapes, key=lambda s: s.height)
    return sorted((s.left / 914400, s.width / 914400) for s in shapes if s is not rule)


def test_a_negative_value_draws_left_of_the_rule(ctx_factory):
    """The invariant the native chart route gets wrong through the render path."""
    ctx = _ctx(ctx_factory, peak=300)
    get_component("diverge")(ctx)
    rule = max(_plain(ctx.slide), key=lambda s: s.height)  # spans the whole rect
    rule_x = rule.left / 914400
    bars = _bars(ctx.slide)
    assert len(bars) == 2, bars
    (neg_left, neg_w), (pos_left, _) = bars[0], bars[1]
    assert neg_left < rule_x - 0.05, "the negative bar does not start left of the rule"
    assert neg_left + neg_w <= rule_x + 0.02, "the negative bar crosses the rule"
    assert pos_left >= rule_x - 0.02, "the positive bar starts left of the rule"


def test_pinning_peak_makes_two_blocks_agree(ctx_factory):
    """Unpinned, each block scales to its own longest bar, so equal values draw unequal —
    two diverges stacked on one slide is the whole reason `peak` exists."""
    both = ctx_factory({"diverge": {"peak": 300, "items": ITEMS}})
    get_component("diverge")(both)
    alone = ctx_factory({"diverge": {"peak": 300, "items": [ITEMS[1]]}})
    get_component("diverge")(alone)
    shared = [round(w, 4) for _, w in _bars(alone.slide)]
    assert shared == [round(w, 4) for _, w in _bars(both.slide) if round(w, 4) in shared]

    unpinned = ctx_factory({"diverge": {"items": [ITEMS[1]]}})
    get_component("diverge")(unpinned)
    assert [round(w, 4) for _, w in _bars(unpinned.slide)] != shared


def test_items_is_required(ctx_factory):
    with pytest.raises(LayoutError, match=r"'items' must be a non-empty list"):
        get_component("diverge")(ctx_factory({"diverge": {}}))


def test_an_item_needs_a_label_and_a_value(ctx_factory):
    ctx = ctx_factory({"diverge": {"items": [{"label": "only"}]}})
    with pytest.raises(LayoutError, match=r"item 1 needs a 'label' and a 'value'"):
        get_component("diverge")(ctx)


def test_a_value_that_is_not_a_number_names_the_item(ctx_factory):
    ctx = ctx_factory({"diverge": {"items": [{"label": "x", "value": "lots"}]}})
    with pytest.raises(LayoutError, match=r"item 1 has value 'lots'"):
        get_component("diverge")(ctx)


def test_an_unknown_item_key_is_refused(ctx_factory):
    ctx = ctx_factory({"diverge": {"items": [{"label": "x", "value": 1, "colour": "red"}]}})
    with pytest.raises(LayoutError, match=r"has the unknown field 'colour'"):
        get_component("diverge")(ctx)


def test_peak_must_be_positive(ctx_factory):
    with pytest.raises(LayoutError, match=r"'peak' is a positive magnitude"):
        get_component("diverge")(_ctx(ctx_factory, peak=0))


def test_label_width_is_a_fraction(ctx_factory):
    with pytest.raises(LayoutError, match=r"'label_width' is a fraction"):
        get_component("diverge")(_ctx(ctx_factory, label_width=3))


def test_a_label_width_that_is_not_a_number_names_the_value(ctx_factory):
    with pytest.raises(
        LayoutError,
        match=r"^slide 1 \(component 'diverge'\): 'label_width' is a fraction of the "
        r"placement's width, got 'wide'$",
    ):
        get_component("diverge")(_ctx(ctx_factory, label_width="wide"))


def test_align_is_refused(ctx_factory):
    ctx = _ctx(ctx_factory)
    ctx.align = "center"
    with pytest.raises(LayoutError, match=r"align 'center' would pull the labels"):
        get_component("diverge")(ctx)


def test_one_reveal_group_per_item(ctx_factory):
    assert len(get_component("diverge")(_ctx(ctx_factory)).groups) == len(ITEMS)


def test_every_returned_id_is_a_real_shape(ctx_factory):
    ctx = _ctx(ctx_factory)
    groups = get_component("diverge")(ctx).groups
    ids = {s.shape_id for s in ctx.slide.shapes}
    assert all(shape_id(spid) in ids for group in groups for spid in group)


def test_diverge_is_registered():
    from deckwright.layouts.components import registered_components

    assert "diverge" in registered_components()


def _bar_fills(ctx):
    """``{sign: fill}`` for each bar, off the shapes the build wrote. The rule and any plate
    span the placement's full height; a bar never does."""
    shapes = _plain(ctx.slide)
    full = max(s.height for s in shapes)
    rule = min((s for s in shapes if s.height == full), key=lambda s: s.width)
    return {
        "+" if s.left >= rule.left else "-": str(s.fill.fore_color.rgb)
        for s in shapes
        if s.height < full
    }


# accent-1 is the blue ground and accent-2 a shade of it, so the bars move on to accent-3,
# and the away bar to accent-4: a yellow only colour separates from the blue.
_BLUE_GROUND = {
    "ink": "000000",
    "inverse": "3282BE",
    "inverse-ink": "000000",
    "accent-1": "3282BE",
    "accent-2": "28608C",
    "accent-3": "262626",
    "accent-4": "FFD000",
}


def _built_on(ctx_factory, theme, roles, **body):
    """A diverge of ``ITEMS`` built under the fixture theme with ``roles`` laid over it."""
    import dataclasses

    from deckwright.theme.palette import build_palette

    palette = build_palette(
        {**theme.palette.roles, **roles},
        pairs={"page": ("ink", "page"), "inverse": ("inverse-ink", "inverse")},
    )
    ctx = ctx_factory(
        {"diverge": {"items": ITEMS, **body}},
        theme_override=dataclasses.replace(theme, palette=palette),
    )
    get_component("diverge")(ctx)
    return ctx


@pytest.mark.parametrize(
    ("page", "body"),
    [("3282BE", {}), ("FFFFFF", {"pair": "inverse"})],
    ids=["on-a-blue-page", "on-its-own-blue-plate"],
)
def test_bars_take_the_first_accents_that_stand_off_what_they_sit_on(
    ctx_factory, theme, page, body
):
    """On the plate, accent-1 reads 4.14:1 off the white page, so a choice made against the
    slide's pair rather than what is behind the bars keeps it."""
    ctx = _built_on(ctx_factory, theme, {**_BLUE_GROUND, "page": page}, **body)
    assert _bar_fills(ctx) == {"+": "262626", "-": "FFD000"}
    recorded = [(s.fill, s.ground) for s in ctx.manifest.slides[0].shapes if s.fill]
    assert recorded == [("262626", "3282BE"), ("FFD000", "3282BE")]


def test_bars_keep_the_first_two_accents_where_both_stand_off(ctx_factory):
    ctx = _ctx(ctx_factory)
    get_component("diverge")(ctx)
    assert _bar_fills(ctx) == {"+": "27B94C", "-": "18CEDA"}


def test_the_away_bar_passes_over_an_accent_it_could_not_be_told_from(ctx_factory, theme):
    """2262AB is a different hex from 1F5FA8 and the same blue to anyone looking."""
    roles = {"page": "FFFFFF", "ink": "000000", "accent-1": "1F5FA8", "accent-2": "2262AB"}
    ctx = _built_on(ctx_factory, theme, {**roles, "accent-3": "A8431C", "accent-4": "6A3FA0"})
    assert _bar_fills(ctx) == {"+": "1F5FA8", "-": "A8431C"}


def test_with_one_colour_that_stands_off_both_directions_share_it(ctx_factory, theme):
    """The ink 000000 stands off the page but not the 262626 already taken."""
    roles = {**_BLUE_GROUND, "page": "3282BE", "accent-4": "3282BE"}
    assert _bar_fills(_built_on(ctx_factory, theme, roles)) == {"+": "262626", "-": "262626"}
