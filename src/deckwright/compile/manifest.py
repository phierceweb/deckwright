"""Record what the build intended, so QA can check what it produced.

A render only proves what survived; the diff against what was *meant* reveals a clipped
line. The format itself, and its readers, are :mod:`deckwright.compile.record`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pf_core.exceptions import InvalidInputError, PreconditionError
from pf_core.utils.io import atomic_write_json

from deckwright.compile.record import (
    _INCH_DP,
    _POINT_DP,
    _RENDERED_VALUES,
    Box,
    PlacementRecord,
    Provenance,
    Rendered,
    ShapeRecord,
    SlideRecord,
    _slim,
)

if TYPE_CHECKING:
    from deckwright.theme.model import Rect


class ManifestRecorder:
    """Accumulates slide records during a build."""

    def __init__(
        self,
        *,
        deck: str,
        theme: str,
        theme_hash: str = "",
        slide_w: float = 0.0,
        slide_h: float = 0.0,
        theme_path: str = "",
        compose_layout: str = "",
    ) -> None:
        self.deck = deck
        self.theme = theme
        self.theme_hash = theme_hash
        self.slide_w = slide_w
        self.slide_h = slide_h
        self.theme_path = theme_path
        # Set while a placement the author declared 'bleed: true' draws, so its
        # shapes carry that intent into the manifest and out of the bounds check.
        self.bleeding = False
        # Which layout the template resolved to; nothing else in the deck records it.
        self.compose_layout = compose_layout
        self.provenance = Provenance()
        self.slides: list[SlideRecord] = []
        self._origin: str | None = None
        self._part = 0
        self._framed: set[int] = set()
        self._named: dict[int, str] = {}

    @property
    def origin(self) -> str | None:
        """The spec node whose shapes are being drawn — ``s3.hero.card``.

        Written into the .pptx too: a shape name survives a hand-edit, so it is what
        maps an edited shape back to its spec.
        """
        return self._origin

    @origin.setter
    def origin(self, value: str | None) -> None:
        self._origin = value
        self._part = 0
        self._framed.clear()

    def begin_slide(
        self, index: int, *, background: str, section: str | None = None, notes: str | None = None
    ) -> None:
        """Start recording a new slide."""
        self.slides.append(
            SlideRecord(index=index, background=background, section=section, notes=notes)
        )
        # Shape ids restart on every slide, so the name map does too.
        self._named.clear()

    def record(
        self,
        shape,
        *,
        part: str | None = None,
        text: str | None = None,
        lines: list[str] | None = None,
        font_pt: float | None = None,
        line_pt: list[float] | None = None,
        fg: str | None = None,
        bg: str | None = None,
        rendered: Rendered = "native",
        plate: bool = False,
        annotation: bool = False,
    ) -> ShapeRecord:
        """Record a placed shape against the current slide, naming it for its origin.

        A shape recorded while :attr:`bleeding` is set is marked so, keeping a declared
        overrun out of the bounds check. ``part`` names it within its origin — a table
        passes ``r1c1``; without one an origin's shapes are numbered as drawn.
        ``line_pt`` is one size per line, for a shape mixing rungs, which ``font_pt``
        alone would over-report. ``annotation`` marks a shape that *depicts* geometry —
        a drawn reserved region — so the geometry checks do not report it against the
        thing it is a picture of.
        """
        if rendered not in _RENDERED_VALUES:
            raise InvalidInputError(
                f"rendered must be one of {', '.join(_RENDERED_VALUES)}, got {rendered!r}"
            )
        if not self.slides:
            raise PreconditionError("call begin_slide() before record()")
        if line_pt is not None and len(line_pt) != len(lines or []):
            raise InvalidInputError(
                f"line_pt has {len(line_pt)} size(s) for {len(lines or [])} line(s) — "
                f"it is one size per recorded line, or omitted"
            )
        rec = ShapeRecord(
            shape_id=int(shape.shape_id),
            name=self._name(shape, part),
            box=Box.from_emu(shape.left, shape.top, shape.width, shape.height),
            text=text if text is not None else (" ".join(lines) if lines else None),
            lines=list(lines or []),
            font_pt=None if font_pt is None else round(font_pt, _POINT_DP),
            line_pt=[round(pt, _POINT_DP) for pt in (line_pt or [])],
            fg=fg,
            bg=bg,
            rendered=rendered,
            bleed=self.bleeding,
            plate=plate,
            annotation=annotation,
        )
        self.slides[-1].shapes.append(rec)
        return rec

    def record_placement(self, origin: str, component: str, rect: Rect) -> None:
        """Note the rect a placement resolved to, so QA can measure its shapes against it."""
        if not self.slides:
            raise PreconditionError("call begin_slide() before record_placement()")
        self.slides[-1].placements.append(
            PlacementRecord(
                origin=origin,
                component=component,
                box=Box.from_inches(rect.left, rect.top, rect.width, rect.height),
            )
        )

    def _name(self, shape, part: str | None) -> str:
        """Name ``shape`` for the current origin, and write that name into the package."""
        if self._origin is None:
            return str(shape.name)
        self._part += 1
        name = f"{self._origin}.{part}" if part else f"{self._origin}#{self._part}"
        # Only a genuinely shared element collapses to the origin: chrome's stacked
        # lines are one frame and cannot hold three names, while a chrome field with its
        # own `at:` takes its own. A table's cells are `_CellBox` and have no element.
        if hasattr(shape, "_element"):
            # Keyed on shape_id: an lxml proxy's address is not an identity — a freed
            # one is reused by another element, collapsing two shapes onto one name.
            key = int(shape.shape_id)
            shared = part is not None and key in self._framed
            shape.name = self._origin if shared else name
            self._framed.add(key)
            # What an animation step names this shape: the package name, not the
            # record's, so a shared frame is named once rather than per paragraph.
            self._named[int(shape.shape_id)] = shape.name
        return name

    def mark_backdrop(self) -> None:
        """Note that the template's own picture shows behind the current slide.

        The render check needs to know those pixels are a photograph, not a palette colour.
        """
        if not self.slides:
            raise PreconditionError("call begin_slide() before mark_backdrop()")
        self.slides[-1].backdrop = True

    def record_animation(
        self, kind: str, groups: list[list[Any]], *, clicks: int, trigger: Any | None = None
    ) -> None:
        """Record an animation build against the current slide, one step per beat.

        ``clicks`` is the slide advances the build spends, which is **not** ``len(groups)``:
        a ``together`` build groups eight shapes and spends one, an interactive reveal
        spends none.

        Entries are shape ids, some carrying an already-resolved motion role. Both are
        recorded as the shape's *name*: an id is not unique on a slide.
        """
        if not self.slides:
            raise PreconditionError("call begin_slide() before record_animation()")
        entry: dict[str, Any] = {
            "kind": kind,
            "clicks": clicks,
            "steps": [[self._step_name(item) for item in group] for group in groups],
        }
        if trigger is not None:
            entry["trigger"] = self._step_name(trigger)
        self.slides[-1].animations.append(entry)

    def _step_name(self, item: Any) -> str:
        """One reveal target as the name its shape carries in the deck."""
        shape_id = item[0] if isinstance(item, (list, tuple)) else item
        # A shape animated but never recorded keeps its id, which at least says which.
        return self._named.get(int(shape_id), f"shape {int(shape_id)}")

    def to_dict(self) -> dict[str, Any]:
        # Provenance first: what produced the file, before the thousands of records it
        # describes, so a reader can tell it is current without scrolling.
        prov = self.provenance
        return {
            "build_id": prov.build_id,
            "deckwright": prov.deckwright,
            "spec": prov.spec,
            "spec_hash": prov.spec_hash,
            "deck": self.deck,
            "deck_hash": prov.deck_hash,
            "theme": self.theme,
            "theme_hash": self.theme_hash,
            "theme_path": self.theme_path,
            "canvas": {
                "w": round(self.slide_w, _INCH_DP),
                "h": round(self.slide_h, _INCH_DP),
                "unit": "in",
            },
            "compose_layout": self.compose_layout,
            "slides": [_slim(s) for s in self.slides],
        }

    def write(self, path: str | Path) -> Path:
        """Write the manifest as JSON beside the deck; returns the path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()
        for key in ("spec", "deck", "theme_path"):
            data[key] = _portable(data.get(key), path.parent)
        atomic_write_json(path, data, indent=2, ensure_ascii=False)
        return path


def _portable(target: Any, base: Path) -> Any:
    """A recorded path, written relative to the manifest wherever that is meaningful.

    An absolute path puts the build machine's username in a file that leaves the machine,
    and does not survive the deck directory moving. Paths sharing only the filesystem
    root stay absolute — climbing out would name that home directory anyway.
    """
    if not isinstance(target, str) or not target:
        return target
    here, there = Path(target), base
    try:
        common = Path(os.path.commonpath([here.resolve(), there.resolve()]))
    except ValueError:  # different drives, or a path that cannot be resolved
        return target
    if common == Path(common.anchor):
        return target
    return os.path.relpath(here.resolve(), there.resolve())
