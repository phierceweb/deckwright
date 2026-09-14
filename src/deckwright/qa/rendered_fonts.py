"""Which faces the render really set the deck in, read from the fonts its PDF embeds.

``fc-list`` answers what this machine has installed, which is not what LibreOffice used: a
renderer that cannot reach a font draws a substitute, and draws CJK blank or as boxes while
``pdftotext`` still extracts the words. The PDF's own font list is the render's answer.

Config (env, read at call time):

- ``DECKWRIGHT_PDFFONTS``           — Poppler's pdffonts command (default ``pdffonts``).
- ``DECKWRIGHT_PDFFONTS_TIMEOUT_S`` — seconds before it is killed (default 60).
"""

from __future__ import annotations

import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from pf_core.log import get_logger
from pf_core.utils.env import resolve_int

from deckwright.qa.model import Finding, Severity
from deckwright.theme.fonts import cjk_postscript_names, postscript_names
from deckwright.utils._cjk import carries_cjk
from deckwright.utils.env import env_str
from deckwright.utils.xml import fromstring as parse_xml

logger = get_logger(__name__)

_PDFFONTS_DEFAULT = "pdffonts"
_TIMEOUT_S_DEFAULT = 60
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_SLIDE = re.compile(r"ppt/slides/slide(\d+)\.xml$")


def embedded_fonts(pdf: Path, *, page: int | None = None) -> list[tuple[str, str]] | None:
    """``(name, encoding)`` for each font the PDF embeds, or None when pdffonts cannot run."""
    binary = env_str(None, "DECKWRIGHT_PDFFONTS", default=_PDFFONTS_DEFAULT)
    timeout_s: int = resolve_int(None, "DECKWRIGHT_PDFFONTS_TIMEOUT_S", default=_TIMEOUT_S_DEFAULT)
    pages = [] if page is None else ["-f", str(page), "-l", str(page)]
    try:
        result = subprocess.run(
            [binary, *pages, str(pdf)],
            capture_output=True,
            check=True,
            timeout=timeout_s,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        logger.info("pdffonts_unavailable", pdffonts=binary)
        return None
    return parse_pdffonts(result.stdout)


def parse_pdffonts(stdout: str) -> list[tuple[str, str]]:
    """pdffonts' table as ``(name, encoding)`` rows, sliced by its own dashed rule."""
    lines = stdout.splitlines()
    rule = next((i for i, line in enumerate(lines) if line.startswith("---")), None)
    if rule is None:
        return []
    spans = [(m.start(), m.end()) for m in re.finditer(r"-+", lines[rule])]
    if len(spans) < 3:
        return []
    rows = []
    for line in lines[rule + 1 :]:
        if not line.strip():
            continue
        name = line[spans[0][0] : spans[0][1]].strip()
        encoding = line[spans[2][0] : spans[2][1]].strip()
        rows.append((name, encoding))
    return rows


def deck_faces(deck: Path) -> set[str]:
    """Every typeface a slide run names as its latin or CJK face."""
    faces: set[str] = set()
    with zipfile.ZipFile(deck) as archive:
        for part in archive.namelist():
            if not _SLIDE.match(part):
                continue
            root = parse_xml(archive.read(part))
            for tag in ("latin", "ea"):
                for font in root.iter(f"{{{_A}}}{tag}"):
                    face = str(font.get("typeface") or "")
                    if face and not face.startswith(("+mj-", "+mn-")):
                        faces.add(face)
    return faces


def check_rendered_faces(deck: Path, pdf: Path, manifest: dict[str, Any]) -> list[Finding] | None:
    """A warning per face the render did not embed, and an error per slide whose CJK text
    no embedded font covers, as fontconfig lists CJK fonts. None when pdffonts cannot run,
    so the caller can fall back; the CJK half is skipped when fontconfig cannot answer."""
    embedded = embedded_fonts(pdf)
    if embedded is None:
        return None
    findings = _substituted(deck, embedded)
    cjk = {_bare(name) for name in cjk_postscript_names() or ()}
    slides = manifest.get("slides") or []
    for slide in slides if cjk else []:
        if not any(carries_cjk(t) for t in _texts(slide)):
            continue
        index = int(slide.get("index", 0))
        page = embedded_fonts(pdf, page=index)
        if page is not None and not any(_bare(name).startswith(c) for name, _ in page for c in cjk):
            findings.append(
                Finding(
                    slide=index,
                    check="cjk-unrendered",
                    severity=Severity.ERROR,
                    detail=(
                        "this slide carries Chinese, Japanese or Korean text, but the render "
                        f"embedded no font that can draw it ({_names(page) or 'none'}) — its "
                        "words render blank or as empty boxes while pdftotext still extracts them, "
                        "so `overflow` passes on text nobody can see. Give LibreOffice a CJK "
                        "font it can reach"
                    ),
                )
            )
    return findings


def _substituted(deck: Path, embedded: list[tuple[str, str]]) -> list[Finding]:
    rendered = {_bare(name) for name, _ in embedded}
    aliases = postscript_names() or {}
    out = []
    for face in sorted(deck_faces(deck)):
        candidates = {_bare(face)} | {_bare(ps) for ps in aliases.get(face.casefold(), ())}
        if any(r.startswith(c) for r in rendered for c in candidates if c):
            continue
        out.append(
            Finding(
                slide=0,
                check="font-substituted",
                severity=Severity.WARN,
                detail=(
                    f"the deck sets type in {face!r}, and the render embedded no such face "
                    f"({_names(embedded) or 'no fonts'}) — LibreOffice drew something else, "
                    f"so `overflow` and `render-contrast` judged a deck your audience will not "
                    f"see. Install the face where the render runs, or read those findings as "
                    f"approximate"
                ),
            )
        )
    return out


def _bare(name: str) -> str:
    """A font name without its subset tag, case, spaces or separators."""
    return re.sub(r"[\s_-]", "", name.split("+", 1)[-1]).casefold()


def _names(fonts: list[tuple[str, str]]) -> str:
    return ", ".join(sorted({name.split("+", 1)[-1] for name, _ in fonts}))


def _texts(slide: dict[str, Any]) -> list[str]:
    return [
        str(line)
        for shape in slide.get("shapes") or []
        for line in (shape.get("lines") or [shape.get("text") or ""])
    ]
