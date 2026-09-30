"""Will PowerPoint open this file at all?

A duplicate shape id, a dangling relationship or an animation targeting a shape that was
never drawn all end in a repair prompt and silently discarded content. LibreOffice is far
more forgiving, so a clean render proves nothing here — these read the saved package.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

from deckwright.qa._parts import rels_part, resolve
from deckwright.qa.model import Finding, Severity
from deckwright.utils.mce import apart
from deckwright.utils.xml import fromstring as parse_xml

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_SLIDE = re.compile(r"ppt/slides/slide(\d+)\.xml$")
# Ids are unsigned 32-bit and 0 is reserved; PowerPoint rejects both ends.
_MAX_ID = 2_147_483_647

# A shape's id, its name, and the ``cNvPr`` that carries both.
_Id = tuple[int, str, Any]


def check_package(deck: str | Path) -> list[Finding]:
    """Every structural fault that would stop PowerPoint opening ``deck``."""
    deck = Path(deck)
    findings: list[Finding] = []
    try:
        archive = zipfile.ZipFile(deck)
    except (OSError, zipfile.BadZipFile) as e:
        return [
            Finding(
                slide=0,
                check="package",
                severity=Severity.ERROR,
                detail=f"{deck.name} is not a readable .pptx: {e}",
            )
        ]
    with archive:
        names = set(archive.namelist())
        slides = {n: m for n in names if (m := _SLIDE.match(n))}
        for part in sorted(slides):
            index = int(slides[part].group(1))
            try:
                root = parse_xml(archive.read(part))
            except etree.XMLSyntaxError as e:
                findings.append(
                    Finding(
                        slide=index,
                        check="package",
                        severity=Severity.ERROR,
                        detail=f"{part} is not well-formed XML: {e}",
                    )
                )
                continue
            ids = _shape_ids(root)
            findings.extend(_duplicate_ids(ids, index))
            findings.extend(_duplicate_names(ids, index))
            findings.extend(_out_of_range_ids(ids, index))
            findings.extend(_dangling_animation_targets(root, ids, index))
            findings.extend(_dangling_relationships(root, archive, part, names, index))
    return findings


def _shape_ids(root) -> list[_Id]:
    """Every drawn shape's id and name, in document order — repeats included.

    A dict would drop exactly the repeats this exists to find.
    """
    out: list[_Id] = []
    for el in root.iter(f"{{{_P}}}cNvPr"):
        try:
            out.append((int(el.get("id", "")), str(el.get("name", "")), el))
        except ValueError:
            continue
    return out


def _earlier(seen: list[tuple[Any, Any]], element) -> Any | None:
    """The first of ``seen`` a reader could see beside ``element``.

    The Choice and Fallback of an ``mc:AlternateContent`` are alternatives, so the two
    copies of one shape PowerPoint writes there may share an id and a name.
    """
    return next((value for value, other in seen if not apart(other, element)), None)


def _duplicate_ids(ids: list[_Id], index: int) -> list[Finding]:
    """Two shapes sharing an id — the classic fault in hand-built shape XML."""
    seen: dict[int, list[tuple[str, Any]]] = {}
    findings = []
    for value, name, element in ids:
        first = _earlier(seen.get(value, []), element)
        if first is not None:
            findings.append(
                Finding(
                    slide=index,
                    check="shape-id",
                    severity=Severity.ERROR,
                    detail=(
                        f"shape id {value} is used by both {first!r} and "
                        f"{name!r}; PowerPoint repairs a slide with a duplicate id"
                    ),
                    shape=name,
                )
            )
        seen.setdefault(value, []).append((name, element))
    return findings


def _duplicate_names(ids: list[_Id], index: int) -> list[Finding]:
    """Two shapes sharing a name — legal and invisible, so nothing else catches it.

    Every shape a build names gets a distinct one, so a repeat means the naming rule
    has drifted.
    """
    seen: dict[str, list[tuple[int, Any]]] = {}
    findings = []
    for value, name, element in ids:
        if not name:
            continue
        first = _earlier(seen.get(name, []), element)
        if first is not None:
            findings.append(
                Finding(
                    slide=index,
                    check="shape-name",
                    severity=Severity.WARN,
                    detail=(
                        f"shape name {name!r} is used by both id {first} and "
                        f"id {value}; a hand-edited shape cannot be mapped back to the "
                        f"spec node that drew it"
                    ),
                    shape=name,
                )
            )
        seen.setdefault(name, []).append((value, element))
    return findings


def _out_of_range_ids(ids: list[_Id], index: int) -> list[Finding]:
    return [
        Finding(
            slide=index,
            check="shape-id",
            severity=Severity.ERROR,
            detail=f"shape id {value} is outside 1..{_MAX_ID}",
            shape=name,
        )
        for value, name, _ in ids
        if value <= 0 or value > _MAX_ID
    ]


def _dangling_animation_targets(root, ids: list[_Id], index: int) -> list[Finding]:
    """An animation naming a shape the slide does not hold.

    Timing is the one tree deckwright writes as raw XML, so a renumbered shape leaves the
    build green and the file broken.
    """
    drawn = {value for value, _, _ in ids}
    findings = []
    for target in root.iter(f"{{{_P}}}spTgt"):
        try:
            spid = int(target.get("spid", ""))
        except ValueError:
            continue
        if spid not in drawn:
            findings.append(
                Finding(
                    slide=index,
                    check="animation-target",
                    severity=Severity.ERROR,
                    detail=(
                        f"an animation targets shape id {spid}, which this slide does "
                        f"not contain — PowerPoint repairs the file and drops the build"
                    ),
                )
            )
    return findings


def _dangling_relationships(root, archive, part: str, names: set[str], index: int) -> list[Finding]:
    """An ``r:embed``/``r:id`` with no matching relationship, or one pointing nowhere."""
    rels = rels_part(part)
    targets: dict[str, str] = {}
    external: set[str] = set()
    if rels in names:
        for rel in parse_xml(archive.read(rels)):
            targets[str(rel.get("Id"))] = str(rel.get("Target"))
            if rel.get("TargetMode") == "External":
                external.add(str(rel.get("Id")))
    findings = []
    # An empty id on a click action is PowerPoint's own spelling for one that relates to nothing.
    used = {
        str(v)
        for el in root.iter()
        for k, v in el.attrib.items()
        if k.startswith(f"{{{_R}}}") and (v or el.get("action") is None)
    }
    for rid in sorted(used):
        if rid not in targets:
            findings.append(
                Finding(
                    slide=index,
                    check="relationship",
                    severity=Severity.ERROR,
                    detail=f"{rid} is referenced but declared in no relationship part",
                )
            )
            continue
        target = targets[rid]
        # An external target is an address, not a part; `link` judges it.
        if rid in external or target.startswith(("http://", "https://", "mailto:", "../slide")):
            continue
        resolved = resolve(part, target)
        if resolved not in names:
            findings.append(
                Finding(
                    slide=index,
                    check="relationship",
                    severity=Severity.ERROR,
                    detail=f"{rid} points at {target}, which the package does not contain",
                )
            )
    return findings
