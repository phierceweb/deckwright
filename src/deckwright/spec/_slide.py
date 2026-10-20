"""Parse one slide document into a :class:`SlideSpec`."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from deckwright.errors import LayoutError, SpecError
from deckwright.spec._checks import _check_links
from deckwright.spec._place import _named, place
from deckwright.spec._scalars import has_text
from deckwright.spec.model import GOTO_JUMPS, Background, Placement, SlideSpec
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
    "carry",
    "drop",
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


def _slide(
    doc: Any,
    *,
    index: int,
    sections: tuple[str, ...],
    source: Path,
    before: tuple[Placement, ...] | None = None,
) -> SlideSpec:
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
        place=_carried(doc, place(doc.get("place"), where=where), before=before, where=where),
        chrome=_chrome(doc, where=where),
        chrome_preset=_preset(doc, where=where),
    )
    _check_links(spec, where=where)
    _check_still(spec)
    return spec


def _carried(
    doc: dict, own: tuple[Placement, ...], *, before: tuple[Placement, ...] | None, where: str
) -> tuple[Placement, ...]:
    """``carry: previous``: the slide before's ``morph:`` placements, in their order, each
    replaced by this slide's placement of the same name; this slide's others follow."""
    if "drop" in doc and doc.get("carry") is None:
        raise SpecError(f"{where}: 'drop' removes carried placements, and nothing is carried")
    if doc.get("carry") is None:
        return own
    if str(doc["carry"]) != "previous":
        raise SpecError(f"{where}: 'carry' takes only previous, got {doc['carry']!r}")
    carried = [p for p in before or () if p.morph is not None]
    if not carried:
        raise SpecError(
            f"{where}: 'carry: previous' copies the slide before's 'morph:' placements, and "
            f"{'there is no slide before' if before is None else 'it names none'}"
        )
    dropped = doc.get("drop") or []
    if not isinstance(dropped, list):
        raise SpecError(f"{where}: 'drop' is a list of morph names, got {dropped!r}")
    names = [str(p.morph) for p in carried]
    for name in dropped:
        if str(name) not in names:
            raise SpecError(
                f"{where}: 'drop' names {name!r}, which is not carried; carried: {', '.join(names)}"
            )
    mine: dict[str, Placement] = {}
    for p in own:
        if p.morph is None:
            continue
        if p.morph in mine:
            raise SpecError(
                f"{p.where}: 'morph: {p.morph}' is already placement "
                f"{own.index(mine[p.morph]) + 1} — a name pairs one placement with its "
                f"namesake on the next slide"
            )
        mine[p.morph] = p
    kept = [n for n in names if n not in {str(d) for d in dropped}]
    # What the slide before showed is on screen when this one lands: out of its build, if any.
    builds = doc.get("animate") not in (None, "none")
    merged = [
        mine.get(str(p.morph))
        or replace(p, where=f"{where}: carried {p.morph!r}", still=builds, reveals=None)
        for p in carried
        if p.morph in kept
    ]
    merged += [p for p in own if p.morph is None or p.morph not in kept]
    ids = [p.id for p in merged if p.id is not None]
    if len(ids) != len(set(ids)):
        twice = sorted({i for i in ids if ids.count(i) > 1})
        raise SpecError(
            f"{where}: a carried placement and one of this slide's share the id {twice[0]!r}"
        )
    return tuple(merged)


def _check_still(spec: SlideSpec) -> None:
    """``animate: none`` only means something on a slide that builds, on a placement the
    slide shows on arrival."""
    for placement in spec.place:
        if not placement.still:
            continue
        if spec.animate in (None, "none"):
            raise SpecError(
                f"{placement.where}: 'animate: none' keeps a placement out of the slide's "
                f"build, and this slide does not build — drop it, or give the slide an "
                f"animate:"
            )
        if placement.reveals is not None:
            raise SpecError(
                f"{placement.where}: 'animate: none' asks for it on screen on arrival, and "
                f"'reveals: {placement.reveals}' hides it until that is clicked — drop one"
            )


def _preset(doc: dict, *, where: str) -> str | None:
    """``chrome: side`` or ``chrome: statement`` — one word for a whole chrome treatment."""
    from deckwright.layouts.chrome import CHROME_ORDER, PRESETS

    value = doc.get("chrome")
    if not isinstance(value, str):
        return None
    if value not in PRESETS:
        raise SpecError(
            f"{where}: 'chrome' is a mapping of field to treatment, or one of "
            f"{', '.join(PRESETS)}; got {value!r}"
        )
    if not any(has_text(doc.get(name)) for name in CHROME_ORDER):
        raise SpecError(
            f"{where}: 'chrome: {value}' places the slide's kicker, title and subtitle, "
            f"and it has none of them"
        )
    return value


def _chrome(doc: dict, *, where: str) -> dict[str, Any]:
    """The slide's per-field chrome overrides. A field with no text has nothing to place."""
    from deckwright.layouts.chrome import chrome_field

    value = doc.get("chrome")
    if value is None or isinstance(value, str):
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
