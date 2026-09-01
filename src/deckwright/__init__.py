"""Compile declarative deck specs into branded PowerPoint files.

The command line is the main surface (``docs/cli.md``); this module is the same
compiler as a Python call, for a caller generating specs rather than writing them::

    result = deckwright.build_deck("deck.deck.yaml")

The spec wire format is ``docs/authoring.md``. There is no Python API for *composing*
a slide: a component the format cannot express is added by registering one
(``docs/extending.md``), not by calling into the layout engine.
"""

from __future__ import annotations

from importlib import metadata

from pf_core import log as _pf_log

# pf-core's implicit setup targets the root logger; claim ours before it fires.
if not _pf_log._setup_done:
    _pf_log.setup_logging(app_logger_name="deckwright")

from deckwright.compile.build import BuildResult, build_deck
from deckwright.errors import LayoutError, MissingToolError, RenderError, SpecError, ThemeError
from deckwright.theme import load_theme

try:
    __version__ = metadata.version("deckwright")
except metadata.PackageNotFoundError:  # a source tree that was never installed
    __version__ = "0.0.0.dev0"

__all__ = [
    "BuildResult",
    "LayoutError",
    "MissingToolError",
    "RenderError",
    "SpecError",
    "ThemeError",
    "build_deck",
    "load_theme",
    "__version__",
]
