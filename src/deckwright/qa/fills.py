"""Whether a shape filled to stand off its ground can be told apart from it."""

from __future__ import annotations

from typing import Any

from deckwright.compile.record import box_of
from deckwright.qa.model import Finding, Severity
from deckwright.qa.walk import all_shapes, slides
from deckwright.theme.model import Theme
from deckwright.utils.color import AA_LARGE, contrast_ratio, delta_e

# Below this a fill differs from its ground in neither lightness nor colour.
_DISTINCT_DELTA_E = 35.0


def check_fill_ground(manifest: dict[str, Any], theme: Theme) -> list[Finding]:
    """Flag a fill that neither luminance nor colour separates from what it was laid on.

    Only a fill meant to stand off records one: a `surface` is a recess by design.
    """
    findings: list[Finding] = []
    for slide in slides(manifest):
        for shape in all_shapes(slide):
            fill, ground = shape.get("fill"), shape.get("ground")
            if not fill or not ground:
                continue
            ratio = contrast_ratio(fill, ground)
            distance = delta_e(fill, ground)
            if ratio >= AA_LARGE or distance >= _DISTINCT_DELTA_E:
                continue
            findings.append(
                Finding(
                    slide=slide["index"],
                    check="fill-ground",
                    severity=Severity.WARN,
                    detail=(
                        f"{fill} laid on {ground} is {ratio:.2f}:1 and {distance:.0f} ΔE apart — "
                        f"no lighter or darker, and too close in colour, so the plate all but "
                        f"vanishes; bind the pair's colour to one that stands off the page"
                    ),
                    box=box_of(shape),
                    shape=shape.get("name"),
                )
            )
    return findings
