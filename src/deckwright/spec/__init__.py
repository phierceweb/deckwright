"""The declarative deck spec."""

from deckwright.spec.model import Background, DeckSpec, Placement, SlideSpec
from deckwright.spec.parse import parse_deck, parse_deck_text

__all__ = ["Background", "DeckSpec", "Placement", "SlideSpec", "parse_deck", "parse_deck_text"]
