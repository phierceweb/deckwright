"""What Keynote draws a link in: the template's ``hlink`` colour, whatever ink the build wrote.

Against each linked shape's recorded ground, that colour is legible or it is not.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

from deckwright.qa.model import Finding, Severity
from deckwright.theme.clrscheme import parse_color_scheme
from deckwright.utils.color import AA_NORMAL, contrast_ratio
from deckwright.utils.xml import fromstring as parse_xml

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_SLIDE = re.compile(r"ppt/slides/slide(\d+)\.xml$")
_THEME = "ppt/theme/theme1.xml"


def check_link_contrast(deck: str | Path, data: dict[str, Any]) -> list[Finding]:
    """A finding per linked shape whose template link colour fails AA on the shape's ground."""
    try:
        archive = zipfile.ZipFile(deck)
    except (OSError, zipfile.BadZipFile):
        return []  # `package` owns that finding
    findings: list[Finding] = []
    with archive:
        names = set(archive.namelist())
        hlink = parse_color_scheme(archive.read(_THEME)).get("hlink") if _THEME in names else None
        if hlink is None:
            return []
        grounds = {
            (int(slide.get("index", 0)), str(shape.get("name", ""))): shape.get("bg")
            for slide in data.get("slides") or []
            for shape in slide.get("shapes") or []
        }
        for part in sorted(n for n in names if _SLIDE.match(n)):
            index = int(part.rsplit("slide", 1)[1].removesuffix(".xml"))
            try:
                root = parse_xml(archive.read(part))
            except etree.XMLSyntaxError:
                continue
            for sp in root.iter(f"{{{_P}}}sp"):
                if sp.find(f".//{{{_A}}}hlinkClick") is None:
                    continue
                name = str(sp.find(f".//{{{_P}}}cNvPr").get("name", ""))
                ground = grounds.get((index, name))
                if not ground:
                    continue
                ratio = contrast_ratio(hlink, str(ground))
                if ratio < AA_NORMAL:
                    findings.append(
                        Finding(
                            slide=index,
                            check="link-contrast",
                            severity=Severity.WARN,
                            shape=name,
                            detail=(
                                f"Keynote draws links in the template's hlink colour {hlink}, "
                                f"{ratio:.1f}:1 on this shape's ground {ground}. PowerPoint and "
                                f"LibreOffice draw the line's own ink. For a Keynote audience, "
                                f"move the link onto the page ground or rebind hlink in the "
                                f"template"
                            ),
                        )
                    )
    return findings
