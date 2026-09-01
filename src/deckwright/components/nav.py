"""The deck's sections across a band, with the one you are in marked.

The active item is larger and bolder as well as coloured, so colour is never the only
thing carrying it.
"""

from __future__ import annotations

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, component
from deckwright.layouts.registry import SlideCtx
from deckwright.utils.color import contrast_ratio
from deckwright.utils.shapes import para, textbox

from deckwright.components._shape import known_fields

_FIELDS = ("items", "active", "color")

# The active label against the rest: emphasis at caption size without disturbing the row.
_ACTIVE_SCALE = 1.18
# Below this against the slide's own paper a label is not there at all — the floor
# `_shape.stroke` holds an author-named line to.
_MIN_VISIBLE_RATIO = 1.2


def _where(ctx: SlideCtx) -> str:
    return f"slide {ctx.spec.index} (component 'nav')"


def _active_ink(ctx: SlideCtx, size_pt: float) -> str:
    """The active label's colour, as hex.

    Same policy as :func:`deckwright.components._shape.stroke`: a named role is used as asked
    and refused only when invisible; the default gives way to the slide's own ink when the
    accent does not read at this size.
    """
    named = ctx.body.get("color")
    if named is None:
        return ctx.accent(size_pt=size_pt)
    colour = ctx.theme.palette.role(str(named))
    ratio = contrast_ratio(colour, ctx.pair.bg)
    if ratio < _MIN_VISIBLE_RATIO:
        raise LayoutError(
            f"{_where(ctx)}: color {named!r} is {colour} against this slide's "
            f"{ctx.pair.bg}, {ratio:.2f}:1 — a label that close to the paper cannot be "
            f"seen; name a role that stands off it"
        )
    return colour


@component("nav")
def nav(ctx: SlideCtx) -> BodyResult:
    """Section names spread evenly across the placement; the active one marked.

    Returns no reveal group: an eyebrow is chrome, and a slide that builds its body
    should not spend a click arriving at its own furniture.
    """
    known_fields(ctx, _FIELDS)
    raw = ctx.body.get("items")
    if not isinstance(raw, list) or not raw:
        raise LayoutError(f"{_where(ctx)}: 'items' must be a non-empty list of section names")
    items = [str(item) for item in raw]
    active = str(ctx.body.get("active", ""))
    if active and active not in items:
        raise LayoutError(
            f"{_where(ctx)}: active {active!r} is not one of the items ({', '.join(items)})"
        )

    style = ctx.style("caption")
    r = ctx.body_rect
    slot = r.width / len(items)

    for index, label in enumerate(items):
        on = label == active
        size = style.size * _ACTIVE_SCALE if on else style.size
        ink = _active_ink(ctx, size) if on else str(ctx.dim())
        tf = textbox(
            ctx.slide, r.left + index * slot, r.top, slot, r.height, anchor=ctx.text_anchor()
        )
        para(
            tf,
            label,
            size,
            ctx.rgb(ink),
            bold=on,
            first=True,
            space_after=0,
            align=ctx.text_align(),
            font=ctx.theme.face,
        )
        ctx.manifest.record(tf._parent, lines=[label], font_pt=size, fg=ink, bg=ctx.pair.bg)
    return BodyResult(groups=[], height=r.height)
