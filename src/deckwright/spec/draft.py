"""Write harvested words back out as a draft ``.deck.yaml``, or as a transcript.

Undesigned by construction: every placement is a full-width band, and whatever the grid
cannot hold is named in a comment rather than dropped.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

import yaml

from deckwright.spec._fit import column_up, content_band, lay_out, loose
from deckwright.theme.load import load_theme
from deckwright.theme.model import Rect, Theme
from deckwright.utils.naming import NO_FOLD, deck_filename, slug_and_title

if TYPE_CHECKING:
    from deckwright.spec._recover import Recovered
    from deckwright.spec.extract import SlideContent, _Lines

_UNNAMEABLE = "deck"

_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")

_SPILLED = "# more than one slide holds — these did not fit, and are yours to place:\n"
_PAINTED = "# this slide was painted {rgb}; name a background pair\n"

_HEADER = """\
# Drafted by `deckwright extract` from {source}.
#
# A starting point: it carries the words — chrome, bullets, tables, notes — and none
# of the design decisions. Read docs/treatments.md before this goes anywhere; a deck
# of one repeated rectangle is what an unedited draft looks like.
"""


@dataclass(frozen=True)
class Draft:
    """A draft spec, and how many harvested lines it holds as a comment rather than
    as a placement."""

    text: str
    spilled: int
    media: dict[str, bytes] = field(default_factory=dict)  # path beside the draft -> bytes


@dataclass(frozen=True)
class _SlideDoc:
    """One slide's document, the harvested lines it could not place, and the comment
    on its backdrop, if that colour is one no pair of the theme owns."""

    doc: dict
    spilled: _Lines
    painted: str | None = None


def _comment(text: str) -> str:
    """A YAML comment ends at the first control character, so no line may carry one."""
    return _CONTROL.sub(" ", text).strip()


def _dump(doc: dict) -> str:
    return yaml.safe_dump(doc, sort_keys=False, width=NO_FOLD, allow_unicode=True)


def _default_out(title: str) -> str:
    """Where the draft's build lands, relative to the spec written beside the deck."""
    slug, _ = slug_and_title(title, fallback=_UNNAMEABLE)
    return f"out/{slug}/{deck_filename(title).strip(' .') or slug} v1.pptx"


def _losses(dropped: _Lines) -> list[str]:
    """One line per kind of shape, counted rather than listed."""
    by_kind: dict[str, list[str]] = {}
    for item in dropped:
        by_kind.setdefault(item.split(" ", 1)[0], []).append(item)
    return [
        found[0] if len(found) == 1 else f"{len(found)} × {kind}" for kind, found in by_kind.items()
    ]


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


def _slide_doc(slide: SlideContent, *, theme: Theme, rect: Rect) -> _SlideDoc:
    doc: dict = {}
    pair = _background(slide.background_rgb, theme)
    if pair and pair != "page":  # page is the default and stays unwritten
        doc["background"] = pair
    for key in ("kicker", "title", "subtitle", "notes", "animate", "transition"):
        value = getattr(slide, key)
        if value:
            doc[key] = value
    if slide.placed:
        place = [_entry(item, theme=theme) for item in slide.placed]
        # What no placement drew was added by hand: named, since there is no band to set
        # it in that the placements read back do not already use.
        spilled = loose(slide) + column_up(place, theme=theme, band=rect)
    else:
        place, spilled = lay_out(slide, theme=theme, area=rect)
    if place:
        doc["place"] = place
    painted = slide.background_rgb if slide.background_rgb and pair is None else None
    return _SlideDoc(doc or {"title": "(empty slide)"}, spilled, painted)


def _entry(item: Recovered, *, theme: Theme) -> dict:
    """A placement read back, at the box it sat in, named as it was."""
    entry: dict = {"at": {"box": _box(*item.box)}}
    for key in ("id", "morph", "reveals"):
        if getattr(item, key):
            entry[key] = getattr(item, key)
    pair = _pair(item.painted, theme)
    if pair is None:
        return {**entry, **item.body}
    ((component, fields),) = item.body.items()
    return {**entry, component: {"pair": pair, **fields}}


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


