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
