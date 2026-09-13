"""The per-slide rendering context and the deck's Python escape hatch.

A slide has no layout: its chrome and its placements come straight from the spec.
A deck's ``extends:`` module is loaded here so it can register components of its own.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pptx.dml.color import RGBColor

from pf_core.log import get_logger

from deckwright.errors import LayoutError, ThemeError
from deckwright.spec.model import SlideSpec
from deckwright.theme.model import Rect, Theme, TypeStyle
from deckwright.theme.palette import Pair
from deckwright.theme.scale import (
    Grid,
)  # not via deckwright.theme: theme/load.py imports this module
from deckwright.utils.color import AA_LARGE, contrast_ratio, required_ratio
from deckwright.utils.shapes import ALIGN, ANCHOR

if TYPE_CHECKING:  # deckwright.imagery.paint takes a ctx, so the name stays annotation-only
    from deckwright.imagery.backdrop import Backdrop

logger = get_logger(__name__)

_LOADED_EXTENSIONS: set[Path] = set()


def _clipped(plate: Rect, bounds: Rect) -> Rect:
    """``plate`` trimmed to ``bounds``, never to a negative size."""
    left = max(plate.left, bounds.left)
    top = max(plate.top, bounds.top)
    right = min(plate.left + plate.width, bounds.left + bounds.width)
    bottom = min(plate.top + plate.height, bounds.top + bounds.height)
    return Rect(left, top, max(0.0, right - left), max(0.0, bottom - top))


@dataclass(frozen=True)
class Disc:
    """A round fill in ``painted``: its frame's corners show whatever was under it."""

    fill: str


@dataclass
class SlideCtx:
    """The slide, the theme, the spec, the recorder — and the placement being drawn."""

    slide: Any
    theme: Theme
    spec: SlideSpec
    manifest: Any  # ManifestRecorder — untyped to keep imports one-way
    sections: tuple[str, ...] = ()  # deck-level section names
    component: str | None = None
    # What a composite is drawing right now — the primitive a `flow` reaches for is not
    # a key the author wrote, so it names the part instead of replacing the component.
    part: str | None = None
    body: dict[str, Any] = field(default_factory=dict)
    rect: Rect | None = None
    align: str = "left"  # the placement's horizontal text alignment
    anchor: str = "top"  # the placement's vertical text anchoring
    placements: dict[str, Rect] = field(default_factory=dict)
    base: Path | None = None  # the deck spec's own directory
    backdrop: Backdrop | None = None  # the art painted over this slide's surface
    # In paint order: a later entry covers an earlier one, fill or picture alike.
    painted: list[tuple[Rect, str | Disc | Backdrop]] = field(default_factory=list)

    @property
    def grid(self) -> Grid:
        return self.theme.grid

    @property
    def media_roots(self) -> tuple[Path, ...]:
        """Directories an image named in the deck spec is looked for in, in order."""
        return () if self.base is None else (self.base,)

    @property
    def body_rect(self) -> Rect:
        """The rectangle this placement resolved to."""
        if self.rect is None:
            raise LayoutError(f"slide {self.spec.index}: no placement rect is set")
        return self.rect

    @property
    def pair(self) -> Pair:
        """The contrast-checked pair the slide's background makes live."""
        return self.theme.palette.pair(self.spec.background.pair)

    def fg(self) -> RGBColor:
        """Text colour on this slide's background."""
        return RGBColor.from_string(self.pair.fg)

    def paper(self) -> RGBColor:
        """The colour this slide's surface is painted."""
        return RGBColor.from_string(self.pair.bg)

    def behind(
        self, rect: Rect | None = None, *, ink: str | None = None, default: str | None = None
    ) -> str:
        """The colour text of ``ink`` at ``rect`` is really on, as hex.

        The painted pair's background, or a backdrop photograph's own pixels there
        composited with any scrim. A surface covering only part of the rect is one more
        surface the line crosses, so the answer is the **worst** of them.
        """
        paper = default or self.pair.bg
        if rect is None:
            return paper
        probe = ink or self.pair.fg
        candidates = [paper if self.backdrop is None else self.backdrop.behind(rect, ink=probe)]
        for frame, surface in self.painted:
            shared = _overlap(frame, rect)
            if shared is None:
                continue
            solid = frame
            if isinstance(surface, Disc):
                colour, solid = surface.fill, _inscribed(frame)
            elif isinstance(surface, str):
                colour = surface
            else:
                colour = surface.behind(shared, ink=probe)
            candidates = [colour] if _covers(solid, rect) else [*candidates, colour]
        return min(candidates, key=lambda colour: contrast_ratio(probe, colour))

    def ink_at(self, rect: Rect, *, preferred: str, required: float = AA_LARGE) -> tuple[str, str]:
        """The ink that really reads at ``rect``, and the colour it reads on.

        A template's background is not one colour, so a slide-wide pair can put a title
        in white on white. ``preferred`` is kept where it clears, else the palette's
        other ink is tried; neither clearing leaves ``preferred`` for QA to report.
        ``required`` is the caller's threshold for the text it is about to draw.
        """
        paper = self.behind(rect, ink=preferred)
        if contrast_ratio(preferred, paper) >= required:
            return preferred, paper
        try:
            alternate = self.theme.palette.ink_for(paper)
        except ThemeError:
            return preferred, paper
        if alternate == preferred:
            return preferred, paper
        return alternate, self.behind(rect, ink=alternate)

    def plate(self, rect: Rect, *, pad: float = 0.2, within: Rect | None = None) -> str:
        """Paint the slide's own paper behind ``rect`` and return the colour laid down.

        The last resort for a line over artwork no single ink reads across. ``within``
        bounds the painted surface, so a mark's padding cannot reach the placement beside it.
        """
        from deckwright.utils.shapes import rect as fill_rect

        margin = rect.height * pad
        plate = Rect(
            max(0.0, rect.left - margin),
            max(0.0, rect.top - margin),
            rect.width + 2 * margin,
            rect.height + 2 * margin,
        )
        if within is not None:
            plate = _clipped(plate, within)
        fill = self.pair.bg
        self.manifest.record(
            fill_rect(self.slide, plate.left, plate.top, plate.width, plate.height, self.rgb(fill)),
            plate=True,
        )
        self.painted.append((plate, fill))
        return fill

    def dim(self) -> RGBColor:
        """Secondary text: the muted role on the page, the pair's own ink elsewhere."""
        if self.spec.background.pair == "page":
            return self.color("muted")
        return self.fg()

    def ink_on(self, background: str) -> str:
        """The ink that reads on a fill this component painted itself, as hex."""
        return self.theme.palette.ink_for(background)

    def accent_on(self, background: str, *, size_pt: float, name: str = "accent-1") -> str:
        """An accent as text on ``background``, as hex.

        An accent is a fill colour, never declared readable as text, so it is used only
        where it clears the ratio this point size demands and otherwise gives way.
        """
        colour = self.theme.palette.role(name)
        if contrast_ratio(colour, background) >= required_ratio(size_pt):
            return colour
        return self.ink_on(background)

    def accent(self, *, size_pt: float, name: str = "accent-1") -> str:
        """An accent as text on the slide's own background."""
        return self.accent_on(self.pair.bg, size_pt=size_pt, name=name)

    def text_ink(self, box: Rect, *, size_pt: float, muted: bool = False) -> tuple[str, str]:
        """The ink for text set in ``box``, and the colour it is really on.

        ``muted`` keeps the muted role only on the page pair, where it was vetted.
        """
        preferred = (
            self.theme.palette.role("muted")
            if muted and self.spec.background.pair == "page"
            else self.pair.fg
        )
        return self.ink_at(box, preferred=preferred, required=required_ratio(size_pt))

    def accent_at(self, box: Rect, *, size_pt: float, name: str = "accent-1") -> tuple[str, str]:
        """An accent as text in ``box``, measured against what is behind it there."""
        paper = self.behind(box, ink=self.theme.palette.role(name))
        return self.accent_on(paper, size_pt=size_pt, name=name), paper

    def text_align(self):
        """The placement's ``align:`` as a paragraph alignment."""
        return ALIGN[self.align]

    def text_anchor(self):
        """The placement's ``anchor:`` as a text-frame vertical anchor."""
        return ANCHOR[self.anchor]

    def rgb(self, hex_colour: str) -> RGBColor:
        return RGBColor.from_string(hex_colour)

    def color(self, role: str) -> RGBColor:
        return RGBColor.from_string(self.theme.palette.role(role))

    def style(self, role: str) -> TypeStyle:
        return self.theme.style(role)