def draft_spec(
    slides: list[SlideContent],
    *,
    title: str,
    theme: str = "base",
    out: str | None = None,
    source: str = "a deck",
    media: str | None = None,
) -> Draft:
    """The draft ``.deck.yaml`` for ``slides`` — valid, buildable, undesigned.

    ``theme`` is loaded, not just named: a placement's ``rows:`` indexes that theme's
    own grid, which ``scale: {rows: N}`` moves. A picture drafted as an ``image:`` names
    its file in ``media``, a folder beside the draft; the files are :attr:`Draft.media`.

    Raises:
        ThemeError: ``theme`` names no theme file and no packaged theme.
    """
    loaded = load_theme(theme)
    config = {"theme": theme, "title": title, "out": out or _default_out(title)}
    parts = [_HEADER.format(source=source) + _dump(config)]
    unplaced = 0
    folder = media or f"{slug_and_title(title, fallback=_UNNAMEABLE)[0]}.media"
    files: dict[str, bytes] = {}
    for harvested in slides:
        slide, found = _filed(harvested, folder=folder)
        files.update(found)
        rect = content_band(slide, loaded)
        drafted = _slide_doc(slide, theme=loaded, rect=rect)
        unplaced += len(drafted.spilled)
        comments = "".join(f"# not converted: {_comment(it)}\n" for it in _losses(slide.dropped))
        comments += "".join(f"# alt text on {_comment(it)}\n" for it in slide.alt)
        comments += "".join(f"# {_comment(it)}\n" for it in slide.remarks)
        if drafted.painted:
            comments += _PAINTED.format(rgb=_comment(drafted.painted))
        if drafted.spilled:
            comments += _SPILLED + "".join(f"#   {_comment(line)}\n" for line in drafted.spilled)
        parts.append(comments + _dump(drafted.doc))
    return Draft("---\n".join(parts), unplaced, files)


def _filed(slide: SlideContent, *, folder: str) -> tuple[SlideContent, dict[str, bytes]]:
    """``slide`` with each picture named by its file in ``folder``, and those files —
    a picture the slide has no room for is written too, for the author to place."""
    pictures = tuple(replace(p, name=f"{folder}/{p.name}") for p in slide.pictures)
    files = {p.name: p.blob for p in pictures}
    placed = []
    for item in slide.placed:
        if item.media:
            image = item.body["image"]
            item = replace(item, body={"image": {**image, "src": f"{folder}/{image['src']}"}})
            files.update((f"{folder}/{name}", blob) for name, blob in item.media)
        placed.append(item)
    return replace(slide, pictures=pictures, placed=tuple(placed)), files


def render_spec(
    slides: list[SlideContent],
    *,
    title: str,
    theme: str = "base",
    out: str | None = None,
    source: str = "a deck",
) -> str:
    """The draft's text alone — :func:`draft_spec` also counts what did not fit."""
    return draft_spec(slides, title=title, theme=theme, out=out, source=source).text


def _grids(item: Recovered) -> list[tuple[tuple[str, ...], ...]]:
    """A table read back, or a chart's data, as rows for the transcript."""
    if "table" in item.body:
        table = item.body["table"]
        return [tuple(tuple(str(c) for c in row) for row in [table["header"], *table["rows"]])]
    if "chart" in item.body:
        return [_chart_grid(item.body["chart"])]
    return []


def _chart_grid(block: dict) -> tuple[tuple[str, ...], ...]:
    data = block["data"]
    if "values" in data[0]:
        names = list(data[0]["values"])
        head = ("category", *names)
        rows = [(str(r["category"]), *(str(r["values"][n]) for n in names)) for r in data]
    else:
        head = ("category", "value")
        rows = [(str(r["category"]), str(r["value"])) for r in data]
    return (head, *rows)


def _picture(alt: str | None) -> str:
    return f"*picture: {alt}*" if alt else "*picture, with no alt text*"


def render_markdown(slides: list[SlideContent], *, title: str) -> str:
    """The deck's words, slide by slide — the shape ``compile/content.py`` writes."""
    lines = [f"# {title}", "", f"{len(slides)} slide(s), read from the file. Not a build.", ""]
    for slide in slides:
        lines += ["---", "", f"## Slide {slide.index}", ""]
        if slide.kicker:
            lines += [f"**{slide.kicker}**", ""]
        if slide.title:
            lines += [f"### {slide.title}", ""]
        if slide.subtitle:
            lines += [slide.subtitle, ""]
        grids = list(slide.tables) + [_chart_grid(c) for c in slide.charts]
        for placed in slide.placed:
            if "image" in placed.body:
                lines += [_picture(placed.body["image"].get("alt")), ""]
            if placed.words:
                lines += [f"- {word}" for word in placed.words] + [""]
            grids += _grids(placed)
        for block in (*slide.blocks, *(tuple(card.values()) for card in slide.cards)):
            lines += [f"- {line}" for line in block] + [""]
        for grid in grids:
            if not grid:
                continue
            lines.append("| " + " | ".join(grid[0]) + " |")
            lines.append("|" + "---|" * len(grid[0]))
            lines += ["| " + " | ".join(row) + " |" for row in grid[1:]]
            lines.append("")
        if slide.notes:
            lines += [f"> {line}" for line in slide.notes.splitlines()] + [""]
        for found in slide.pictures:
            lines += [_picture(found.alt), ""]
        for item in _losses(slide.dropped):
            lines += [f"*not converted: {item}*", ""]
        for item in slide.alt:
            lines += [f"*alt text on {item}*", ""]
    return "\n".join(lines).rstrip() + "\n"
