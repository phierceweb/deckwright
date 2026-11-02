"""Write a slide's chrome lines: the ink each reads in, any plate it needs, and its frame."""

from __future__ import annotations

from collections.abc import Mapping

from deckwright.errors import LayoutError
from deckwright.layouts.chrome import ChromeBand
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.model import Rect
from deckwright.utils.color import contrast_ratio, required_ratio
from deckwright.utils.shapes import ALIGN, ANCHOR, para, textbox
from deckwright.utils.text import LINE_HEIGHT, text_em, wrapped_lines


def write_chrome(ctx: SlideCtx, bands: tuple[ChromeBand, ...]) -> dict[str, int]:
    """Write the chrome lines; return the shape id of each line in a frame of its own.

    Stacked lines share one frame, a paragraph each, so a title wrapping wider than the
    build-time estimate pushes the subtitle down instead of drawing through it. A line
    placed with an ``at:`` gets its own frame, which is what lets it carry an anchor.
    """
    # One origin for the whole chrome, each line a part of it: stacked lines really do
    # share a frame, so a per-line origin would name the same shape three times.
    ctx.manifest.origin = f"s{ctx.spec.index}.chrome"
    # Every colour is settled, and every plate painted, before the first frame exists:
    # a plate added later would be a shape drawn over the line it exists to carry.
    faces = {
        band.name: ctx.theme.font_for(ctx.style(band.field.rung or band.name)) for band in bands
    }
    reach = reaches(bands, faces)
    paint = {band.name: _chrome_paint(ctx, band, reach[band.name]) for band in bands}
    for run in _runs([band for band in bands if band.stacked]):
        frame = _stack(run)
        tf = textbox(ctx.slide, frame.left, frame.top, frame.width, frame.height)
        for i, band in enumerate(run):
            _chrome_para(ctx, tf, band, paint[band.name], first=(i == 0), part=band.name)
    framed: dict[str, int] = {}
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
        framed[band.name] = tf._parent.shape_id
    ctx.manifest.origin = None
    return framed


def reaches(bands: tuple[ChromeBand, ...], faces: Mapping[str, str | None]) -> dict[str, Rect]:
    """Where each chrome line's words can land: what its ink is tried against, its plate
    covers, and `qa`'s `chrome-overlap` measures.

    A band is the line's full measure at the depth the wrap estimate gave it. A line that
    does not wrap covers only its own width; a stacked line rises by however much the lines
    above it in the frame can come out shorter than estimated; a line in a box of its own
    sits at the box's anchor, as deep as its words.
    """
    out: dict[str, Rect] = {}
    for run in _runs([band for band in bands if band.stacked]):
        rise = 0.0
        for band in run:
            out[band.name] = _reach(band, faces.get(band.name), rise=rise)
            rise += band.rect.height - band.size_pt * LINE_HEIGHT / 72
    for band in bands:
        if not band.stacked:
            out[band.name] = _reach(band, faces.get(band.name), rise=0.0)
    return out


def _reach(band: ChromeBand, face: str | None, *, rise: float) -> Rect:
    rect = band.rect
    lines = wrapped_lines(band.text, width_in=rect.width, size_pt=band.size_pt, face=face)
    top, height = rect.top - rise, rect.height + rise
    if not band.stacked:
        height = min(rect.height, lines * band.size_pt * LINE_HEIGHT / 72)
        top = {
            "top": rect.top,
            "middle": rect.top + (rect.height - height) / 2,
            "bottom": rect.bottom - height,
        }[band.field.anchoring]
    if lines > 1:
        return Rect(rect.left, top, rect.width, height)
    width = min(rect.width, text_em(band.text, face) * band.size_pt / 72)
    left = {
        "left": rect.left,
        "center": rect.left + (rect.width - width) / 2,
        "right": rect.right - width,
    }[band.field.alignment]
    return Rect(left, top, width, height)


def _chrome_paint(ctx: SlideCtx, band: ChromeBand, reach: Rect) -> tuple[str, str]:
    """Settle one chrome line's ink and the colour it will sit on, across ``reach``.

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
        paper = ctx.behind(reach, ink=ink)
        if contrast_ratio(ink, paper) < need:
            raise LayoutError(
                f"slide {ctx.spec.index}: chrome {band.name!r} is inked {ink} from "
                f"{named!r}, which reads at {contrast_ratio(ink, paper):.2f}:1 on the "
                f"{paper} this slide paints — below {need}:1. Choose a colour that "
                f"suits this background, or place a panel behind the line."
            )
        return ink, paper
    ink, paper = ctx.ink_at(reach, preferred=ink, required=need)
    if contrast_ratio(ink, paper) < need:
        return ctx.pair.fg, ctx.plate(reach, part=f"{band.name}.plate")
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
