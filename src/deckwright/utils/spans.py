"""The fractions a placement can name, and what they resolve to on a grid.

Quarters are absent: every quarter is one of N equal siblings, which ``split:`` covers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Share:
    """One child of a ``split:`` — its slice of the band, unresolved until the grid."""

    band: Any  # the band's own cols: a name, or (start, end)
    index: int  # shares before this one
    span: int  # shares it takes
    total: int  # shares in the band


# name -> (start, end, denominator), as a fraction of the axis.
COL_SPANS: dict[str, tuple[int, int, int]] = {
    "full": (0, 1, 1),
    "left-half": (0, 1, 2),
    "right-half": (1, 2, 2),
    "left-third": (0, 1, 3),
    "mid-third": (1, 2, 3),
    "right-third": (2, 3, 3),
    "left-two-thirds": (0, 2, 3),
    "right-two-thirds": (1, 3, 3),
}

ROW_SPANS: dict[str, tuple[int, int, int]] = {
    "band": (0, 1, 1),
    "top-half": (0, 1, 2),
    "bottom-half": (1, 2, 2),
    "top-third": (0, 1, 3),
    "mid-third": (1, 2, 3),
    "bottom-third": (2, 3, 3),
    "top-two-thirds": (0, 2, 3),
    "bottom-two-thirds": (1, 3, 3),
}


def spans_for(key: str) -> dict[str, tuple[int, int, int]]:
    """The vocabulary for ``cols`` or ``rows``.

    Raises rather than defaulting: a decorated key silently offering the wrong axis's
    names makes the error read as though the author wrote nonsense.
    """
    if key not in ("cols", "rows"):
        raise KeyError(f"no span vocabulary for {key!r}; expected 'cols' or 'rows'")
    return COL_SPANS if key == "cols" else ROW_SPANS


def divides(name: str, divisor: int, *, key: str) -> bool:
    """Whether a grid of ``divisor`` parts can express this fraction exactly."""
    return divisor % spans_for(key)[name][2] == 0


def resolve(name: str, divisor: int, *, key: str) -> tuple[int, int]:
    """A name as ``(start, end)`` indices on a grid of ``divisor`` parts.

    Caller checks :func:`divides` first: a grid that cannot express the fraction would
    otherwise round two "thirds" to different widths on the same slide.
    """
    start, end, denominator = spans_for(key)[name]
    step = divisor // denominator
    return start * step, end * step


def parse_span(
    value: Any, key: str, *, where: str, error: type[Exception]
) -> str | tuple[int, int]:
    """A named fraction, or ``{from:, to:}`` where no fraction names the span.

    A name stays a name — resolving it needs the theme's grid. ``error`` is the caller's
    class: a slide's ``at:`` is a spec error, a chrome ``at:`` a layout one.
    """
    names = spans_for(key)
    if isinstance(value, str):
        if value not in names:
            raise error(f"{where}: {key} {value!r} names no fraction; one of: {', '.join(names)}")
        return value
    if isinstance(value, list):
        span = f"{{from: {value[0]}, to: {value[1]}}}" if len(value) == 2 else "{from: N, to: N}"
        raise error(
            f"{where}: {key} is a name or a mapping, not a list — write {span}, "
            f"or one of: {', '.join(names)}"
        )
    if not isinstance(value, dict) or set(value) != {"from", "to"}:
        raise error(
            f"{where}: {key} must be a name or {{from: N, to: N}}, got {value!r}; "
            f"names: {', '.join(names)}"
        )
    start, end = value["from"], value["to"]
    if not all(isinstance(n, int) and not isinstance(n, bool) for n in (start, end)):
        raise error(f"{where}: {key} from and to are whole indices, got {value!r}")
    if start < 0:
        raise error(f"{where}: {key} from {start} must be 0 or more")
    if start >= end:
        raise error(f"{where}: {key} from {start} must be less than to {end}")
    return start, end


def parse_box(
    value: Any, *, where: str, error: type[Exception]
) -> tuple[float, float, float, float]:
    """``{x, y, w, h}`` as percents. ``0.105`` and ``10.5in`` look alike; ``10.5%`` cannot."""
    if isinstance(value, list):
        raise error(
            f"{where}: box is keyed, not a list — write "
            f"{{x: 0%, y: 0%, w: 100%, h: 100%}}, in percents of the canvas"
        )
    if not isinstance(value, dict) or set(value) != {"x", "y", "w", "h"}:
        raise error(f"{where}: box needs x, y, w and h as percents of the canvas, got {value!r}")
    out = tuple(percent(value[k], f"box.{k}", where=where, error=error) for k in "xywh")
    if out[2] <= 0 or out[3] <= 0:
        raise error(f"{where}: box needs a positive width and height, got {value!r}")
    return out  # type: ignore[return-value]


def percent(value: Any, key: str, *, where: str, error: type[Exception]) -> float:
    """A percent string as a fraction — ``10.5%`` is ``0.105``."""
    if isinstance(value, str) and value.endswith("%"):
        try:
            return float(value[:-1]) / 100.0
        except ValueError:
            pass
    raise error(
        f"{where}: {key} is a percent of the canvas, got {value!r} — write '50%' for half of it"
    )
