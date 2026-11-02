"""deckwright command-line entry point.

``_app.py`` holds the Typer app and its ``--verbose`` / ``--version`` callback;
``_run.py`` maps what a command raises to a message and an exit code.
"""

from __future__ import annotations

import io
import sys

from deckwright.cli._app import app
from deckwright.cli._run import run_cli
from deckwright.cli import build, glyphs, onboarding, reading  # noqa: F401 — import registers the commands
from deckwright.config import load_env

__all__ = ["app", "main"]


def main() -> None:
    # Findings quote deck copy, which carries em dashes and curly quotes whatever the
    # console encoding is. Without this a legacy code page raises instead of printing.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
    load_env()
    run_cli(app)