def load_extension(path: str | Path) -> None:
    """Import a deck-local module so its ``@component`` registrations take effect.

    Idempotent: re-importing the same file would re-run its decorators and hit the
    duplicate-registration guard, breaking a build→qa→rebuild loop in one process.
    """
    path = Path(path)
    if not path.is_file():
        raise LayoutError(f"extension module not found: {path}")
    resolved = path.resolve()
    if resolved in _LOADED_EXTENSIONS:
        return
    spec = importlib.util.spec_from_file_location(f"deckwright_ext_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise LayoutError(f"failed to import extension module: {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise LayoutError(f"failed to import extension module {path}: {e}") from e
    _LOADED_EXTENSIONS.add(resolved)
    logger.info("layout_extension_loaded", path=str(path))


def _covers(outer: Rect, inner: Rect) -> bool:
    """True when ``outer`` fully contains ``inner``."""
    return (
        outer.left <= inner.left
        and outer.top <= inner.top
        and outer.right >= inner.right
        and outer.bottom >= inner.bottom
    )


def _inscribed(frame: Rect) -> Rect:
    """The square a circle drawn in ``frame`` fully covers."""
    side = min(frame.width, frame.height) / 2**0.5
    return Rect(
        frame.left + (frame.width - side) / 2, frame.top + (frame.height - side) / 2, side, side
    )


def _overlap(outer: Rect, inner: Rect) -> Rect | None:
    """The part of ``inner`` that lies over ``outer``, or None if they miss.

    Text half over a photograph is measured against the half that is, because the
    unreadable part is the part that decides whether the line can be read.
    """
    left, top = max(outer.left, inner.left), max(outer.top, inner.top)
    right, bottom = min(outer.right, inner.right), min(outer.bottom, inner.bottom)
    if right <= left or bottom <= top:
        return None
    return Rect(left, top, right - left, bottom - top)
