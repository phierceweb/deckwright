"""Flatten a transparent slide-master background onto an opaque colour.

Nothing in the file says what a transparent master picture composites over, so
PowerPoint picks white and Keynote black. Only the built deck's copy is altered.
"""

from __future__ import annotations

import io
import re

from PIL import Image

from pf_core.log import get_logger

logger = get_logger(__name__)

_BG_EMBED = re.compile(rb"<p:bg>.*?r:embed=\"(rId\d+)\"", re.DOTALL)


def flatten_master_background(prs, rgb: tuple[int, int, int]) -> bool:
    """Composite each master's background picture onto ``rgb``. Returns True if changed."""
    changed = False
    for master in prs.slide_masters:
        match = _BG_EMBED.search(master.part.blob)
        if match is None:
            continue
        try:
            part = master.part.related_part(match.group(1).decode())
        except KeyError:
            continue
        flattened = _flatten(part.blob, rgb)
        if flattened is None:
            continue
        part._blob = flattened
        changed = True
        logger.info("master_background_flattened", part=str(part.partname), rgb=rgb)
    return changed


def _flatten(blob: bytes, rgb: tuple[int, int, int]) -> bytes | None:
    """Return ``blob`` composited onto ``rgb``, or None if it has no alpha to flatten."""
    try:
        image = Image.open(io.BytesIO(blob))
    except OSError:
        return None
    if image.mode not in ("RGBA", "LA", "P"):
        return None
    rgba = image.convert("RGBA")
    if rgba.getchannel("A").getextrema()[0] == 255:
        return None
    flat = Image.new("RGB", rgba.size, rgb)
    flat.paste(rgba, mask=rgba.getchannel("A"))
    buf = io.BytesIO()
    flat.save(buf, format="PNG")
    return buf.getvalue()
