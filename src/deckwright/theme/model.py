"""Theme value objects: type styles, rectangles, and the resolved theme.

All measurements are inches; conversion to EMU happens at the python-pptx boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from deckwright.errors import ThemeError
from deckwright.theme.chartstyle import ChartStyle
from deckwright.theme.palette import Palette
from deckwright.theme.surface import Surface

if TYPE_CHECKING:  # every consumer imports these from deckwright.theme, never from here
    from deckwright.layouts.chrome import ChromeField
    from deckwright.layouts.place import Reserved
    from deckwright.theme.scale import Grid, Scale


@dataclass(frozen=True)
class TypeStyle:
    """One rung of the type ramp, in points per inch of canvas height."""

    rung: float
    scale: Scale
    bold: bool = False
    italic: bool = False
    face: str | None = None  # resolved typeface; None means the theme's body face

    def __post_init__(self) -> None:
        if self.rung <= 0:
            raise ThemeError(f"type rung must be positive, got {self.rung}")

    @property
    def size(self) -> float:
        """Resolved point size on this canvas."""
        return self.scale.pt(self.rung)


@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle in inches."""

    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    def inset(self, dx: float, dy: float) -> Rect:
        """Shrink by ``dx`` on each side and ``dy`` top and bottom."""
        return Rect(self.left + dx, self.top + dy, self.width - 2 * dx, self.height - 2 * dy)


@dataclass(frozen=True)
class Transition:
    """How the show arrives *at* a slide, from the one before it.

    ``kind`` of ``"none"`` writes no ``<p:transition>`` at all — the hard cut a deck
    gets when its theme says nothing about transitions.
    """

    kind: str = "none"
    direction: str = ""
    speed: str = "fast"


# A component reports what it *is*; the theme decides how that kind of thing moves.
DEFAULT_MOTION_ROLES = {
    "text": "fade",  # bullets, callouts, copy
    "surface": "fade",  # cards, panels, plates
    "line": "wiperight",  # rule, connector — a line draws itself
    "datum": "wipeup",  # chart elements grow out of the axis
    "figure": "fade",  # images, document cards, icons
}


@dataclass(frozen=True)
class Motion:
    """The brand's motion language: how a reveal is paced, and how slides arrive.

    ``stagger_ms`` offsets each shape after the first within one click; ``0`` keeps
    them simultaneous. ``advance: after_previous`` chains a ``one_at_a_time`` build's
    groups onto one click, ``beat_ms`` apart. ``roles`` binds each semantic motion
    role to a wire-format entrance kind.
    """

    stagger_ms: int = 0
    advance: str = "on_click"
    beat_ms: int = 400
    roles: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MOTION_ROLES))
    transition: Transition = field(default_factory=lambda: Transition())


@dataclass(frozen=True)
class Theme:
    """A resolved theme: palette from the template, geometry from YAML."""

    name: str
    template: Path | None
    drop_template_slides: bool
    palette: Palette
    scale: Scale
    face: str  # body typeface
    mono: str
    ramp: dict[str, TypeStyle]
    min_pt: float
    grid: Grid
    line_weight: float  # pt, stroke weight for a chart line series
    chart: ChartStyle  # aesthetic knobs read by charts/native.py
    motion: Motion = field(default_factory=Motion)
    marks: dict[str, dict] = field(default_factory=dict)
    reserve: tuple[Reserved, ...] = ()
    chrome: dict[str, ChromeField] = field(default_factory=dict)
    hash: str = ""  # identity for panel cache keys
    heading_face: str = ""  # display typeface; empty means fall back to face
    compose_layout: str | None = None  # the template layout named by the theme, if any
    surface: Surface | None = None  # what the template already paints behind a slide
    icons: Path | None = None  # a directory of .svg glyphs searched before the built-in set
    ea: dict[str, str] = field(default_factory=dict)  # CJK face per script key in EA_SCRIPTS

    def font_for(self, style: TypeStyle) -> str:
        """The typeface a ramp rung renders in — its own face, else the body face."""
        return style.face or self.face

    def style(self, role: str) -> TypeStyle:
        """Resolve a type-ramp role to a ``TypeStyle``."""
        try:
            return self.ramp[role]
        except KeyError:
            raise ThemeError(
                f"theme {self.name!r} has no type role {role!r}; "
                f"known roles: {', '.join(sorted(self.ramp))}"
            ) from None
