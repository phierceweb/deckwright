"""The colour each series and each point of a chart is filled with.

``highlight:`` is emphasis by isolation: the marked row keeps its colour and every other mark
recedes, so no other mark on the plot shares the marked one's fill.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from deckwright.charts._native_types import _PIE_FAMILY_CHART_TYPES
from deckwright.charts.model import ChartSpec
from deckwright.utils.color import delta_e, mix, stands_off

# How far a receding mark moves toward the ground: halfway, then on in steps until an ink
# reads on it at the label's size — legibility outranks how little the fade shows.
_RECEDE = tuple(0.5 + 0.05 * step for step in range(10))
# The same ladder, run from the start: a pie's quiet wedges must also stand off the ground
# they sit on, and that only gets harder past the point _RECEDE alone starts searching from.
_ISOLATE = tuple(0.05 * step for step in range(1, 10)) + _RECEDE
_WHITE, _BLACK = "FFFFFF", "000000"


@dataclass(frozen=True)
class Fills:
    """One colour per series, which its legend swatch shows, and one per point of each."""

    series: tuple[str, ...]
    points: tuple[tuple[str, ...], ...]


def chart_fills(
    spec: ChartSpec,
    *,
    accents: tuple[str, ...],
    muted: str,
    ground: str,
    legible: Callable[[str], bool],
) -> Fills:
    """Resolve every fill of ``spec`` from the theme's accents, as hex.

    Series cycle the accents; a pie's wedges go round them with no two touching alike. A
    highlight keeps the marked row's colour and recedes every other mark: one series to
    ``muted``, a pie's wedges toward ``ground`` from the marked wedge's own accent, as far as
    they can go while still standing off ``ground`` themselves, and several series each
    toward ``ground`` in its own hue. A fade goes on until ``legible`` finds an ink that
    reads on it; a grey that is not itself legible fades the same way rather than standing
    as a mid-tone no ink clears.
    """
    series = tuple(accents[i % len(accents)] for i in range(len(spec.series)))
    marked = spec.highlight
    if spec.type in _PIE_FAMILY_CHART_TYPES:
        count = len(spec.categories)
        if marked is None:
            apart = partial(_apart, accents=accents, ground=ground, legible=legible)
            return Fills(series, (_ring(accents, count, apart=apart),))
        accent = series[0]
        quiet = _quiet(accent, ground, legible=legible)
        return Fills(series, (_isolated(count, marked, accent=accent, quiet=quiet),))
    points = []
    for colour, data in zip(series, spec.series, strict=True):
        count = len(data.values or data.points or ())
        rest = colour
        if marked is not None:
            rest = (
                _grey(muted, ground, legible=legible)
                if len(spec.series) == 1
                else _recede(colour, ground, legible=legible)
            )
        points.append(tuple(colour if i == marked else rest for i in range(count)))
    return Fills(series, tuple(points))


def _ring(
    accents: tuple[str, ...], count: int, *, apart: Callable[[str, str], str]
) -> tuple[str, ...]:
    """``count`` wedge fills round a circle, no two touching wedges alike, the last included.

    A colour the distinct accents cannot supply comes from ``apart``, given its two neighbours.
    """
    colours = list(dict.fromkeys(accents))
    if len(colours) == 1 and count > 1:
        colours.append(apart(colours[0], colours[0]))
    fills = [colours[i % len(colours)] for i in range(count)]
    if count > 1 and fills[-1] == fills[0]:
        spare = [c for c in colours if c not in (fills[-2], fills[0])]
        fills[-1] = spare[0] if spare else apart(fills[-2], fills[0])
    return tuple(fills)


def _apart(
    left: str,
    right: str,
    *,
    accents: tuple[str, ...],
    ground: str,
    legible: Callable[[str], bool],
) -> str:
    """The first fade of an accent, toward the ground and then white and black, that an ink
    reads on and that stands off both neighbours; failing that, the one farthest from both."""
    fades = dict.fromkeys(
        mix(accent, toward, amount)
        for toward in (ground, _WHITE, _BLACK)
        for accent in dict.fromkeys(accents)
        for amount in _RECEDE
    )
    for fade in fades:
        if legible(fade) and stands_off(fade, left) and stands_off(fade, right):
            return fade
    return max(fades, key=lambda fade: min(delta_e(fade, left), delta_e(fade, right)))


def _recede(colour: str, ground: str, *, legible: Callable[[str], bool]) -> str:
    fades = [mix(colour, ground, amount) for amount in _RECEDE]
    return next((fade for fade in fades if legible(fade)), fades[-1])


def _quiet(accent: str, ground: str, *, legible: Callable[[str], bool]) -> tuple[str, str]:
    """Two fades of ``accent`` toward ``ground``: the fullest one the fill-ground rule still
    allows, and half that fade — so both stand off ``ground`` by less than ``accent`` itself
    (which never fades at all), and touching wedges never repeat the same level.

    ``_RECEDE`` alone can overshoot here: it starts already halfway to ``ground``, and an
    accent far from its ground in lightness can cross out of ``stands_off`` well before that
    point. Legibility still outranks it — a palette with no safe fade at all falls back to
    ``_recede``'s own answer for both levels, exactly as it would for any other mark.
    """
    fades = {amount: mix(accent, ground, amount) for amount in _ISOLATE}
    safe = [amt for amt, fade in fades.items() if stands_off(fade, ground) and legible(fade)]
    if not safe:
        worst = _recede(accent, ground, legible=legible)
        return worst, worst
    far = fades[safe[-1]]
    near = mix(accent, ground, safe[-1] / 2)
    return (near, far) if near != far else (far, _recede(far, ground, legible=legible))


def _grey(muted: str, ground: str, *, legible: Callable[[str], bool]) -> str:
    """``muted`` as it stands, unless no ink reads on it — a theme's grey is not vetted
    against a highlighted chart's own label ink, only its own pair."""
    return muted if legible(muted) else _recede(muted, ground, legible=legible)


def _isolated(count: int, marked: int, *, accent: str, quiet: tuple[str, str]) -> tuple[str, ...]:
    """The marked wedge in the accent; the rest alternate the two ``quiet`` fades, starting
    from the wedge after it, so the run of fades never shows two touching wedges alike."""
    fills = [accent] * count
    for step in range(1, count):
        fills[(marked + step) % count] = quiet[(step - 1) % 2]
    return tuple(fills)
