"""What a render was made from, recorded beside it so the next reader can reuse it.

``render`` writes the stamp after every successful conversion. A reader reuses the render
only when the deck on disk has the bytes the stamp names, a render now would be given the
same font files, and every file the render wrote is still there with the bytes it had — so
a stamp outlived by its files vouches for nothing.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pf_core.log import get_logger
from pf_core.utils.hashing import content_hash
from pf_core.utils.io import atomic_write_json

from deckwright.paths import SCRATCH, scratch

logger = get_logger(__name__)

# Bump when a change to how a deck is rendered should retire every earlier render.
RECIPE = 1
_NAME = "render.json"


def write_stamp(
    outdir: Path,
    *,
    deck_hash: str,
    fonts: list[Path],
    pdf: Path,
    images: list[Path],
    dpi: int,
    fmt: str,
) -> None:
    """Record that ``pdf`` and ``images`` in ``outdir`` were rendered from ``deck_hash``
    with ``fonts`` linked."""
    atomic_write_json(
        scratch(outdir) / _NAME,
        {
            "recipe": RECIPE,
            "deck_sha256": deck_hash,
            "fonts": [str(f) for f in fonts],
            "dpi": dpi,
            "format": fmt,
            "pages": len(images),
            "pdf": pdf.name,
            "images": [p.name for p in images],
            "files": {p.name: _digest(p) for p in (pdf, *images)},
        },
    )


def matching_render(
    pptx: Path, outdir: Path, *, dpi: int, fonts: Callable[[], list[Path]]
) -> list[str] | None:
    """The page images in ``outdir`` if they were rendered from ``pptx`` as it is now, with
    the font files ``fonts`` answers, at ``dpi`` or finer, and every file intact; otherwise
    None. ``fonts`` is asked last, since it runs fontconfig."""
    stamp = _read(outdir / SCRATCH / _NAME)
    reason = "no stamp" if stamp is None else _mismatch(stamp, pptx, outdir, dpi=dpi, fonts=fonts)
    if stamp is None or reason:
        logger.info("render_not_reused", outdir=str(outdir), reason=reason)
        return None
    return [str(outdir / name) for name in stamp["images"]]


def _mismatch(
    stamp: dict[str, Any],
    pptx: Path,
    outdir: Path,
    *,
    dpi: int,
    fonts: Callable[[], list[Path]],
) -> str:
    if stamp.get("recipe") != RECIPE:
        return "rendered by another version"
    if stamp.get("pdf") != f"{pptx.stem}.pdf":
        return "rendered from another deck"
    if stamp.get("deck_sha256") != content_hash(pptx.read_bytes()):
        return "the deck has changed since"
    if not isinstance(stamp.get("dpi"), int) or stamp["dpi"] < dpi:
        return f"rendered at {stamp.get('dpi')} dpi, below {dpi}"
    images, files = stamp.get("images"), stamp.get("files")
    if not isinstance(images, list) or not images or not isinstance(files, dict):
        return "the stamp names no pages"
    if set(files) != {stamp["pdf"], *images} or any(Path(n).name != n for n in files):
        return "the stamp's files are not its pages"
    for name, digest in files.items():
        path = outdir / name
        if not path.is_file() or _digest(path) != digest:
            return f"{name} is missing or changed"
    if stamp.get("fonts") != [str(f) for f in fonts()]:
        return "a render now would be given other fonts"
    return ""


def _read(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _digest(path: Path) -> str:
    return content_hash(path.read_bytes())
