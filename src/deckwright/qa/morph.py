"""A morph slide pairs what it shares with the slide before. What it shares is a name."""

from __future__ import annotations

from typing import Any

from deckwright.motion.transition import MORPH
from deckwright.qa.model import Finding, Severity
from deckwright.spec._origin import counted, origin_of
from deckwright.theme.model import Theme


def check_morph(data: dict[str, Any], theme: Theme) -> list[Finding]:
    """A finding per name new on a morph slide while a name of the same component from the
    slide before is gone — a shape renamed, which Morph cannot pair — and per morph slide that
    names nothing. A new name with no such loss is a shape entering the sequence."""
    findings: list[Finding] = []
    slides = list(data.get("slides") or [])
    before: dict[str, set[str]] = {}
    for slide in slides:
        here = _names(slide)
        if slide.get("transition") == MORPH:
            index = int(slide.get("index", 0))
            for name in sorted(here.keys() - before.keys()):
                dropped = sorted(n for n in before.keys() - here.keys() if before[n] & here[name])
                if not dropped:
                    continue
                gone = ", ".join(f"'{n}'" for n in dropped)
                appears = "appears" if len(dropped) == 1 else "appear"
                findings.append(
                    Finding(
                        slide=index,
                        check="morph-unpaired",
                        severity=Severity.WARN,
                        detail=(
                            f"'morph: {name}' has no namesake on slide {index - 1}, where "
                            f"{gone} no longer {appears} — if it is the same shape renamed, "
                            f"Morph fades one out and the other in rather than gliding"
                        ),
                    )
                )
            if not here:
                findings.append(
                    Finding(
                        slide=index,
                        check="morph-unpaired",
                        severity=Severity.WARN,
                        detail=(
                            "the slide asks to morph and names nothing: no placement on it "
                            "carries 'morph:', so Morph is given no name to pair"
                        ),
                    )
                )
        before = here
    return findings


def _names(slide: dict[str, Any]) -> dict[str, set[str]]:
    """Each `morph:` name a slide's shapes carry, with the components drawn under it."""
    names: dict[str, set[str]] = {}
    for shape in slide.get("shapes") or []:
        named = _morph_name(str(shape.get("name", "")))
        if named is not None:
            names.setdefault(named[0], set()).add(named[1])
    return names


def _morph_name(full: str) -> tuple[str, str] | None:
    """A morph shape's name and component, or None for any other shape."""
    origin = origin_of(full)
    if origin is not None:
        return (origin.placement, origin.component) if origin.morph else None
    if not full.startswith("m."):
        return None
    # A component the deck registers itself (`extends:`) is not in the registry qa loads.
    name, dot, component = counted(full[2:])[0].rpartition(".")
    return (name, component) if dot else None
