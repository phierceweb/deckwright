"""Tests for the HTML→PNG helpers (pure parts only; no real browser)."""

from __future__ import annotations

import os

import pytest
from PIL import Image

from deckwright.errors import RenderError
from deckwright.services.htmlshot import (
    CSP_META,
    _HEIGHT_PROBE,
    _NO_SANDBOX_ENV_VAR,
    _autocrop,
    _check_not_clipped,
    _chrome_cmd,
    _no_sandbox,
    _probe_height,
    _sandbox_advice,
    _with_csp,
)


def _dom(height: int) -> str:
    return f'<!DOCTYPE html><html data-deckwright-doc-h="{height}"><body></body></html>'


def _shot(path, *, top: bool = False, bottom: bool = False):
    """A white render canvas at ``path``, inked on the edge rows asked for."""
    img = Image.new("RGB", (40, 40), (255, 255, 255))
    for x in range(img.width):
        if top:
            img.putpixel((x, 0), (10, 20, 30))
        if bottom:
            img.putpixel((x, img.height - 1), (10, 20, 30))
    img.save(path)
    return path


def test_autocrop_trims_white_border():
    img = Image.new("RGB", (200, 200), (255, 255, 255))
    for x in range(50, 150):
        for y in range(60, 140):
            img.putpixel((x, y), (10, 20, 30))
    assert _autocrop(img).size == (100, 80)


def test_autocrop_pad_expands_within_bounds():
    img = Image.new("RGB", (200, 200), (255, 255, 255))
    for x in range(50, 150):
        for y in range(60, 140):
            img.putpixel((x, y), (10, 20, 30))
    assert _autocrop(img, pad=10).size == (120, 100)


def test_chrome_cmd_shape():
    cmd = _chrome_cmd(
        "chrome",
        "file:///x.html",
        "/tmp/o.png",
        width=940,
        height=4000,
        scale=2,
        user_data_dir="/tmp/p",
    )
    assert "--headless=new" in cmd
    assert "--screenshot=/tmp/o.png" in cmd
    assert "--window-size=940,4000" in cmd
    assert "--force-device-scale-factor=2" in cmd
    assert "--dump-dom" in cmd
    assert cmd[-1] == "file:///x.html"


def test_the_probe_reads_the_published_document_height():
    assert _probe_height(_dom(6743)) == 6743


def test_a_dom_without_the_probe_reads_as_unknown():
    assert _probe_height("<!DOCTYPE html><html><body></body></html>") is None


def test_content_shorter_than_the_canvas_is_accepted(tmp_path):
    _check_not_clipped(_dom(3999), canvas_height=4000, out_path=tmp_path / "o.png")


def test_content_exactly_filling_the_canvas_is_accepted(tmp_path):
    """A page shorter than the viewport reports the viewport's own height."""
    _check_not_clipped(_dom(4000), canvas_height=4000, out_path=tmp_path / "o.png")


def test_content_taller_than_the_canvas_is_rejected(tmp_path):
    with pytest.raises(RenderError, match=r"6743px.*canvas is only 4000px"):
        _check_not_clipped(_dom(6743), canvas_height=4000, out_path=tmp_path / "o.png")


def test_the_rejection_names_the_canvas_env_knob(tmp_path):
    with pytest.raises(RenderError, match=r"DECKWRIGHT_SHOT_CANVAS_H to at least 6743"):
        _check_not_clipped(_dom(6743), canvas_height=4000, out_path=tmp_path / "o.png")


def test_an_unreadable_probe_does_not_reject(tmp_path):
    """No measurement is not evidence of truncation — the render is let through."""
    _check_not_clipped("<html></html>", canvas_height=4000, out_path=_shot(tmp_path / "o.png"))


def test_an_unreadable_probe_over_a_render_that_reaches_the_canvas_floor_is_rejected(tmp_path):
    """A card floats on white, so ink on the last row is the canvas cutting it off."""
    with pytest.raises(RenderError, match="DECKWRIGHT_SHOT_CANVAS_H"):
        _check_not_clipped(
            "<html></html>", canvas_height=400, out_path=_shot(tmp_path / "o.png", bottom=True)
        )


def test_a_full_bleed_page_with_no_measurement_is_still_let_through(tmp_path):
    """Ink on both edges is what ``deckwright shot`` renders on purpose."""
    _check_not_clipped(
        "<html></html>",
        canvas_height=400,
        out_path=_shot(tmp_path / "o.png", top=True, bottom=True),
    )


def test_the_probe_publishes_the_scroll_height_under_the_expected_attribute():
    assert "data-deckwright-doc-h" in _HEIGHT_PROBE
    assert "scrollHeight" in _HEIGHT_PROBE


def _as_normal_user(monkeypatch):
    """Pin the euid so these read the same for a developer and a root CI container."""
    monkeypatch.setattr(os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.delenv(_NO_SANDBOX_ENV_VAR, raising=False)


def test_the_browser_is_sandboxed_by_default(monkeypatch):
    """A card's HTML can carry script, so the flag that switches the sandbox off is
    opt-in. Make `_no_sandbox` return True unconditionally and this goes red."""
    _as_normal_user(monkeypatch)
    assert _no_sandbox() is False
    cmd = _chrome_cmd(
        "chrome",
        "file:///x.html",
        "/tmp/o.png",
        width=940,
        height=4000,
        scale=2,
        user_data_dir="/tmp/p",
    )
    assert "--no-sandbox" not in cmd


def test_the_env_var_switches_the_sandbox_off(monkeypatch):
    _as_normal_user(monkeypatch)
    monkeypatch.setenv(_NO_SANDBOX_ENV_VAR, "1")
    assert _no_sandbox() is True
    cmd = _chrome_cmd(
        "chrome",
        "file:///x.html",
        "/tmp/o.png",
        width=940,
        height=4000,
        scale=2,
        user_data_dir="/tmp/p",
    )
    assert "--no-sandbox" in cmd


def test_root_gets_the_flag_because_the_sandbox_cannot_work_there(monkeypatch):
    monkeypatch.delenv(_NO_SANDBOX_ENV_VAR, raising=False)
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    assert _no_sandbox() is True


def test_a_sandbox_failure_names_the_escape_hatch():
    """Chrome's own wording, so the error a user actually sees points somewhere."""
    assert _NO_SANDBOX_ENV_VAR in _sandbox_advice(
        "[0806/120000.1:FATAL:zygote_host_impl_linux.cc(200)] No usable sandbox! "
        "Update your kernel or see https://chromium.googlesource.com/..."
    )


def test_an_unrelated_crash_gets_no_sandbox_advice():
    assert _sandbox_advice("[FATAL] out of memory while decoding image") == ""


def test_the_content_policy_is_the_first_thing_inside_head():
    html = '<!doctype html><html><head><meta charset="utf-8"><style>x</style></head><body></body></html>'
    out = _with_csp(html)
    assert out.index(CSP_META) == out.index("<head>") + len("<head>")


def test_a_fragment_with_no_head_still_gets_the_policy_first():
    assert _with_csp("<div>card</div>").startswith(CSP_META)


def test_the_policy_names_no_source_a_frame_object_or_embed_could_load_from():
    assert "default-src 'none'" in CSP_META
    assert not any(d in CSP_META for d in ("frame-src", "child-src", "object-src"))
    assert "file:" not in CSP_META
