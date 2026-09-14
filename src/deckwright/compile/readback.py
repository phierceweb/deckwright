"""Read a hand-edited deck back against the build that made it.

A shape name survives an edit, so it is the join between deck and manifest. Matching runs
from the **deck** side: one shape can answer for several records, and only the deck knows
which names the package really carries.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pf_core.log import get_logger
from pf_core.utils.io import atomic_write_text

from deckwright.compile.record import box_of
from deckwright.errors import SpecError
from deckwright.utils.deck import open_presentation
from deckwright.utils.mce import resolved_shapes

logger = get_logger(__name__)

_EMU_PER_INCH = 914400
# Inches — twenty times the manifest's rounding, so float dust is not a move.
_MOVED = 0.01

Kind = Literal["moved", "retyped", "added", "gone"]


@dataclass(frozen=True)
class Change:
    """One difference between the deck on disk and the build that made it."""

    kind: Kind
    slide: int
    shape: str
    detail: str


@dataclass(frozen=True)
class Drift:
    """Everything that changed in a deck since it was built."""

    deck: str
    spec: str
    edited: bool  # the .pptx no longer hashes to what was built
    changes: tuple[Change, ...] = ()

    def of(self, kind: Kind) -> list[Change]:
        return [c for c in self.changes if c.kind == kind]


def read_back(deck: str | Path, *, manifest: str | Path | None = None) -> Drift:
    """Compare ``deck`` against its build manifest, defaulting to the sibling one.

    Raises:
        SpecError: the deck or its manifest is missing or unreadable.
    """
    deck = Path(deck)
    path = Path(manifest) if manifest else deck.with_suffix(".manifest.json")
    if not path.is_file():
        raise SpecError(
            f"manifest not found: {path} — a deck can only be read back against the "
            f"build that made it. Build it with 'deckwright build'."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    prs = open_presentation(deck, what="deck", error=SpecError)
    changes: list[Change] = []
    for index, slide in enumerate(prs.slides, start=1):
        changes.extend(_slide_drift(slide, _records(data, index), index))
    drift = Drift(
        deck=str(deck),
        spec=str(data.get("spec") or "?"),
        edited=_edited(deck, data),
        changes=tuple(changes),
    )
    logger.info("deck_read_back", deck=deck.name, edited=drift.edited, changes=len(drift.changes))
    return drift


def _edited(deck: Path, data: dict[str, Any]) -> bool:
    """Whether the file differs from the one the manifest was written beside."""
    recorded = data.get("deck_hash")
    if not recorded:
        return False
    return hashlib.sha256(deck.read_bytes()).hexdigest()[: len(recorded)] != recorded


def _records(data: dict[str, Any], index: int) -> list[dict[str, Any]]:
    for slide in data.get("slides") or []:
        if slide.get("index") == index:
            return list(slide.get("shapes") or [])
    return []


def _claimed(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The records a package shape answers for — itself, or its parts.

    ``s1.chrome`` claims ``s1.chrome.title`` and its siblings. A table frame is
    ``…table#1`` and so claims no cells, which are ``…table.r1c1`` — never shapes.
    """
    return [
        r for r in records if r.get("name") == name or str(r.get("name", "")).startswith(f"{name}.")
    ]


def _slide_drift(slide, records: list[dict[str, Any]], index: int) -> list[Change]:
    out: list[Change] = []
    seen: set[str] = set()
    for shape in resolved_shapes(slide.shapes):
        name = str(shape.name)
        claimed = _claimed(name, records)
        if not claimed:
            out.append(
                Change(
                    "added",
                    index,
                    name,
                    "not in the build — added by hand, so no placement made it",
                )
            )
            continue
        seen.update(str(r["name"]) for r in claimed)
        out.extend(_shape_drift(shape, claimed, index, name))
    for record in records:
        rec_name = str(record.get("name", ""))
        if rec_name and rec_name not in seen:
            out.append(
                Change("gone", index, rec_name, "the build drew this and the deck no longer has it")
            )
    return out


def _shape_drift(shape, claimed: list[dict[str, Any]], index: int, name: str) -> list[Change]:
    out: list[Change] = []
    was = box_of(claimed[0])
    if was is not None and getattr(shape, "left", None) is not None:
        now = tuple(
            round(v / _EMU_PER_INCH, 3) for v in (shape.left, shape.top, shape.width, shape.height)
        )
        if any(abs(a - b) > _MOVED for a, b in zip(was, now, strict=True)):
            out.append(Change("moved", index, name, f"{_fmt(was)} → {_fmt(now)}"))
    before = " ".join(t for t in (_text(r) for r in claimed) if t).strip()
    after = _shape_text(shape)
    was_text, now_text = _flat(before), _flat(after)
    if was_text and now_text and was_text != now_text:
        out.append(Change("retyped", index, name, f"{was_text!r} → {now_text!r}"))
    return out


def _text(record: dict[str, Any]) -> str:
    lines = record.get("lines") or []
    return " ".join(str(x) for x in lines) if lines else str(record.get("text") or "")


def _shape_text(shape) -> str:
    frame = getattr(shape, "text_frame", None)
    return frame.text.strip() if frame is not None else ""


def _flat(text: str) -> str:
    return " ".join(text.split())


def _fmt(box) -> str:
    return f"{box[0]:g},{box[1]:g} {box[2]:g}×{box[3]:g}in"


def render_drift(drift: Drift) -> str:
    """The differences as markdown, ordered by slide."""
    lines = [f"# Read-back — {Path(drift.deck).name}", ""]
    if not drift.edited:
        lines += ["The deck is the one that was built; nothing to carry back.", ""]
        return "\n".join(lines)
    lines += [f"Edited since it was built from `{drift.spec}`.", ""]
    if not drift.changes:
        lines += [
            "The file differs but no shape does — a resave, or a change this "
            "cannot see (a colour, a font, a size).",
            "",
        ]
        return "\n".join(lines)
    for index in sorted({c.slide for c in drift.changes}):
        lines.append(f"## Slide {index}")
        lines += [
            f"- **{c.kind}** `{c.shape}` — {c.detail}" for c in drift.changes if c.slide == index
        ]
        lines.append("")
    return "\n".join(lines)


def write_drift(drift: Drift, path: str | Path) -> Path:
    """Write the read-back as markdown; returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, render_drift(drift))
    return path
