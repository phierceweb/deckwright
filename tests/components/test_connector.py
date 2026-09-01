import pytest

import deckwright.components  # noqa: F401 — registers the built-in components
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component, registered_components
from deckwright.theme.model import Rect
from deckwright.utils.color import AA_LARGE, contrast_ratio

EMU = 914400

LEFT_BOX = Rect(1.0, 2.0, 2.0, 1.0)
RIGHT_BOX = Rect(6.0, 2.0, 2.0, 1.0)
LOWER_BOX = Rect(1.0, 5.0, 2.0, 1.0)
STEP_BOX = Rect(4.0, 4.0, 1.0, 1.0)


def _line(ctx):
    get_component("connector")(ctx)
    return ctx.slide.shapes[0]


def _span(shape):
    return (shape.begin_x / EMU, shape.begin_y / EMU), (shape.end_x / EMU, shape.end_y / EMU)


def _geometry(shape) -> str:
    return shape._element.spPr.prstGeom.get("prst")


def _bends(shape) -> tuple[int, int, list[tuple[int, int]]]:
    path = shape._element.spPr.custGeom.pathLst[0]
    return (
        shape.left,
        shape.top,
        [(int(pt.get("x")), int(pt.get("y"))) for pt in path.iter() if pt.get("x")],
    )


def _joined(ctx_factory, body, **boxes):
    ctx = ctx_factory({"connector": body})
    ctx.placements.update(boxes)
    return ctx


def test_side_by_side_placements_are_joined_at_their_facing_edges(ctx_factory):
    ctx = _joined(ctx_factory, {"from": "a", "to": "b"}, a=LEFT_BOX, b=RIGHT_BOX)
    start, end = _span(_line(ctx))
    assert start == pytest.approx((LEFT_BOX.right, 2.5))
    assert end == pytest.approx((RIGHT_BOX.left, 2.5))


def test_the_join_follows_the_placements_when_the_order_is_reversed(ctx_factory):
    ctx = _joined(ctx_factory, {"from": "b", "to": "a"}, a=LEFT_BOX, b=RIGHT_BOX)
    start, end = _span(_line(ctx))
    assert start == pytest.approx((RIGHT_BOX.left, 2.5))
    assert end == pytest.approx((LEFT_BOX.right, 2.5))


def test_stacked_placements_are_joined_bottom_to_top(ctx_factory):
    ctx = _joined(ctx_factory, {"from": "a", "to": "c"}, a=LEFT_BOX, c=LOWER_BOX)
    start, end = _span(_line(ctx))
    assert start == pytest.approx((2.0, LEFT_BOX.bottom))
    assert end == pytest.approx((2.0, LOWER_BOX.top))


def test_two_points_are_read_as_fractions_of_the_canvas(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8]}})
    start, end = _span(_line(ctx))
    scale = ctx.grid.scale
    assert start == pytest.approx((scale.x(0.1), scale.y(0.2)))
    assert end == pytest.approx((scale.x(0.9), scale.y(0.8)))


def test_a_placement_can_be_joined_to_a_bare_point(ctx_factory):
    ctx = _joined(ctx_factory, {"from": "a", "to": [0.9, 0.4]}, a=LEFT_BOX)
    start, _ = _span(_line(ctx))
    assert start == pytest.approx((LEFT_BOX.right, 2.5))


def test_the_default_line_is_straight(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8]}})
    assert _geometry(_line(ctx)) == "line"


def test_an_elbow_is_one_shape_with_its_bends_written_out(ctx_factory):
    """Explicit custGeom, not a bentConnector: LibreOffice re-routes a free bent
    connector with its own heuristic, running the last leg flush along the target."""
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8], "kind": "elbow"}})
    get_component("connector")(ctx)
    assert len(ctx.slide.shapes) == 1
    assert "custGeom" in ctx.slide.shapes[0]._element.xml


def test_an_elbow_enters_a_rect_square_on(ctx_factory):
    """The last leg must be perpendicular to the attached edge, so the arrowhead
    points into the card rather than alongside it."""
    from deckwright.components.connector import _route

    points = _route((4.5, 3.5), (5.7, 5.2), "h", "h")
    # entering a left/right edge: the final segment is horizontal
    (x1, y1), (x2, y2) = points[-2], points[-1]
    assert y1 == y2 and x1 != x2

    points = _route((4.5, 3.5), (5.7, 5.2), "v", "v")
    (x1, y1), (x2, y2) = points[-2], points[-1]
    assert x1 == x2 and y1 != y2


