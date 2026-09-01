"""Drive a brand template through every capability and report what it can carry."""

from deckwright.conform.adopt import Adoption, install, plan
from deckwright.conform.derive import derive, notes
from deckwright.conform.run import Conformance, conform

__all__ = ["Adoption", "Conformance", "conform", "derive", "install", "notes", "plan"]
