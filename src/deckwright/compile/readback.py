"""Read a hand-edited deck back against the build that made it.

A shape name survives an edit, so it is the join between deck and manifest. Slides are matched
by ``_slides.paired``. Shapes are matched from the **deck** side: one shape can answer for
several records, and only the deck knows which names the package really carries.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pptx.oxml.ns import qn
from pw_foundation.log import get_logger
from pw_foundation.utils.io import atomic_write_text

from deckwright.compile._drift import Change, Kind, motion_drift, style_drift
from deckwright.compile._slides import moved_slides, paired, unmatched
from deckwright.compile.record import box_of
from deckwright.errors import SpecError
from deckwright.motion.transition import read_kind
from deckwright.spec.matching import drawn, numbers, placed, recorded, unplaced
from deckwright.utils.a11y import described
from deckwright.utils.deck import open_presentation
from deckwright.utils.provenance import find_manifest, read_manifest

logger = get_logger(__name__)

_EMU_PER_INCH = 914400
# Inches — twenty times the manifest's rounding, so float dust is not a move.
_MOVED = 0.01


@dataclass(frozen=True)
class Drift:
    """Everything that changed in a deck since it was built."""

    deck: str
    spec: str
    manifest: str
    edited: bool | None  # the .pptx no longer hashes to what was built; None with no hash to check
    changes: tuple[Change, ...] = ()

    def of(self, kind: Kind) -> list[Change]:
        return [c for c in self.changes if c.kind == kind]


def read_back(deck: str | Path, *, manifest: str | Path | None = None) -> Drift:
    """Compare ``deck`` against its build manifest, defaulting to the sibling one.

    Raises:
        SpecError: the deck or its manifest is missing or unreadable, or the manifest
            records no slides.
    """
    deck = Path(deck)
    prs = open_presentation(deck, what="deck", error=SpecError)
    path = Path(manifest) if manifest else _manifest_for(deck, prs)
    if not path.is_file():
        raise SpecError(f"manifest not found: {path}")
    data = read_manifest(path)
    slides = list(data.get("slides") or [])
    if not slides:
        raise SpecError(
            f"{path.name} records no slides — nothing to read {deck.name} back against; build "
            f"the spec again and pass the manifest it writes with --manifest"
        )
    deck_slides = [drawn(slide, unfilled=False) for slide in prs.slides]
    built = {int(s["index"]): recorded(s.get("shapes")) for s in slides}
    matched = paired(
        deck_slides,
        built,
        kinds=[read_kind(slide._element) for slide in prs.slides],
        built_kinds={int(s["index"]): s.get("transition") for s in slides},
        notes=[_notes(slide) for slide in prs.slides],
        built_notes={int(s["index"]): _flat(str(s.get("notes") or "")) for s in slides},
        firsts=[_first_number(slide) for slide in prs.slides],
    )
    recorded_by = {int(s["index"]): list(s.get("shapes") or []) for s in slides}
    changes: list[Change] = []
    indexed: dict[int, Any] = {}
    placed: list[tuple[int, int]] = []
    for position, slide in enumerate(prs.slides, start=1):
        index = matched.get(position)
        if index is None:
            detail = unmatched(deck_slides[position - 1], matched, built)
            changes.append(Change("slide-added", position, f"slide {position}", detail))
            continue
        indexed[index] = slide
        placed.append((index, position))
    changes.extend(moved_slides(placed, built=len(slides)))
    for record in slides:
        index = int(record["index"])
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
        changes.extend(
            _slide_drift(indexed[index], list(record.get("shapes") or []), index, recorded_by)
        )
        changes.extend(motion_drift(indexed[index], list(record.get("animations") or []), index))
        was, now = record.get("transition"), read_kind(indexed[index]._element)
        if was is not None and was != now:
            changes.append(Change("retimed", index, f"slide {index}", f"transition {was} → {now}"))
    drift = Drift(
        deck=str(deck),
        spec=str(data.get("spec") or "?"),
        manifest=str(path),
        edited=_edited(deck, data),
        changes=tuple(changes),
    )
    logger.info("deck_read_back", deck=deck.name, edited=drift.edited, changes=len(drift.changes))
    return drift


def _manifest_for(deck: Path, prs) -> Path:
    """The sibling manifest, else the one beside the deck that records the deck's build id."""
    found = find_manifest(deck, str(prs.core_properties.identifier or ""))
    if found is not None:
        return found
    ident = str(prs.core_properties.identifier or "")
    raise SpecError(
        f"manifest not found: {deck.with_suffix('.manifest.json')}, and no manifest deckwright "
        f"can read in {deck.parent} records build {ident or '(none recorded)'} — a deck can "
        f"only be read "
        f"back against the build that made it. Keep the copy beside its build, or pass "
        f"--manifest."
    )


