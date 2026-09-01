"""Colour maths shared by the palette and the QA contrast check."""

from __future__ import annotations

import re

from deckwright.errors import ThemeError

AA_NORMAL = 4.5
AA_LARGE = 3.0
LARGE_PT = 18.0
"""Point size at which WCAG's large-text allowance starts. AA also allows 14pt bold,
which both the components and the QA check deliberately treat as normal."""

_HEX = re.compile(r"^[0-9A-F]{6}$")


def normalize_hex(value: str) -> str:
    """Uppercase 6-digit hex with any leading ``#`` stripped."""
    text = str(value).strip().lstrip("#").upper()
    if not _HEX.match(text):
        raise ThemeError(f"{value!r} is not a 6-digit hex colour")
    return text


def relative_luminance(hex_colour: str) -> float:
    """WCAG relative luminance of a 6-digit hex colour."""
    value = normalize_hex(hex_colour)
    channels = []
    for offset in (0, 2, 4):
        c = int(value[offset : offset + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two hex colours, 1.0 to 21.0."""
    a, b = relative_luminance(foreground), relative_luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def required_ratio(size_pt: float) -> float:
    """The WCAG AA ratio text of this size must clear."""
    return AA_LARGE if size_pt >= LARGE_PT else AA_NORMAL
