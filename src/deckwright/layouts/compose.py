"""Draw a slide: its backdrop, its chrome, then every placement."""

from __future__ import annotations

import dataclasses

from pw_foundation.exceptions import AppError, FlowException

from deckwright.imagery.paint import paint_backdrop
from deckwright.errors import LayoutError
from deckwright.layouts.components import RevealItem, as_body_result, get_component
from deckwright.layouts.chrome import (
    CHROME_ORDER,
    ChromeBand,
    ChromeField,
    chrome_bands,
    statement_fields,
)
from deckwright.layouts.chrome_ink import write_chrome
from deckwright.layouts.place import (
    Placed,
    check_placements,
    clear_reserved,
    content_rect,
    resolve_at,
)
from deckwright.layouts.registry import SlideCtx
from deckwright.spec.model import Placement
from deckwright.theme.model import Rect
from deckwright.layouts.motion import apply_click_reveals, apply_reveal, apply_transition


def render_slide(ctx: SlideCtx) -> None:
    """Paint the backdrop, draw every placement, write the chrome, apply the reveal.

    The chrome is *placed* first, because the content band starts below the stacked
    lines, but *drawn* last: a title told to sit on a painted panel has to land on
    top of it.
    """
    ctx.manifest.origin = f"s{ctx.spec.index}.bg"
    paint_backdrop(ctx)
    ctx.manifest.origin = None
    bands = _chrome(ctx)
    if ctx.spec.chrome_preset == "side":
        # The chrome is a rail, not a header: the body takes the columns beside it.
        area = content_rect(grid=ctx.grid, reserved=ctx.theme.reserve)
        # Two gutters: one reads as the rail's own edge, not a gap between columns.
        start = _rail(ctx).right + 2 * ctx.grid.gutter
        area = Rect(start, area.top, area.right - start, area.height)
    else:
        area = content_rect(grid=ctx.grid, chrome=bands, reserved=ctx.theme.reserve)
    placed: list[Placed] = []
    for i, placement in enumerate(ctx.spec.place, start=1):
        where = f"slide {ctx.spec.index} placement {i} ({placement.component})"
        rect = resolve_at(placement.at, grid=ctx.grid, area=area, where=where)
        if ctx.spec.chrome_preset == "side" and placement.at and "box" not in placement.at:
            rect = _beside(rect, grid=ctx.grid, area=area)
        # A box: is exact geometry the author wrote, so it is never narrowed — it
        # meets the reserved regions in check_placements instead.
        if "box" not in placement.at and not placement.bleed:
            rect = clear_reserved(rect, reserved=ctx.theme.reserve, grid=ctx.grid, where=where)
        placed.append(Placed(where, rect, bleed=placement.bleed, exact="box" in placement.at))
        if placement.id is not None:
            ctx.placements[placement.id] = rect
    check_placements(placed, area=area, grid=ctx.grid, reserved=ctx.theme.reserve)
    groups: list[list[RevealItem]] = []
    drawn: list[tuple[Placement, list[list[RevealItem]]]] = []
    for i, (placement, item) in enumerate(zip(ctx.spec.place, placed, strict=True), start=1):
        made = _draw(ctx, placement, item.rect, origin=_origin(ctx, placement, i))
        drawn.append((placement, made))
        if not placement.still:
            groups.extend(made)
    framed = write_chrome(ctx, bands)
    last: list[list[RevealItem]] = [
        [(framed[band.name], "text")] for band in bands if band.field.build == "last"
    ]
    if any(p.reveals for p, _ in drawn):
        if last:
            raise LayoutError(
                f"slide {ctx.spec.index}: a chrome line that builds and a 'reveals:' trigger "
                f"would share the slide's one animation timeline — drop one"
            )
        apply_click_reveals(ctx, drawn)
    else:
        apply_reveal(ctx, groups, last)
    apply_transition(ctx)


def _chrome(ctx: SlideCtx) -> tuple[ChromeBand, ...]:
    """Where every chrome line the slide carries goes. Nothing is drawn yet."""
    fields = _chrome_fields(ctx)
    rail = None
    if ctx.spec.chrome_preset == "statement":
        fields = {name: fields[name].merge(f) for name, f in statement_fields().items()}
    elif ctx.spec.chrome_preset == "side":
        # The rail takes the whole stack: a theme's own placing of a line gives way to it.
        fields = {
            name: dataclasses.replace(f, at=None, auto_height=False, anchor=None)
            for name, f in fields.items()
        }
        rail = _rail(ctx)
    lines, faces = {}, {}
    for name in CHROME_ORDER:
        text = getattr(ctx.spec, name)
        if text:
            style = ctx.style(fields[name].rung or name)
            lines[name] = (str(text), style.size)
            faces[name] = ctx.theme.font_for(style)
    if not lines:
        return ()
    bands = chrome_bands(
        lines,
        fields=fields,
        grid=ctx.grid,
        faces=faces,
        slide=ctx.spec.index,
        rail=rail,
        preset=ctx.spec.chrome_preset,
    )
    if rail is not None and max(band.rect.bottom for band in bands) > rail.bottom:
        raise LayoutError(
            f"slide {ctx.spec.index}: 'chrome: side' stacks its lines in the left third, and "
            f"they reach {max(b.rect.bottom for b in bands):.2f}in, past the "
            f"{rail.bottom:.2f}in bottom margin — shorten them, or move the chrome yourself"
        )
    return bands


