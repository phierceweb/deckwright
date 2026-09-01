"""Cache rendered panel PNGs by content hash.

The key includes the theme hash and the content policy as well as the HTML: editing
the template changes the palette, and a PNG keyed only on markup would serve the old
colours — or a render made under an older policy — forever.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import Protocol

from pf_core.log import get_logger

from deckwright.errors import RenderError
from deckwright.panels.model import Panel
from deckwright.services.htmlshot import CSP_META
from deckwright.utils.env import env_str

logger = get_logger(__name__)

_CACHE_DIR_DEFAULT = ".deckwright-cache"
_CACHE_DIR_ENV_VAR = "DECKWRIGHT_CACHE_DIR"


class PanelRenderer(Protocol):
    def __call__(self, html: str, path: str, *, width: int, scale: int) -> str: ...


def _cache_dir() -> Path:
    return Path(env_str(None, _CACHE_DIR_ENV_VAR, default=_CACHE_DIR_DEFAULT)) / "panels"


def cache_key(html: str, *, width: int, scale: int, theme_hash: str) -> str:
    """Identity of a rendered panel: its markup, its geometry, its theme, its policy."""
    digest = hashlib.sha256()
    for part in (html, str(width), str(scale), theme_hash, CSP_META):
        digest.update(part.encode())
        digest.update(b"\0")
    return digest.hexdigest()[:20]


def cached_png(panel: Panel, *, scale: int, theme_hash: str, render: PanelRenderer) -> Path:
    """Return a PNG of ``panel``, rendering it only on a cache miss.

    Renders to a temp file and swaps it into place: a process killed mid-render or a
    concurrent build must never leave a partial file a later call would treat as a hit.
    """
    key = cache_key(panel.html, width=panel.width, scale=scale, theme_hash=theme_hash)
    path = _cache_dir() / f"{key}.png"
    if path.is_file():
        logger.info("panel_cache_hit", key=key)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{key}.{uuid.uuid4().hex}.tmp.png")
    try:
        render(panel.html, str(tmp_path), width=panel.width, scale=scale)
        if not tmp_path.is_file() or tmp_path.stat().st_size == 0:
            raise RenderError(f"renderer produced no file for panel {key}")
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)
    logger.info("panel_cache_miss", key=key, width=panel.width, scale=scale)
    return path
