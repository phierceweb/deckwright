"""Ask fontconfig a question, answering None when it cannot be asked.

Config (env, read at call time):

- ``DECKWRIGHT_FC_LIST``           — fontconfig's fc-list command (default ``fc-list``).
- ``DECKWRIGHT_FC_MATCH``          — fontconfig's fc-match command (default ``fc-match``).
- ``DECKWRIGHT_FC_LIST_TIMEOUT_S`` — seconds before either is killed (default 20).
"""

from __future__ import annotations

import subprocess

from pf_core.utils.env import resolve_int

from deckwright.utils.env import env_str

FC_LIST_DEFAULT = "fc-list"
_FC_MATCH_DEFAULT = "fc-match"
_TIMEOUT_S_DEFAULT = 20
CJK_LANGS = ("ja", "ko", "zh-cn", "zh-tw")


def fc_list(
    args: list[str], *, fc_list: str | None = None, timeout: int | None = None
) -> str | None:
    """fc-list's stdout for ``args``, or None when it is absent, fails or times out."""
    binary = env_str(fc_list, "DECKWRIGHT_FC_LIST", default=FC_LIST_DEFAULT)
    return _run([binary, *args], timeout=timeout)


def fc_match(args: list[str]) -> str | None:
    """fc-match's stdout for ``args``, or None when it is absent, fails or times out."""
    binary = env_str(None, "DECKWRIGHT_FC_MATCH", default=_FC_MATCH_DEFAULT)
    return _run([binary, *args], timeout=None)


def _run(argv: list[str], *, timeout: int | None) -> str | None:
    timeout_s: int = resolve_int(
        timeout, "DECKWRIGHT_FC_LIST_TIMEOUT_S", default=_TIMEOUT_S_DEFAULT
    )
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            check=True,
            timeout=timeout_s,
            encoding="utf-8",
            errors="replace",
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
