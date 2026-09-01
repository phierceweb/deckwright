"""A chip per palette role, labelled with the role and the hex it resolved to.

The values are read from the live theme, so a deck showing what `conform` derived from
a brand template cannot fall out of step with the theme it was built against.
"""

from __future__ import annotations

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, RevealItem, component
from deckwright.layouts.registry import SlideCtx
from deckwright.utils.color import contrast_ratio
from deckwright.utils.shapes import para, rrect, textbox
from deckwright.utils.text import LINE_HEIGHT, wrapped_lines

from deckwright.components._shape import known_fields
from deckwright.components._shared import body as body_line

_FIELDS = ("roles", "caption", "columns")
_MAX_COLUMNS = 8
# Fractions of canvas height: the chip, its two label lines, and the gap to a caption.
_CHIP_H_RUNG = 0.133
_LABEL_H_RUNG = 0.08
_CAPTION_GAP_RUNG = 0.02
# Drawn between a chip and its label; counted in the extent so the two agree.
_LABEL_GAP = 0.06
# Below this ratio against the slide's paper a chip needs an edge to exist at all.
_MIN_EDGE_RATIO = 1.2


@component("swatches")
def swatches(ctx: SlideCtx) -> BodyResult:
    """One chip per role, wrapped across the placement, with an optional caption."""
    known_fields(ctx, _FIELDS)
    roles = _roles(ctx)
    rect = ctx.body_rect
    columns = min(len(roles), _MAX_COLUMNS)
    gutter = ctx.grid.gutter
    chip_w = (rect.width - gutter * (columns - 1)) / columns
    chip_h = ctx.theme.scale.y(_CHIP_H_RUNG)
    label_h = ctx.theme.scale.y(_LABEL_H_RUNG)
    rows = -(-len(roles) // columns)
    extent = rows * (chip_h + _LABEL_GAP + label_h) + (rows - 1) * gutter

    caption = str(ctx.body.get("caption", ""))
    caption_w = ctx.grid.span_w(9)
    caption_h = _caption_h(ctx, caption, caption_w)
    if caption:
        # Must match the box drawn below, or the fit check passes and the draw overflows.
        extent += ctx.theme.scale.y(_CAPTION_GAP_RUNG) + caption_h
    if extent > rect.height:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'swatches'): {len(roles)} roles in "
            f"{columns} columns need {extent:.2f}in but the body rect is only "
            f"{rect.height:.2f}in — show fewer roles or split the slide"
        )

    groups: list[list[RevealItem]] = []
    for index, role in enumerate(roles):
        row, column = divmod(index, columns)
        left = rect.left + column * (chip_w + gutter)
        top = rect.top + row * (chip_h + label_h + gutter)
        hex_value = ctx.theme.palette.role(role)
        # A chip the colour of the paper is no chip at all — the roles most worth
        # showing (page, surface, an inverse ink) are exactly the ones that vanish.
        edge = (
            None if contrast_ratio(hex_value, ctx.pair.bg) >= _MIN_EDGE_RATIO else ctx.color("line")
        )
        chip = rrect(ctx.slide, left, top, chip_w, chip_h, ctx.color(role), line=edge, radius=0.12)
        ctx.manifest.record(chip, bg=hex_value)

        frame = textbox(ctx.slide, left, top + chip_h + _LABEL_GAP, chip_w, label_h)
        caption_style = ctx.style("caption")
        para(
            frame,
            role,
            caption_style.size,
            ctx.fg(),
            bold=True,
            first=True,
            space_after=1,
            font=ctx.theme.face,
        )
        para(frame, hex_value, caption_style.size, ctx.dim(), space_after=0, font=ctx.theme.mono)
        ctx.manifest.record(frame._parent, text=role)
        groups.append([chip.shape_id, frame._parent.shape_id])

    if caption:
        top = (
            rect.top
            + rows * (chip_h + _LABEL_GAP + label_h)
            + (rows - 1) * gutter
            + ctx.theme.scale.y(_CAPTION_GAP_RUNG)
        )
        note = textbox(ctx.slide, rect.left, top, caption_w, caption_h)
        body_line(ctx, note, caption, first=True)
        ctx.manifest.record(note._parent, text=caption)
        groups.append([note._parent.shape_id])
    return BodyResult(groups=groups, height=extent)


def _caption_h(ctx: SlideCtx, caption: str, width_in: float) -> float:
    """How deep the caption sets at *width_in*.

    Reserved and drawn from the same measure: a flat two label-lines both wasted the
    depth a one-line caption does not use and refused a placement that would have fit.
    """
    if not caption:
        return 0.0
    style = ctx.style("body")
    lines = wrapped_lines(caption, width_in=width_in, size_pt=style.size, face=ctx.theme.face)
    return lines * style.size * LINE_HEIGHT / 72


def _roles(ctx: SlideCtx) -> list[str]:
    """The roles named, or every role the palette declares."""
    declared = ctx.body.get("roles")
    if declared is None:
        return list(ctx.theme.palette.roles)
    if not isinstance(declared, list) or not declared:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'swatches'): 'roles' is a list of "
            f"palette role names; omit it to show every role the theme declares"
        )
    known = set(ctx.theme.palette.roles)
    unknown = [str(r) for r in declared if str(r) not in known]
    if unknown:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'swatches'): no palette role(s) "
            f"{', '.join(unknown)}; declared roles: {', '.join(sorted(known))}"
        )
    return [str(r) for r in declared]
