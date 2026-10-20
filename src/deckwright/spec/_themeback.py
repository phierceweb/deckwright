"""A read-back deck's colours, rungs and moved chrome, as fields of the drafting theme.

The file holds hex and points and boxes; a spec names pairs, roles, rungs and percentages.
Each resolver answers only where the theme has exactly that value, and says so where not.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING

from deckwright.components.image import OVER_RUNG_DEFAULT
from deckwright.layouts.chrome import CHROME_ORDER, ChromeField, chrome_bands
from deckwright.theme.model import Theme

if TYPE_CHECKING:
    from deckwright.spec._recover import Recovered
    from deckwright.spec.extract import SlideContent

# A frame within this of where the theme stacks its line has not been moved.
_SAME_IN = 0.05


def _hex(colour: str) -> str:
    return colour.strip().lstrip("#").upper()


def _background(rgb: str | None, theme: Theme) -> str | None:
    """The pair whose surface this fill is, or None when it is not one of them.

    Exact matches only: a near-miss would set the words on a surface the theme never
    contrast-checked them against. The page colour is ``page`` whichever other pairs
    share its surface, since those pairs differ only in the ink they set on it.
    """
    if not rgb:
        return None
    wanted = _hex(rgb)
    matches = [name for name, pair in theme.palette.pairs.items() if _hex(pair.bg) == wanted]
    if not matches:
        return None
    return "page" if "page" in matches else matches[0]


def _chrome(slide: SlideContent, theme: Theme) -> dict:
    """The ``chrome:`` block for each line drawn in a frame of its own that is not where, or
    as, the theme would set it — each key only where it differs from the default."""
    fields = {name: theme.chrome.get(name) or ChromeField() for name in CHROME_ORDER}
    lines = {
        name: (text, theme.style(fields[name].rung or name).size)
        for name in CHROME_ORDER
        if (text := getattr(slide, name))
    }
    faces = {name: theme.font_for(theme.style(fields[name].rung or name)) for name in lines}
    stacked = {
        band.name: band.rect
        for band in chrome_bands(lines, fields=fields, grid=theme.grid, faces=faces)
    }
    width, height = theme.grid.slide_w, theme.grid.slide_h
    out: dict = {}
    for frame in slide.frames:
        if frame.field not in lines:
            continue
        x, y, w, h = frame.box
        drawn = (x * width, y * height, w * width, h * height)
        here = stacked.get(frame.field)
        keys: dict = {}
        if here is None or any(
            abs(a - b) > _SAME_IN
            for a, b in zip(drawn, (here.left, here.top, here.width, here.height), strict=True)
        ):
            keys["at"] = {"box": _box(*frame.box)}
        default = fields[frame.field].rung or frame.field
        rung, _ = _rung(frame.size_pt, theme, default=default)
        if rung not in (None, default):
            keys["rung"] = rung
        if frame.align and frame.align != fields[frame.field].alignment:
            keys["align"] = frame.align
        if frame.built:
            keys.setdefault("at", {"box": _box(*frame.box)})
            keys["build"] = "last"
        if "at" in keys and frame.anchor and frame.anchor != "top":
            keys["anchor"] = frame.anchor
        if keys:
            out[frame.field] = keys
    return out


def _rungs_over(item: Recovered, *, theme: Theme, remarks: list[str]) -> Recovered:
    """An image's ``over:`` lines on the rung each was set at, where it is not the default."""
    image = dict(item.body["image"])
    over: list = []
    for line, size in zip(image["over"], item.sizes, strict=True):
        rung, why = _rung(size, theme, default=OVER_RUNG_DEFAULT)
        if why:
            remarks.append(f"{item.token}: {line!r} is set at {size:g}pt, {why}")
        over.append(line if rung in (None, OVER_RUNG_DEFAULT) else {"text": line, "rung": rung})
    return replace(item, body={"image": {**image, "over": over}})


def _rung(size_pt: float | None, theme: Theme, *, default: str) -> tuple[str | None, str | None]:
    """The rung ``theme`` sets at ``size_pt``, and why it is not a clean answer, if it is not.

    Sizes within half a point match. Two rungs of one size take ``default`` when it is one
    of them, else the first in the ramp's order.
    """
    if size_pt is None:
        return None, None
    matches = [name for name, style in theme.ramp.items() if abs(style.size - size_pt) <= 0.5]
    if not matches:
        return None, "which no rung is, so it comes back at the default rung"
    if default in matches or len(matches) == 1:
        return (default if default in matches else matches[0]), None
    return matches[0], f"which {' and '.join(matches)} share, so it is drafted as {matches[0]}"


def _inked(item: Recovered, theme: Theme) -> dict:
    """An icon's mapping with the role its fill is, when the theme has one that colour."""
    if item.inked is None:
        return item.body
    role = next((n for n, rgb in theme.palette.roles.items() if _hex(rgb) == item.inked), None)
    if role is None:
        return item.body
    fields = dict(item.body["icon"])
    return {"icon": {"name": fields.pop("name"), "ink": role, **fields}}


def _pair(painted: tuple[str, str | None] | None, theme: Theme) -> str | None:
    """The pair a plate was painted in, when the theme declares one; ``surface`` is the
    default and stays unwritten. Its words' ink tells apart pairs sharing a ground."""
    if painted is None:
        return None
    fill, ink = painted
    grounds = [n for n, p in theme.palette.pairs.items() if _hex(p.bg) == fill]
    found = [n for n in grounds if ink is None or _hex(theme.palette.pairs[n].fg) == ink]
    return None if not found or "surface" in found else found[0]


def _box(x: float, y: float, w: float, h: float) -> dict[str, str]:
    """A box in percent of the canvas, rounded outward so a box drawn tight around its
    words still holds them."""
    left, top = math.floor(_milli(x)), math.floor(_milli(y))
    # A rule's line is zero across, and a box may not be; the line draws at its top-left.
    right = max(math.ceil(_milli(x + w)), left + 1)
    bottom = max(math.ceil(_milli(y + h)), top + 1)
    return {"x": _pct(left), "y": _pct(top), "w": _pct(right - left), "h": _pct(bottom - top)}


def _milli(fraction: float) -> float:
    """Thousandths of a percent, float noise shed so an exact edge is not pushed outward."""
    return round(fraction * 100_000, 6)


def _pct(thousandths: int) -> str:
    return f"{thousandths / 1000:.3f}".rstrip("0").rstrip(".") + "%"
