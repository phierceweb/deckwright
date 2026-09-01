"""Placing photographs: how a source fits a box, and what its pixels do to text on it."""

from deckwright.imagery.backdrop import Backdrop
from deckwright.imagery.draw import place_picture, paint_scrim
from deckwright.imagery.fit import FITS, MASKS, ImageFit, fit_image, parse_aspect, square
from deckwright.imagery.paint import paint_backdrop
from deckwright.imagery.sample import cells, composite, effective_bg, solve_alpha, weakest
from deckwright.imagery.scrim import Scrim, ScrimSpec, scrim_spec

__all__ = [
    "Backdrop",
    "FITS",
    "ImageFit",
    "MASKS",
    "Scrim",
    "ScrimSpec",
    "cells",
    "composite",
    "effective_bg",
    "fit_image",
    "paint_backdrop",
    "paint_scrim",
    "parse_aspect",
    "place_picture",
    "scrim_spec",
    "solve_alpha",
    "square",
    "weakest",
]
