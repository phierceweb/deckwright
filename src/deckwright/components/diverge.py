"""Signed bars growing either side of a centre rule, one row per datapoint.

Geometry rather than a native chart: LibreOffice, which `render` and `qa` go through,
draws a negative bar rightward and strips the sign from its label.
"""

from __future__ import annotations

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, RevealItem, component
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.model import Rect
from deckwright.utils.shapes import para, rect, textbox

from deckwright.components._shape import known_fields, known_item_fields

_FIELDS = ("items", "peak", "unit", "label_width", "pair")
_ITEM_FIELDS = frozenset({"label", "value", "note"})

_LABEL_WIDTH_DEFAULT = 0.30
_LABEL_WIDTH_RANGE = (0.1, 0.6)
# Room kept outside the longest bar for its own value label, so a full-scale row never
# writes its number over the label column.
_VALUE_GUTTER = 0.95
_VALUE_W = 0.8
_AXIS_W = 0.016
_BAR_LANE_FRACTION = 0.44
_BAR_MAX = 0.32
_NOTE_W = 2.4


def _label_width(ctx: SlideCtx) -> float:
    raw = ctx.body.get("label_width", _LABEL_WIDTH_DEFAULT)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'diverge'): 'label_width' is a fraction "
            f"of the placement's width, got {raw!r}"
        ) from None
    low, high = _LABEL_WIDTH_RANGE
    if not low <= value <= high:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'diverge'): 'label_width' is a fraction "
            f"of the placement's width, {low} to {high}; got {value:g}"
        )
    return value


def _items(ctx: SlideCtx) -> list[dict]:
    raw = ctx.body.get("items")
    if not isinstance(raw, list) or not raw:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'diverge'): 'items' must be a non-empty list"
        )
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict) or "label" not in item or "value" not in item:
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'diverge'): item {index} needs a "
                f"'label' and a 'value'"
            )
        known_item_fields(ctx, item, _ITEM_FIELDS, index=index)
        try:
            float(item["value"])
        except (TypeError, ValueError):
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'diverge'): item {index} has value "
                f"{item['value']!r} — a value is the signed number the bar draws"
            ) from None
    return raw


def _peak(ctx: SlideCtx, items: list[dict]) -> float:
    """The magnitude the longest bar stands for — pinned, so two diverges can agree."""
    raw = ctx.body.get("peak")
    if raw is None:
        return max(abs(float(i["value"])) for i in items) or 1.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'diverge'): 'peak' is the magnitude the "
            f"longest bar stands for, got {raw!r}"
        ) from None
    if value <= 0:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'diverge'): 'peak' is a positive "
            f"magnitude; got {value:g}"
        )
    return value


