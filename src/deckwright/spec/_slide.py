"""Parse one slide document into a :class:`SlideSpec`."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from deckwright.errors import LayoutError, SpecError
from deckwright.spec._checks import _check_links
from deckwright.spec._place import _named, place
from deckwright.spec._scalars import has_text
from deckwright.spec.model import GOTO_JUMPS, Background, SlideSpec
from deckwright.utils.keys import refuse_unknown

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
    "id",
    "lang",
)
_LANG_TAG = re.compile(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{1,8})*")
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


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def _lang(value: Any, *, where: str) -> str | None:
    """A BCP 47 language tag such as ``ja``, ``zh-Hant`` or ``ko-KR``."""
    if value is None:
        return None
    text = str(value)
    if not _LANG_TAG.fullmatch(text):
        raise SpecError(
            f"{where}: 'lang' is a language tag like ja, ko, zh-Hans or zh-TW, got {value!r}"
        )
    return text


def _slide(doc: Any, *, index: int, sections: tuple[str, ...], source: Path) -> SlideSpec:
    where = f"{source.name}: slide {index}"
    if not isinstance(doc, dict):
        raise SpecError(f"{where}: expected a mapping, got {type(doc).__name__}")
    for gone, hint in _GONE.items():
        if gone in doc:
            raise SpecError(f"{where}: {hint}")
    refuse_unknown(doc, _SLIDE_FIELDS, error=SpecError, where=where, suggest=True)

    section = _text(doc.get("section"))
    if section is not None and sections and section not in sections:
        raise SpecError(
            f"{where}: section {section!r} is not in the deck's sections ({', '.join(sections)})"
        )

    slide_id = _named(doc.get("id"), "'id'", where=where)
    if slide_id in GOTO_JUMPS:
        raise SpecError(
            f"{where}: a slide cannot be called {slide_id!r} — 'goto: {slide_id}' already "
            f"jumps relative to the slide clicked; choose another id"
        )
    spec = SlideSpec(
        index=index,
        id=slide_id,
        lang=_lang(doc.get("lang"), where=where),
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
    _check_links(spec, where=where)
    return spec


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
        if not has_text(doc.get(name)):
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

    refuse_unknown(
        value,
        _BACKGROUND_FIELDS,
        error=SpecError,
        where=where,
        lead="background has no key",
        label="known keys",
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
