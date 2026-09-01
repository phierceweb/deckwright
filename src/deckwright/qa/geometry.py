"""Checks that read only the build manifest — no render, fast enough for a hook."""

from __future__ import annotations

from typing import Any

from deckwright.compile.record import box_of, owns
from deckwright.qa.model import Finding, Severity
from deckwright.qa.walk import all_shapes, slides, unique_shapes
from deckwright.theme.model import Rect, Theme
from deckwright.utils.text import LINE_HEIGHT, wrapped_lines
from deckwright.utils.color import AA_LARGE, contrast_ratio, required_ratio

_EDGE_TOLERANCE = 0.01
_FULL_BLEED_TOLERANCE = 0.02


def _is_full_bleed(box: tuple[float, float, float, float], theme: Theme) -> bool:
    left, top, width, height = box
    return (
        abs(left) <= _FULL_BLEED_TOLERANCE
        and abs(top) <= _FULL_BLEED_TOLERANCE
        and width >= theme.grid.slide_w - _FULL_BLEED_TOLERANCE
        and height >= theme.grid.slide_h - _FULL_BLEED_TOLERANCE
    )


# A recorded box is rounded to three decimals and a wrap estimate carries its own small
# safety margin, so a hair over is arithmetic rather than a defect.
_FIT_SLACK = 0.06


def check_bounds(manifest: dict[str, Any], theme: Theme) -> list[Finding]:
    """Flag shapes that fall outside the slide."""
    findings: list[Finding] = []
    for slide in slides(manifest):
        for shape in unique_shapes(slide):
            box = box_of(shape)
            # A declared bleed is the author saying "off the canvas is the point".
            if (
                not box
                or shape.get("bleed")
                or shape.get("annotation")
                or _is_full_bleed(box, theme)
            ):
                continue
            left, top, width, height = box
            if (
                left < -_EDGE_TOLERANCE
                or top < -_EDGE_TOLERANCE
                or left + width > theme.grid.slide_w + _EDGE_TOLERANCE
                or top + height > theme.grid.slide_h + _EDGE_TOLERANCE
            ):
                findings.append(
                    Finding(
                        slide=slide["index"],
                        check="bounds",
                        severity=Severity.ERROR,
                        detail=(
                            f"{shape.get('name', 'shape')!r} extends outside the "
                            f"{theme.grid.slide_w:g}×{theme.grid.slide_h:g}in slide"
                        ),
                        box=box,
                        shape=shape.get("name"),
                    )
                )
    return findings


