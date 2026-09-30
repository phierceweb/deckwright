"""Hand LibreOffice the fonts the deck names, so a render sets the deck's own type.

A LibreOffice started on a fresh profile may not reach the system's fonts at all: on macOS
it then sets Helvetica in Linux Libertine and draws CJK blank. Every file fontconfig holds
for a face the deck names is linked into the profile's ``user/fonts``, and, when the deck
carries CJK text, the file fontconfig picks for each CJK language. Only an installed family
whose name is the requested face is linked, never a substitute, so a face this machine lacks
is still reported by ``font-substituted``.

The files linked are recorded in the render's stamp, so installing a face retires a render
made without it.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

from pf_core.log import get_logger

from deckwright.utils._cjk import carries_cjk
from deckwright.utils.fontconfig import CJK_LANGS, fc_list, fc_match
from deckwright.utils.xml import fromstring as parse_xml

logger = get_logger(__name__)

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
_PART = re.compile(
    r"ppt/(theme/theme|slides/slide|slideLayouts/slideLayout|slideMasters/slideMaster"
    r"|charts/chart)\d+\.xml$"
)
_FACE_TAGS = tuple(f"{{{_A}}}{tag}" for tag in ("latin", "ea", "cs", "font", "buFont"))
_TEXT_TAGS = (f"{{{_A}}}t", f"{{{_C}}}v")


def deck_fonts(pptx: Path) -> tuple[frozenset[str], bool]:
    """Every typeface the deck's theme, masters, layouts, slides and charts name, and
    whether any of their text is Chinese, Japanese or Korean.

    Theme-slot references (``+mj-lt``, ``+mn-ea``) resolve to a face the theme names
    itself, so they are skipped.
    """
    faces: set[str] = set()
    cjk = False
    with zipfile.ZipFile(pptx) as archive:
        for part in archive.namelist():
            if not _PART.match(part):
                continue
            root = parse_xml(archive.read(part))
            for element in root.iter(*_FACE_TAGS):
                face = (element.get("typeface") or "").strip()
                if face and not face.startswith(("+mj-", "+mn-")):
                    faces.add(face)
            cjk = cjk or any(carries_cjk(t.text or "") for t in root.iter(*_TEXT_TAGS))
    return frozenset(faces), cjk


def font_files(faces: frozenset[str], *, cjk: bool) -> list[Path] | None:
    """The installed font files to hand LibreOffice, or None when fontconfig cannot be asked.

    A face matches an installed family, or any of its localised names, when the two are
    equal ignoring case and blanks — how fontconfig compares family names itself.
    """
    listing = fc_list(["-f", "%{family}\t%{file}\n"])
    if listing is None:
        return None
    wanted = {_key(face) for face in faces}
    files: dict[str, None] = {}
    for line in listing.splitlines():
        families, _, file = line.partition("\t")
        if file and any(_key(name) in wanted for name in families.split(",")):
            files[file] = None
    if cjk:
        chosen = [fc_match(["-f", "%{file}", f":lang={lang}"]) for lang in CJK_LANGS]
        if not any(chosen):
            logger.info("render_cjk_fonts_unavailable")
        files.update(dict.fromkeys(c.strip() for c in chosen if c))
    return [Path(f) for f in sorted(files) if Path(f).is_file()]


def deck_font_files(pptx: Path) -> list[Path]:
    """The font files a render of ``pptx`` hands LibreOffice on this machine.

    Anything that stops the lookup — a deck that is not a package, no fontconfig — answers
    none, and the render runs as it would have without them.
    """
    try:
        faces, cjk = deck_fonts(pptx)
    except (zipfile.BadZipFile, KeyError, etree.XMLSyntaxError) as e:
        logger.info("render_fonts_unread", pptx=str(pptx), reason=str(e))
        return []
    files = font_files(faces, cjk=cjk)
    if files is None:
        logger.info("render_fonts_unavailable", faces=len(faces))
        return []
    logger.info("render_fonts_found", faces=len(faces), files=len(files), cjk=cjk)
    return files


def seed_fonts(profile: Path, files: list[Path]) -> None:
    """Link ``files`` into the fonts directory of LibreOffice ``profile``."""
    if not files:
        return
    target = profile / "user" / "fonts"
    target.mkdir(parents=True, exist_ok=True)
    for index, file in enumerate(files):
        # Two families can ship files with the same name from different directories.
        (target / f"{index:03d}-{file.name}").symlink_to(file)


def _key(name: str) -> str:
    return re.sub(r"\s", "", name).casefold()
