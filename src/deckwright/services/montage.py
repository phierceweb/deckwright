"""Stitch slide images into a single contact-sheet PNG for visual QA."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from pf_core.exceptions import InvalidInputError
from pf_core.log import get_logger

logger = get_logger(__name__)


def contact_sheet(
    images,
    out_path,
    *,
    cols: int = 4,
    thumb_width: int = 480,
    pad: int = 12,
    bg: tuple[int, int, int] = (245, 246, 248),
    numbers: bool = True,
) -> str:
    """Arrange ``images`` into a ``cols``-wide grid and save to ``out_path``.

    Args:
        images: Ordered image paths (e.g. ``render/slide-*.jpg``).
        out_path: Destination ``.png``.
        cols: Number of columns in the grid.
        thumb_width: Width each thumbnail is scaled to (px); height keeps aspect.
        pad: Gap and outer margin around thumbnails (px).
        bg: Background color.
        numbers: Draw a 1-based index badge on each thumbnail.

    Returns:
        ``str(out_path)``.

    Raises:
        InvalidInputError: ``images`` is empty.
    """
    paths = [Path(p) for p in images]
    if not paths:
        raise InvalidInputError("contact_sheet requires at least one image")
    cols = max(1, cols)

    thumbs = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        height = round(im.height * thumb_width / im.width)
        thumbs.append(im.resize((thumb_width, height)))

    cell_h = max(t.height for t in thumbs)
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (pad + cols * (thumb_width + pad), pad + rows * (cell_h + pad)), bg)
    draw = ImageDraw.Draw(sheet)
    for i, thumb in enumerate(thumbs):
        row, col = divmod(i, cols)
        x = pad + col * (thumb_width + pad)
        y = pad + row * (cell_h + pad)
        sheet.paste(thumb, (x, y))
        if numbers:
            _badge(draw, x + 4, y + 4, str(i + 1))

    sheet.save(out_path)
    logger.info("contact_sheet_done", images=len(thumbs), cols=cols, out=str(out_path))
    return str(out_path)


def _badge(draw: ImageDraw.ImageDraw, x: int, y: int, text: str) -> None:
    w = 14 + 8 * len(text)
    draw.rectangle([x, y, x + w, y + 18], fill=(10, 25, 54))
    draw.text((x + 6, y + 4), text, fill=(255, 255, 255))
