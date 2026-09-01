"""The translucent layer between a photograph and the text on it.

A scrim's colour and its ink are one contrast-checked palette pair, so full opacity is
guaranteed legible. :func:`resolve` measures how little of that colour these particular
pixels need in order to still clear WCAG AA.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deckwright.errors import LayoutError
from deckwright.imagery.sample import Cell, effective_bg, solve_alpha
from deckwright.theme.palette import Palette
from deckwright.utils.color import contrast_ratio

GRADIENTS = ("none", "top", "bottom")
AUTO = "auto"

_SCRIM_KEYS = ("pair", "opacity", "gradient")


@dataclass(frozen=True)
class ScrimSpec:
    """What an author asked for. ``opacity`` of None means "solve it from the pixels"."""

    pair: str
    opacity: float | None = None
    gradient: str = "none"


@dataclass(frozen=True)
class Scrim:
    """A resolved scrim: the colour to lay down, the ink that reads on it, how opaque."""

    colour: str
    ink: str
    opacity: float
    gradient: str = "none"

    def bg_over(self, sampled: tuple[Cell, ...], *, fraction: float = 1.0) -> str:
        """The colour behind ink sitting where the scrim reaches ``fraction`` of its peak."""
        return effective_bg(sampled, ink=self.ink, scrim=self.colour, alpha=self.opacity * fraction)


def scrim_spec(cfg: Any, *, default_pair: str, where: str) -> ScrimSpec:
    """Validate a ``scrim:`` mapping. ``true`` is shorthand for an auto solve."""
    if cfg is True:
        return ScrimSpec(pair=default_pair)
    if not isinstance(cfg, dict):
        raise LayoutError(
            f"{where}: 'scrim' must be a mapping of {', '.join(_SCRIM_KEYS)} "
            f"(or true for an auto-solved one), got {type(cfg).__name__}"
        )
    unknown = sorted(set(cfg) - set(_SCRIM_KEYS))
    if unknown:
        raise LayoutError(
            f"{where}: scrim has no key {unknown[0]!r}; known keys: {', '.join(_SCRIM_KEYS)}"
        )
    gradient = str(cfg.get("gradient", "none"))
    if gradient not in GRADIENTS:
        raise LayoutError(
            f"{where}: scrim gradient must be one of {', '.join(GRADIENTS)}, got {gradient!r}"
        )
    return ScrimSpec(
        pair=str(cfg.get("pair", default_pair)),
        opacity=_opacity(cfg.get("opacity"), where=where),
        gradient=gradient,
    )


def _opacity(value: Any, *, where: str) -> float | None:
    if value is None or value == AUTO:
        return None
    try:
        opacity = float(value)
    except (TypeError, ValueError):
        raise LayoutError(
            f"{where}: scrim opacity is a fraction 0..1 or {AUTO!r}, got {value!r}"
        ) from None
    if not 0.0 <= opacity <= 1.0:
        raise LayoutError(f"{where}: scrim opacity is a fraction 0..1 or {AUTO!r}, got {opacity}")
    return opacity


def resolve(
    spec: ScrimSpec,
    *,
    palette: Palette,
    sampled: tuple[Cell, ...],
    required: float,
    fraction: float = 1.0,
    where: str,
) -> Scrim:
    """Turn a declared scrim into a drawable one against the pixels it will cover.

    ``fraction`` is how much of the scrim's peak opacity actually reaches the text —
    1.0 under a flat scrim, less under a gradient whose clear end the text runs into.
    An auto opacity is solved so that even that weakest point clears ``required``.
    """
    pair = palette.pair(spec.pair)
    if spec.opacity is not None:
        return Scrim(pair.bg, pair.fg, spec.opacity, spec.gradient)
    if fraction <= 0:
        raise LayoutError(
            f"{where}: an auto scrim cannot be solved here — a {spec.gradient!r} "
            f"gradient is fully clear where this text sits, so no opacity makes it "
            f"legible; give the scrim an explicit 'opacity:' or drop the gradient"
        )
    needed = solve_alpha(sampled, ink=pair.fg, scrim=pair.bg, required=required)
    peak = needed / fraction
    if peak > 1.0:
        raise LayoutError(
            f"{where}: a {spec.gradient!r} gradient scrim cannot make this legible — "
            f"the text reaches far enough into the clear end that it would need "
            f"{peak:.0%} peak opacity; move the text toward the {spec.gradient} edge "
            f"or use a flat scrim"
        )
    return Scrim(pair.bg, pair.fg, peak, spec.gradient)


def gradient_fraction(gradient: str, *, band_top: float, band_bottom: float) -> float:
    """How much of a gradient's peak opacity reaches a band, at the band's weakest point.

    ``band_top``/``band_bottom`` are fractions down the scrim's own rectangle. A
    ``bottom`` gradient is weakest at the band's top edge, a ``top`` one at its bottom.
    """
    if gradient == "none":
        return 1.0
    if gradient == "bottom":
        return max(0.0, min(1.0, band_top))
    if gradient == "top":
        return max(0.0, min(1.0, 1.0 - band_bottom))
    raise LayoutError(
        f"unknown scrim gradient {gradient!r}; expected one of {', '.join(GRADIENTS)}"
    )


def checked(
    scrim: Scrim, *, sampled: tuple[Cell, ...], required: float, fraction: float = 1.0
) -> tuple[str, float]:
    """The background an explicit scrim really produces, and its measured ratio."""
    bg = scrim.bg_over(sampled, fraction=fraction)
    return bg, contrast_ratio(scrim.ink, bg)
