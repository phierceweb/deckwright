"""What the stale-page sweep may delete, and what the render reports back. ``--outdir`` is a
free-form user path, so a sweep matching every ``slide-*`` in it eats the PDF just written for a
deck named ``slide-deck.pptx``. Both subprocesses are faked; the sweep's result is a file fact."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from deckwright.services import render as render_mod

PAGES = 2

JPEG = b"\xff\xd8\xff"


@pytest.fixture
def captured(monkeypatch):
    """Fake soffice (leaves a PDF) and pdftoppm (leaves PAGES pages), keeping both argv."""
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        if "--convert-to" in argv:
            outdir = Path(argv[argv.index("--outdir") + 1])
            (outdir / f"{Path(argv[-1]).stem}.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
        else:
            prefix = Path(argv[-1])
            for page in range(1, PAGES + 1):
                prefix.with_name(f"{prefix.name}-{page}.jpg").write_bytes(JPEG)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(render_mod.subprocess, "run", fake_run)
    return calls


def _render(tmp_path, outdir=None, *, deck="deck.pptx") -> list[str]:
    """Drive one render and return the image paths it reports."""
    source = tmp_path / deck
    source.write_bytes(b"not really a deck")
    return render_mod.render_to_images(source, outdir or tmp_path)


def test_notes_beside_the_pages_survive_the_sweep(captured, tmp_path):
    """Per-slide notes sit under the page glob; only their suffix keeps them."""
    notes = tmp_path / "slide-2-notes.md"
    notes.write_text("what slide 2 is for")
    _render(tmp_path)
    assert notes.exists()


def test_a_hand_named_export_of_one_slide_survives_the_sweep(captured, tmp_path):
    """A raster suffix is not enough to make a file ours: `slide-3-final.png` is
    something someone named and kept, and the sweep deletes what it matches."""
    kept = tmp_path / "slide-3-final.png"
    kept.write_bytes(JPEG)
    _render(tmp_path)
    assert kept.exists()


def test_a_deck_named_for_a_slide_keeps_its_own_pdf(captured, tmp_path):
    """The sweep runs after the conversion: this is the rasterizer's own input."""
    _render(tmp_path, deck="slide-deck.pptx")
    assert (tmp_path / "slide-deck.pdf").exists()


def test_a_page_from_a_longer_previous_render_is_removed(captured, tmp_path):
    """Two pages this time, ninety-nine last time — page 99 is nobody's."""
    stale = tmp_path / "slide-99.jpg"
    stale.write_bytes(JPEG)
    _render(tmp_path)
    assert not stale.exists()


def test_a_directory_named_like_a_page_is_not_swept(captured, tmp_path):
    """Unlinking a directory raises; the sweep skips it rather than taking the render down."""
    archive = tmp_path / "slide-9.jpg"
    archive.mkdir()
    _render(tmp_path)
    assert archive.is_dir()


def test_an_outdir_with_a_bracket_in_its_name_reports_its_pages(captured, tmp_path):
    """``[v2]`` is a character class to ``glob.glob``, which then matches no page at all."""
    images = _render(tmp_path, tmp_path / "Deck [v2]" / "render")
    assert [Path(p).name for p in images] == ["slide-1.jpg", "slide-2.jpg"]


def test_the_rasterizer_command_is_configurable(captured, tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_PDFTOPPM", "poppler-pdftoppm")
    _render(tmp_path)
    rasterize = next(c for c in captured if "-jpeg" in c)
    assert rasterize[0] == "poppler-pdftoppm"
