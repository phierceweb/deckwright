"""Fit a source image to a box: which part of it shows, and where it lands.

A trim is expressed as the four fractions OOXML's ``a:srcRect`` wants, so a picture is
never distorted to fit — it is cropped or it is inset.
"""

from __future__ import annotations

from dataclasses import dataclass

from deckwright.errors import LayoutError
from deckwright.theme.model import Rect

FITS = ("cover", "contain")
MASKS = ("none", "circle", "rounded")

_ALIGN_U = {"left": 0.0, "center": 0.5, "right": 1.0}
_ANCHOR_V = {"top": 0.0, "middle": 0.5, "bottom": 1.0}


@dataclass(frozen=True)
class ImageFit:
    """Where a source lands on the canvas, and the window of it that shows.

    ``trim`` is ``(left, top, right, bottom)`` fractions of the *original* source cut
    off each edge; ``dest`` is inches.
    """

    dest: Rect
    trim: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    @property
    def window(self) -> tuple[float, float, float, float]:
        """The visible part of the source, as ``(x0, y0, x1, y1)`` source fractions."""
        left, top, right, bottom = self.trim
        return (left, top, 1.0 - right, 1.0 - bottom)

    def window_under(self, rect: Rect) -> tuple[float, float, float, float] | None:
        """The source fractions showing behind ``rect``, or None if it misses the picture.

        A ``contain`` fit leaves letterbox bands inside the placement, so a caller
        asking what is behind text there gets None rather than a lie about the photo.
        """
        x0 = max(rect.left, self.dest.left)
        x1 = min(rect.right, self.dest.right)
        y0 = max(rect.top, self.dest.top)
        y1 = min(rect.bottom, self.dest.bottom)
        if x1 <= x0 or y1 <= y0:
            return None
        sx0, sy0, sx1, sy1 = self.window
        u0 = (x0 - self.dest.left) / self.dest.width
        u1 = (x1 - self.dest.left) / self.dest.width
        v0 = (y0 - self.dest.top) / self.dest.height
        v1 = (y1 - self.dest.top) / self.dest.height
        return (
            sx0 + u0 * (sx1 - sx0),
            sy0 + v0 * (sy1 - sy0),
            sx0 + u1 * (sx1 - sx0),
            sy0 + v1 * (sy1 - sy0),
        )


def parse_aspect(value: object, *, where: str) -> float:
    """Read an aspect as ``"16:9"``, ``"16/9"`` or a bare number. Returns width ÷ height."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        ratio = float(value)
    else:
        text = str(value).strip()
        for separator in (":", "/", "x"):
            if separator in text:
                head, _, tail = text.partition(separator)
                try:
                    ratio = float(head) / float(tail)
                except (TypeError, ValueError, ZeroDivisionError):
                    raise LayoutError(
                        f"{where}: {value!r} is not an aspect — write it as '16:9' or 1.78"
                    ) from None
                break
        else:
            try:
                ratio = float(text)
            except ValueError:
                raise LayoutError(
                    f"{where}: {value!r} is not an aspect — write it as '16:9' or 1.78"
                ) from None
    if ratio <= 0:
        raise LayoutError(f"{where}: an aspect must be positive, got {value!r}")
    return ratio


def fit_image(
    *,
    source_aspect: float,
    box: Rect,
    fit: str = "cover",
    crop: float | None = None,
    align: str = "center",
    anchor: str = "middle",
) -> ImageFit:
    """Fit a source of ``source_aspect`` into ``box``.

    ``crop`` trims the source to that aspect first, centred, so a portrait shot can
    be told to read as a 16:9 band before the box gets a say. ``align``/``anchor``
    only matter for ``contain``, where the fitted picture is smaller than the box.
    """
    if fit not in FITS:
        raise LayoutError(f"unknown fit {fit!r}; expected one of {', '.join(FITS)}")
    if source_aspect <= 0:
        raise LayoutError(f"source image aspect must be positive, got {source_aspect}")
    trim = (0.0, 0.0, 0.0, 0.0)
    aspect = source_aspect
    if crop is not None:
        trim = _centre_trim(aspect, crop)
        aspect = crop
    if fit == "cover":
        return ImageFit(box, _compose(trim, _centre_trim(aspect, box.width / box.height)))
    return ImageFit(_inset(box, aspect, align=align, anchor=anchor), trim)


def square(box: Rect, *, align: str = "center", anchor: str = "middle") -> Rect:
    """The largest square inside ``box``, placed by ``align``/``anchor``.

    A ``circle`` mask on an oblong box draws an ellipse; squaring the box first is
    what makes the mask actually round.
    """
    side = min(box.width, box.height)
    return Rect(
        box.left + (box.width - side) * _u(align),
        box.top + (box.height - side) * _v(anchor),
        side,
        side,
    )


def _u(align: str) -> float:
    try:
        return _ALIGN_U[align]
    except KeyError:
        raise LayoutError(
            f"unknown align {align!r}; expected one of {', '.join(_ALIGN_U)}"
        ) from None


def _v(anchor: str) -> float:
    try:
        return _ANCHOR_V[anchor]
    except KeyError:
        raise LayoutError(
            f"unknown anchor {anchor!r}; expected one of {', '.join(_ANCHOR_V)}"
        ) from None


def _inset(box: Rect, aspect: float, *, align: str, anchor: str) -> Rect:
    width, height = box.width, box.width / aspect
    if height > box.height:
        width, height = box.height * aspect, box.height
    return Rect(
        box.left + (box.width - width) * _u(align),
        box.top + (box.height - height) * _v(anchor),
        width,
        height,
    )


def _centre_trim(aspect: float, target: float) -> tuple[float, float, float, float]:
    """Fractions to cut off each edge of a window of ``aspect`` to leave ``target``."""
    if abs(aspect - target) < 1e-9:
        return (0.0, 0.0, 0.0, 0.0)
    if aspect > target:
        cut = (1.0 - target / aspect) / 2
        return (cut, 0.0, cut, 0.0)
    cut = (1.0 - aspect / target) / 2
    return (0.0, cut, 0.0, cut)


def _compose(
    outer: tuple[float, float, float, float], inner: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    """Stack a trim taken of an already-trimmed window back onto source fractions."""
    left, top, right, bottom = outer
    width, height = 1.0 - left - right, 1.0 - top - bottom
    return (
        left + inner[0] * width,
        top + inner[1] * height,
        right + inner[2] * width,
        bottom + inner[3] * height,
    )
