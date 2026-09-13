"""What a successful `fanout` build never reaches: every `raise`, and the invariant that a
mark left outside every reveal group is on screen from the first beat, not merely unanimated."""

from __future__ import annotations

import pytest

import deckwright.components  # noqa: F401 — registers the built-ins
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component, shape_id

ITEMS = [
    {"icon": "mail", "text": "Subscriber digest"},
    {"icon": "search", "text": "Search index update"},
    {"text": "A dozen cache invalidations"},
]


def _ctx(ctx_factory, **body):
    return ctx_factory({"fanout": {"source": "publish(post)", "items": ITEMS, **body}})


def test_every_icon_is_inside_a_reveal_group(ctx_factory):
    """The bug this exists for: an ungrouped shape shows before the first click."""
    ctx = _ctx(ctx_factory)
    groups = get_component("fanout")(ctx).groups
    grouped = {shape_id(spid) for group in groups for spid in group}
    icons = [s.shape_id for s in ctx.slide.shapes if s.name.startswith("Icon ")]
    assert icons, "no icons were drawn, so this proves nothing"
    assert set(icons) <= grouped, "an icon is outside every group and shows from beat 0"


def test_a_row_without_an_icon_still_gets_a_group(ctx_factory):
    ctx = _ctx(ctx_factory)
    groups = get_component("fanout")(ctx).groups
    assert len(groups) == len(ITEMS) + 1  # the source plate leads


def test_the_source_and_bus_arrive_together(ctx_factory):
    """Branches hanging off a spine that has not arrived reads as a broken slide."""
    ctx = _ctx(ctx_factory)
    first = get_component("fanout")(ctx).groups[0]
    assert len(first) == 4  # plate, its text, trunk, spine


def test_source_is_required(ctx_factory):
    ctx = ctx_factory({"fanout": {"items": ITEMS}})
    with pytest.raises(LayoutError, match=r"'source' is the call the branches leave"):
        get_component("fanout")(ctx)


def test_one_item_is_refused(ctx_factory):
    ctx = ctx_factory({"fanout": {"source": "x()", "items": [ITEMS[0]]}})
    with pytest.raises(LayoutError, match=r"needs at least 2 items"):
        get_component("fanout")(ctx)


def test_an_item_needs_text(ctx_factory):
    ctx = ctx_factory({"fanout": {"source": "x()", "items": [{"icon": "mail"}, ITEMS[1]]}})
    with pytest.raises(LayoutError, match=r"item 1 needs a 'text'"):
        get_component("fanout")(ctx)


def test_an_unknown_item_key_is_refused(ctx_factory):
    ctx = ctx_factory(
        {"fanout": {"source": "x()", "items": [{"text": "a", "colour": "red"}, ITEMS[1]]}}
    )
    with pytest.raises(LayoutError, match=r"has the unknown field 'colour'"):
        get_component("fanout")(ctx)


def test_weight_out_of_range_is_refused(ctx_factory):
    with pytest.raises(LayoutError, match=r"'weight' scales the bus stroke"):
        get_component("fanout")(_ctx(ctx_factory, weight=99))


def test_every_returned_id_is_a_real_shape(ctx_factory):
    ctx = _ctx(ctx_factory)
    groups = get_component("fanout")(ctx).groups
    ids = {s.shape_id for s in ctx.slide.shapes}
    assert all(shape_id(spid) in ids for group in groups for spid in group)


def test_fanout_is_registered():
    from deckwright.layouts.components import registered_components

    assert "fanout" in registered_components()