@component("diverge")
def diverge(ctx: SlideCtx) -> BodyResult:
    """One signed bar per item; one reveal group each.

    Rows are laid against a centre rule, so ``align`` is refused: the label column is
    set flush to the rule and centring it would pull every label off the axis.
    """
    if ctx.align != "left":
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'diverge'): align {ctx.align!r} would "
            f"pull the labels off the centre rule they are set against; 'diverge' sets "
            f"each label flush to the rule"
        )
    known_fields(ctx, _FIELDS)
    items = _items(ctx)
    label_w = _label_width(ctx)
    peak = _peak(ctx, items)
    r = ctx.body_rect

    # Inked, and recorded, against the ground this component paints rather than the slide's.
    pair_name = ctx.body.get("pair")
    if pair_name:
        ground = ctx.theme.palette.pair(str(pair_name))
        plate = rect(ctx.slide, r.left, r.top, r.width, r.height, ctx.rgb(ground.bg))
        ctx.manifest.record(plate)
        ctx.painted.append((r, ground.bg))
        ink_hex, bg_hex = ctx.ink_on(ground.bg), ground.bg
    else:
        ink_hex, bg_hex = ctx.text_ink(r, size_pt=ctx.style("body").size)
    ink = ctx.rgb(ink_hex)

    axis_x = r.left + r.width * label_w
    span = r.width - r.width * label_w - 0.1
    reach = max(span / 2 - _VALUE_GUTTER, 0.4)
    lane = r.height / len(items)
    bar_h = min(lane * _BAR_LANE_FRACTION, _BAR_MAX)
    centre = axis_x + span / 2
    unit = str(ctx.body.get("unit", ""))
    body, caption = ctx.style("body"), ctx.style("caption")
    toward, away = ctx.color("accent-1"), ctx.color("accent-2")
    groups: list[list[RevealItem]] = []

    for index, item in enumerate(items):
        value = float(item["value"])
        mid = r.top + index * lane + lane / 2
        width = abs(value) / peak * reach
        ids: list[RevealItem] = []

        label = textbox(
            ctx.slide,
            r.left,
            mid - lane * 0.32,
            r.width * label_w - 0.12,
            lane * 0.64,
            anchor=MSO_ANCHOR.MIDDLE,
        )
        para(
            label,
            str(item["label"]),
            body.size,
            ink,
            align=PP_ALIGN.RIGHT,
            first=True,
            space_after=0,
            font=ctx.theme.face,
        )
        ctx.manifest.record(
            label._parent, lines=[str(item["label"])], font_pt=body.size, fg=ink_hex, bg=bg_hex
        )
        ids.append((label._parent.shape_id, "text"))

        left = centre if value > 0 else centre - width
        bar = rect(ctx.slide, left, mid - bar_h / 2, width, bar_h, toward if value > 0 else away)
        fill = str(toward if value > 0 else away)
        ctx.manifest.record(
            bar, fill=fill, ground=ctx.behind(Rect(left, mid - bar_h / 2, width, bar_h), ink=fill)
        )
        ctx.painted.append((Rect(left, mid - bar_h / 2, width, bar_h), fill))
        ids.append((bar.shape_id, "surface"))

        reading = f"{'+' if value > 0 else '−'}{abs(value):g}{unit}"
        value_x = left + width + 0.06 if value > 0 else left - _VALUE_W - 0.06
        shown = textbox(
            ctx.slide, value_x, mid - bar_h, _VALUE_W, bar_h * 2, anchor=MSO_ANCHOR.MIDDLE
        )
        para(
            shown,
            reading,
            body.size,
            ink,
            bold=True,
            align=PP_ALIGN.LEFT if value > 0 else PP_ALIGN.RIGHT,
            first=True,
            space_after=0,
            font=ctx.theme.face,
        )
        ctx.manifest.record(
            shown._parent, lines=[reading], font_pt=body.size, fg=ink_hex, bg=bg_hex
        )
        ids.append((shown._parent.shape_id, "text"))

        # The note sits in the half its own bar does not use, so it cannot collide with
        # the bar, the value or the label column however long the bar runs.
        note = str(item.get("note", ""))
        if note:
            # Clamped to the rect: _NOTE_W is a fixed width, and a placement narrower
            # than the axis plus that width leaves the note hanging over its neighbour.
            if value > 0:
                note_x = max(r.left, centre - 0.12 - _NOTE_W)
                note_w = centre - 0.12 - note_x
            else:
                note_x = centre + 0.12
                note_w = min(_NOTE_W, r.right - note_x)
            noted = textbox(
                ctx.slide, note_x, mid - lane * 0.32, note_w, lane * 0.64, anchor=MSO_ANCHOR.MIDDLE
            )
            para(
                noted,
                note,
                caption.size,
                ink,
                align=PP_ALIGN.RIGHT if value > 0 else PP_ALIGN.LEFT,
                first=True,
                space_after=0,
                font=ctx.theme.face,
            )
            ctx.manifest.record(
                noted._parent, lines=[note], font_pt=caption.size, fg=ink_hex, bg=bg_hex
            )
            ids.append((noted._parent.shape_id, "text"))

        groups.append(ids)

    axis = rect(ctx.slide, centre - _AXIS_W / 2, r.top, _AXIS_W, r.height, ctx.color("line"))
    ctx.manifest.record(axis)
    return BodyResult(groups=groups, height=r.height)