def _edited(deck: Path, data: dict[str, Any]) -> bool | None:
    """Whether the file differs from the one the manifest was written beside; None when the
    manifest records no hash to check it against."""
    recorded = data.get("deck_hash")
    if not recorded:
        return None
    return hashlib.sha256(deck.read_bytes()).hexdigest()[: len(recorded)] != recorded


def _claimed(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The records a package shape answers for — itself, its dotted children, and the parts
    of the frame it is.

    ``s1.chrome`` claims ``s1.chrome.title``. A frame ``…table#1`` claims ``…table.r1c1``,
    and ``…chart#1`` claims ``…chart.labels``: parts that are records and never shapes. A
    record marked ``plate`` is a shape of its own, so only that shape claims it.
    """
    prefixes = (f"{name}.", f"{name.rsplit('#', 1)[0]}.")
    return [
        r
        for r in records
        if r.get("name") == name
        or (str(r.get("name", "")).startswith(prefixes) and not r.get("plate"))
    ]


def _slide_drift(
    slide, records: list[dict[str, Any]], index: int, recorded_by: dict[int, list[dict[str, Any]]]
) -> list[Change]:
    out: list[Change] = []
    seen: set[str] = set()
    for shape, box in placed(slide):
        if unplaced(shape):
            continue
        name = str(shape.name)
        claimed = _claimed(name, records)
        if not claimed:
            source = next(
                (n for n, theirs in sorted(recorded_by.items()) if _claimed(name, theirs)), None
            )
            detail = (
                f"drawn by the build on slide {source} — pasted here by hand"
                if source is not None
                else "not in the build — added by hand, so no placement made it"
            )
            out.append(Change("added", index, name, detail))
            continue
        seen.update(str(r["name"]) for r in claimed)
        out.extend(_shape_drift(shape, box, claimed, index, name))
    for record in records:
        rec_name = str(record.get("name", ""))
        if rec_name and rec_name not in seen:
            out.append(
                Change("gone", index, rec_name, "the build drew this and the deck no longer has it")
            )
    return out


def _shape_drift(
    shape,
    box: tuple[int, int, int, int] | None,
    claimed: list[dict[str, Any]],
    index: int,
    name: str,
) -> list[Change]:
    out: list[Change] = []
    was = box_of(claimed[0])
    if was is not None and box is not None:
        now = tuple(round(v / _EMU_PER_INCH, 3) for v in box)
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
    if drift.edited is False:
        lines += ["The deck is the one that was built; nothing to carry back.", ""]
        return "\n".join(lines)
    unknown = drift.edited is None
    lines += [
        f"Whether it was edited since its build from `{drift.spec}` is unknown: "
        f"{Path(drift.manifest).name} records no file hash."
        if unknown
        else f"Edited since it was built from `{drift.spec}`.",
        "",
    ]
    if not drift.changes:
        lines += [
            "No shape differs from the build."
            if unknown
            else "The file differs but no shape does — a resave, or a change this "
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


def _notes(slide) -> str:
    frame = slide.notes_slide.notes_text_frame if slide.has_notes_slide else None
    return _flat(frame.text) if frame is not None else ""


def _first_number(slide) -> int | None:
    """The slide number of the first build-named shape the slide draws, bottom of the stack up:
    a pasted shape lands on top."""
    for element in slide.shapes._spTree.iter(qn("p:cNvPr")):
        for found in numbers({str(element.get("name", "")): ((), "")}):
            return found
    return None
