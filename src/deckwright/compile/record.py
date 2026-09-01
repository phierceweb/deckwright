"""What a manifest *is*, and how to read one back — apart from the recorder that writes it."""

from __future__ import annotations

from dataclasses import MISSING, asdict, dataclass, field, fields, is_dataclass
from typing import Any, Iterator, Literal

from deckwright.errors import SpecError

_EMU_PER_INCH = 914400
# Dividing EMU back out leaves binary residue — a 13pt line records 12.99975pt — so
# both are rounded well inside qa's own tolerances.
_INCH_DP = 3
_POINT_DP = 2

Rendered = Literal["native", "image", "picture"]
_RENDERED_VALUES = ("native", "image", "picture")


@dataclass(frozen=True)
class Provenance:
    """What produced this manifest, and what it described when written.

    ``deck_hash`` is the built ``.pptx``; a deck hand-edited afterwards no longer
    matches, which is the only way to tell that the records below are stale.
    """

    build_id: str = ""
    deckwright: str = ""
    spec: str = ""
    spec_hash: str = ""
    deck_hash: str = ""


@dataclass(frozen=True)
class Box:
    """A shape's rectangle in inches, from the top-left of the slide."""

    x: float
    y: float
    w: float
    h: float

    @classmethod
    def from_emu(cls, left: int, top: int, width: int, height: int) -> Box:
        return cls(*(round(v / _EMU_PER_INCH, _INCH_DP) for v in (left, top, width, height)))

    def __iter__(self) -> Iterator[float]:
        """Left, top, width, height — so ``Rect(*box)`` and ``tuple(box)`` hold."""
        return iter((self.x, self.y, self.w, self.h))

    @classmethod
    def from_inches(cls, left: float, top: float, width: float, height: float) -> Box:
        return cls(*(round(v, _INCH_DP) for v in (left, top, width, height)))


def _slim(record: Any) -> dict[str, Any]:
    """A record as a dict, less every field still at its default.

    Defaults stay on the dataclass, so what is omitted and what a reader falls back to
    cannot drift.
    """
    out: dict[str, Any] = {}
    for f in fields(record):
        value = getattr(record, f.name)
        if f.default is not MISSING and value == f.default:
            continue
        if f.default_factory is not MISSING and value == f.default_factory():
            continue
        if is_dataclass(value) and not isinstance(value, type):
            out[f.name] = asdict(value)
        elif isinstance(value, list) and value and is_dataclass(value[0]):
            out[f.name] = [_slim(v) for v in value]
        else:
            out[f.name] = value
    return out


def canvas_of(manifest: dict[str, Any]) -> tuple[float, float]:
    """The slide size in inches, or ``(0.0, 0.0)`` where the manifest records none.

    Zero rather than a raise: ``qa.imagery`` turns an unmappable canvas into a finding
    of its own, which says more than a traceback.
    """
    canvas = manifest.get("canvas") or {}
    return float(canvas.get("w") or 0.0), float(canvas.get("h") or 0.0)


def box_of(shape: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """A recorded box as ``(left, top, width, height)``; ``None`` if it has none.

    Every reader goes through here: a raw ``dict`` survives ``tuple()`` and ``Rect(*box)``
    by yielding its *key names*, so a missed call site corrupts rather than raises.
    """
    box = shape.get("box")
    if not box:
        return None
    if not isinstance(box, dict):
        raise SpecError(
            f"{shape.get('name') or 'a shape'!r} carries a positional box {box!r}. "
            f"This manifest was written before boxes were keyed — rebuild the deck "
            f"with 'deckwright build' and run this again."
        )
    return (box["x"], box["y"], box["w"], box["h"])


def owns(origin: str, name: str) -> bool:
    """True when ``name`` is a shape the placement recorded as ``origin`` drew.

    The separator is required, not decorative: it is what keeps ``s7.p1.card`` off
    ``s7.p10.card#1``. See ``ManifestRecorder._name`` for the two forms.
    """
    return name == origin or name.startswith(f"{origin}.") or name.startswith(f"{origin}#")


@dataclass
class ShapeRecord:
    """One shape the build placed."""

    shape_id: int
    name: str  # the origin that named it; see ManifestRecorder.origin
    box: Box
    text: str | None = None
    lines: list[str] = field(default_factory=list)
    font_pt: float | None = None  # the dominant size; see line_pt for a mixed shape
    line_pt: list[float] = field(default_factory=list)
    fg: str | None = None
    bg: str | None = None
    rendered: Rendered = "native"
    bleed: bool = False  # the author declared this one off-canvas
    plate: bool = False  # a surface painted so something else reads on it
    annotation: bool = False  # depicts geometry rather than occupying it


@dataclass
class PlacementRecord:
    """One placement's resolved rectangle — the constraint its shapes were drawn into.

    ``origin`` is the prefix every shape the placement drew carries in ``name``: the
    only link from a shape back to the rect it belongs inside.
    """

    origin: str
    component: str
    box: Box


@dataclass
class SlideRecord:
    """One slide: what was placed on it and how it animates."""

    index: int
    background: str  # the palette pair the slide was painted on
    section: str | None = None
    notes: str | None = None  # speaker notes; content, so the content view carries them
    backdrop: bool = False  # the template's own picture shows behind this slide
    placements: list[PlacementRecord] = field(default_factory=list)
    shapes: list[ShapeRecord] = field(default_factory=list)
    animations: list[dict[str, Any]] = field(default_factory=list)

    def texts(self) -> list[str]:
        """Text a PDF extractor should be able to find — native records, one entry per line."""
        out: list[str] = []
        for shape in self.shapes:
            if shape.rendered != "native":
                continue
            if shape.lines:
                out.extend(shape.lines)
            elif shape.text:
                out.append(shape.text)
        return out
