"""A sequence of steps: the timeline / process slide.

Nothing new is drawn here — the plate is ``card``, the disc is ``ellipse``, the join is
``connector``, each on a sub-context. ``flow`` owns the arithmetic that divides one
placement into steps, and the lane the joins run down.
"""

from __future__ import annotations

from deckwright.errors import LayoutError
from deckwright.layouts.components import (
    BodyResult,
    RevealItem,
    as_body_result,
    component,
)
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.model import Rect
from deckwright.utils.text import LINE_HEIGHT

from deckwright.components._shape import ARROWS, anchored, choice, flag, known_fields, pair_named
from deckwright.components._shared import coerce_int, require_list, subcontext
from deckwright.components.card import card, plate_height
from deckwright.components.connector import connector
from deckwright.components.ellipse import ellipse
from deckwright.utils.keys import unknown_field

_FIELDS = ("items", "direction", "numbered", "current", "pair", "arrow")
_ITEM_FIELDS = frozenset({"head", "body", "icon"})
_DIRECTIONS = ("horizontal", "vertical")
_PAIR_DEFAULT = "surface"
_BADGE_PAIR = "accent-1"
_CURRENT_PAIR = "accent-1"
# The highlighted step's disc has to stand off its own plate, which by then is the accent.
_CURRENT_BADGE_PAIR = "inverse"
_MIN_STEPS = 2
# The gap between two steps is a lane a join runs down, not just the space that keeps
# two blocks apart, so it is wider than the gutter that would merely separate them.
_LANE_GUTTERS = 2.0
# The disc is a mark beside the copy, sized like a card's icon: two heading line-heights.
_BADGE_LINES = 2.0
# A point of slack on the plate: 'card' re-derives its inner area from the depth given
# here and refuses copy that overruns it by any amount, float noise included.
_SLACK_IN = 1 / 72
_TAIL, _HEAD = "flow:from", "flow:to"


@component("flow")
def flow(ctx: SlideCtx) -> BodyResult:
    """Lay the steps out along the placement and join them in order."""
    known_fields(ctx, _FIELDS)
    items = _items(ctx)
    direction = choice(ctx, "direction", _DIRECTIONS, default="horizontal")
    numbered = flag(ctx, "numbered")
    current = _current(ctx, len(items))
    arrow = choice(ctx, "arrow", ARROWS, default="end")
    plate_pair = str(ctx.body.get("pair", _PAIR_DEFAULT))
    pair_named(ctx, _PAIR_DEFAULT)  # refuse an undeclared pair against 'flow', not 'card'

    rect = ctx.body_rect
    cells = _cells(ctx, rect, len(items), direction)
    diameter = _badge_diameter(ctx, cells[0], direction) if numbered else 0.0
    depth = _plate_depth(ctx, items, cells[0], diameter, direction)

    groups: list[list[RevealItem]] = []
    marks: list[Rect] = []
    for index, (item, cell) in enumerate(zip(items, cells, strict=True), start=1):
        badge, plate = _split(ctx, cell, diameter, depth, direction)
        shapes: list[RevealItem] = []
        if badge is not None:
            shapes.append(_badge(ctx, badge, index, current=index == current))
        shapes.extend(
            _plate(ctx, plate, item, pair=_CURRENT_PAIR if index == current else plate_pair)
        )
        marks.append(badge if badge is not None else plate)
        if index > 1:
            shapes.insert(0, _join(ctx, marks[-2], marks[-1], arrow))
        groups.append(shapes)
    extent = rect.height if direction == "vertical" else _rail(ctx, diameter) + depth
    return BodyResult(groups=groups, height=extent)


def _rail(ctx: SlideCtx, diameter: float) -> float:
    """What the numbered disc costs the step it sits beside: itself and a gutter."""
    return diameter + ctx.grid.gutter if diameter else 0.0


def _items(ctx: SlideCtx) -> list[dict]:
    items = require_list(ctx, "items")
    if len(items) < _MIN_STEPS:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'flow'): a flow needs at least "
            f"{_MIN_STEPS} steps to be a sequence — a single step is the 'card' component"
        )
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or not str(item.get("head", "")).strip():
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'flow'): step {index} needs a 'head'"
            )
        unknown = sorted(set(item) - _ITEM_FIELDS)
        if unknown:
            raise LayoutError(
                unknown_field(
                    unknown[0],
                    sorted(_ITEM_FIELDS),
                    where=f"slide {ctx.spec.index} (component 'flow')",
                    lead=f"step {index} has the unknown field",
                    label="a step reads",
                )
            )
    return items


def _current(ctx: SlideCtx, count: int) -> int | None:
    raw = ctx.body.get("current")
    if raw is None:
        return None
    index = coerce_int(ctx, "current", raw, 0)
    if not 1 <= index <= count:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'flow'): 'current' is the 1-based step to "
            f"highlight, so it runs 1 to {count} for these items; got {index}"
        )
    return index


