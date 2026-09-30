"""Read a hand-edited deck back against the build that made it.

A shape name survives an edit, so it is the join between deck and manifest. Matching runs
from the **deck** side: one shape can answer for several records, and only the deck knows
which names the package really carries.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pf_core.log import get_logger
from pf_core.utils.io import atomic_write_text

from deckwright.compile._drift import Change, Kind, motion_drift, style_drift
from deckwright.compile.record import box_of
from deckwright.errors import SpecError
from deckwright.motion.transition import read_kind
from deckwright.utils.a11y import described
from deckwright.utils.deck import open_presentation
from deckwright.utils.mce import resolved_shapes
from deckwright.utils.provenance import find_manifest

logger = get_logger(__name__)

_EMU_PER_INCH = 914400
# Inches — twenty times the manifest's rounding, so float dust is not a move.
_MOVED = 0.01

_ORIGIN = re.compile(r"^s(\d+)\.")


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
    prs = open_presentation(deck, what="deck", error=SpecError)
    path = Path(manifest) if manifest else _manifest_for(deck, prs)
    if not path.is_file():
        raise SpecError(f"manifest not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    changes: list[Change] = []
    indexed: dict[int, Any] = {}
    placed: list[tuple[int, int]] = []
    for position, slide in enumerate(prs.slides, start=1):
        index = _build_index(slide, position)
        if index is None:
            changes.append(
                Change(
                    "slide-added",
                    position,
                    f"slide {position}",
                    "not in the build — added by hand",
                )
            )
            continue
        if index in indexed:
            changes.append(
                Change(
                    "slide-added",
                    position,
                    f"slide {position}",
                    f"a copy of slide {index} — added by hand",
                )
            )
            continue
        indexed[index] = slide
        placed.append((index, position))
    changes.extend(_moved(placed, built=len(data.get("slides") or [])))
    for recorded in data.get("slides") or []:
        index = int(recorded.get("index", 0))
        if index not in indexed:
            changes.append(
                Change(
                    "slide-gone",
                    index,
                    f"slide {index}",
                    "the build made this slide and the deck no longer has it",
                )
            )
            continue
        changes.extend(_slide_drift(indexed[index], list(recorded.get("shapes") or []), index))
        changes.extend(motion_drift(indexed[index], list(recorded.get("animations") or []), index))
        was, now = recorded.get("transition"), read_kind(indexed[index]._element)
        if was is not None and was != now:
            changes.append(Change("retimed", index, f"slide {index}", f"transition {was} → {now}"))
    drift = Drift(
        deck=str(deck),
        spec=str(data.get("spec") or "?"),
        edited=_edited(deck, data),
        changes=tuple(changes),
    )
    logger.info("deck_read_back", deck=deck.name, edited=drift.edited, changes=len(drift.changes))
    return drift


def _moved(placed: list[tuple[int, int]], *, built: int) -> list[Change]:
    """The slides out of build order, as few as explain the order the deck is in.

    ``placed`` is ``(build number, position)`` in deck order. The longest run still in build
    order stayed put; the rest were moved.
    """
    numbers = [index for index, _ in placed]
    best: list[list[int]] = []
    for i, number in enumerate(numbers):
        runs = [best[j] for j in range(i) if numbers[j] < number]
        longest: list[int] = []
        for run in runs:
            if len(run) > len(longest):
                longest = run
        best.append([*longest, number])
    stayed: set[int] = set()
    for run in best:
        if len(run) > len(stayed):
            stayed = set(run)
    return [
        Change("slide-moved", index, f"slide {index}", f"built at {index} of {built}, now at {at}")
        for index, at in placed
        if index not in stayed
    ]


def _manifest_for(deck: Path, prs) -> Path:
    """The sibling manifest, else the one beside the deck that records the deck's build id."""
    found = find_manifest(deck, str(prs.core_properties.identifier or ""))
    if found is not None:
        return found
    ident = str(prs.core_properties.identifier or "")
    raise SpecError(
        f"manifest not found: {deck.with_suffix('.manifest.json')}, and no manifest in "
        f"{deck.parent} records build {ident or '(none recorded)'} — a deck can only be read "
        f"back against the build that made it. Keep the copy beside its build, or pass "
        f"--manifest."
    )


def _edited(deck: Path, data: dict[str, Any]) -> bool:
    """Whether the file differs from the one the manifest was written beside."""
    recorded = data.get("deck_hash")
    if not recorded:
        return False
    return hashlib.sha256(deck.read_bytes()).hexdigest()[: len(recorded)] != recorded


def _build_index(slide, position: int) -> int | None:
    """The slide number the build gave this slide, read off its first `sN.` shape name.

    A slide holding only morph-named shapes carries no number, and is taken where it sits.
    """
    names = [str(shape.name) for shape in resolved_shapes(slide.shapes)]
    for name in names:
        if match := _ORIGIN.match(name):
            return int(match.group(1))
    return position if any(name.startswith("m.") for name in names) else None


def _claimed(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The records a package shape answers for — itself, its dotted children, and the parts
    of the frame it is.

    ``s1.chrome`` claims ``s1.chrome.title``. A frame ``…table#1`` claims ``…table.r1c1``,
    and ``…chart#1`` claims ``…chart.labels``: parts that are records and never shapes.
    """
    prefixes = (f"{name}.", f"{name.rsplit('#', 1)[0]}.")
    return [
        r for r in records if r.get("name") == name or str(r.get("name", "")).startswith(prefixes)
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
    out.extend(style_drift(shape, claimed, index, name))
    own = next((r for r in claimed if r.get("name") == name), None)
    if own is not None:
        was_alt, was_skipped = own.get("alt") or None, bool(own.get("decorative"))
        now_alt, now_skipped = described(shape)
        if was_skipped != now_skipped:
            mark = "decorative" if now_skipped else "not decorative"
            out.append(Change("relabelled", index, name, f"marked {mark}"))
        elif was_alt != now_alt:
            out.append(Change("relabelled", index, name, f"alt {was_alt or 'none'} → {now_alt!r}"))
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
            "cannot see (a fill, a face, anything on the master).",
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
