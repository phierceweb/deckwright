"""Stand-in photographs for the conformance run.

Generated rather than shipped, so no binary lands in the repo, and deliberately dark
at one end and blown-out at the other — a flat source would clear any scrim opacity
and prove nothing about the solve.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# The gradient is drawn at this long edge and scaled up; the noise blended over it puts
# back the pixel-scale variation that makes the sampler's cell average mean something.
_COARSE = 96
_NOISE_SIGMA = 26
_NOISE_WEIGHT = 0.22
_WIDE = (1600, 900)
_TALL = (900, 1600)


def photographs(outdir: Path) -> dict[str, Path]:
    """Write the stand-in sources into ``outdir``, returning them by placeholder name."""
    return {
        "photo": _write(outdir / "photo-wide.png", _WIDE),
        "portrait": _write(outdir / "photo-tall.png", _TALL),
    }


def _write(path: Path, size: tuple[int, int]) -> Path:
    if not path.is_file():
        _paint(size).save(path)
    return path.resolve()


def _paint(size: tuple[int, int]) -> Image.Image:
    width, height = size
    scale = _COARSE / max(size)
    small = (max(2, round(width * scale)), max(2, round(height * scale)))
    base = _sky(small).resize(size, Image.Resampling.BICUBIC)
    noise = Image.effect_noise(size, _NOISE_SIGMA).convert("RGB")
    return Image.blend(base, noise, _NOISE_WEIGHT).filter(ImageFilter.GaussianBlur(radius=1.0))


def _sky(size: tuple[int, int]) -> Image.Image:
    """A near-white top fading to a near-black base, with two bright blooms in it."""
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1, height - 1)
        draw.line(
            [(0, y), (width, y)],
            fill=(round(246 - 232 * t**1.4), round(242 - 228 * t**1.3), round(232 - 214 * t**1.2)),
        )
    for cx, cy, r in ((0.24, 0.66, 0.20), (0.78, 0.30, 0.13)):
        box = [(cx - r) * width, (cy - r) * height, (cx + r) * width, (cy + r) * height]
        draw.ellipse(box, fill=(252, 248, 236))
    return image.filter(ImageFilter.GaussianBlur(radius=max(1, width // 24)))
