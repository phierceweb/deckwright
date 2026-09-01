"""Paint a slide's backdrop: its surface colour, its art, and the scrim over that.

A backdrop is painted as a *colour* first and only then embellished with an image, so a
theme that ships no art still renders its own ink legibly. The page is the exception: it
is painted unless :func:`deckwright.theme.surface.inherited_surface` says the template has
already laid down that exact colour — what a master carries is never assumable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from deckwright.errors import ThemeError
from deckwright.imagery.backdrop import Backdrop
from deckwright.imagery.draw import paint_scrim, place_picture
from deckwright.imagery.fit import ImageFit, fit_image
from deckwright.imagery.sample import aspect, cells
from deckwright.imagery.scrim import gradient_fraction, resolve
from deckwright.theme.media import resolve_media
from deckwright.theme.model import Rect
from deckwright.utils.color import AA_NORMAL
from deckwright.utils.shapes import rect as fill_rect

if TYPE_CHECKING:
    from deckwright.layouts.registry import SlideCtx

_BLANK = "FFFFFF"


def paint_backdrop(ctx: SlideCtx) -> None:
    """Paint the slide's surface and lay its art over it.

    Sets ``ctx.backdrop`` when art landed, so every line of text drawn afterwards can
    record the colour it is really on rather than the pair's nominal paper.
    """
    background = ctx.spec.background
    grid = ctx.grid
    canvas = Rect(0.0, 0.0, grid.slide_w, grid.slide_h)
    base = ctx.pair.bg
    if background.kind == "page":
        paint_inherited(ctx, canvas)
        return
    ctx.manifest.record(fill_rect(ctx.slide, 0, 0, grid.slide_w, grid.slide_h, ctx.rgb(base)))
    art = background.image or _mark_media(ctx, background.pair)
    if art is None:
        return
    where = f"slide {ctx.spec.index} background"
    if background.image:
        path = resolve_media(art, template=ctx.theme.template, roots=ctx.media_roots)
        fit = fit_image(
            source_aspect=aspect(path), box=canvas, fit=background.fit, crop=background.crop
        )
    else:
        # Brand art is drawn for this canvas, so it is stretched to it, never cropped.
        path = resolve_media(art, template=ctx.theme.template)
        fit = ImageFit(canvas)
    ctx.manifest.record(place_picture(ctx.slide, str(path), fit), rendered="picture")
    scrim = None
    if background.scrim is not None:
        scrim = resolve(
            background.scrim,
            palette=ctx.theme.palette,
            sampled=cells(path, fit.window, base=base),
            required=AA_NORMAL,
            fraction=gradient_fraction(background.scrim.gradient, band_top=0.0, band_bottom=1.0),
            where=where,
        )
        shape = paint_scrim(ctx.slide, canvas, scrim)
        if shape is not None:
            ctx.manifest.record(shape)
    ctx.backdrop = Backdrop(path, fit, base, scrim)


def paint_inherited(ctx: SlideCtx, canvas: Rect) -> None:
    """Reconcile the page pair with what the template already paints behind the slide.

    A picture is left where it is and sampled instead, so the template's own art
    survives and every line records the pixels it truly sits on.
    """
    page = ctx.pair.bg
    surface = ctx.theme.surface
    if surface is not None and surface.media is not None:
        path = resolve_media(surface.media, template=ctx.theme.template)
        ctx.backdrop = Backdrop(path, ImageFit(canvas), page)
        ctx.manifest.mark_backdrop()
        return
    # Declaring no background is itself a colour: every renderer shows white there.
    showing = _BLANK if surface is None else surface.flat
    if showing == page:
        return
    ctx.manifest.record(fill_rect(ctx.slide, 0, 0, canvas.width, canvas.height, ctx.rgb(page)))


def _mark_media(ctx: SlideCtx, name: str) -> str | None:
    """The image file a theme mark names, if the theme declares that mark."""
    mark = ctx.theme.marks.get(name)
    if mark is None:
        return None
    if not isinstance(mark, dict) or not mark.get("media"):
        raise ThemeError(f"theme mark {name!r} needs a 'media:' naming an image file")
    return str(mark["media"])
