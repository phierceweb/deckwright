"""Place the chrome lines of a slide — its kicker, title and subtitle.

A chrome field is an ordinary placement resolved against the *whole canvas*; one naming
no ``at:`` falls back to the default stack. Every value is a fraction, never an inch, so
one treatment renders proportionally at any slide size.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from deckwright.errors import LayoutError
from deckwright.layouts.place import AT_KEYS, resolve_at
from deckwright.theme.model import Rect
from deckwright.theme.scale import Grid
from deckwright.utils.shapes import ALIGNS, ANCHORS
from deckwright.utils.spans import parse_box, parse_span
from deckwright.utils.text import LINE_HEIGHT, estimate_caveat, wrapped_lines

CHROME_ORDER = ("kicker", "title", "subtitle")
"""The chrome field vocabulary, and the order fields stack in when they name no ``at:``."""

_CHROME_KEYS = ("at", "align", "anchor", "rung", "pair", "ink")
# Rounding slack on a canvas fraction, so 0.9 + 0.1 still counts as inside.
_FRAC_EPS = 1e-6


@dataclass(frozen=True)
class ChromeField:
    """How one chrome line is placed and painted. Every geometry value is a fraction.

    An unset key means "inherit" — :meth:`merge` is how a slide overrides a theme.
    """

    at: dict[str, Any] | None = None
    auto_height: bool = False  # `box: {h: auto}` — the box is as deep as its text wraps
    align: str | None = None
    anchor: str | None = None
    rung: str | None = None  # type-ramp role; None means the field's own name
    pair: str | None = None  # palette pair supplying this line's ink
    ink: str | None = None  # colour role painted as this line's text

    def merge(self, over: ChromeField | None) -> ChromeField:
        """This field with every key ``over`` actually sets replacing it."""
        if over is None:
            return self
        return replace(self, **{k: v for k, v in vars(over).items() if v is not None})

    @property
    def alignment(self) -> str:
        return self.align or "left"

    @property
    def anchoring(self) -> str:
        return self.anchor or "top"


@dataclass(frozen=True)
class ChromeBand:
    """One placed chrome line: its text, its rectangle, and how to paint it.

    ``stacked`` marks a line that took its position from the default stack rather
    than from an ``at:`` — only those push the content band down.
    """

    name: str
    text: str
    size_pt: float
    rect: Rect
    field: ChromeField
    stacked: bool


def chrome_field(cfg: Any, *, name: str) -> ChromeField:
    """Validate one chrome-field mapping. Raises :class:`LayoutError` without a source
    prefix, so the theme loader and the spec parser can each raise their own type."""
    if name not in CHROME_ORDER:
        raise LayoutError(f"unknown chrome field {name!r}; known fields: {', '.join(CHROME_ORDER)}")
    if cfg is None:
        return ChromeField()
    if not isinstance(cfg, dict):
        raise LayoutError(
            f"chrome field {name!r} must be a mapping of {', '.join(_CHROME_KEYS)}, "
            f"got {type(cfg).__name__}"
        )
    unknown = sorted(set(cfg) - set(_CHROME_KEYS))
    if unknown:
        raise LayoutError(
            f"chrome field {name!r}: unknown key {unknown[0]!r}; "
            f"known keys: {', '.join(_CHROME_KEYS)}"
        )
    at, auto_height = _chrome_at(cfg.get("at"), name=name)
    return ChromeField(
        at=at,
        auto_height=auto_height,
        align=_chrome_choice(cfg.get("align"), key="align", options=ALIGNS, name=name),
        anchor=_chrome_choice(cfg.get("anchor"), key="anchor", options=ANCHORS, name=name),
        rung=None if cfg.get("rung") is None else str(cfg["rung"]),
        pair=None if cfg.get("pair") is None else str(cfg["pair"]),
        ink=None if cfg.get("ink") is None else str(cfg["ink"]),
    )


def _chrome_choice(value: Any, *, key: str, options: tuple[str, ...], name: str) -> str | None:
    if value is None:
        return None
    if str(value) not in options:
        raise LayoutError(
            f"chrome field {name!r}: {key} must be one of {', '.join(options)}, got {value!r}"
        )
    return str(value)


def _chrome_at(value: Any, *, name: str) -> tuple[dict[str, Any] | None, bool]:
    """Shape-check a chrome ``at:``, and whether its box asked to size to its text.

    ``resolve_at`` does the rest against the grid.
    """
    if value is None:
        return None, False
    where = f"chrome field {name!r}"
    if not isinstance(value, dict):
        raise LayoutError(
            f"{where}: 'at' must be a mapping with 'cols' or 'box', got {type(value).__name__}"
        )
    unknown = sorted(set(value) - set(AT_KEYS))
    if unknown:
        raise LayoutError(
            f"{where}: unknown 'at' key {unknown[0]!r}; known keys: {', '.join(AT_KEYS)}"
        )
    if "box" in value:
        box, auto_height = _auto_height(value["box"])
        x, y, w, h = parse_box(box, where=where, error=LayoutError)
        if x < 0 or y < 0 or x + w > 1 + _FRAC_EPS or y + h > 1 + _FRAC_EPS:
            raise LayoutError(
                f"{where}: box {value['box']!r} leaves the canvas — a chrome box is'"
                f" percents of the canvas, never inches"
            )
        return {"box": (x, y, w, h)}, auto_height
    if "cols" not in value:
        raise LayoutError(f"{where}: 'at' needs 'cols' or 'box'")
    at: dict[str, Any] = {"cols": parse_span(value["cols"], "cols", where=where, error=LayoutError)}
    if "rows" in value:
        at["rows"] = parse_span(value["rows"], "rows", where=where, error=LayoutError)
    return at, False


def _auto_height(box: Any) -> tuple[Any, bool]:
    """``h: auto`` swapped for the room left below ``y``, and a flag saying it was.

    The substitute is only a ceiling for the canvas check; the band takes the height its
    text really wraps to.
    """
    if not isinstance(box, dict) or str(box.get("h", "")).strip().lower() != "auto":
        return box, False
    y = box.get("y")
    room = 1.0 - float(str(y)[:-1]) / 100.0 if isinstance(y, str) and y.endswith("%") else 1.0
    return {**box, "h": f"{max(room, 0.0) * 100:.4f}%"}, True


_BOX_SLACK = 0.02


def chrome_bands(
    lines: Mapping[str, tuple[str, float]],
    *,
    fields: Mapping[str, ChromeField],
    grid: Grid,
    faces: Mapping[str, str] | None = None,
    slide: int | None = None,
) -> tuple[ChromeBand, ...]:
    """Place every chrome line that has text.

    A stacked band is as tall as its text *wraps*: a title sized at one line while it
    renders as two draws over the subtitle beneath it.

    Args:
        lines: Chrome field to its text and resolved point size.
        faces: Chrome field to the typeface it will be set in, for the wrap estimate.
        slide: Numbers the slide in anything raised here. Every other build error
            carries it, and this is the one an author meets most.
    """
    at = f"slide {slide}: " if slide is not None else ""
    unknown = sorted(set(lines) - set(CHROME_ORDER))
    if unknown:
        raise LayoutError(
            f"unknown chrome field {unknown[0]!r}; known fields: {', '.join(CHROME_ORDER)}"
        )
    canvas = Rect(0.0, 0.0, grid.slide_w, grid.slide_h)
    out: list[ChromeBand] = []
    y = grid.top
    for name in CHROME_ORDER:
        if name not in lines:
            continue
        text, size_pt = _chrome_line(lines[name], name)
        face = (faces or {}).get(name)
        field = fields.get(name) or ChromeField()
        if field.at is None:
            if field.anchor is not None:
                raise LayoutError(
                    f"{at}chrome field {name!r} sets anchor {field.anchor!r} but no 'at:' — "
                    f"a stacked line shares the stack's frame, so it has no frame of its "
                    f"own to anchor in; give it an 'at:'"
                )
            height = _wrap_height(text, width_in=grid.content_w, size_pt=size_pt, face=face)
            out.append(
                ChromeBand(
                    name, text, size_pt, Rect(grid.left, y, grid.content_w, height), field, True
                )
            )
            y += height
            continue
        rect = resolve_at(field.at, grid=grid, area=canvas, where=f"chrome field {name!r}")
        if "box" not in field.at and "rows" not in field.at:
            # cols: alone fixes the measure, not the depth: the line keeps its place in
            # the stack rather than jumping to the top margin.
            height = _wrap_height(text, width_in=rect.width, size_pt=size_pt, face=face)
            out.append(
                ChromeBand(name, text, size_pt, Rect(rect.left, y, rect.width, height), field, True)
            )
            y += height
            continue
        needed = _wrap_height(text, width_in=rect.width, size_pt=size_pt, face=face)
        if field.auto_height:
            # The point of `h: auto`: the box is as deep as the text turns out to be, so
            # re-shuffling content cannot leave a hand-measured depth behind.
            out.append(
                ChromeBand(
                    name, text, size_pt, Rect(rect.left, rect.top, rect.width, needed), field, False
                )
            )
            continue
        if needed > rect.height + _BOX_SLACK:
            raise LayoutError(
                f"{at}chrome field {name!r} wraps to {needed:.2f}in but its box is only "
                f"{rect.height:.2f}in tall — it would be drawn through the line below; "
                f"deepen the box, shorten the text, or drop to a smaller rung"
                f"{estimate_caveat(face)}"
            )
        out.append(ChromeBand(name, text, size_pt, rect, field, False))
    return tuple(out)


def _wrap_height(text: str, *, width_in: float, size_pt: float, face: str | None = None) -> float:
    return (
        wrapped_lines(text, width_in=width_in, size_pt=size_pt, face=face)
        * size_pt
        * LINE_HEIGHT
        / 72
    )


def _chrome_line(value: Any, name: str) -> tuple[str, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise LayoutError(f"chrome band {name!r} needs a (text, type size) pair, got {value!r}")
    text, raw = value
    try:
        size_pt = float(raw)
    except (TypeError, ValueError):
        raise LayoutError(f"chrome band {name!r} needs a numeric type size, got {raw!r}") from None
    if size_pt <= 0:
        raise LayoutError(f"chrome band {name!r} needs a positive type size, got {size_pt}")
    return str(text), size_pt
