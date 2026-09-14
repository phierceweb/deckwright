"""Does every picture and chart say what it shows, or say that it shows nothing?

Reads the saved package, so alternative text written by hand after the build counts. A
table is text a screen reader already reaches, so its frame is not asked for any.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

from deckwright.qa.model import Finding, Severity
from deckwright.utils.a11y import description, is_file_name
from deckwright.utils.xml import fromstring as parse_xml

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_TABLE = "http://schemas.openxmlformats.org/drawingml/2006/table"
_CHART = "http://schemas.openxmlformats.org/drawingml/2006/chart"
_SLIDE = re.compile(r"ppt/slides/slide(\d+)\.xml$")


def check_alt_text(deck: str | Path) -> list[Finding]:
    """A warning for each picture or graphic frame carrying neither alt text nor the
    decorative flag. An unreadable package is ``check_package``'s finding, not this one's."""
    try:
        archive = zipfile.ZipFile(deck)
    except (OSError, zipfile.BadZipFile):
        return []
    findings: list[Finding] = []
    with archive:
        for part in sorted(archive.namelist(), key=_slide_number):
            match = _SLIDE.match(part)
            if match is None:
                continue
            try:
                root = parse_xml(archive.read(part))
            except etree.XMLSyntaxError:
                continue
            findings.extend(_unlabelled(root, int(match.group(1))))
    return findings


def _slide_number(part: str) -> int:
    match = _SLIDE.match(part)
    return int(match.group(1)) if match else 0


def _unlabelled(root, index: int) -> list[Finding]:
    out = []
    for element in root.iter(f"{{{_P}}}pic", f"{{{_P}}}graphicFrame"):
        # A fallback is what an older reader draws instead of its Choice, not a second figure.
        # An embedded object's preview picture belongs to the object's own frame.
        if any(a.tag in (f"{{{_MC}}}Fallback", f"{{{_P}}}oleObj") for a in element.iterancestors()):
            continue
        kind = _kind(element)
        if kind is None:
            continue
        c_nv_pr = element.find(f"*/{{{_P}}}cNvPr")
        if c_nv_pr is None:
            continue
        alt, decorative = description(c_nv_pr)
        if decorative or (alt and not is_file_name(alt)):
            continue
        name = str(c_nv_pr.get("name", ""))
        missing = (
            f"has only its file name {alt!r} as alternative text, which a screen reader reads aloud"
            if alt
            else "has no alternative text, so a screen reader announces it without "
            "saying what it shows"
        )
        out.append(
            Finding(
                slide=index,
                check="alt-text",
                severity=Severity.WARN,
                detail=(
                    f"{kind} {name!r} {missing} — set 'alt:' on the component that draws "
                    f"it, or 'decorative: true' when it carries no meaning"
                ),
                shape=name,
            )
        )
    return out


def _kind(element) -> str | None:
    """What to call a figure in a finding; None for a frame that holds text."""
    if element.tag == f"{{{_P}}}pic":
        return "picture"
    data = element.find(f"{{{_A}}}graphic/{{{_A}}}graphicData")
    uri = data.get("uri", "") if data is not None else ""
    if uri == _TABLE:
        return None
    return "chart" if uri == _CHART else "graphic frame"
