"""Which faces a theme sets type in, and whether this machine has them.

fontconfig is asked through :mod:`deckwright.utils.fontconfig`, which lists its knobs.
"""

from __future__ import annotations

from pf_core.log import get_logger

from deckwright.theme.model import Theme
from deckwright.utils.env import env_str
from deckwright.utils.fontconfig import CJK_LANGS, FC_LIST_DEFAULT
from deckwright.utils.fontconfig import fc_list as _fc_list

logger = get_logger(__name__)


def theme_faces(theme: Theme) -> tuple[str, ...]:
    """Every distinct typeface this theme can set type in, in reading order."""
    named = [
        theme.face,
        theme.heading_face,
        *(style.face or "" for style in theme.ramp.values()),
        theme.mono,
    ]
    return tuple(dict.fromkeys(face for face in named if face))


def installed_families(
    *, fc_list: str | None = None, timeout: int | None = None
) -> frozenset[str] | None:
    """Every font family this machine can set, casefolded — or None if it cannot be asked.

    None and an empty set are different answers: None means fontconfig is absent or
    failed, so a caller must not conclude anything about a face.
    """
    found = _fc_list([":", "family"], fc_list=fc_list, timeout=timeout)
    if found is None:
        logger.info(
            "font_scan_unavailable",
            fc_list=env_str(fc_list, "DECKWRIGHT_FC_LIST", default=FC_LIST_DEFAULT),
        )
        return None
    families = {
        alias.strip().casefold()
        for line in found.splitlines()
        for alias in line.split(",")
        if alias.strip()
    }
    logger.info("font_scan_done", families=len(families))
    return frozenset(families)


def cjk_postscript_names(
    *, fc_list: str | None = None, timeout: int | None = None
) -> frozenset[str] | None:
    """The PostScript names of every installed font covering Chinese, Japanese or Korean.

    None when fontconfig cannot be asked.
    """
    names: set[str] = set()
    for lang in CJK_LANGS:
        found = _fc_list([f":lang={lang}", "postscriptname"], fc_list=fc_list, timeout=timeout)
        if found is None:
            return None
        names.update(
            line.partition("postscriptname=")[2].strip()
            for line in found.splitlines()
            if "postscriptname=" in line
        )
    return frozenset(n for n in names if n)


def postscript_names(
    *, fc_list: str | None = None, timeout: int | None = None
) -> dict[str, frozenset[str]] | None:
    """Each installed family, casefolded, with the PostScript names a PDF embeds it under.

    A PDF names ``游ゴシック`` as ``YuGothic-Medium``, so a family name alone cannot be found
    in one. None when fontconfig cannot be asked.
    """
    found = _fc_list([":", "family", "postscriptname"], fc_list=fc_list, timeout=timeout)
    if found is None:
        return None
    names: dict[str, set[str]] = {}
    for line in found.splitlines():
        families, _, rest = line.partition(":")
        postscript = rest.partition("postscriptname=")[2].strip()
        if not postscript:
            continue
        for family in families.split(","):
            if family.strip():
                names.setdefault(family.strip().casefold(), set()).add(postscript)
    return {family: frozenset(ps) for family, ps in names.items()}


def missing_faces(theme: Theme, installed: frozenset[str] | None) -> tuple[str, ...]:
    """The faces ``theme`` names that ``installed`` lacks. Empty when ``installed`` is None."""
    if installed is None:
        return ()
    return tuple(face for face in theme_faces(theme) if face.casefold() not in installed)
