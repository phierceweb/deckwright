"""The per-slide context, the deck's extension hook, and slide composition."""

from deckwright.layouts.chrome import (
    CHROME_ORDER,
    ChromeBand,
    ChromeField,
    chrome_bands,
    chrome_field,
)
from deckwright.layouts.compose import render_slide
from deckwright.layouts.place import (
    Placed,
    Reserved,
    check_placements,
    content_rect,
    resolve_at,
)
from deckwright.layouts.registry import SlideCtx, load_extension

__all__ = [
    "CHROME_ORDER",
    "ChromeBand",
    "ChromeField",
    "Placed",
    "Reserved",
    "SlideCtx",
    "check_placements",
    "chrome_bands",
    "chrome_field",
    "content_rect",
    "load_extension",
    "render_slide",
    "resolve_at",
]