def _placement_index(slide: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Origin -> its placement record, less any origin recorded twice.

    A collision means two placements share a name, which `shape-name` already reports;
    guessing which rect a shape belonged to would invent a finding on top of it.
    """
    index: dict[str, dict[str, Any]] = {}
    collided: set[str] = set()
    for placement in slide.get("placements") or []:
        origin = placement.get("origin")
        if not origin:
            continue
        if origin in index:
            collided.add(origin)
        index[origin] = placement
    return {k: v for k, v in index.items() if k not in collided}


def _placement_of(name: str | None, index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """The placement a shape's name says drew it — longest origin wins.

    Longest, not first: an author's `id:` may itself contain the separator, and a
    shorter origin would otherwise claim a shape that is not its own.
    """
    if not name:
        return None
    matches = [origin for origin in index if owns(origin, name)]
    return index[max(matches, key=len)] if matches else None


def check_placement_fit(manifest: dict[str, Any], theme: Theme) -> list[Finding]:
    """Flag shapes that escape the placement rect they were drawn into.

    `bounds` measures against the slide, so a component landing on its neighbour is
    invisible to it. `theme` is unused, kept so every manifest-only check shares a signature.
    """
    findings: list[Finding] = []
    for slide in slides(manifest):
        index = _placement_index(slide)
        if not index:
            continue
        for shape in unique_shapes(slide):
            box = box_of(shape)
            # A declared bleed is the author saying "off the canvas is the point"; a
            # plate is the compiler painting a surface deliberately wider than its text.
            if not box or shape.get("bleed") or shape.get("plate") or shape.get("annotation"):
                continue
            placement = _placement_of(shape.get("name"), index)
            # No placement owns it: chrome and the background, which never had a rect.
            if placement is None or placement.get("component") == "connector":
                continue
            rect = box_of(placement)
            if not rect or rect[2] <= 0 or rect[3] <= 0 or box[2] <= 0 or box[3] <= 0:
                continue
            over = max(
                rect[0] - box[0],
                rect[1] - box[1],
                (box[0] + box[2]) - (rect[0] + rect[2]),
                (box[1] + box[3]) - (rect[1] + rect[3]),
            )
            if over > _EDGE_TOLERANCE:
                findings.append(
                    Finding(
                        slide=slide["index"],
                        check="placement-fit",
                        severity=Severity.ERROR,
                        detail=(
                            f"{shape.get('name', 'shape')!r} runs {over:.2f}in past the "
                            f"[{rect[0]:g}, {rect[1]:g}, {rect[2]:g}, {rect[3]:g}]in rect "
                            f"its placement was given — that space belongs to the next "
                            f"placement"
                        ),
                        box=box,
                        shape=shape.get("name"),
                    )
                )
    return findings


def check_reserved(manifest: dict[str, Any], theme: Theme) -> list[Finding]:
    """Flag shapes intruding on one of the theme's reserved regions."""
    findings: list[Finding] = []
    if not theme.reserve:
        return findings
    for slide in slides(manifest):
        for shape in unique_shapes(slide):
            box = box_of(shape)
            # A declared bleed is the author's override, here as in bounds and fit.
            if (
                not box
                or shape.get("bleed")
                or shape.get("annotation")
                or _is_full_bleed(box, theme)
            ):
                continue
            for region in theme.reserve:
                if region.hits(Rect(*box), scale=theme.scale):
                    findings.append(
                        Finding(
                            slide=slide["index"],
                            check="reserved",
                            severity=Severity.ERROR,
                            detail=(
                                f"{shape.get('name', 'shape')!r} intrudes on reserved "
                                f"region {region.name!r}"
                            ),
                            box=box,
                            shape=shape.get("name"),
                        )
                    )
                    break  # one finding per shape; the first region named is enough to act on
    return findings


def check_type_sizes(manifest: dict[str, Any], theme: Theme) -> list[Finding]:
    """Flag text smaller than the theme's minimum. A row that recorded no size is
    skipped without a finding — it is unmeasured, not clean."""
    findings: list[Finding] = []
    for slide in slides(manifest):
        for shape in all_shapes(slide):
            size = shape.get("font_pt")
            if size is None or size >= theme.min_pt:
                continue
            findings.append(
                Finding(
                    slide=slide["index"],
                    check="min-font",
                    severity=Severity.WARN,
                    detail=f"{size:g}pt is below the theme minimum of {theme.min_pt:g}pt",
                    box=box_of(shape),
                    shape=shape.get("name"),
                )
            )
    return findings


def check_text_fit(manifest: dict[str, Any], theme: Theme) -> list[Finding]:
    """Flag a shape whose own recorded lines need more height than its recorded box.

    A multi-line record without per-line sizes is skipped rather than guessed at:
    measuring a body paragraph at its heading's size over-reports badly, so a component
    owes a ``line_pt`` before this check can see it.
    """
    findings: list[Finding] = []
    for slide in slides(manifest):
        for shape in all_shapes(slide):
            lines, size, box = shape.get("lines"), shape.get("font_pt"), shape.get("box")
            sizes = shape.get("line_pt") or ([size] if lines and len(lines) == 1 else [])
            if not lines or not size or not box or len(sizes) != len(lines):
                continue
            if shape.get("rendered", "native") != "native":
                continue  # a screenshotted panel's text is not set by us
            width, height = box.get("w", 0.0), box.get("h", 0.0)
            if width <= 0 or height <= 0:
                continue
            needed = sum(
                wrapped_lines(str(line), width_in=width, size_pt=pt, face=theme.face)
                * pt
                * LINE_HEIGHT
                / 72
                for line, pt in zip(lines, sizes, strict=True)
            )
            if needed > height + _FIT_SLACK:
                findings.append(
                    Finding(
                        slide=slide["index"],
                        check="text-fit",
                        severity=Severity.WARN,
                        detail=(
                            f"the recorded text needs {needed:.2f}in but the shape "
                            f"declares {height:.2f}in — it runs past its own box, "
                            f"which `bounds` cannot see"
                        ),
                        box=box_of(shape),
                        shape=shape.get("name"),
                    )
                )
    return findings


def check_contrast(manifest: dict[str, Any], theme: Theme) -> list[Finding]:
    """Flag foreground/background pairs below WCAG AA.

    The manifest records no boldness, so 'large text' is approximated by point size alone.
    A shape with a colour but no type size is a mark, held to WCAG 1.4.11's 3:1 for
    graphics rather than to a body ratio.
    """
    findings: list[Finding] = []
    for slide in slides(manifest):
        for shape in all_shapes(slide):
            fg, bg = shape.get("fg"), shape.get("bg")
            if not fg or not bg or shape.get("rendered", "native") != "native":
                continue
            size = shape.get("font_pt") or 0.0
            required = required_ratio(size) if size else AA_LARGE
            ratio = contrast_ratio(fg, bg)
            if ratio < required:
                # Below 3:1 no backdrop redeems it; above, the real one may be better.
                severity = Severity.ERROR if ratio < AA_LARGE else Severity.WARN
                findings.append(
                    Finding(
                        slide=slide["index"],
                        check="contrast",
                        severity=severity,
                        detail=(
                            f"{fg} on {bg} is {ratio:.2f}:1, below the {required:g}:1 "
                            f"WCAG AA minimum"
                        ),
                        box=box_of(shape),
                        shape=shape.get("name"),
                    )
                )
    return findings
