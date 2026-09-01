"""Check text on a photograph against the rendered pixels, not against the manifest.

There is no recorded pair to read behind a picture, so this opens the render and measures
what actually surrounds each line — the only check that catches a scrim the build thought
was enough and a renderer composited differently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence, cast

from PIL import Image

from pf_core.log import get_logger

from deckwright.compile.record import box_of, canvas_of
from deckwright.qa.model import Finding, Severity
from deckwright.utils.color import contrast_ratio, normalize_hex, required_ratio

logger = get_logger(__name__)

# Vertical slices each text box is measured in, so a gradient scrim is judged where it
# is weakest rather than on its average.
BANDS = 3
# Channel bucket width for the modal-colour estimate. Coarse enough that JPEG ringing
# and antialiasing fall into the background's own bucket.
_BUCKET = 24
_MIN_PIXELS = 24
# Slack below the WCAG threshold before a measurement is called a failure: a rendered
# glyph edge is never exactly the colour the build asked for.
_SLACK = 0.15
# Under this the measured surface and the one the build recorded are the same colour,
# so nothing was composited between them and the remedy is not a scrim.
_SAME_SURFACE = 1.1


def check_render_contrast(manifest: dict[str, Any], images: Sequence[str | Path]) -> list[Finding]:
    """Flag text whose rendered surroundings fall below WCAG AA.

    Only slides showing a picture are measured — one this deck placed, or the one the
    template paints behind every slide. Everywhere else the manifest's own colours are
    the truth and :func:`deckwright.qa.geometry.check_contrast` has already read them.
    """
    findings: list[Finding] = []
    by_index = {i + 1: Path(path) for i, path in enumerate(images)}
    slide_w, slide_h = canvas_of(manifest)
    if slide_w <= 0 or slide_h <= 0:
        return [
            Finding(
                slide=0,
                check="canvas-size",
                severity=Severity.WARN,
                detail=(
                    f"manifest records a {slide_w:g}x{slide_h:g}in canvas, so the "
                    f"render's pixels cannot be mapped to slide coordinates — no "
                    f"text on a picture was measured"
                ),
            )
        ]
    for slide in manifest.get("slides", []):
        shapes = slide.get("shapes", [])
        if not slide.get("backdrop") and not any(s.get("rendered") == "picture" for s in shapes):
            continue
        path = by_index.get(slide.get("index"))
        if path is None or not path.is_file():
            continue
        page = Image.open(path).convert("RGB")
        for shape in shapes:
            finding = _measure(slide, shape, page, slide_w=slide_w, slide_h=slide_h)
            if finding is not None:
                findings.append(finding)
    return findings


def _measure(
    slide: dict[str, Any],
    shape: dict[str, Any],
    page: Image.Image,
    *,
    slide_w: float,
    slide_h: float,
) -> Finding | None:
    fg, box = shape.get("fg"), box_of(shape)
    if not fg or not box or shape.get("rendered", "native") != "native":
        return None
    if not shape.get("text"):
        return None
    ink = normalize_hex(fg)
    required = required_ratio(shape.get("font_pt") or 0.0)
    worst = _worst_band(page, box, slide_w=slide_w, slide_h=slide_h, ink=ink)
    if worst is None:
        return None
    colour, ratio = worst
    if ratio >= required - _SLACK:
        return None
    return Finding(
        slide=slide["index"],
        check="render-contrast",
        severity=Severity.WARN,
        detail=(
            f"{ink} renders on {colour} — measured {ratio:.1f}:1 in the render, "
            f"below the {required:g}:1 WCAG AA minimum; {_remedy(shape, colour)}"
        ),
        box=box,
        shape=shape.get("name"),
    )


def _remedy(shape: dict[str, Any], measured: str) -> str:
    """What to actually do about it, which is not always a scrim.

    Most shapes measured here have no picture behind them — a template backdrop
    qualifies the whole deck.
    """
    recorded = shape.get("bg")
    if not recorded:
        return "the picture behind this text needs a scrim, or a heavier one"
    recorded = normalize_hex(recorded)
    if contrast_ratio(measured, recorded) <= _SAME_SURFACE:
        return (
            "nothing is showing through — the render found the background the build "
            "recorded, so this is the ink's own contrast and a scrim would not "
            "change it"
        )
    return (
        f"the build recorded {recorded} behind this text and the render found "
        f"{measured}, so a picture is showing through — it needs a scrim, or a "
        f"heavier one"
    )


def _worst_band(
    page: Image.Image, box: Sequence[float], *, slide_w: float, slide_h: float, ink: str
) -> tuple[str, float] | None:
    """The weakest of the box's horizontal bands: its modal colour and its ratio."""
    per_x, per_y = page.width / slide_w, page.height / slide_h
    left = max(0, int(box[0] * per_x))
    top = max(0, int(box[1] * per_y))
    right = min(page.width, int((box[0] + box[2]) * per_x))
    bottom = min(page.height, int((box[1] + box[3]) * per_y))
    if right - left < 2 or bottom - top < 2:
        return None
    results: list[tuple[str, float]] = []
    # Split evenly rather than stepping: a one-pixel remainder band is the box's own
    # antialiased border, and would read as the worst surface on the slide.
    height = bottom - top
    for band in range(BANDS):
        patch = page.crop(
            (left, top + height * band // BANDS, right, top + height * (band + 1) // BANDS)
        )
        if patch.width * patch.height < _MIN_PIXELS:
            continue
        colour = _modal(cast("list[tuple[int, int, int]]", patch.get_flattened_data()))
        results.append((colour, contrast_ratio(ink, colour)))
    if not results:
        return None
    return min(results, key=lambda pair: pair[1])


def _modal(pixels: Iterable[tuple[int, int, int]]) -> str:
    """The commonest colour in a patch, as hex.

    The mode, not the mean: glyphs cover a minority of a text box, so averaging drags
    the estimate toward the ink and understates how bad the real background is.
    """
    counts: dict[tuple[int, int, int], int] = {}
    totals: dict[tuple[int, int, int], list[int]] = {}
    for pixel in pixels:
        key = (pixel[0] // _BUCKET, pixel[1] // _BUCKET, pixel[2] // _BUCKET)
        counts[key] = counts.get(key, 0) + 1
        running = totals.setdefault(key, [0, 0, 0])
        for channel in range(3):
            running[channel] += pixel[channel]
    key = max(counts, key=lambda k: counts[k])
    n = counts[key]
    return "".join(f"{round(totals[key][channel] / n):02X}" for channel in range(3))
