"""Resolve an image named in a deck spec or a theme to a file on disk.

Callers differ only in the ``roots`` they pass; the template is always a *fallback*,
never the only place to look, because a themeless deck has no template.

Config (env, read at call time, so ``.env`` changes take effect between runs):

- ``DECKWRIGHT_CACHE_DIR`` — root for the extracted-media cache (default ``.deckwright-cache``).
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Sequence

from pf_core.utils.io import atomic_write_bytes

from deckwright.errors import ThemeError
from deckwright.utils.env import env_str

_CACHE_DIR_DEFAULT = ".deckwright-cache"
_CACHE_DIR_ENV_VAR = "DECKWRIGHT_CACHE_DIR"


def _cache_dir() -> Path:
    """Root of the extracted-media cache. Read at call time, not import time."""
    root = env_str(None, _CACHE_DIR_ENV_VAR, default=_CACHE_DIR_DEFAULT)
    return Path(root) / "media"


def resolve_media(name: str, *, template: Path | None = None, roots: Sequence[Path] = ()) -> Path:
    """Return a filesystem path to the image ``name``.

    An absolute ``name`` is taken as written. Otherwise each directory in ``roots`` is
    tried in order, then the directory holding ``template``, and finally the
    template's own ``ppt/media/<name>``, extracted to a cache keyed on the template's
    content hash — a name-keyed cache would serve stale art after an in-place edit.

    Raises:
        ThemeError: the image is in none of those places, or a relative ``name``
            climbs out of them with ``..``.
    """
    path = Path(name)
    if path.is_absolute():
        if path.is_file():
            return path
        raise ThemeError(f"image {name!r} does not exist")
    if ".." in path.parts:
        raise ThemeError(
            f"image {name!r} climbs out of every directory it would be looked for "
            f"in — name it relative to the deck spec or the theme's template, or "
            f"give the full path"
        )
    searched = [*roots, *(() if template is None else (template.parent,))]
    for root in searched:
        candidate = root / name
        if candidate.is_file():
            return candidate
    if template is None:
        raise ThemeError(
            f"image {name!r} was not found in {_places(searched)}, and the theme names "
            f"no template to fall back on — put the file beside the deck spec, or give "
            f"the theme a 'template:' that carries it"
        )
    return _from_template(template, name, searched)


def _from_template(template: Path, name: str, searched: Sequence[Path]) -> Path:
    digest = hashlib.sha256(template.read_bytes()).hexdigest()[:16]
    cached = _cache_dir() / digest / name
    if cached.is_file():
        return cached
    try:
        with zipfile.ZipFile(template) as archive:
            data = archive.read(f"ppt/media/{name}")
    except (KeyError, OSError, zipfile.BadZipFile) as e:
        raise ThemeError(
            f"image {name!r} was not found in {_places(searched)}, nor inside "
            f"{template} at ppt/media/{name}"
        ) from e
    cached.parent.mkdir(parents=True, exist_ok=True)
    # A torn cache entry is served as a hit forever after: the key is the template's
    # digest, not the extracted file's.
    atomic_write_bytes(cached, data)
    return cached


def _places(searched: Sequence[Path]) -> str:
    return ", ".join(str(p) for p in searched) if searched else "any search directory"
