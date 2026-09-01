"""Which faces a theme sets type in, and whether this machine has them.

Config (env, read at call time, so ``.env`` changes take effect between runs):

- ``DECKWRIGHT_FC_LIST``           — fontconfig's fc-list command (default ``fc-list``).
- ``DECKWRIGHT_FC_LIST_TIMEOUT_S`` — seconds before it is killed (default 20).
"""

from __future__ import annotations

import subprocess

from pf_core.log import get_logger
from pf_core.utils.env import resolve_int

from deckwright.theme.model import Theme
from deckwright.utils.env import env_str

logger = get_logger(__name__)

_FC_LIST_DEFAULT = "fc-list"
_TIMEOUT_S_DEFAULT = 20


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
    binary = env_str(fc_list, "DECKWRIGHT_FC_LIST", default=_FC_LIST_DEFAULT)
    timeout_s: int = resolve_int(
        timeout, "DECKWRIGHT_FC_LIST_TIMEOUT_S", default=_TIMEOUT_S_DEFAULT
    )
    try:
        result = subprocess.run(
            [binary, ":", "family"],
            capture_output=True,
            check=True,
            timeout=timeout_s,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        logger.info("font_scan_unavailable", fc_list=binary)
        return None
    families = {
        alias.strip().casefold()
        for line in result.stdout.splitlines()
        for alias in line.split(",")
        if alias.strip()
    }
    logger.info("font_scan_done", families=len(families))
    return frozenset(families)


def missing_faces(theme: Theme, installed: frozenset[str] | None) -> tuple[str, ...]:
    """The faces ``theme`` names that ``installed`` lacks. Empty when ``installed`` is None."""
    if installed is None:
        return ()
    return tuple(face for face in theme_faces(theme) if face.casefold() not in installed)