def _beside(rect: Rect, *, grid, area: Rect) -> Rect:
    """``rect``'s columns, read as fractions of the band beside a side rail rather than of
    the whole content width: ``cols: full`` is the rest of the slide."""
    scale = area.width / grid.content_w
    return Rect(
        area.left + (rect.left - grid.left) * scale, rect.top, rect.width * scale, rect.height
    )


def _rail(ctx: SlideCtx) -> Rect:
    """``chrome: side``'s column: the left third, from where the body starts to the bottom."""
    grid = ctx.grid
    band = Rect(
        grid.left, grid.body_top, grid.content_w, grid.slide_h - grid.bottom - grid.body_top
    )
    return resolve_at({"cols": "left-third"}, grid=grid, area=band, where="chrome: side")


def _chrome_fields(ctx: SlideCtx) -> dict[str, ChromeField]:
    """The treatment of each chrome field: the theme's, with the slide's keys over it."""
    return {
        name: (ctx.theme.chrome.get(name) or ChromeField()).merge(ctx.spec.chrome.get(name))
        for name in CHROME_ORDER
    }


def _origin(ctx: SlideCtx, placement: Placement, index: int) -> str:
    """What to name the shapes this placement draws.

    An ``id:`` fixes the name across edits; without one the index shifts when a
    placement is inserted above it, and every name below the insert moves with it.
    """
    if placement.morph:
        # No slide number: PowerPoint pairs a shape with its namesake on the next slide.
        return f"m.{placement.morph}.{placement.component}"
    return f"s{ctx.spec.index}.{placement.id or f'p{index}'}.{placement.component}"


_EMU_PER_INCH = 914400


def _settle(ctx: SlideCtx, rect: Rect, anchor: str, drawn: list) -> None:
    """Move what a placement drew so its extent sits where ``anchor`` says inside ``rect``.

    Measured off the shapes rather than off ``BodyResult.height``: a component that already
    positions itself then measures as correct and is left alone.
    """
    tops = [s.top for s in drawn]
    bottoms = [s.top + s.height for s in drawn]
    if not tops:
        return
    top, extent = min(tops), max(bottoms) - min(tops)
    slack = int(rect.height * _EMU_PER_INCH) - extent
    if slack <= 0:
        return
    share = {"top": 0, "middle": slack // 2, "bottom": slack}[anchor]
    target = int(rect.top * _EMU_PER_INCH) + share
    shift = target - top
    if not shift:
        return
    ids = {int(s.shape_id) for s in drawn}
    for shape in drawn:
        shape.top += shift
    inches = round(shift / _EMU_PER_INCH, 3)
    for rec in ctx.manifest.slides[-1].shapes:
        if rec.shape_id in ids:
            # `replace` rather than the class: the recorder owns Box, and this layer
            # may not import upward to name it.
            rec.box = dataclasses.replace(rec.box, y=round(rec.box.y + inches, 3))


def _draw(
    ctx: SlideCtx, placement: Placement, rect: Rect, *, origin: str
) -> list[list[RevealItem]]:
    ctx.component = placement.component
    ctx.body = placement.body
    ctx.rect = rect
    ctx.align = placement.align
    ctx.anchor = placement.anchor
    ctx.still = placement.still
    ctx.manifest.bleeding = placement.bleed
    ctx.manifest.goto = placement.goto
    ctx.manifest.origin = origin
    ctx.manifest.record_placement(origin, placement.component, rect, bleed=placement.bleed)
    # Shape ids, not object ids: lxml frees element proxies and hands their addresses
    # to later shapes, so an identity test reads old shapes as new.
    before = {s.shape_id for s in ctx.slide.shapes}
    try:
        result = as_body_result(get_component(placement.component)(ctx))
    except (FlowException, AppError):
        raise
    except Exception as e:
        # A bug, not a refusal: keep the traceback, and say where the deck hit it.
        e.add_note(
            f"slide {ctx.spec.index} (component {placement.component!r}): raised by the component's own code, not refused by it"
        )
        raise
    finally:
        ctx.manifest.bleeding = False
        ctx.manifest.goto = None
        ctx.manifest.origin = None
    drawn = [s for s in ctx.slide.shapes if s.shape_id not in before]
    # A bleed is a declared overrun; settling it would undo what the author asked for.
    if placement.anchor != "top" and not placement.bleed:
        _settle(ctx, rect, placement.anchor, drawn)
    if placement.goto is not None:
        ctx.gotos.extend((shape, placement.goto) for shape in drawn)
    return [g for g in result.groups if g]
