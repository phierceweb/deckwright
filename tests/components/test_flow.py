"""What a successful flow build never reaches, plus the four choices its output hides: how
deep a plate is drawn, which step takes the accent, which mark the join attaches to, and
which step reveals it."""

import pytest

import deckwright.components  # noqa: F401 — registers the built-in components
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component
from deckwright.theme.model import Rect

EMU = 914400

STEPS = [
    {"head": "Draft", "body": "Write it."},
    {"head": "Review", "body": "Read it."},
    {"head": "Ship", "body": "Send it."},
]

# The fixture theme sets 'head' at 18pt on a 7.5in canvas and gutters at 0.18in.
BADGE_IN = 18 * 1.2 / 72 * 2
LANE_IN = 0.18 * 2
ACCENT_FILL = "27B94C"
SURFACE_FILL = "F5F6F8"


def _flow(ctx, body):
    ctx.component, ctx.body = "flow", body
    return get_component("flow")(ctx)


def _prst(shape) -> str | None:
    geom = shape._element.spPr.prstGeom
    return None if geom is None else geom.get("prst")


def _of(ctx, prst):
    return sorted((s for s in ctx.slide.shapes if _prst(s) == prst), key=lambda s: (s.left, s.top))


def _joins(ctx):
    return [s for s in ctx.slide.shapes if hasattr(s, "begin_x")]


def test_the_numbered_disc_is_two_heading_line_heights_across(ctx_factory):
    ctx = ctx_factory({})
    _flow(ctx, {"numbered": True, "items": STEPS})
    discs = _of(ctx, "ellipse")
    assert len(discs) == 3
    # Against BADGE_IN, never a bare 0.6 beside it: a literal on both sides of an
    # equality is a comparison nothing in `src/` can redden.
    assert [d.width / EMU for d in discs] == pytest.approx([BADGE_IN] * 3)


def test_a_step_across_the_page_stands_its_disc_above_the_plate(ctx_factory):
    ctx = ctx_factory({})
    _flow(ctx, {"numbered": True, "items": STEPS})
    disc, plate = _of(ctx, "ellipse")[0], _of(ctx, "roundRect")[0]
    assert disc.top + disc.height <= plate.top
    assert (disc.left + disc.width / 2) == pytest.approx(plate.left + plate.width / 2)


def test_a_step_down_the_page_stands_its_disc_beside_the_plate(ctx_factory):
    ctx = ctx_factory({})
    _flow(ctx, {"direction": "vertical", "numbered": True, "items": STEPS})
    disc, plate = _of(ctx, "ellipse")[0], _of(ctx, "roundRect")[0]
    assert disc.left + disc.width <= plate.left
    assert (disc.top + disc.height / 2) == pytest.approx(plate.top + plate.height / 2)


def test_every_plate_is_drawn_as_deep_as_the_wordiest_step(ctx_factory):
    wordy = [
        {"head": "Draft", "body": "Write it."},
        {
            "head": "Review",
            "body": "Read the whole thing back slowly and mark every line that "
            "will not survive a second reader.",
        },
        {"head": "Ship", "body": "Send it."},
    ]
    ctx = ctx_factory({})
    _flow(ctx, {"items": wordy})
    depths = {p.height for p in _of(ctx, "roundRect")}
    assert len(depths) == 1

    plain = ctx_factory({})
    _flow(plain, {"items": STEPS})
    assert depths.pop() > _of(plain, "roundRect")[0].height


def test_the_highlighted_step_is_the_only_plate_painted_in_the_accent(ctx_factory):
    ctx = ctx_factory({})
    _flow(ctx, {"current": 2, "items": STEPS})
    fills = [str(p.fill.fore_color.rgb) for p in _of(ctx, "roundRect")]
    assert fills == [SURFACE_FILL, ACCENT_FILL, SURFACE_FILL]


def test_the_join_attaches_to_the_discs_when_the_steps_are_numbered(ctx_factory):
    ctx = ctx_factory({})
    _flow(ctx, {"numbered": True, "items": STEPS[:2]})
    rect = ctx.body_rect
    cell_w = (rect.width - LANE_IN) / 2
    join = _joins(ctx)[0]
    assert join.begin_x / EMU == pytest.approx(rect.left + cell_w / 2 + BADGE_IN / 2)
    assert join.begin_y / EMU == pytest.approx(rect.top + BADGE_IN / 2)


def test_the_join_attaches_to_the_plates_when_no_step_is_numbered(ctx_factory):
    ctx = ctx_factory({})
    _flow(ctx, {"items": STEPS[:2]})
    rect = ctx.body_rect
    cell_w = (rect.width - LANE_IN) / 2
    assert _joins(ctx)[0].begin_x / EMU == pytest.approx(rect.left + cell_w)


def test_the_join_into_a_step_is_revealed_with_that_step(ctx_factory):
    ctx = ctx_factory({})
    result = _flow(ctx, {"numbered": True, "items": STEPS})
    joined = {s.shape_id for s in _joins(ctx)}
    assert len(joined) == 2
    ids = [{g[0] if isinstance(g, tuple) else g for g in group} for group in result.groups]
    assert [len(joined & group) for group in ids] == [0, 1, 1]


def test_a_flow_of_one_step_is_refused(ctx_factory):
    ctx = ctx_factory({})
    with pytest.raises(LayoutError, match="at least 2 steps"):
        _flow(ctx, {"items": STEPS[:1]})


def test_a_step_without_a_head_is_refused(ctx_factory):
    ctx = ctx_factory({})
    with pytest.raises(LayoutError, match="step 2 needs a 'head'"):
        _flow(ctx, {"items": [STEPS[0], {"body": "No heading here."}]})


def test_a_step_carrying_a_field_a_step_does_not_read_is_refused(ctx_factory):
    ctx = ctx_factory({})
    with pytest.raises(LayoutError, match="step 1 has the unknown field 'title'"):
        _flow(ctx, {"items": [{"head": "Draft", "title": "Draft"}, STEPS[1]]})


def test_a_current_step_outside_the_run_is_refused(ctx_factory):
    ctx = ctx_factory({})
    with pytest.raises(LayoutError, match="runs 1 to 3"):
        _flow(ctx, {"current": 4, "items": STEPS})


def test_steps_the_placement_cannot_hold_side_by_side_are_refused(ctx_factory):
    ctx = ctx_factory({})
    ctx.rect = Rect(1.0, 1.0, 0.5, 3.0)
    with pytest.raises(LayoutError, match="3 steps and the 0.36in lanes"):
        _flow(ctx, {"items": STEPS})


def test_a_step_too_shallow_for_its_own_disc_is_refused(ctx_factory):
    ctx = ctx_factory({})
    ctx.rect = Rect(1.0, 1.0, 9.0, 0.5)
    with pytest.raises(LayoutError, match="numbered disc is 0.60in across"):
        _flow(ctx, {"numbered": True, "items": STEPS})
