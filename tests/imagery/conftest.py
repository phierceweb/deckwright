"""Image fixtures. Every one is generated, so no test reads the brand template."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw


def _write(path, size, painter):
    image = Image.new("RGB", size, "white")
    painter(ImageDraw.Draw(image), *size)
    image.save(path)
    return path


@pytest.fixture
def white_wide(tmp_path):
    """A 16:9 sheet of pure white — nothing legible under white ink without a scrim."""
    return _write(
        tmp_path / "white_wide.png",
        (320, 180),
        lambda d, w, h: d.rectangle([0, 0, w, h], fill=(255, 255, 255)),
    )


@pytest.fixture
def black_tall(tmp_path):
    """A 1:2 sheet of pure black."""
    return _write(
        tmp_path / "black_tall.png",
        (100, 200),
        lambda d, w, h: d.rectangle([0, 0, w, h], fill=(0, 0, 0)),
    )


@pytest.fixture
def split_wide(tmp_path):
    """16:9, white top half and black bottom half — the halves must measure differently."""

    def paint(d, w, h):
        d.rectangle([0, 0, w, h // 2], fill=(255, 255, 255))
        d.rectangle([0, h // 2, w, h], fill=(0, 0, 0))

    return _write(tmp_path / "split_wide.png", (320, 180), paint)


@pytest.fixture
def striped_wide(tmp_path):
    """16:9 white with one narrow black stripe down the left eighth."""

    def paint(d, w, h):
        d.rectangle([0, 0, w, h], fill=(255, 255, 255))
        d.rectangle([0, 0, w // 8, h], fill=(0, 0, 0))

    return _write(tmp_path / "striped_wide.png", (320, 180), paint)