def _cells(ctx: SlideCtx, rect: Rect, count: int, direction: str) -> list[Rect]:
    """One rectangle per step, with a lane left between consecutive steps."""
    lane = ctx.grid.gutter * _LANE_GUTTERS
    horizontal = direction == "horizontal"
    span = rect.width if horizontal else rect.height
    extent = (span - lane * (count - 1)) / count
    if extent <= 0:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'flow'): {count} steps and the "
            f"{lane:.2f}in lanes between them need more than the {span:.2f}in this "
            f"placement runs {'across' if horizontal else 'down'} — drop a step or grow "
            f"the placement"
        )
    if horizontal:
        return [
            Rect(rect.left + i * (extent + lane), rect.top, extent, rect.height)
            for i in range(count)
        ]
    return [
        Rect(rect.left, rect.top + i * (extent + lane), rect.width, extent) for i in range(count)
    ]


def _badge_diameter(ctx: SlideCtx, cell: Rect, direction: str) -> float:
    """The numbered disc's diameter, off the type ramp, refusing a cell too small for it."""
    diameter = ctx.style("head").size * LINE_HEIGHT / 72 * _BADGE_LINES
    gap = ctx.grid.gutter
    along, across = (
        (cell.height, cell.width) if direction == "horizontal" else (cell.width, cell.height)
    )
    if diameter + gap >= along or diameter > across:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'flow'): a numbered disc is "
            f"{diameter:.2f}in across at this canvas's head size, and each step is only "
            f"{cell.width:.2f}x{cell.height:.2f}in — grow the placement or drop 'numbered'"
        )
    return diameter


def _plate_depth(
    ctx: SlideCtx, items: list[dict], cell: Rect, diameter: float, direction: str
) -> float:
    """How deep every plate is drawn: what the wordiest step needs, bounded by the cell.

    One depth for all of them, or the run reads as a ragged edge rather than a sequence.
    """
    rail = _rail(ctx, diameter)
    horizontal = direction == "horizontal"
    width = cell.width if horizontal else cell.width - rail
    limit = cell.height - rail if horizontal else cell.height
    natural = max(
        plate_height(
            ctx,
            width=width,
            heading=str(item["head"]),
            copy=str(item.get("body") or ""),
            icon=bool(item.get("icon")),
        )
        for item in items
    )
    return min(natural + _SLACK_IN, limit)


def _split(
    ctx: SlideCtx, cell: Rect, diameter: float, depth: float, direction: str
) -> tuple[Rect | None, Rect]:
    """A step's cell divided into the disc's rail and the plate beside or below it."""
    rail = _rail(ctx, diameter)
    if direction == "horizontal":
        plate = Rect(cell.left, cell.top + rail, cell.width, depth)
        badge = (
            anchored(cell, diameter, diameter, align="center", anchor="top") if diameter else None
        )
        return badge, plate
    # Down the page the plate floats in the middle of its cell, so the disc on the rail
    # sits level with the copy rather than with the top of a shorter plate.
    plate = Rect(cell.left + rail, cell.top + (cell.height - depth) / 2, cell.width - rail, depth)
    badge = anchored(cell, diameter, diameter, align="left", anchor="middle") if diameter else None
    return badge, plate


def _badge(ctx: SlideCtx, rect: Rect, index: int, *, current: bool) -> RevealItem:
    fields = {"label": str(index), "pair": _CURRENT_BADGE_PAIR if current else _BADGE_PAIR}
    sub = subcontext(ctx, "step disc", fields, rect, align="center", anchor="middle")
    return as_body_result(ellipse(sub)).groups[0][0]


def _plate(ctx: SlideCtx, rect: Rect, item: dict, *, pair: str) -> list[RevealItem]:
    fields: dict = {"heading": str(item["head"]), "pair": pair}
    if item.get("body"):
        fields["body"] = str(item["body"])
    if item.get("icon"):
        fields["icon"] = str(item["icon"])
    return as_body_result(card(subcontext(ctx, "step plate", fields, rect))).groups[0]


def _join(ctx: SlideCtx, tail: Rect, head: Rect, arrow: str) -> RevealItem:
    """The line from one step's mark to the next, drawn by ``connector`` itself.

    The two ends are handed over as a placement table private to this call, so the slide
    need not declare an id per step.
    """
    fields = {"from": _TAIL, "to": _HEAD, "arrow": arrow}
    sub = subcontext(
        ctx,
        "step join",
        fields,
        ctx.body_rect,
        align="left",
        anchor="top",
        placements={_TAIL: tail, _HEAD: head},
    )
    return as_body_result(connector(sub)).groups[0][0]
