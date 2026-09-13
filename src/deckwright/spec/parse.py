"""Parse a multi-document ``.deck.yaml`` into a :class:`DeckSpec`.

Validation is strict: an unknown or malformed field is an error, never a silent drop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pf_core.log import get_logger

from deckwright.errors import LayoutError, SpecError
from deckwright.spec._scalars import SpecLoader
from deckwright.spec._place import place
from deckwright.utils.keys import unknown_field
from deckwright.spec.model import Background, DeckSpec, SlideSpec

logger = get_logger(__name__)

_SLIDE_FIELDS = (
    "title",
    "kicker",
    "subtitle",
    "notes",
    "section",
    "animate",
    "transition",
    "background",
    "place",
    "chrome",
)
_DECK_CONFIG_FIELDS = ("theme", "title", "sections", "extends", "out")
_BACKGROUND_FIELDS = ("image", "fit", "crop", "scrim")
_GONE = {
    "layout": (
        "'layout' is gone — a slide has no layout; put components under 'place:' "
        "and pick a backdrop with 'background:'"
    ),
    "body": (
        "'body' is gone — a component's name is its own key inside a 'place:' entry, "
        "e.g. place: [{at: {cols: full}, bullets: {items: [...]}}]"
    ),
    "reveal": (
        "'reveal' is gone — use 'animate', e.g. animate: one_at_a_time instead of reveal: per-item"
    ),
}


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
    unknown = sorted(set(config) - set(_DECK_CONFIG_FIELDS))
    if unknown:
        raise SpecError(
            f"{source.name}: deck config: {unknown_field(unknown[0], _DECK_CONFIG_FIELDS, suggest=True)}"
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

    base = source.parent
    extends = (base / str(config["extends"])) if config.get("extends") else None
    if extends is not None:
        _load_extension(extends)

    slides = tuple(
        _slide(doc, index=i, sections=sections, source=source)
        for i, doc in enumerate(slide_docs, start=1)
    )
    _check_section_runs(slides, sections=sections, source=source)
    deck = DeckSpec(
        theme=str(config["theme"]),
        slides=slides,
        source=source,
        title=config.get("title"),
        sections=sections,
        out=(base / str(config["out"])) if config.get("out") else None,
        extends=extends,
    )
    logger.info("spec_parsed", source=str(source), slides=len(slides), theme=deck.theme)
    return deck


def _load_extension(path: Path) -> None:
    """Import the deck's ``extends:`` module before placements are validated.

    Late import: ``deckwright.layouts.registry`` imports this package's model.
    """
    from deckwright.layouts.registry import load_extension

    load_extension(path)


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def _check_section_runs(
    slides: tuple[SlideSpec, ...], *, sections: tuple[str, ...], source: Path
) -> None:
    """Refuse a chapter that resumes, or that runs out of the order ``sections:`` lists.

    A slide with no section of its own sits inside the run it falls in and does not
    break it.

    Raises:
        SpecError: a section's slides are not contiguous, or its run begins before one
            ``sections:`` lists ahead of it.
    """
    ended: dict[str, int] = {}
    current: str | None = None
    last = 0
    for slide in slides:
        name = slide.section
        if name is None or name == current:
            if name is not None:
                last = slide.index
            continue
        if current is not None:
            ended[current] = last
        if name in ended:
            raise SpecError(
                f"{source.name}: slide {slide.index} resumes section {name!r}, which "
                f"ended at slide {ended[name]} when {current!r} began — a chapter runs "
                f"once, so 'sections:' cannot describe this order. Move the slide back "
                f"into its run, or give it the section it now sits in"
            )
        if (
            current in sections
            and name in sections
            and sections.index(name) < sections.index(current)
        ):
            raise SpecError(
                f"{source.name}: slide {slide.index} begins section {name!r} after "
                f"{current!r}, but 'sections:' lists {', '.join(sections)} — reorder the "
                f"slides or the list, so a nav drawn from it names the chapters in order"
            )
        current = name
        last = slide.index


def _slide(doc: Any, *, index: int, sections: tuple[str, ...], source: Path) -> SlideSpec:
    where = f"{source.name}: slide {index}"
    if not isinstance(doc, dict):
        raise SpecError(f"{where}: expected a mapping, got {type(doc).__name__}")
    for gone, hint in _GONE.items():
        if gone in doc:
            raise SpecError(f"{where}: {hint}")
    unknown = sorted(set(doc) - set(_SLIDE_FIELDS))
    if unknown:
        raise SpecError(f"{where}: {unknown_field(unknown[0], _SLIDE_FIELDS, suggest=True)}")

    section = _text(doc.get("section"))
    if section is not None and sections and section not in sections:
        raise SpecError(
            f"{where}: section {section!r} is not in the deck's sections ({', '.join(sections)})"
        )

    return SlideSpec(
        index=index,
        background=_background(doc.get("background"), where=where),
        title=_text(doc.get("title")),
        kicker=_text(doc.get("kicker")),
        subtitle=_text(doc.get("subtitle")),
        notes=_text(doc.get("notes")),
        section=section,
        animate=_text(doc.get("animate")),
        transition=_text(doc.get("transition")),
        place=place(doc.get("place"), where=where),
        chrome=_chrome(doc, where=where),
    )


def _chrome(doc: dict, *, where: str) -> dict[str, Any]:
    """The slide's per-field chrome overrides. A field with no text has nothing to place."""
    from deckwright.layouts.chrome import chrome_field

    value = doc.get("chrome")
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SpecError(
            f"{where}: 'chrome' must be a mapping of chrome field to its treatment, "
            f"got {type(value).__name__}"
        )
    out = {}
    for key, cfg in value.items():
        name = str(key)
        try:
            out[name] = chrome_field(cfg, name=name)
        except LayoutError as e:
            raise SpecError(f"{where}: {e}") from None
        if not doc.get(name):
            raise SpecError(
                f"{where}: 'chrome' sets {name!r} but the slide has no {name!r} text, "
                f"so there is no line to place"
            )
    return out


def _background(value: Any, *, where: str) -> Background:
    """The slide's surface: any palette pair by name, or a picture."""
    if value is None:
        return Background()
    if isinstance(value, str):
        return Background(kind=value)
    if isinstance(value, dict) and "image" in value:
        return _image_background(value, where=where)
    raise SpecError(
        f"{where}: 'background' must name a colour pair ('page', 'inverse', "
        f"'accent-1', …) or be a mapping with 'image:', got {value!r}"
    )


def _image_background(value: dict, *, where: str) -> Background:
    """An image backdrop and how it fills the canvas. Late imports: ``deckwright.imagery``
    reaches back into ``deckwright.theme``, which imports this package's model."""
    from deckwright.imagery.fit import FITS, parse_aspect
    from deckwright.imagery.scrim import scrim_spec

    unknown = sorted(set(value) - set(_BACKGROUND_FIELDS))
    if unknown:
        raise SpecError(
            f"{where}: background has no key {unknown[0]!r}; "
            f"known keys: {', '.join(_BACKGROUND_FIELDS)}"
        )
    fit = str(value.get("fit", "cover"))
    if fit not in FITS:
        raise SpecError(f"{where}: background fit must be one of {', '.join(FITS)}, got {fit!r}")
    place = f"{where} background"
    try:
        crop = None if value.get("crop") is None else parse_aspect(value["crop"], where=place)
        scrim = (
            None
            if value.get("scrim") is None
            else scrim_spec(value["scrim"], default_pair="inverse", where=place)
        )
    except LayoutError as e:
        raise SpecError(str(e)) from None
    return Background(kind="image", image=str(value["image"]), fit=fit, crop=crop, scrim=scrim)