def test_another_connector_resolving_mid_build_does_not_move_this_ones_bends(
    ctx_factory, monkeypatch
):
    """The axis each end attached on travels back with its point, so a connector
    resolving between this one's attach and its route cannot re-route it."""
    from deckwright.components import connector as mod

    body = {"from": "a", "to": "b", "kind": "elbow"}
    solo = _bends(_line(_joined(ctx_factory, body, a=LEFT_BOX, b=STEP_BOX)))

    ctx = _joined(ctx_factory, body, a=LEFT_BOX, b=STEP_BOX)
    other = _joined(ctx_factory, {"from": "a", "to": "b"}, a=LOWER_BOX, b=RIGHT_BOX)
    run, pending = mod._run, [other]

    def interleave(target):
        ends = run(target)
        while pending:
            get_component("connector")(pending.pop())
        return ends

    monkeypatch.setattr(mod, "_run", interleave)
    assert _bends(_line(ctx)) == solo


def test_a_curved_connector_is_curved(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8], "kind": "curved"}})
    assert _geometry(_line(ctx)) == "curvedConnector3"


def test_an_unknown_kind_lists_the_three(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8], "kind": "dogleg"}})
    with pytest.raises(LayoutError, match="'kind' must be one of straight, elbow, curved"):
        get_component("connector")(ctx)


def test_no_arrowhead_is_drawn_by_default(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8]}})
    assert "End" not in _line(ctx).line._get_or_add_ln().xml


def test_an_end_arrow_marks_the_far_end_only(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8], "arrow": "end"}})
    xml = _line(ctx).line._get_or_add_ln().xml
    assert "tailEnd" in xml
    assert "headEnd" not in xml


def test_a_both_arrow_marks_each_end(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8], "arrow": "both"}})
    xml = _line(ctx).line._get_or_add_ln().xml
    assert "headEnd" in xml
    assert "tailEnd" in xml


def test_an_unknown_arrow_lists_the_three(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8], "arrow": "dot"}})
    with pytest.raises(LayoutError, match="'arrow' must be one of none, end, both"):
        get_component("connector")(ctx)


def test_an_id_no_placement_declares_is_refused_listing_the_ones_that_exist(ctx_factory):
    ctx = _joined(ctx_factory, {"from": "a", "to": "typo"}, a=LEFT_BOX, b=RIGHT_BOX)
    with pytest.raises(LayoutError, match="ids here: a, b"):
        get_component("connector")(ctx)


def test_an_id_on_a_slide_with_no_ids_at_all_says_so(ctx_factory):
    ctx = ctx_factory({"connector": {"from": "a", "to": [0.5, 0.5]}})
    with pytest.raises(LayoutError, match="no placement on this slide has one"):
        get_component("connector")(ctx)


def test_a_missing_end_is_refused_naming_both_forms_it_accepts(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2]}})
    with pytest.raises(LayoutError, match="'to' is required — give it a placement id"):
        get_component("connector")(ctx)


def test_a_point_that_is_not_two_numbers_is_refused(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2, 0.3], "to": [0.9, 0.8]}})
    with pytest.raises(LayoutError, match="'from' must be a placement id, or two numbers"):
        get_component("connector")(ctx)


def test_two_ends_at_the_same_point_are_refused(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.5, 0.5], "to": [0.5, 0.5]}})
    with pytest.raises(LayoutError, match="the same point on the canvas"):
        get_component("connector")(ctx)


def test_align_is_refused_because_a_line_sets_no_text(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8]}})
    ctx.align = "center"
    with pytest.raises(LayoutError, match="align 'center' has nothing to act on"):
        get_component("connector")(ctx)


def test_the_default_colour_is_the_accent_where_the_accent_reads(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8]}}, background="inverse")
    palette = ctx.theme.palette
    assert contrast_ratio(palette.role("accent-1"), ctx.pair.bg) >= AA_LARGE
    assert str(_line(ctx).line.color.rgb) == palette.role("accent-1")


def test_the_default_colour_gives_way_where_the_accent_does_not_read(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8]}})
    palette = ctx.theme.palette
    assert contrast_ratio(palette.role("accent-1"), ctx.pair.bg) < AA_LARGE
    assert str(_line(ctx).line.color.rgb) == palette.role("muted")


def test_the_weight_is_the_themes_line_weight(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8]}})
    assert _line(ctx).line.width.pt == pytest.approx(ctx.theme.line_weight)


def test_an_unknown_field_lists_the_ones_the_connector_reads(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8], "head": "x"}})
    with pytest.raises(LayoutError, match="known fields: from, to, kind, color, weight, arrow"):
        get_component("connector")(ctx)


def test_the_line_is_recorded_for_qa(ctx_factory):
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8]}})
    get_component("connector")(ctx)
    record = ctx.manifest.slides[0].shapes[-1]
    assert record.shape_id == ctx.slide.shapes[0].shape_id


def test_the_reveal_group_is_the_line_itself(ctx_factory):
    """A connector reports the ``line`` motion role; the theme binds it to a kind."""
    ctx = ctx_factory({"connector": {"from": [0.1, 0.2], "to": [0.9, 0.8]}})
    result = get_component("connector")(ctx)
    assert result.groups == [[(ctx.slide.shapes[0].shape_id, "line")]]


def test_the_connector_is_registered():
    assert "connector" in registered_components()
