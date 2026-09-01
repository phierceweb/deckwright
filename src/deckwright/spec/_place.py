"""Validate a slide's ``place:`` list — one placement, its ``at:``, and how it sets text."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from deckwright.errors import SpecError
from deckwright.spec.model import Placement
from deckwright.utils.shapes import ALIGNS, ANCHORS
from deckwright.utils.spans import Share, parse_box, parse_span
from deckwright.utils.keys import unknown_field

PLACEMENT_FIELDS = ("at", "id", "bleed", "align", "anchor", "reveals")
AT_FIELDS = ("cols", "rows", "box")


def _named(value: Any, key: str, *, where: str) -> str | None:
    """An author-written name that ends up as a shape name in the package.

    Control characters must be rejected here: lxml raises a bare ``ValueError`` for them
    deep inside the write. Metacharacters are fine — python-pptx escapes them.
    """
    if value is None:
        return None
    text = str(value)
    bad = next((c for c in text if c < " " or c == "\x7f"), None)
    if bad is not None:
        raise SpecError(
            f"{where}: {key} {text!r} contains the control character {bad!r}, which "
            f"cannot go into a shape name — use printable characters"
        )
    return text


def known_components() -> tuple[str, ...]:
    """Registered component names. Imported late: the registry reads this package's model."""
    import deckwright.components  # noqa: F401 — importing registers the built-ins
    from deckwright.layouts.components import registered_components

    return registered_components()


def place(value: Any, *, where: str) -> tuple[Placement, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise SpecError(f"{where}: 'place' must be a list, got {type(value).__name__}")
    placements: list[Placement] = []
    seen: set[str] = set()
    for n, entry in enumerate(value, start=1):
        spot = f"{where}: placement {n}"
        made = (
            _split(entry, where=spot)
            if isinstance(entry, dict) and "split" in entry
            else [_placement(entry, where=spot)]
        )
        for placement in made:
            if placement.id is not None:
                if placement.id in seen:
                    raise SpecError(f"{spot}: duplicate id {placement.id!r}")
                seen.add(placement.id)
            placements.append(placement)
    return tuple(placements)


def _split(entry: dict[str, Any], *, where: str) -> list[Placement]:
    """A band divided among its children, left to right: one placement in, several out."""
    unknown = sorted(set(entry) - {"at", "split"})
    if unknown:
        raise SpecError(
            f"{where}: a placement with 'split' takes only 'at' and 'split'; "
            f"{unknown_field(unknown[0], ('at', 'split'), suggest=True)}"
        )
    children = entry["split"]
    if not isinstance(children, list) or not children:
        raise SpecError(
            f"{where}: 'split' is a non-empty list of placements to divide the band "
            f"among, got {children!r}"
        )
    raw = entry.get("at") or {}
    if isinstance(raw, dict) and "box" in raw:
        raise SpecError(
            f"{where}: 'split' divides a column band, so its 'at' takes "
            f"'cols' and 'rows', not 'box'"
        )
    # The band is the whole width unless narrowed: a split usually says only how deep.
    band = _at({"cols": "full", **raw} if isinstance(raw, dict) else raw, where=where)
    spans = [_share_span(c, where=f"{where}: split {i}") for i, c in enumerate(children, start=1)]
    total = sum(spans)
    out: list[Placement] = []
    taken = 0
    for i, (child, span) in enumerate(zip(children, spans, strict=True), start=1):
        spot = f"{where}: split {i}"
        body = {k: v for k, v in child.items() if k != "span"}
        if "at" in body:
            raise SpecError(f"{spot}: a split child has no 'at' — the band gives it its rectangle")
        at: dict[str, Any] = {"cols": Share(band=band["cols"], index=taken, span=span, total=total)}
        if "rows" in band:
            at["rows"] = band["rows"]
        out.append(replace(_placement({**body, "at": {"cols": "full"}}, where=spot), at=at))
        taken += span
    return out


def _share_span(child: Any, *, where: str) -> int:
    if not isinstance(child, dict):
        raise SpecError(f"{where}: expected a mapping, got {type(child).__name__}")
    span = child.get("span", 1)
    if not isinstance(span, int) or isinstance(span, bool) or span < 1:
        raise SpecError(f"{where}: 'span' is a whole number of shares, got {span!r}")
    return span


def _placement(entry: Any, *, where: str) -> Placement:
    if not isinstance(entry, dict):
        raise SpecError(f"{where}: expected a mapping, got {type(entry).__name__}")
    known = known_components()
    allowed = (*PLACEMENT_FIELDS, *known)
    keys = [k for k in entry if k not in PLACEMENT_FIELDS]
    unknown = [k for k in keys if k not in known]
    if unknown:
        raise SpecError(f"{where}: {unknown_field(unknown[0], allowed, suggest=True)}")
    if not keys:
        raise SpecError(
            f"{where}: no component — a placement needs exactly one component key; "
            f"known components: {', '.join(known)}"
        )
    if len(keys) > 1:
        raise SpecError(
            f"{where}: more than one component — found "
            f"{' and '.join(repr(k) for k in sorted(keys))}; give each its own placement"
        )

    name = keys[0]
    body = entry[name] if entry[name] is not None else {}
    if not isinstance(body, dict):
        raise SpecError(f"{where}: component {name!r} must be a mapping, got {type(body).__name__}")
    bleed = entry.get("bleed", False)
    if not isinstance(bleed, bool):
        raise SpecError(f"{where}: 'bleed' must be true or false, got {bleed!r}")
    if "at" not in entry and not bleed:
        raise SpecError(
            f"{where}: missing required field 'at' — a placement says where it goes, "
            f"unless it declares 'bleed: true' and is drawn off the canvas"
        )
    return Placement(
        at=_at(entry["at"], where=where) if "at" in entry else {},
        component=name,
        body=body,
        id=_named(entry.get("id"), "'id'", where=where),
        reveals=_named(entry.get("reveals"), "'reveals'", where=where),
        bleed=bleed,
        align=_choice(entry.get("align"), "align", ALIGNS, default="left", where=where),
        anchor=_choice(entry.get("anchor"), "anchor", ANCHORS, default="top", where=where),
    )


def _choice(value: Any, key: str, options: tuple[str, ...], *, default: str, where: str) -> str:
    if value is None:
        return default
    if str(value) not in options:
        raise SpecError(f"{where}: {key!r} must be one of {', '.join(options)}, got {value!r}")
    return str(value)


def _at(value: Any, *, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SpecError(f"{where}: 'at' must be a mapping, got {type(value).__name__}")
    unknown = sorted(set(value) - set(AT_FIELDS))
    if unknown:
        raise SpecError(f"{where}: 'at': {unknown_field(unknown[0], AT_FIELDS, suggest=True)}")
    if "box" in value:
        if "cols" in value or "rows" in value:
            raise SpecError(f"{where}: 'at.box' cannot be combined with 'cols' or 'rows'")
        return {"box": _box(value["box"], where=where)}
    if "cols" not in value:
        raise SpecError(f"{where}: 'at' needs 'cols' or 'box'")
    at: dict[str, Any] = {"cols": _span(value["cols"], "cols", where=where)}
    if "rows" in value:
        at["rows"] = _span(value["rows"], "rows", where=where)
    return at


def _span(value: Any, key: str, *, where: str) -> str | tuple[int, int]:
    return parse_span(value, key, where=f"{where}: 'at'", error=SpecError)


def _box(value: Any, *, where: str) -> tuple[float, float, float, float]:
    return parse_box(value, where=f"{where}: 'at'", error=SpecError)
