"""Draw a slide: its backdrop, its chrome, then every placement."""

from __future__ import annotations

import dataclasses

from pf_core.exceptions import AppError, FlowException

from deckwright.errors import LayoutError
from deckwright.imagery.paint import paint_backdrop
from deckwright.layouts.components import RevealItem, as_body_result, get_component
from deckwright.layouts.chrome import CHROME_ORDER, ChromeBand, ChromeField, chrome_bands
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
from deckwright.utils.color import contrast_ratio, required_ratio
from deckwright.utils.shapes import ALIGN, ANCHOR, para, textbox


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
    area = content_rect(grid=ctx.grid, chrome=bands, reserved=ctx.theme.reserve)
    placed: list[Placed] = []
    for i, placement in enumerate(ctx.spec.place, start=1):
        where = f"slide {ctx.spec.index} placement {i} ({placement.component})"
        rect = resolve_at(placement.at, grid=ctx.grid, area=area, where=where)
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
        groups.extend(made)
    _write_chrome(ctx, bands)
    if any(p.reveals for p, _ in drawn):
        apply_click_reveals(ctx, drawn)
    else:
        apply_reveal(ctx, groups)
    apply_transition(ctx)


def _chrome(ctx: SlideCtx) -> tuple[ChromeBand, ...]:
    """Where every chrome line the slide carries goes. Nothing is drawn yet."""
    fields = _chrome_fields(ctx)
    lines, faces = {}, {}
    for name in CHROME_ORDER:
        text = getattr(ctx.spec, name)
        if text:
            style = ctx.style(fields[name].rung or name)
            lines[name] = (str(text), style.size)
            faces[name] = ctx.theme.font_for(style)
    if not lines:
        return ()
    return chrome_bands(lines, fields=fields, grid=ctx.grid, faces=faces, slide=ctx.spec.index)


def _write_chrome(ctx: SlideCtx, bands: tuple[ChromeBand, ...]) -> None:
    """Write the chrome lines.

    Stacked lines share one frame, a paragraph each, so a title wrapping wider than the
    build-time estimate pushes the subtitle down instead of drawing through it. A line
    placed with an ``at:`` gets its own frame, which is what lets it carry an anchor.
    """
    # Every colour is settled, and every plate painted, before the first frame exists:
    # a plate added later would be a shape drawn over the line it exists to carry.
    paint = {band.name: _chrome_paint(ctx, band) for band in bands}
    # One origin for the whole chrome, each line a part of it: stacked lines really do
    # share a frame, so a per-line origin would name the same shape three times.
    ctx.manifest.origin = f"s{ctx.spec.index}.chrome"
    for run in _runs([band for band in bands if band.stacked]):
        frame = _stack(run)
        tf = textbox(ctx.slide, frame.left, frame.top, frame.width, frame.height)
        for i, band in enumerate(run):
            _chrome_para(ctx, tf, band, paint[band.name], first=(i == 0), part=band.name)
    for band in bands:
        if band.stacked:
            continue
        rect = band.rect
        tf = textbox(
            ctx.slide,
            rect.left,
            rect.top,
            rect.width,
            rect.height,
            anchor=ANCHOR[band.field.anchoring],
        )
        _chrome_para(ctx, tf, band, paint[band.name], first=True, part=band.name)
    ctx.manifest.origin = None


def _chrome_fields(ctx: SlideCtx) -> dict[str, ChromeField]:
    """The treatment of each chrome field: the theme's, with the slide's keys over it."""
    return {
        name: (ctx.theme.chrome.get(name) or ChromeField()).merge(ctx.spec.chrome.get(name))
        for name in CHROME_ORDER
    }


def _chrome_paint(ctx: SlideCtx, band: ChromeBand) -> tuple[str, str]:
    """Settle one chrome line's ink and the colour it will sit on.

    A named pair lends its ink only: the paper stays whatever the slide actually painted,
    so borrowed ink cannot go invisible while the manifest claims paper never laid down.
    An unasked-for colour may move to suit where the line landed.
    """
    pair = ctx.theme.palette.pair(band.field.pair) if band.field.pair else ctx.pair
    ink = ctx.theme.palette.role(band.field.ink) if band.field.ink else pair.fg
    named = band.field.ink or band.field.pair
    # The threshold QA will hold this line to, so a subtitle small enough to need
    # 4.5:1 is not settled against a title's 3:1 and then warned about.
    need = required_ratio(band.size_pt)
    if named:
        paper = ctx.behind(band.rect, ink=ink)
        if contrast_ratio(ink, paper) < need:
            raise LayoutError(
                f"slide {ctx.spec.index}: chrome {band.name!r} is inked {ink} from "
                f"{named!r}, which reads at {contrast_ratio(ink, paper):.2f}:1 on the "
                f"{paper} this slide paints — below {need}:1. Choose a colour that "
                f"suits this background, or place a panel behind the line."
            )
        return ink, paper
    ink, paper = ctx.ink_at(band.rect, preferred=ink, required=need)
    if contrast_ratio(ink, paper) < need:
        return ctx.pair.fg, ctx.plate(band.rect)
    return ink, paper


def _chrome_para(
    ctx: SlideCtx,
    tf,
    band: ChromeBand,
    paint: tuple[str, str],
    *,
    first: bool,
    part: str | None = None,
) -> None:
    """Write one chrome line in the ink :func:`_chrome_paint` settled on."""
    ink, paper = paint
    style = ctx.style(band.field.rung or band.name)
    para(
        tf,
        band.text,
        style.size,
        ctx.rgb(ink),
        bold=style.bold,
        italic=style.italic,
        align=ALIGN[band.field.alignment],
        first=first,
        space_after=0,
        font=ctx.theme.font_for(style),
    )
    ctx.manifest.record(tf._parent, part=part, text=band.text, font_pt=style.size, fg=ink, bg=paper)


def _runs(bands: list[ChromeBand]) -> list[list[ChromeBand]]:
    """Consecutive stacked bands grouped by measure.

    Only lines of the same measure can share a frame, so a field narrowed to its own
    columns starts a new one.
    """
    runs: list[list[ChromeBand]] = []
    for band in bands:
        measure = (band.rect.left, band.rect.width)
        if runs and (runs[-1][0].rect.left, runs[-1][0].rect.width) == measure:
            runs[-1].append(band)
        else:
            runs.append([band])
    return runs


def _stack(bands: list[ChromeBand]) -> Rect:
    """The single rect the stacked chrome bands cover."""
    top = min(band.rect.top for band in bands)
    bottom = max(band.rect.bottom for band in bands)
    first = bands[0].rect
    return Rect(first.left, top, first.width, bottom - top)


def _origin(ctx: SlideCtx, placement: Placement, index: int) -> str:
    """What to name the shapes this placement draws.

    An ``id:`` fixes the name across edits; without one the index shifts when a
    placement is inserted above it, and every name below the insert moves with it.
    """
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
    ctx.manifest.bleeding = placement.bleed
    ctx.manifest.origin = origin
    ctx.manifest.record_placement(origin, placement.component, rect)
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
        ctx.manifest.origin = None
    # A bleed is a declared overrun; settling it would undo what the author asked for.
    if placement.anchor != "top" and not placement.bleed:
        _settle(
            ctx,
            rect,
            placement.anchor,
            [s for s in ctx.slide.shapes if s.shape_id not in before],
        )
    return [g for g in result.groups if g]
