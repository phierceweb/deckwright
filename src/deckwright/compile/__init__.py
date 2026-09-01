"""Compile a deck spec into a .pptx plus its build manifest."""

from deckwright.compile.build import BuildResult, build_deck
from deckwright.compile.record import ShapeRecord, SlideRecord
from deckwright.compile.manifest import ManifestRecorder

__all__ = ["BuildResult", "ManifestRecorder", "ShapeRecord", "SlideRecord", "build_deck"]
