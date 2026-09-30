"""A morph slide pairs what it shares with the slide before. What it shares is a name."""

from __future__ import annotations

from typing import Any

from deckwright.motion.transition import MORPH
from deckwright.qa.model import Finding, Severity
from deckwright.theme.model import Theme

_PREFIX = "m."


def check_morph(data: dict[str, Any], theme: Theme) -> list[Finding]:
    """A finding per morph name with no namesake on the slide before, and per morph slide
    that names nothing."""
    findings: list[Finding] = []
    before: set[str] = set()
    for slide in data.get("slides") or []:
        here = _names(slide)
        if slide.get("transition") == MORPH:
            index = int(slide.get("index", 0))
            for name in sorted(here - before):
                findings.append(
                    Finding(
                        slide=index,
                        check="morph-unpaired",
                        severity=Severity.WARN,
                        detail=(
                            f"'morph: {name}' has no namesake on slide {index - 1}, so "
                            f"Morph has nothing of that name to pair it with"
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


def _names(slide: dict[str, Any]) -> set[str]:
    """The `morph:` names a slide's shapes carry: `m.<name>.<component>#k` read from the right."""
    return {
        str(shape["name"])[len(_PREFIX) :].rsplit(".", 1)[0]
        for shape in slide.get("shapes") or []
        if str(shape.get("name", "")).startswith(_PREFIX)
    }
