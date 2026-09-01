"""The slide-wide photograph, and what it does to the ink over it.

A slide painted on an image has no single background colour. :class:`Backdrop` keeps the
placed picture and its scrim together so any text can ask what is *really* underneath
it, and the manifest can record that instead of the pair's nominal paper.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from deckwright.imagery.fit import ImageFit
from deckwright.imagery.sample import cells, composite, effective_bg, weakest
from deckwright.imagery.scrim import Scrim, gradient_fraction
from deckwright.theme.model import Rect


@dataclass(frozen=True)
class Backdrop:
    """A picture covering (part of) the canvas, the paint under it, the scrim over it."""

    path: Path
    fit: ImageFit
    base: str  # the painted colour the picture sits on
    scrim: Scrim | None = None

    def behind(self, rect: Rect, *, ink: str) -> str:
        """The colour text of ``ink`` at ``rect`` is really on, as hex.

        Sampled from the pixels the picture actually shows there, then composited
        with the scrim at the opacity the scrim reaches over that band.
        """
        scrim = self.scrim
        window = self.fit.window_under(rect)
        if window is None:
            return self.base if scrim is None else composite(self.base, scrim.colour, scrim.opacity)
        sampled = cells(self.path, window, base=self.base)
        if scrim is None:
            return weakest(sampled, ink=ink)
        return effective_bg(
            sampled, ink=ink, scrim=scrim.colour, alpha=scrim.opacity * self._fraction(scrim, rect)
        )

    def _fraction(self, scrim: Scrim, rect: Rect) -> float:
        dest = self.fit.dest
        return gradient_fraction(
            scrim.gradient,
            band_top=(rect.top - dest.top) / dest.height,
            band_bottom=(rect.bottom - dest.top) / dest.height,
        )
