"""What a hand-edit changed that a shape's box and words do not show: its type, and its slide's
build."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from deckwright.motion.read import clicks, sequences

Kind = Literal[
    "moved",
    "retyped",
    "restyled",
    "relabelled",
    "retimed",
    "added",
    "gone",
    "slide-added",
    "slide-moved",
    "slide-gone",
]

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"


@dataclass(frozen=True)
class Change:
    """One difference between the deck on disk and the build that made it."""

    kind: Kind
    slide: int
    shape: str
    detail: str


def style_drift(shape, claimed: list[dict[str, Any]], index: int, name: str) -> list[Change]:
    """A size the build never set, or the recorded ink gone from every run.

    Runs are compared as sets: a heading in an accent beside body text in the ink is one
    shape with two colours, and only the ink is recorded.
    """
    sizes, colours = _run_styles(shape)
    was_sizes = {
        round(float(v), 1)
        for r in claimed
        for v in (r.get("line_pt") or [r.get("font_pt")])
        if v is not None
    }
    was_inks = {str(r["fg"]).upper() for r in claimed if r.get("fg")}
    parts = []
    if sizes and was_sizes and sizes != was_sizes:
        parts.append(f"size {_pts(was_sizes)} → {_pts(sizes)}")
    if colours and was_inks and not was_inks & colours:
        parts.append(f"colour {', '.join(sorted(was_inks))} → {', '.join(sorted(colours))}")
    return [Change("restyled", index, name, "; ".join(parts))] if parts else []


def _run_styles(shape) -> tuple[set[float], set[str]]:
    """Every point size and literal colour the shape's runs set."""
    props = shape._element.findall(f".//{{{_A}}}r/{{{_A}}}rPr")
    sizes = {round(int(p.get("sz")) / 100, 1) for p in props if p.get("sz")}
    colours = {
        str(c.get("val")).upper()
        for p in props
        for c in p.findall(f"{{{_A}}}solidFill/{{{_A}}}srgbClr")
    }
    return sizes, colours


def _pts(sizes: set[float]) -> str:
    return "/".join(f"{s:g}" for s in sorted(sizes, reverse=True)) + "pt"


@dataclass(frozen=True)
class _Motion:
    """What a slide's build spends and shows, in terms both the manifest and the file carry."""

    clicks: int
    revealed: frozenset[str]
    triggers: frozenset[str]

    def __str__(self) -> str:
        return (
            f"{self.clicks} click(s), {len(self.revealed)} shape(s) revealed, "
            f"{len(self.triggers)} trigger(s)"
        )


def motion_drift(slide, animations: list[dict[str, Any]], index: int) -> list[Change]:
    timing = slide._element.find(f"{{{_P}}}timing")
    if not animations and timing is None:
        return []
    was = _Motion(
        clicks=sum(int(a.get("clicks", 0)) for a in animations),
        revealed=frozenset(
            str(n).split(" ¶", 1)[0]
            for a in animations
            for step in a.get("steps") or []
            for n in step
        ),
        triggers=frozenset(_placement(str(a["trigger"])) for a in animations if a.get("trigger")),
    )
    now = _Motion(0, frozenset(), frozenset())
    if timing is not None:
        names = {
            int(str(e.get("id"))): str(e.get("name", ""))
            for e in slide._element.iter(f"{{{_P}}}cNvPr")
            if str(e.get("id", "")).isdigit()
        }
        interactive, main = sequences(timing)
        shown = main | {spid for _, targets in interactive for spid in targets}
        now = _Motion(
            clicks=clicks(timing),
            revealed=frozenset(names.get(s, str(s)) for s in shown),
            triggers=frozenset(
                _placement(names.get(t, str(t))) for t, _ in interactive if t is not None
            ),
        )
    return [] if was == now else [Change("retimed", index, f"slide {index}", f"{was} → {now}")]


def _placement(name: str) -> str:
    """A shape's name without its part number: every shape a placement drew listens as one."""
    return name.rsplit("#", 1)[0]
