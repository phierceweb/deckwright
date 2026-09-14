"""A photograph in a placement, optionally with text reversed out of it.

``over:`` lines are placed inside the picture's own rectangle and get a measured scrim by
default, solved against the pixels those lines actually cover.
"""

from __future__ import annotations

from deckwright.components._shape import figure_text, known_fields
from deckwright.components._shared import LINE_HEIGHT
from deckwright.errors import LayoutError
from deckwright.imagery.backdrop import Backdrop
from deckwright.imagery.draw import paint_scrim, place_picture
from deckwright.imagery.fit import FITS, MASKS, fit_image, parse_aspect, square
from deckwright.imagery.sample import aspect, cells, weakest
from deckwright.imagery.scrim import Scrim, gradient_fraction, resolve, scrim_spec
from deckwright.layouts.components import BodyResult, RevealItem, component
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.media import resolve_media
from deckwright.theme.model import Rect
from deckwright.utils.a11y import describe
from deckwright.utils.color import required_ratio
from deckwright.utils.shapes import ALIGN, ANCHOR, para, textbox
from deckwright.utils.text import wrapped_lines

_FIELDS = ("src", "alt", "decorative", "fit", "crop", "mask", "radius", "inset", "scrim", "over")
_OVER_KEYS = ("text", "rung", "align")
_MAX_RADIUS = 0.5
_INSET_DEFAULT = 0.025  # fraction of canvas width between the picture and its text
_OVER_RUNG_DEFAULT = "title"
_OVER_PAIR_DEFAULT = "inverse"


@component("image")
def image(ctx: SlideCtx) -> BodyResult:
    """Fit a source into the placement, mask it, scrim it, and write any text on it."""
    known_fields(ctx, _FIELDS)
    alt, decorative = figure_text(ctx)
    src = ctx.body.get("src")
    if not src:
        raise LayoutError(f"{_where(ctx)}: 'src' must name an image file")
    path = resolve_media(str(src), template=ctx.theme.template, roots=ctx.media_roots)
    mask = _choice(ctx, "mask", MASKS, "none")
    how = _choice(ctx, "fit", FITS, "cover")
    if mask == "circle" and how == "contain":
        raise LayoutError(
            f"{_where(ctx)}: a circle mask needs 'fit: cover'. 'contain' letterboxes "
            f"the picture down to the source's own aspect, and the mask drawn on that "
            f"oblong is an oval, not a circle — crop it with 'crop: 1:1' instead"
        )
    box = (
        square(ctx.body_rect, align=ctx.align, anchor=ctx.anchor)
        if mask == "circle"
        else ctx.body_rect
    )
    fit = fit_image(
        source_aspect=aspect(path),
        box=box,
        fit=how,
        crop=_crop(ctx),
        align=ctx.align,
        anchor=ctx.anchor,
    )
    picture = place_picture(ctx.slide, str(path), fit, mask=mask, radius=_radius(ctx))
    describe(picture, alt=alt, decorative=decorative)
    ctx.manifest.record(picture, rendered="picture")
    shapes: list[RevealItem] = [(picture.shape_id, "figure")]
    lines = _over(ctx)
    scrim = _scrim(ctx, path=path, fit=fit, lines=lines)
    # With its scrim, so chrome laid over the picture measures what it really shows.
    ctx.painted.append((fit.dest, Backdrop(path, fit, ctx.pair.bg, scrim)))
    if scrim is not None:
        painted = paint_scrim(ctx.slide, fit.dest, scrim)
        if painted is not None:
            shapes.append((painted.shape_id, "surface"))
            ctx.manifest.record(painted)
    if lines:
        shapes.append((_write(ctx, path=path, fit=fit, lines=lines, scrim=scrim).shape_id, "text"))
    return BodyResult(groups=[shapes], height=fit.dest.height)


def _where(ctx: SlideCtx) -> str:
    return f"slide {ctx.spec.index} (component 'image')"


def _choice(ctx: SlideCtx, key: str, options: tuple[str, ...], default: str) -> str:
    value = str(ctx.body.get(key, default))
    if value not in options:
        raise LayoutError(
            f"{_where(ctx)}: {key} must be one of {', '.join(options)}, got {value!r}"
        )
    return value


def _crop(ctx: SlideCtx) -> float | None:
    raw = ctx.body.get("crop")
    return None if raw is None else parse_aspect(raw, where=_where(ctx))


