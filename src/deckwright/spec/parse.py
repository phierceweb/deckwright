"""Parse a multi-document ``.deck.yaml`` into a :class:`DeckSpec`.

Validation is strict: an unknown or malformed field is an error, never a silent drop.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from pf_core.log import get_logger

from deckwright.errors import SpecError
from deckwright.spec._checks import (
    _check_gotos,
    _check_morphs,
    _check_section_runs,
    _refuse_bad_links,
)
from deckwright.spec._scalars import SpecLoader
from deckwright.spec._slide import _SLIDE_FIELDS, _lang, _slide  # noqa: F401 — _SLIDE_FIELDS re-exported for tests
from deckwright.spec.model import DeckSpec
from deckwright.utils.keys import refuse_unknown

logger = get_logger(__name__)

_DECK_CONFIG_FIELDS = ("theme", "title", "sections", "extends", "out", "lang")


def parse_deck(path: str | Path) -> DeckSpec:
    """Read and parse a ``.deck.yaml`` from disk."""
    path = Path(path)
    if not path.is_file():
        raise SpecError(f"spec file not found: {path}")
    return parse_deck_text(path.read_text(encoding="utf-8"), source=path)


def parse_deck_text(text: str, *, source: Path) -> DeckSpec:
    """Parse deck-spec YAML. ``source`` anchors relative paths and error messages."""
    try:
        docs = list(yaml.load_all(text, Loader=SpecLoader))
    except yaml.YAMLError as e:
        raise SpecError(f"{source.name}: invalid YAML — {e}") from e

    if not docs:
        raise SpecError(f"{source.name}: empty spec")

    config = docs[0] or {}
    if not isinstance(config, dict):
        raise SpecError(f"{source.name}: deck config: expected a mapping")
    refuse_unknown(
        config,
        _DECK_CONFIG_FIELDS,
        error=SpecError,
        where=f"{source.name}: deck config",
        suggest=True,
    )
    if not config.get("theme"):
        raise SpecError(f"{source.name}: deck config: missing required field 'theme'")

    slide_docs = [d for d in docs[1:] if d is not None]
    if not slide_docs:
        raise SpecError(f"{source.name}: no slides — a deck needs at least one slide document")

    raw_sections = config.get("sections")
    if raw_sections is None:
        raw_sections = []
    if not isinstance(raw_sections, (list, tuple)):
        raise SpecError(
            f"{source.name}: deck config: 'sections' must be a list, "
            f"got {type(raw_sections).__name__}"
        )
    sections = tuple(str(s) for s in raw_sections)
    for section in sections:
        _refuse_bad_links(section, where=f"{source.name}: deck config: sections")

    base = source.parent
    extends = (base / str(config["extends"])) if config.get("extends") else None
    if extends is not None:
        _load_extension(extends)

    slides = tuple(
        _slide(doc, index=i, sections=sections, source=source)
        for i, doc in enumerate(slide_docs, start=1)
    )
    _check_section_runs(slides, sections=sections, source=source)
    _check_gotos(slides, source=source)
    _check_morphs(slides, source=source)
    deck = DeckSpec(
        theme=str(config["theme"]),
        slides=slides,
        source=source,
        title=config.get("title"),
        sections=sections,
        out=(base / str(config["out"])) if config.get("out") else None,
        extends=extends,
        lang=_lang(config.get("lang"), where=f"{source.name}: deck config"),
    )
    logger.info("spec_parsed", source=str(source), slides=len(slides), theme=deck.theme)
    return deck


def _load_extension(path: Path) -> None:
    """Import the deck's ``extends:`` module before placements are validated.

    Late import: ``deckwright.layouts.registry`` imports this package's model.
    """
    from deckwright.layouts.registry import load_extension

    load_extension(path)
