"""Tests for the contact-sheet montage."""

from __future__ import annotations

import pytest
from PIL import Image

from pf_core.exceptions import InvalidInputError
from deckwright.services.montage import contact_sheet


def _write_img(path, color, size=(160, 90)):
    Image.new("RGB", size, color).save(path)


def test_contact_sheet_grid_dimensions(tmp_path):
    imgs = []
    for i in range(5):
        p = tmp_path / f"slide-{i:02d}.png"
        _write_img(p, (40 * i, 100, 200))
        imgs.append(p)
    out = tmp_path / "sheet.png"

    contact_sheet(imgs, out, cols=2, thumb_width=100, pad=10)

    assert out.exists()
    # 160x90 → 100x56 thumbs; 5 images over 2 cols = 3 rows.
    w, h = Image.open(out).size
    assert w == 10 + 2 * (100 + 10)
    assert h == 10 + 3 * (56 + 10)


def test_contact_sheet_empty_raises(tmp_path):
    with pytest.raises(InvalidInputError):
        contact_sheet([], tmp_path / "out.png")
