"""Does every click action and hyperlink in the saved deck go somewhere?

`relationship` already fails a reference nothing declares. This asks the next question: a
slide jump must land on a slide the show contains, a relative jump must be one PowerPoint
knows, and a web link must be an address a browser can open.
"""

from __future__ import annotations

import posixpath
import re
import zipfile
from pathlib import Path

from lxml import etree

from deckwright.qa.model import Finding, Severity
from deckwright.utils.links import web_address_problem
from deckwright.utils.xml import fromstring as parse_xml

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_SLIDE = re.compile(r"ppt/slides/slide(\d+)\.xml$")
_JUMPS = frozenset(
    {"firstslide", "lastslide", "nextslide", "previousslide", "lastslideviewed", "endshow"}
)


def check_links(deck: str | Path) -> list[Finding]:
    """A finding for each click action or hyperlink that cannot reach its target."""
    try:
        archive = zipfile.ZipFile(deck)
    except (OSError, zipfile.BadZipFile):
        return []
    findings: list[Finding] = []
    with archive:
        names = set(archive.namelist())
        shown = _slides_in_show(archive, names)
        for part, match in sorted((n, m) for n in names if (m := _SLIDE.match(n))):
            index = int(match.group(1))
            try:
                root = parse_xml(archive.read(part))
            except etree.XMLSyntaxError:
                continue
            rels = _relationships(archive, part, names)
            for link in root.iter(
                f"{{{_A}}}hlinkClick", f"{{{_A}}}hlinkHover", f"{{{_A}}}hlinkMouseOver"
            ):
                problem = _problem(link, rels, part, shown)
                if problem is not None:
                    severity, detail = problem
                    findings.append(
                        Finding(slide=index, check="link", severity=severity, detail=detail)
                    )
    return findings


def _problem(link, rels, part: str, shown: set[str]) -> tuple[Severity, str] | None:
    action = link.get("action") or ""
    rid = link.get(f"{{{_R}}}id") or ""
    if action.startswith("ppaction://hlinkshowjump"):
        jump = action.partition("jump=")[2]
        if jump in _JUMPS:
            return None
        return Severity.WARN, f"a click jumps to {jump or 'nothing'!r}, which no show can follow"
    if action.startswith("ppaction://hlinksldjump"):
        rel = rels.get(rid)
        if rel is None:
            return (
                Severity.ERROR,
                f"a click jumps to a slide through {rid!r}, which is declared nowhere",
            )
        target = posixpath.normpath(posixpath.join(posixpath.dirname(part), rel[0]))
        if target not in shown:
            return (
                Severity.ERROR,
                f"a click jumps to {target}, which is not a slide in this show",
            )
        return None
    if action:
        return None  # media, macros, custom shows: not a link this check reads
    rel = rels.get(rid)
    if rel is None:
        return None if not rid else (Severity.ERROR, f"a link's {rid!r} is declared nowhere")
    address, external = rel
    if not external:
        return None
    problem = web_address_problem(address)
    return None if problem is None else (Severity.WARN, f"a link to {problem}")


def _relationships(archive, part: str, names: set[str]) -> dict[str, tuple[str, bool]]:
    """``{rId: (target, external)}`` for ``part``."""
    rels_part = posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels")
    if rels_part not in names:
        return {}
    out = {}
    for rel in parse_xml(archive.read(rels_part)).iter(f"{{{_REL}}}Relationship"):
        out[str(rel.get("Id"))] = (str(rel.get("Target")), rel.get("TargetMode") == "External")
    return out


def _slides_in_show(archive, names: set[str]) -> set[str]:
    """The slide parts ``presentation.xml`` lists, resolved to package names."""
    if "ppt/presentation.xml" not in names:
        return set()
    rels = _relationships(archive, "ppt/presentation.xml", names)
    root = parse_xml(archive.read("ppt/presentation.xml"))
    out = set()
    for sld in root.iter(f"{{{_P}}}sldId"):
        rel = rels.get(str(sld.get(f"{{{_R}}}id")))
        if rel is not None:
            out.add(posixpath.normpath(posixpath.join("ppt", rel[0])))
    return out