def _number(ctx: SlideCtx, key: str, default: float) -> float:
    raw = ctx.body.get(key, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise LayoutError(f"{_where(ctx)}: {key!r} must be a number, got {raw!r}") from None


def _radius(ctx: SlideCtx) -> float:
    value = _number(ctx, "radius", 0.08)
    if not 0.0 <= value <= _MAX_RADIUS:
        raise LayoutError(
            f"{_where(ctx)}: 'radius' is a fraction of the picture's short side, "
            f"0..{_MAX_RADIUS} ({_MAX_RADIUS} is a circle); got {value}"
        )
    return value


def _over(ctx: SlideCtx) -> tuple[tuple[str, str, str], ...]:
    """The lines to reverse out of the picture, as ``(text, rung, align)`` triples."""
    raw = ctx.body.get("over")
    if raw is None:
        return ()
    if not isinstance(raw, list) or not raw:
        raise LayoutError(
            f"{_where(ctx)}: 'over' must be a non-empty list of lines, "
            f"each a mapping of {', '.join(_OVER_KEYS)}"
        )
    out = []
    for entry in raw:
        if isinstance(entry, str):
            entry = {"text": entry}
        if not isinstance(entry, dict) or not entry.get("text"):
            raise LayoutError(f"{_where(ctx)}: every 'over' line needs a 'text', got {entry!r}")
        unknown = sorted(set(entry) - set(_OVER_KEYS))
        if unknown:
            raise LayoutError(
                f"{_where(ctx)}: an 'over' line has no key "
                f"{unknown[0]!r}; known keys: {', '.join(_OVER_KEYS)}"
            )
        align = str(entry.get("align", ctx.align))
        if align not in ALIGN:
            raise LayoutError(
                f"{_where(ctx)}: an 'over' line's align must be one of "
                f"{', '.join(ALIGN)}, got {align!r}"
            )
        out.append((str(entry["text"]), str(entry.get("rung", _OVER_RUNG_DEFAULT)), align))
    return tuple(out)


def _text_rect(ctx: SlideCtx, fit, lines: tuple[tuple[str, str, str], ...]) -> Rect:
    """Where the ``over`` lines go: inset inside the picture, stacked to the anchor."""
    inset = ctx.theme.scale.x(_number(ctx, "inset", _INSET_DEFAULT))
    dest = fit.dest
    width = dest.width - 2 * inset
    if width <= 0:
        raise LayoutError(
            f"{_where(ctx)}: an inset of {_number(ctx, 'inset', _INSET_DEFAULT)} leaves "
            f"the text no width inside a picture {dest.width:.2f}in wide"
        )
    height = sum(_line_height(ctx, text, rung, width) for text, rung, _ in lines)
    room = max(0.0, dest.height - 2 * inset - height)
    top = dest.top + inset + room * {"top": 0.0, "middle": 0.5, "bottom": 1.0}[ctx.anchor]
    return Rect(dest.left + inset, top, width, height)


def _line_height(ctx: SlideCtx, text: str, rung: str, width: float) -> float:
    style = ctx.style(rung)
    return (
        wrapped_lines(text, width_in=width, size_pt=style.size, face=ctx.theme.font_for(style))
        * style.size
        * LINE_HEIGHT
        / 72
    )


def _scrim(ctx: SlideCtx, *, path, fit, lines) -> Scrim | None:
    """The scrim to lay over the picture, solved against what it has to cover.

    With ``over`` text the solve is against that text's own band, not the whole picture.
    """
    declared = ctx.body.get("scrim", True if lines else None)
    if declared is None or declared is False:
        return None
    spec = scrim_spec(declared, default_pair=_OVER_PAIR_DEFAULT, where=_where(ctx))
    band = _text_rect(ctx, fit, lines) if lines else fit.dest
    window = fit.window_under(band) or fit.window
    smallest = min((ctx.style(rung).size for _, rung, _ in lines), default=0.0)
    return resolve(
        spec,
        palette=ctx.theme.palette,
        sampled=cells(path, window, base=ctx.pair.bg),
        required=required_ratio(smallest),
        fraction=_fraction(spec.gradient, fit, band),
        where=_where(ctx),
    )


def _fraction(gradient: str, fit, band: Rect) -> float:
    dest = fit.dest
    return gradient_fraction(
        gradient,
        band_top=(band.top - dest.top) / dest.height,
        band_bottom=(band.bottom - dest.top) / dest.height,
    )


def _write(ctx: SlideCtx, *, path, fit, lines, scrim: Scrim | None):
    """Write the ``over`` lines, recording the colour each is measurably sitting on."""
    rect = _text_rect(ctx, fit, lines)
    ink = scrim.ink if scrim is not None else ctx.pair.fg
    window = fit.window_under(rect)
    bg = ctx.pair.bg
    if window is not None:
        sampled = cells(path, window, base=ctx.pair.bg)
        bg = (
            scrim.bg_over(sampled, fraction=_fraction(scrim.gradient, fit, rect))
            if scrim is not None
            else weakest(sampled, ink=ink)
        )
    tf = textbox(ctx.slide, rect.left, rect.top, rect.width, rect.height, anchor=ANCHOR[ctx.anchor])
    for i, (text, rung, align) in enumerate(lines):
        style = ctx.style(rung)
        para(
            tf,
            text,
            style.size,
            ctx.rgb(ink),
            bold=style.bold,
            italic=style.italic,
            align=ALIGN[align],
            first=(i == 0),
            space_after=0,
            font=ctx.theme.font_for(style),
        )
        ctx.manifest.record(tf._parent, text=text, font_pt=style.size, fg=ink, bg=bg)
    return tf._parent
