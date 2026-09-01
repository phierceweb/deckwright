"""Write harvested words back out as a draft ``.deck.yaml``, or as a transcript.

Undesigned by construction: every placement is a full-width band, and whatever the grid
cannot hold is named in a comment rather than dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import yaml

from deckwright.spec._fit import band, bullet_budget, column_up, content_band, fit
from deckwright.theme.load import load_theme
from deckwright.theme.model import Rect, Theme
from deckwright.utils.naming import NO_FOLD, deck_filename, slug_and_title

if TYPE_CHECKING:
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


def _slide_doc(slide: SlideContent, *, theme: Theme, budget: int, rect: Rect) -> _SlideDoc:
    doc: dict = {}
    pair = _background(slide.background_rgb, theme)
    if pair and pair != "page":  # page is the default and stays unwritten
        doc["background"] = pair
    for field in ("kicker", "title", "subtitle", "notes"):
        value = getattr(slide, field)
        if value:
            doc[field] = value
    items, spilled = fit(slide, theme=theme, band=rect)
    place: list[dict] = [{"at": {"cols": "full"}, **item.body} for item in items]
    band(place, [item.rows for item in items], rows=theme.grid.rows)
    spilled += column_up(place, budget=budget, rows=theme.grid.rows)
    if place:
        doc["place"] = place
    painted = slide.background_rgb if slide.background_rgb and pair is None else None
    return _SlideDoc(doc or {"title": "(empty slide)"}, spilled, painted)


def draft_spec(
    slides: list[SlideContent],
    *,
    title: str,
    theme: str = "base",
    out: str | None = None,
    source: str = "a deck",
) -> Draft:
    """The draft ``.deck.yaml`` for ``slides`` — valid, buildable, undesigned.

    ``theme`` is loaded, not just named: a placement's ``rows:`` indexes that theme's
    own grid, which ``scale: {rows: N}`` moves.

    Raises:
        ThemeError: ``theme`` names no theme file and no packaged theme.
    """
    loaded = load_theme(theme)
    config = {"theme": theme, "title": title, "out": out or _default_out(title)}
    parts = [_HEADER.format(source=source) + _dump(config)]
    unplaced = 0
    for slide in slides:
        rect = content_band(slide, loaded)
        drafted = _slide_doc(slide, theme=loaded, budget=bullet_budget(loaded, rect), rect=rect)
        unplaced += len(drafted.spilled)
        comments = "".join(f"# not converted: {_comment(it)}\n" for it in _losses(slide.dropped))
        if drafted.painted:
            comments += _PAINTED.format(rgb=_comment(drafted.painted))
        if drafted.spilled:
            comments += _SPILLED + "".join(f"#   {_comment(line)}\n" for line in drafted.spilled)
        parts.append(comments + _dump(drafted.doc))
    return Draft("---\n".join(parts), unplaced)


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
        for block in slide.blocks:
            lines += [f"- {line}" for line in block] + [""]
        for grid in slide.tables:
            if not grid:
                continue
            lines.append("| " + " | ".join(grid[0]) + " |")
            lines.append("|" + "---|" * len(grid[0]))
            lines += ["| " + " | ".join(row) + " |" for row in grid[1:]]
            lines.append("")
        if slide.notes:
            lines += [f"> {line}" for line in slide.notes.splitlines()] + [""]
        for item in _losses(slide.dropped):
            lines += [f"*not converted: {item}*", ""]
    return "\n".join(lines).rstrip() + "\n"
