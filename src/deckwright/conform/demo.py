"""Every capability in one deck, against a theme named rather than derived.

The catalogue is :data:`deckwright.conform.exercise.EXERCISE` — the same slides ``conform``
drives against real templates, so it cannot fall behind the library.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pf_core.log import get_logger

from deckwright.compile.build import build_deck, resolve_theme, theme_dir
from deckwright.conform import assemble
from deckwright.conform.exercise import EXERCISE
from deckwright.errors import ThemeError
from deckwright.paths import scratch

logger = get_logger(__name__)


def demo(
    theme: str, outdir: str | Path, *, exercises: dict[str, dict[str, Any]] | None = None
) -> Path:
    """Build the whole catalogue into one deck; returns its path.

    Raises:
        ThemeError: no theme of that name.
        LayoutError: a capability this theme cannot carry. ``conform`` builds each
            alone and reports every failure rather than stopping at the first.
    """
    outdir = Path(outdir)
    theme_path = resolve_theme(theme).resolve()
    if not theme_path.is_file():
        raise ThemeError(
            f"no theme named {theme!r} at {theme_path} — name one in "
            f"{theme_dir()}, or onboard a template with 'deckwright conform'"
        )
    slides = list((exercises or EXERCISE).values())
    dest = outdir / f"{theme} capabilities.pptx"
    source = outdir / f"{theme} capabilities.deck.yaml"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        assemble.fill(
            assemble.spec(slides, theme=theme, out=dest.name),
            assemble.assets(scratch(outdir)),
        ),
        encoding="utf-8",
    )
    build_deck(source, theme_path=theme_path, out=dest)
    logger.info("demo_built", theme=theme, slides=len(slides), deck=str(dest))
    return dest
