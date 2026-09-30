"""Where a template's master art leaves a clear band for the chrome: a column run read off
a coarse probe of the picture."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PIL import Image

from deckwright.imagery.sample import load
from deckwright.theme.defaults import default_grid
from deckwright.theme.scale import Scale

# The grid the background is probed on for artwork, and how far a column's pixels may
# spread before it counts as decorated rather than free.
_PROBE_COLS, _PROBE_ROWS = 48, 32
_UNIFORM_SPREAD = 12
# A run narrower than this much of the canvas is not worth steering a title into.
_MIN_CLEAR_RUN = 0.3
# The vertical slice of the canvas the chrome stack occupies.
CHROME_BAND = (0.0, 0.3)


def clear_run(path: Path, band: tuple[float, float]) -> tuple[float, float] | None:
    """The widest horizontal run of ``band`` a background picture leaves uniform.

    A column counts as decorated when it differs from the *typical* column of the
    band, not when it varies down its own length — a banded background varies
    everywhere and none of that is artwork.

    Returns:
        ``(start, end)`` as fractions of the width, or None when the whole band is
        plain (nothing to avoid) or none of it is (nowhere to go).
    """
    top, bottom = band
    image = load(path).convert("RGB").resize((_PROBE_COLS, _PROBE_ROWS), Image.Resampling.BOX)
    rows = range(
        max(0, int(top * _PROBE_ROWS)), max(1, min(_PROBE_ROWS, int(bottom * _PROBE_ROWS) + 1))
    )
    columns = [
        [cast("tuple[int, int, int]", image.getpixel((x, y))) for y in rows]
        for x in range(_PROBE_COLS)
    ]
    typical = [
        tuple(sorted(channel)[len(channel) // 2] for channel in zip(*pixels, strict=True))
        for pixels in zip(*columns, strict=True)
    ]
    quiet = [
        max(
            abs(a - b)
            for pixel, ref in zip(column, typical, strict=True)
            for a, b in zip(pixel, ref, strict=True)
        )
        <= _UNIFORM_SPREAD
        for column in columns
    ]
    if all(quiet) or not any(quiet):
        return None
    best: tuple[int, int] | None = None
    start = 0
    run = 0
    for x, free in (*enumerate(quiet), (_PROBE_COLS, False)):
        if free:
            start = x if run == 0 else start
            run += 1
            continue
        if best is None or run > best[1] - best[0]:
            best = (start, x) if run else best
        run = 0
    if best is None or (best[1] - best[0]) < _PROBE_COLS * _MIN_CLEAR_RUN:
        return None
    return best[0] / _PROBE_COLS, best[1] / _PROBE_COLS


def columns(run: tuple[float, float]) -> tuple[int, int]:
    """A canvas-fraction run as a pair of grid column indices, clamped to the grid."""
    grid = default_grid(Scale(slide_w=1.0, slide_h=1.0))
    span = 1.0 - grid.left_frac - grid.right_frac
    edges = [
        min(grid.columns, max(0, round((frac - grid.left_frac) / span * grid.columns)))
        for frac in run
    ]
    return edges[0], max(edges[0] + 1, edges[1])
