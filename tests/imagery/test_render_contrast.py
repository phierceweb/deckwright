"""The only check that measures a rendered photograph instead of the manifest. Every case builds
the render by hand; the greys are chosen for their WCAG ratio against white — 9A9A9A is 2.81:1,
979797 is 2.92:1, and large text needs 3.0:1."""

from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

from deckwright.qa.imagery import check_render_contrast
from deckwright.qa.model import Severity

SLIDE_W, SLIDE_H = 10.0, 5.0
_PX = 100  # pixels per inch in the fixture renders


def _render(tmp_path, bands: list[tuple[float, str]], name="slide-1.png"):
    """A page painted in horizontal bands: ``(height as a fraction, hex colour)``."""
    page = Image.new("RGB", (int(SLIDE_W * _PX), int(SLIDE_H * _PX)))
    top = 0
    for fraction, colour in bands:
        height = round(fraction * page.height)
        rgb = tuple(int(colour[i : i + 2], 16) for i in (0, 2, 4))
        page.paste(Image.new("RGB", (page.width, height), rgb), (0, top))
        top += height
    path = tmp_path / name
    page.save(path)
    return path


def _manifest(
    *,
    fg="FFFFFF",
    font_pt=32.0,
    box=(1.0, 1.0, 8.0, 3.0),
    picture=True,
    text="A line over a photograph",
    bg=None,
) -> dict[str, Any]:
    shapes: list[dict[str, Any]] = [
        {
            "name": "text",
            "text": text,
            "fg": fg,
            "font_pt": font_pt,
            "box": dict(zip("xywh", box, strict=True)),
        }
    ]
    if bg is not None:
        shapes[0]["bg"] = bg
    if picture:
        shapes.insert(
            0,
            {
                "name": "pic",
                "rendered": "picture",
                "box": dict(zip("xywh", (0.0, 0.0, SLIDE_W, SLIDE_H), strict=True)),
            },
        )
    return {
        "canvas": {"w": SLIDE_W, "h": SLIDE_H, "unit": "in"},
        "slides": [{"index": 1, "shapes": shapes}],
    }


def test_white_text_on_a_white_photograph_is_flagged(tmp_path):
    findings = check_render_contrast(_manifest(), [_render(tmp_path, [(1.0, "FFFFFF")])])
    assert len(findings) == 1
    assert findings[0].check == "render-contrast"
    assert findings[0].severity is Severity.WARN
    assert findings[0].slide == 1


def test_white_text_on_a_dark_photograph_passes(tmp_path):
    assert check_render_contrast(_manifest(), [_render(tmp_path, [(1.0, "202020")])]) == []


def test_the_finding_names_the_colour_that_was_measured(tmp_path):
    findings = check_render_contrast(_manifest(), [_render(tmp_path, [(1.0, "9A9A9A")])])
    assert "FFFFFF renders on 9A9A9A" in findings[0].detail
    assert "2.8:1" in findings[0].detail


def test_a_surface_the_build_agrees_with_blames_the_ink_not_a_scrim(tmp_path):
    """A template backdrop puts every slide through this check, most with no picture behind the
    text at all. The build recorded white here and the render found white."""
    manifest = _manifest(fg="FF8000", font_pt=12.0, bg="FFFFFF", picture=False)
    manifest["slides"][0]["backdrop"] = True
    findings = check_render_contrast(manifest, [_render(tmp_path, [(1.0, "FFFFFF")])])
    assert len(findings) == 1
    assert "scrim would not change it" in findings[0].detail
    assert "needs a scrim" not in findings[0].detail


def test_a_surface_the_build_did_not_expect_asks_for_a_scrim(tmp_path):
    """The build laid white ink on a dark plate; the render found white paper. That gap is the
    diagnostic — something composited over it — so the message names both colours."""
    findings = check_render_contrast(_manifest(bg="202020"), [_render(tmp_path, [(1.0, "FFFFFF")])])
    assert len(findings) == 1
    assert "recorded 202020 behind this text and the render found FFFFFF" in findings[0].detail
    assert "needs a scrim" in findings[0].detail


def test_a_shape_recording_no_background_keeps_the_original_advice(tmp_path):
    """Nothing to compare against, so the check cannot tell — it does not guess."""
    findings = check_render_contrast(_manifest(), [_render(tmp_path, [(1.0, "FFFFFF")])])
    assert "the picture behind this text needs a scrim" in findings[0].detail


def test_a_slide_with_no_picture_is_left_to_the_manifest_checks(tmp_path):
    """Without a photograph the build knows the background, and geometry.py read it."""
    assert (
        check_render_contrast(_manifest(picture=False), [_render(tmp_path, [(1.0, "FFFFFF")])])
        == []
    )


