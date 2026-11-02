"""Copy that was never meant to ship: scaffold lines, lorem, TODO markers."""

from __future__ import annotations

import re
from typing import Any

from deckwright.compile.record import box_of
from deckwright.compile.scaffold import SCAFFOLD_WORDS
from deckwright.qa.model import Finding, Severity
from deckwright.qa.walk import all_shapes, slides
from deckwright.theme.model import Theme

# `todo` is an ordinary Spanish word: a bare TODO that goes on in capitals is a kicker, and
# the lowercase form is a marker only as a line's prefix.
_GENERIC = re.compile(
    r"(?i:\b(?:lorem|ipsum|fixme)\b|\[insert|@todo\b)"
    r"|\bTODO:|\bTODO\b(?!\s+[A-ZÁÉÍÓÚÜÑ]{2})"
    r"|(?m:^todo:)"
    r"|\bx{3,}\b|\bX{3,}\b"
)

_DETAIL = "reads like copy nobody meant to ship"


def _hit(text: str) -> str | None:
    for word in SCAFFOLD_WORDS:
        if word in text:
            return word
    found = _GENERIC.search(text)
    return found.group(0) if found else None


def _texts(shape: dict[str, Any]) -> list[str]:
    """A shape's recorded words: chrome fields and table cells record ``text``, not ``lines``."""
    lines = shape.get("lines")
    if lines:
        return [str(line) for line in lines]
    text = shape.get("text")
    return [str(text)] if text else []


def check_placeholder(manifest: dict[str, Any], theme: Theme) -> list[Finding]:
    """Flag recorded text that reads like scaffold or placeholder copy.

    Blind to a rasterized panel's copy, which never reaches the manifest (``docs/qa.md``).
    """
    findings: list[Finding] = []
    for slide in slides(manifest):
        for shape in all_shapes(slide):
            for line in _texts(shape):
                word = _hit(line)
                if not word:
                    continue
                findings.append(
                    Finding(
                        slide=slide["index"],
                        check="placeholder",
                        severity=Severity.WARN,
                        detail=f"{word!r} {_DETAIL}",
                        box=box_of(shape),
                        shape=shape.get("name"),
                    )
                )
        word = _hit(str(slide.get("notes") or ""))
        if word:
            findings.append(
                Finding(
                    slide=slide["index"],
                    check="placeholder",
                    severity=Severity.WARN,
                    detail=f"{word!r} in the speaker notes {_DETAIL}",
                )
            )
    return findings
