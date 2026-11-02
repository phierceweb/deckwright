"""The clear run a master picture leaves for the chrome, on pictures small enough to read."""

from __future__ import annotations

from PIL import Image

from deckwright.conform.chromeband import CHROME_BAND, clear_run, columns

# The probe is 48 columns wide; at 480px each probe column is ten pixels, so a region
# given in tens of pixels lands on a column edge.
_W, _H = 480, 320


def _picture(tmp_path, regions, *, below: int = 0):
    """Vertical regions of ``(width_px, colour)`` left to right, drawn from ``below`` px down."""
    img = Image.new("RGB", (_W, _H), "white")
    x = 0
    for width, colour in regions:
        img.paste(colour, (x, below, x + width, _H))
        x += width
    path = tmp_path / "art.png"
    img.save(path)
    return path


def test_a_plain_band_has_nothing_to_avoid(tmp_path):
    assert clear_run(_picture(tmp_path, [(_W, "white")]), CHROME_BAND) is None


def test_the_run_is_the_half_the_artwork_leaves_alone(tmp_path):
    art = _picture(tmp_path, [(240, "black"), (240, "white")])
    assert clear_run(art, CHROME_BAND) == (0.5, 1.0)


def test_a_run_narrower_than_three_tenths_of_the_canvas_is_not_offered(tmp_path):
    """Twelve quiet columns of forty-eight: a title steered into a quarter of the width wraps."""
    art = _picture(tmp_path, [(170, "black"), (120, (128, 128, 128)), (190, "white")])
    assert clear_run(art, CHROME_BAND) is None


def test_only_the_band_is_read(tmp_path):
    art = _picture(tmp_path, [(240, "black"), (240, "white")], below=160)
    assert clear_run(art, CHROME_BAND) is None
    assert clear_run(art, (0.5, 1.0)) == (0.5, 1.0)


def test_a_run_becomes_grid_columns_clamped_to_the_grid_and_at_least_one_wide():
    assert columns((0.5, 1.0)) == (6, 12)
    assert columns((0.0, 0.01)) == (0, 1)
