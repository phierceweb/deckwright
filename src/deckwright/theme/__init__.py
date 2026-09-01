"""Theme loading: the built-in design system, optionally specialized into a template."""

from deckwright.theme.chartstyle import ChartStyle
from deckwright.theme.defaults import (
    DEFAULT_PALETTE,
    DEFAULT_RAMP,
    DEFAULT_ROLES,
    blank_presentation,
    default_theme,
)
from deckwright.theme.load import load_theme
from deckwright.theme.model import Theme, TypeStyle
from deckwright.theme.palette import Pair, Palette, build_palette
from deckwright.theme.scale import Grid, Scale

__all__ = [
    "DEFAULT_PALETTE",
    "DEFAULT_RAMP",
    "DEFAULT_ROLES",
    "ChartStyle",
    "Grid",
    "Pair",
    "Palette",
    "Scale",
    "Theme",
    "TypeStyle",
    "blank_presentation",
    "build_palette",
    "default_theme",
    "load_theme",
]
