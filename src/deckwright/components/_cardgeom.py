"""How deep a card's contents set, and where its rounded corners leave room for type.

Shared with the components that size plates the way a card does — `flow`, `callouts`.
"""

from __future__ import annotations

import math

from deckwright.theme.model import Rect, Theme
from deckwright.utils.text import LINE_HEIGHT, wrapped_lines

from deckwright.components._shared import HEAD_SPACE_AFTER_PT

RADIUS_DEFAULT = 0.06
ICON_LINES = 2.0


def copy_height(theme: Theme, *, width: float, heading: str, copy: str) -> float:
    """The height a card's type needs set to ``width``, in inches."""
    head_style, body_style = theme.style("head"), theme.style("body")
    needed = 0.0
    if heading:
        needed += (
            wrapped_lines(
                heading,
                width_in=width,
                size_pt=head_style.size,
                face=theme.font_for(head_style),
            )
            * head_style.size
            * LINE_HEIGHT
            + HEAD_SPACE_AFTER_PT
        ) / 72
    if copy:
        needed += (
            wrapped_lines(
                copy, width_in=width, size_pt=body_style.size, face=theme.font_for(body_style)
            )
            * body_style.size
            * LINE_HEIGHT
            / 72
        )
    return needed


def icon_side(theme: Theme) -> float:
    """The side of a card's icon: two heading line-heights, in inches."""
    return theme.style("head").size * LINE_HEIGHT / 72 * ICON_LINES


def plate_height(
    theme: Theme,
    *,
    width: float,
    heading: str,
    copy: str,
    icon: bool = False,
    radius: float = RADIUS_DEFAULT,
) -> float:
    """The plate a card of this content fills at ``width``: its parts plus the inset.

    ``icon`` counts, or a caller sizes its steps by their copy and then has no room for
    the mark above it.
    """
    inset = theme.grid.gutter
    mark = icon_side(theme) + inset if icon else 0.0

    def depth(side: float) -> float:
        return (
            copy_height(theme, width=width - 2 * side, heading=heading, copy=copy)
            + mark
            + 2 * inset
        )

    # The corner reach needs the plate's height, so size once against the square corner
    # and again against the curve that height earns — the same rule `card()` insets by.
    height = depth(inset)
    side = inset + corner_reach(Rect(0.0, 0.0, width, height), radius, depth=inset)
    return height if side == inset else depth(side)


def corner_reach(rect: Rect, radius: float, *, depth: float) -> float:
    """How far the corner arc cuts in horizontally, ``depth`` below the plate's top edge.

    The corner is a quarter-circle of radius ``r = radius * min(w, h)`` centred at
    ``(r, r)``, so its edge at height ``d`` sits at ``r - sqrt(r^2 - (r - d)^2)``.
    """
    r = radius * min(rect.width, rect.height)
    if depth >= r:
        return 0.0
    return r - math.sqrt(r * r - (r - depth) * (r - depth))
