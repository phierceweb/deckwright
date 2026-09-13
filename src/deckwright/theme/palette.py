"""Semantic colour roles, their resolved pairs, and OOXML luminance transforms."""

from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass
from functools import partial

from pf_core.log import get_logger

from deckwright.errors import ThemeError
from deckwright.utils.color import AA_LARGE, AA_NORMAL, contrast_ratio, normalize_hex

logger = get_logger(__name__)

_ACCENT = re.compile(r"^accent-(\d+)$")

AUTO_INK = "auto"
"""Pair foreground meaning "whichever declared ink reads on this background"."""

_INK_CANDIDATES = ("ink", "page")
#: Consulted only when neither of the two above reads, so a resolved pair never moves.
_FALLBACK_INK_CANDIDATES = ("inverse", "surface-ink", "inverse-ink", "surface")


def _rank_inks(resolve, background: str, roles) -> list[tuple[float, str, str]]:
    """``(ratio, label, hex)`` by contrast on ``background``, best first.

    Only colours the theme declares — a brand's ink is never invented here.
    """

    def rank(names):
        return [(contrast_ratio(resolve(n), background), n, resolve(n)) for n in names]

    ranked = sorted(rank(_INK_CANDIDATES), reverse=True)
    if ranked and ranked[0][0] >= AA_NORMAL:
        return ranked
    return sorted(ranked + rank([n for n in _FALLBACK_INK_CANDIDATES if n in roles]), reverse=True)


@dataclass(frozen=True)
class Pair:
    """A foreground colour on a background colour."""

    fg: str
    bg: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "fg", normalize_hex(self.fg))
        object.__setattr__(self, "bg", normalize_hex(self.bg))

    def contrast(self) -> float:
        """WCAG contrast ratio of this pair, 1.0 to 21.0."""
        return contrast_ratio(self.fg, self.bg)


def lum(hex_colour: str, factor: float, offset: float) -> str:
    """OOXML ``lumMod``/``lumOff``: HSL luminance scaled then offset, clamped to 0..1."""
    red, green, blue = (int(hex_colour[i : i + 2], 16) / 255 for i in (0, 2, 4))
    hue, light, sat = colorsys.rgb_to_hls(red, green, blue)
    light = min(1.0, max(0.0, light * factor + offset))
    return "".join(f"{round(c * 255):02X}" for c in colorsys.hls_to_rgb(hue, light, sat))


@dataclass(frozen=True)
class Palette:
    """Semantic colour roles plus the fg/bg pair each background offers.

    A pair below WCAG AA is logged, never refused — `deckwright qa` judges contrast against
    what was really painted.
    """

    roles: dict[str, str]
    pairs: dict[str, Pair]
    accents: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", {k: normalize_hex(v) for k, v in self.roles.items()})
        for name in self.accents:
            if name not in self.roles:
                raise ThemeError(
                    f"accent {name!r} names no declared colour role; "
                    f"declared roles: {', '.join(sorted(self.roles))}"
                )
        for name, pair in sorted(self.pairs.items()):
            ratio = pair.contrast()
            if ratio < AA_NORMAL:
                # Reported, not refused: `qa` judges it against what was really painted.
                logger.warning(
                    "theme_pair_below_aa",
                    pair=name,
                    fg=pair.fg,
                    bg=pair.bg,
                    ratio=round(ratio, 2),
                    minimum=AA_NORMAL,
                )
        self._check_inverse_stands_off_page()

    def _check_inverse_stands_off_page(self) -> None:
        """Warn when an inverse plate would vanish into the page it is laid on.

        ``surface`` is left alone: it is a deliberate recess, near the page by design.
        """
        page, inverse = self.roles.get("page"), self.roles.get("inverse")
        if page is None or inverse is None:
            return
        ratio = contrast_ratio(page, inverse)
        if ratio < AA_LARGE:
            logger.warning(
                "theme_inverse_matches_page",
                page=page,
                inverse=inverse,
                ratio=round(ratio, 2),
                minimum=AA_LARGE,
                fix="bind inverse and inverse-ink to colours that stand off the page, "
                "or re-adopt the template to rebind them",
            )

    def role(self, name: str) -> str:
        """The hex a semantic role resolves to."""
        try:
            return self.roles[name]
        except KeyError:
            raise ThemeError(
                f"no colour role {name!r}; declared roles: {', '.join(sorted(self.roles))}"
            ) from None

    def pair(self, name: str) -> Pair:
        """The fg/bg pair a background declares.

        Raises:
            ThemeError: the pair is undeclared.
        """
        try:
            return self.pairs[name]
        except KeyError:
            raise ThemeError(
                f"no colour pair {name!r}; declared pairs: {', '.join(sorted(self.pairs))}"
            ) from None

    def ink_for(self, background: str) -> str:
        """Whichever declared ink reads on an arbitrary fill.

        The same choice :data:`AUTO_INK` makes, for a fill no pair names.

        Raises:
            ThemeError: the theme declares no ink role at all.
        """
        bg = normalize_hex(background)
        ranked = _rank_inks(self.role, bg, self.roles)
        ratio, ink, hex_ = ranked[0]
        if ratio < AA_NORMAL:
            logger.warning(
                "fill_ink_below_aa",
                fill=bg,
                ink=ink,
                hex=hex_,
                ratio=round(ratio, 2),
                minimum=AA_NORMAL,
            )
        return hex_

    def tint(self, name: str, pct: int) -> str:
        """Lighten a role ``pct`` of the way to white — OOXML ``lumMod``+``lumOff``."""
        if not 0 <= pct <= 100:
            raise ThemeError(f"tint percentage must be in 0..100, got {pct}")
        return lum(self.role(name), 1 - pct / 100, pct / 100)

    def shade(self, name: str, pct: int) -> str:
        """Darken a role ``pct`` of the way to black — OOXML ``lumMod``."""
        if not 0 <= pct <= 100:
            raise ThemeError(f"shade percentage must be in 0..100, got {pct}")
        return lum(self.role(name), 1 - pct / 100, 0.0)


def build_palette(roles: dict[str, str], *, pairs: dict[str, tuple[str, str]]) -> Palette:
    """Build a palette from semantic roles and the ``(fg_role, bg_role)`` of each pair.

    A pair names roles, never hex, so rebinding a role moves every pair that cites it.
    A pair whose foreground is :data:`AUTO_INK` takes whichever declared ink reads best
    on its background.
    """
    resolved = {k: normalize_hex(v) for k, v in roles.items()}

    def role(name: str, *, pair: str) -> str:
        try:
            return resolved[name]
        except KeyError:
            raise ThemeError(
                f"colour pair {pair!r} names unknown role {name!r}; "
                f"declared roles: {', '.join(sorted(resolved))}"
            ) from None

    built: dict[str, Pair] = {}
    for name, (fg, bg) in pairs.items():
        background = role(bg, pair=name)
        if fg != AUTO_INK:
            built[name] = Pair(role(fg, pair=name), background)
            continue
        ranked = _rank_inks(partial(role, pair=name), background, resolved)
        built[name] = Pair(ranked[0][2], background)

    numbered = sorted(
        ((int(m.group(1)), name) for name in roles if (m := _ACCENT.match(name))),
    )
    return Palette(
        roles=resolved,
        pairs=built,
        accents=tuple(name for _, name in numbered),
    )