def test_a_slide_on_the_templates_own_picture_is_measured(tmp_path):
    """The template's backdrop is not a placed shape, so the slide flag is the only tell."""
    manifest = _manifest(picture=False)
    manifest["slides"][0]["backdrop"] = True
    findings = check_render_contrast(manifest, [_render(tmp_path, [(1.0, "FFFFFF")])])
    assert [f.check for f in findings] == ["render-contrast"]


def test_a_gradient_is_judged_where_it_is_weakest_not_on_its_average(tmp_path):
    """The text box's top third is clear white; the dark rest must not excuse it."""
    page = _render(tmp_path, [(0.2, "000000"), (0.24, "FFFFFF"), (0.56, "000000")])
    findings = check_render_contrast(_manifest(), [page])
    assert len(findings) == 1
    assert "on FFFFFF" in findings[0].detail


def test_a_border_row_at_the_bottom_of_a_box_is_not_a_band(tmp_path):
    """A 46px box does not divide by three. The leftover row is the box's own edge, and
    measuring it as a band of its own condemns every line of text above it."""
    page = _render(tmp_path, [(0.29, "202020"), (0.002, "FFFFFF"), (0.708, "202020")])
    assert check_render_contrast(_manifest(box=(1.0, 1.0, 8.0, 0.46)), [page]) == []


def test_a_measurement_just_under_the_threshold_is_within_the_render_slack(tmp_path):
    """2.92:1 against a 3.0 requirement: a glyph edge is never the colour asked for."""
    assert check_render_contrast(_manifest(), [_render(tmp_path, [(1.0, "979797")])]) == []


def test_a_measurement_below_the_slack_is_flagged(tmp_path):
    """2.81:1 is further under 3.0 than the slack allows."""
    assert len(check_render_contrast(_manifest(), [_render(tmp_path, [(1.0, "9A9A9A")])])) == 1


def test_small_text_is_held_to_the_stricter_wcag_ratio(tmp_path):
    """8C8C8C is 3.36:1 — fine for 32pt, short of the 4.5 a 12pt line needs."""
    page = _render(tmp_path, [(1.0, "8C8C8C")])
    assert check_render_contrast(_manifest(font_pt=32.0), [page]) == []
    assert len(check_render_contrast(_manifest(font_pt=12.0), [page])) == 1


def test_a_textless_shape_is_not_measured_for_contrast(tmp_path):
    """A rule or a plate carries a colour but no glyphs; there is nothing to read."""
    manifest = _manifest()
    manifest["slides"][0]["shapes"].append(
        {
            "name": "rule",
            "fg": "FFFFFF",
            "font_pt": 32.0,
            "box": dict(zip("xywh", (1.0, 1.0, 8.0, 0.1), strict=True)),
        }
    )
    findings = check_render_contrast(manifest, [_render(tmp_path, [(1.0, "FFFFFF")])])
    assert [f.shape for f in findings] == ["text"]


def test_the_picture_itself_is_not_measured(tmp_path):
    """Measuring the photograph against itself would report every photo slide."""
    manifest = _manifest()
    manifest["slides"][0]["shapes"][0].update(fg="FFFFFF", text="alt", font_pt=32.0)
    findings = check_render_contrast(manifest, [_render(tmp_path, [(1.0, "FFFFFF")])])
    assert [f.shape for f in findings] == ["text"]


def test_the_background_is_the_commonest_colour_not_the_average(tmp_path):
    """A box 55% white paper and 45% black strokes averages to 8C8C8C, a 3.4:1 pass. The mode
    says the paper is white; the mean is dragged toward the ink and excuses it."""
    page = _render(tmp_path, [(0.011, "FFFFFF" if i % 20 < 11 else "000000") for i in range(90)])
    findings = check_render_contrast(_manifest(), [page])
    assert len(findings) == 1
    assert "on FFFFFF" in findings[0].detail


def test_a_slide_whose_render_is_missing_is_skipped(tmp_path):
    assert check_render_contrast(_manifest(), [tmp_path / "absent.png"]) == []


@pytest.mark.parametrize("axis", ["w", "h"])
def test_a_manifest_with_no_canvas_size_is_reported_not_silently_skipped(tmp_path, axis):
    """Either axis alone leaves the render unmappable; a silent skip reads as a pass."""
    manifest = _manifest()
    manifest["canvas"][axis] = 0
    findings = check_render_contrast(manifest, [_render(tmp_path, [(1.0, "FFFFFF")])])
    assert len(findings) == 1
    assert findings[0].check == "canvas-size"
    assert findings[0].severity is Severity.WARN
    assert findings[0].slide == 0


@pytest.mark.parametrize("box", [(1.0, 1.0, 0.015, 3.0), (1.0, 1.0, 8.0, 0.015)])
def test_a_text_box_barely_a_pixel_across_is_skipped(tmp_path, box):
    """One pixel of a rounding artefact is not a measurement of anything."""
    assert check_render_contrast(_manifest(box=box), [_render(tmp_path, [(1.0, "FFFFFF")])]) == []
