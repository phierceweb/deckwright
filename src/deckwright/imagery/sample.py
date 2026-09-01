"""Read an image's actual pixels, and solve the scrim that makes text on them legible.

The alpha chosen is the smallest at which the *weakest* sampled cell clears WCAG AA, so
the ratio recorded in the build manifest is a measurement, not an intention.
"""

from __future__ import annotations

from typing import cast

from functools import lru_cache
from pathlib import Path

from PIL import Image

from deckwright.errors import LayoutError
from deckwright.utils.color import contrast_ratio, normalize_hex

Cell = tuple[int, int, int]

# Long-edge cell count for the averaged window — roughly glyph-stroke scale: finer and
# one antialiased pixel decides the scrim, coarser and a small highlight averages away.
CELLS = 64
# Fraction of cells allowed to be worse than the solved ratio. Zero would let one
# stray specular pixel black out a whole slide.
TOLERANCE = 0.02
_ALPHA_STEP = 0.05


@lru_cache(maxsize=32)
def _source(path: str, stamp: tuple[int, float]) -> Image.Image:
    """The decoded image, cached on path plus size and mtime so an edit invalidates it."""
    del stamp
    try:
        return Image.open(path).convert("RGBA")
    except (OSError, ValueError) as e:
        raise LayoutError(f"cannot read image {path}: {e}") from e


def load(path: str | Path) -> Image.Image:
    """Decode an image, reusing the decode across the slides that share it."""
    p = Path(path)
    try:
        stat = p.stat()
    except OSError as e:
        raise LayoutError(f"cannot read image {p}: {e}") from e
    return _source(str(p), (stat.st_size, stat.st_mtime))


def aspect(path: str | Path) -> float:
    """Width ÷ height of the source, in pixels."""
    image = load(path)
    return image.width / image.height


def cells(
    path: str | Path, window: tuple[float, float, float, float], *, base: str
) -> tuple[Cell, ...]:
    """Average the source's ``window`` down to a grid of opaque colours.

    ``window`` is ``(x0, y0, x1, y1)`` in source fractions. Transparent pixels are
    composited onto ``base`` first, because that is what the renderer will show
    through them.
    """
    image = load(path)
    x0, y0, x1, y1 = window
    left = max(0, min(image.width - 1, int(round(x0 * image.width))))
    top = max(0, min(image.height - 1, int(round(y0 * image.height))))
    right = max(left + 1, min(image.width, int(round(x1 * image.width))))
    bottom = max(top + 1, min(image.height, int(round(y1 * image.height))))
    patch = image.crop((left, top, right, bottom))
    flat = Image.new("RGBA", patch.size, _rgb(base) + (255,))
    flat.alpha_composite(patch)
    scale = CELLS / max(patch.size)
    if scale < 1.0:
        size = (max(1, int(patch.width * scale)), max(1, int(patch.height * scale)))
        flat = flat.resize(size, Image.Resampling.BOX)
    return cast("tuple[tuple[int, int, int], ...]", tuple(flat.convert("RGB").get_flattened_data()))


def weakest(sampled: tuple[Cell, ...], *, ink: str, tolerance: float = TOLERANCE) -> str:
    """The sampled colour at the ``tolerance`` percentile of contrast against ``ink``."""
    if not sampled:
        raise LayoutError("no pixels were sampled, so no background can be reported")
    ranked = sorted(sampled, key=lambda cell: contrast_ratio(_hex(cell), ink))
    index = min(int(tolerance * (len(ranked) - 1)), len(ranked) - 1)
    return _hex(ranked[index])


def composite(colour: str, scrim: str, alpha: float) -> str:
    """``scrim`` laid over ``colour`` at ``alpha``, the way a renderer blends it."""
    if not 0.0 <= alpha <= 1.0:
        raise LayoutError(f"scrim opacity is a fraction 0..1, got {alpha}")
    under, over = _rgb(colour), _rgb(scrim)
    return "".join(
        f"{round(o * alpha + u * (1 - alpha)):02X}" for u, o in zip(under, over, strict=True)
    )


def effective_bg(
    sampled: tuple[Cell, ...],
    *,
    ink: str,
    scrim: str | None,
    alpha: float,
    tolerance: float = TOLERANCE,
) -> str:
    """The colour behind ``ink`` once the scrim is on: the weakest cell, composited."""
    weak = weakest(sampled, ink=ink, tolerance=tolerance)
    if scrim is None or alpha <= 0:
        return weak
    return composite(weak, scrim, alpha)


def solve_alpha(
    sampled: tuple[Cell, ...],
    *,
    ink: str,
    scrim: str,
    required: float,
    tolerance: float = TOLERANCE,
) -> float:
    """The smallest opacity at which the sampled pixels clear ``required`` under ``ink``.

    Always solvable: at full opacity the scrim *is* its pair's background colour, and
    the palette contrast-checked that pair against its own ink when the theme loaded.
    """
    steps = int(round(1.0 / _ALPHA_STEP))
    for step in range(steps + 1):
        alpha = step / steps
        got = effective_bg(sampled, ink=ink, scrim=scrim, alpha=alpha, tolerance=tolerance)
        if contrast_ratio(ink, got) >= required:
            return alpha
    return 1.0


def _hex(cell: Cell) -> str:
    return "".join(f"{channel:02X}" for channel in cell)


def _rgb(colour: str) -> tuple[int, int, int]:
    value = normalize_hex(colour)
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
