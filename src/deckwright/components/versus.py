"""Two magnitudes either side of a glyph — a before and an after, or a this and a that.

The glyph makes the pair read as one comparison rather than two facts; `highlight` says
which side the slide is arguing for.
"""

from __future__ import annotations

import re

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from deckwright.errors import LayoutError
from deckwright.icons.draw import place_icon
from deckwright.layouts.components import BodyResult, RevealItem, component
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.model import Rect
from deckwright.utils.shapes import para, rrect, textbox
from deckwright.utils.text import text_em

from deckwright.components._shape import known_fields, known_item_fields

_FIELDS = ("left", "right", "icon")
_SIDE_FIELDS = frozenset({"value", "label", "note", "highlight"})

_ICON_DEFAULT = "schedule"
_MIDDLE = 1.05
_GLYPH_SIDE = 0.66
_INSET = 0.24
_RADIUS = 0.05
# The stat rung is sized for a tile that fills its placement; a side here also carries a
# label and sometimes a note, so the number gives a little back.
_VALUE_SCALE = 0.86
_MIN_SIDE = 1.2  # no plate reads as a plate below this, whatever its text measures
# The number inside a written value, whatever unit is set around it.
_MAGNITUDE = re.compile(r"-?\d[\d,]*\.?\d*")


def _magnitude(value: object) -> float | None:
    """The number a side's value carries, or ``None`` when it carries none."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    found = _MAGNITUDE.search(str(value))
    if found is None:
        return None
    try:
        return float(found.group().replace(",", ""))
    except ValueError:
        return None


def _unit(value: object) -> str:
    """Whatever is written around the number, folded so `Days` and `days` agree.

    Matched whole. No string rule separates a plural from another unit — `hrs`/`hr` and
    `ms`/`m` are the same shape — and sizing two different units against each other
    argues the opposite of the data, so only an exact match compares.
    """
    if isinstance(value, (bool, int, float)):
        return ""
    return "".join("".join(_MAGNITUDE.split(str(value))).casefold().split())


def _side_floor(
    side: dict,
    *,
    value_pt: float,
    label_pt: float,
    note_pt: float,
    value_face: str | None,
    text_face: str | None,
) -> float:
    """The narrowest plate this side's text can be set in without breaking mid-word.

    Width only. Whether the stack then fits the band is `qa`'s `text-fit` check, which
    measures the shape as drawn; solving it here needs a width the placement may not
    have, and a component cannot refuse its way out of a band that is simply too short.
    """
    rows = [(str(side["value"]), value_pt), (str(side["label"]), label_pt)]
    if side.get("note"):
        rows.append((str(side["note"]), note_pt))
    widest = max(
        (
            text_em(word, value_face if pt == value_pt else text_face) * pt / 72
            for text, pt in rows
            for word in text.split()
        ),
        default=0.0,
    )
    return max(_MIN_SIDE, widest + 2 * _INSET)


def _plate_widths(
    sides: tuple[dict, dict], total: float, floors: tuple[float, float]
) -> tuple[float, float]:
    """Each plate's width, in proportion to its value.

    Two plates of identical width state that the magnitudes are equal, which is the one
    thing a versus is never used to say. Values that are not numbers keep the even split,
    and so do two written in different units: `2 days` against `4 hours` compares 2 with
    4 and would draw the longer span smaller.
    """
    left, right = (_magnitude(s["value"]) for s in sides)
    if (
        left is None
        or right is None
        or left <= 0
        or right <= 0
        or _unit(sides[0]["value"]) != _unit(sides[1]["value"])
    ):
        share = total / 2
    else:
        share = total * left / (left + right)
    share = min(max(share, floors[0]), total - floors[1])
    return share, total - share


def _side(ctx: SlideCtx, key: str) -> dict:
    raw = ctx.body.get(key)
    if not isinstance(raw, dict) or "value" not in raw or "label" not in raw:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'versus'): {key!r} needs a 'value' and "
            f"a 'label' — a versus is two named magnitudes"
        )
    known_item_fields(ctx, raw, _SIDE_FIELDS, noun=key)
    return raw


@component("versus")
def versus(ctx: SlideCtx) -> BodyResult:
    """Two plates and the glyph between them; one reveal group per side."""
    # Both plates fill the placement and centre their own type, so neither key can act.
    for key, value in (("align", ctx.align), ("anchor", ctx.anchor)):
        if value != ("left" if key == "align" else "top"):
            raise LayoutError(
                f"slide {ctx.spec.index} (component 'versus'): {key} {value!r} has "
                f"nothing to act on — a versus fills its placement and sets its own "
                f"type; drop the {key}, or bound the placement with 'rows:'"
            )
    known_fields(ctx, _FIELDS)
    sides = (_side(ctx, "left"), _side(ctx, "right"))
    if all(s.get("highlight") for s in sides):
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'versus'): both sides set 'highlight' — "
            f"it marks the one the slide is arguing for, so only one side takes it"
        )
    glyph = str(ctx.body.get("icon", _ICON_DEFAULT))
    r = ctx.body_rect
    total = r.width - _MIDDLE
    stat, body, caption = ctx.style("stat"), ctx.style("body"), ctx.style("caption")

    def floor(side: dict) -> float:
        return _side_floor(
            side,
            value_pt=stat.size * _VALUE_SCALE,
            label_pt=body.size,
            note_pt=caption.size,
            value_face=ctx.theme.font_for(stat),
            text_face=ctx.theme.face,
        )

    floors = (floor(sides[0]), floor(sides[1]))
    if floors[0] + floors[1] > total:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'versus'): the two sides need "
            f"{floors[0]:.2f}in and {floors[1]:.2f}in to set their own type but the "
            f"placement leaves {total:.2f}in for both — widen the placement, or "
            f"shorten the longest value or label"
        )
    widths = _plate_widths(sides, total, floors)

    groups: list[list[RevealItem]] = []

    lefts = (r.left, r.left + widths[0] + _MIDDLE)
    for side, x, half in zip(sides, lefts, widths, strict=True):
        role = "accent-1" if side.get("highlight") else "muted"
        fill_hex = ctx.theme.palette.role(role)
        plate = rrect(ctx.slide, x, r.top, half, r.height, ctx.color(role), radius=_RADIUS)
        ctx.manifest.record(plate)
        # The plate is its own surface: the type has to read on it, not on the slide.
        ink = ctx.rgb(ctx.ink_on(fill_hex))
        tf = textbox(
            ctx.slide, x + _INSET, r.top, half - 2 * _INSET, r.height, anchor=MSO_ANCHOR.MIDDLE
        )
        para(
            tf,
            str(side["value"]),
            stat.size * _VALUE_SCALE,
            ink,
            bold=True,
            align=PP_ALIGN.CENTER,
            first=True,
            space_after=2,
            font=ctx.theme.font_for(stat),
        )
        para(
            tf,
            str(side["label"]),
            body.size,
            ink,
            align=PP_ALIGN.CENTER,
            space_after=0,
            font=ctx.theme.face,
        )
        if side.get("note"):
            para(
                tf,
                str(side["note"]),
                caption.size,
                ink,
                align=PP_ALIGN.CENTER,
                space_after=0,
                font=ctx.theme.face,
            )
        recorded = [str(side["value"]), str(side["label"])]
        sizes = [stat.size * _VALUE_SCALE, body.size]
        if side.get("note"):
            recorded.append(str(side["note"]))
            sizes.append(caption.size)
        ctx.manifest.record(
            tf._parent,
            lines=recorded,
            font_pt=body.size,
            line_pt=sizes,
            fg=ctx.ink_on(fill_hex),
            bg=fill_hex,
        )
        groups.append([plate.shape_id, tf._parent.shape_id])

    mark = place_icon(
        ctx.slide,
        glyph,
        Rect(
            r.left + widths[0] + (_MIDDLE - _GLYPH_SIDE) / 2,
            r.top + (r.height - _GLYPH_SIDE) / 2,
            _GLYPH_SIDE,
            _GLYPH_SIDE,
        ),
        # The slide pair's ink, not the 'ink' role: the glyph sits on the background
        # between the plates, and on 'inverse' the role is near-invisible there.
        fill=ctx.pair.fg,
        theme=ctx.theme,
    )
    ctx.manifest.record(mark)
    # The glyph joins the first side's group: left outside every group it would be on
    # screen from the first beat, hanging between two plates that have not arrived.
    groups[0].append(mark.shape_id)
    return BodyResult(groups=groups, height=r.height)
