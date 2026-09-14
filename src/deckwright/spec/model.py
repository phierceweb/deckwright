"""Deck-spec value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # deckwright.layouts imports this module, so the name stays annotation-only
    from deckwright.imagery.scrim import ScrimSpec
    from deckwright.layouts.chrome import ChromeField

# Only the kinds whose pair is not simply their own name. Anything else names a pair
# in the theme's palette — an accent, a surface — and the palette validates it.
_PAIR_FOR_KIND = {"image": "inverse"}


@dataclass(frozen=True)
class Background:
    """The slide's backdrop. ``kind`` selects which colour pair is live on it.

    ``fit``, ``crop`` and ``scrim`` only mean anything to an image backdrop.
    """

    kind: str = "page"  # page | inverse | image
    image: str | None = None
    fit: str = "cover"
    crop: float | None = None  # aspect the source is trimmed to, width ÷ height
    scrim: ScrimSpec | None = None

    @property
    def pair(self) -> str:
        """The palette pair this backdrop makes live — the one its text must use."""
        return _PAIR_FOR_KIND.get(self.kind, self.kind)


# What `goto:` takes besides a slide id: a jump relative to the running show.
GOTO_JUMPS = ("first", "previous", "next", "last")


@dataclass(frozen=True)
class Placement:
    """One component, the mapping it reads, and where it goes.

    ``at`` is validated but still grid-relative — ``layouts/place.py`` resolves inches.
    """

    at: dict[str, Any]
    component: str
    body: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
    reveals: str | None = None
    goto: str | None = None  # a slide id, or a relative jump in GOTO_JUMPS
    bleed: bool = False
    align: str = "left"
    anchor: str = "top"
    where: str = field(default="", compare=False)  # how refusals name it: "…: placement 2: split 1"


@dataclass(frozen=True)
class SlideSpec:
    """One slide: optional chrome, a backdrop, and its placements.

    ``chrome`` overrides the theme's treatment field by field.
    """

    index: int  # 1-based, for error messages and the manifest
    id: str | None = None  # what a placement's goto: names
    lang: str | None = None  # the language this slide's CJK text is in, over the deck's
    background: Background = Background()
    title: str | None = None
    kicker: str | None = None
    subtitle: str | None = None
    notes: str | None = None
    section: str | None = None
    animate: str | None = None
    transition: str | None = None
    place: tuple[Placement, ...] = ()
    chrome: dict[str, ChromeField] = field(default_factory=dict)


@dataclass(frozen=True)
class DeckSpec:
    """A parsed ``.deck.yaml``."""

    theme: str
    slides: tuple[SlideSpec, ...]
    source: Path
    title: str | None = None
    sections: tuple[str, ...] = ()
    out: Path | None = None
    extends: Path | None = None
    lang: str | None = None  # a BCP 47 tag: which language Han-only text is written in
