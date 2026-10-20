"""Tests for the contact-sheet montage."""

from __future__ import annotations

import pytest
from PIL import Image

from pw_foundation.exceptions import InvalidInputError
from deckwright.services.montage import contact_sheet


def _write_img(path, color=(40, 100, 200), size=(160, 90)):
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
    # 160x90 → 100x56 thumbs under a 22px number strip; 5 images over 2 cols = 3 rows.
    w, h = Image.open(out).size
    assert w == 10 + 2 * (100 + 10)
    assert h == 10 + 3 * (22 + 56 + 10)


def test_contact_sheet_without_numbers_has_no_strip(tmp_path):
    p = tmp_path / "slide.png"
    _write_img(p)
    contact_sheet([p], tmp_path / "sheet.png", cols=1, thumb_width=100, pad=10, numbers=False)
    assert Image.open(tmp_path / "sheet.png").size == (120, 76)


def test_the_number_badge_covers_none_of_the_slide(tmp_path):
    """A badge painted on the thumbnail hid the first letters of every two-digit kicker."""
    imgs = []
    for i in range(12):
        p = tmp_path / f"slide-{i:02d}.png"
        _write_img(p, (200, 120, 30))
        imgs.append(p)
    out = tmp_path / "sheet.png"
    contact_sheet(imgs, out, cols=4, thumb_width=100, pad=10)
    colours = Image.open(out).getcolors(maxcolors=1 << 16)
    painted = next(n for n, c in colours if c == (200, 120, 30))
    assert painted == 12 * 100 * 56


def test_contact_sheet_empty_raises(tmp_path):
    with pytest.raises(InvalidInputError):
        contact_sheet([], tmp_path / "out.png")
