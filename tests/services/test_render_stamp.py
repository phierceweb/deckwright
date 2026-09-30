"""When a render already on disk may stand in for a new one. Both converters are faked; the stamp
they leave is the real one ``render_to_images`` writes."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from deckwright.services import render as render_mod
from deckwright.services import render_stamp


@pytest.fixture
def rendered(monkeypatch, tmp_path):
    """A two-page render of ``deck.pptx`` in ``render/``, given one font: (deck, outdir, images)."""

    def fake_run(argv, **kwargs):
        if "--convert-to" in argv:
            outdir = Path(argv[argv.index("--outdir") + 1])
            (outdir / f"{Path(argv[-1]).stem}.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
        elif "-jpeg" in argv:
            prefix = Path(argv[-1])
            for page in (1, 2):
                prefix.with_name(f"{prefix.name}-{page}.jpg").write_bytes(b"\xff\xd8\xff%d" % page)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(render_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(render_mod, "deck_font_files", lambda pptx: [Path("/fonts/Helvetica.ttc")])
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"deck bytes")
    out = tmp_path / "render"
    images = render_mod.render_to_images(deck, out)
    return deck, out, images


def test_a_render_of_the_deck_as_it_is_is_reused(rendered):
    deck, out, images = rendered
    assert render_mod.reuse_render(deck, out) == images
    assert [Path(p).name for p in images] == ["slide-1.jpg", "slide-2.jpg"]


def _edit_deck(deck, out, images, monkeypatch):
    deck.write_bytes(b"deck bytes, edited")
    return deck


def _lose_a_page(deck, out, images, monkeypatch):
    Path(images[1]).unlink()
    return deck


def _overwrite_a_page(deck, out, images, monkeypatch):
    Path(images[0]).write_bytes(b"another deck's page")
    return deck


def _overwrite_the_pdf(deck, out, images, monkeypatch):
    (out / "deck.pdf").write_bytes(b"%PDF-1.4\n% another deck\n%%EOF\n")
    return deck


def _ask_for_a_finer_render(deck, out, images, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_RENDER_DPI", "200")
    return deck


def _change_how_decks_render(deck, out, images, monkeypatch):
    monkeypatch.setattr(render_stamp, "RECIPE", render_stamp.RECIPE + 1)
    return deck


def _install_a_face_the_deck_names(deck, out, images, monkeypatch):
    """`font-substituted` says to install the face; the next `qa` has to see it set."""
    installed = [Path("/Library/Fonts/Poppins-Regular.ttf")]
    monkeypatch.setattr(render_mod, "deck_font_files", lambda pptx: installed)
    return deck


def _ask_for_a_copy_under_another_name(deck, out, images, monkeypatch):
    """Same bytes, so the same hash — but its PDF would be ``twin.pdf``, which is not there."""
    return Path(shutil.copy(deck, deck.with_name("twin.pptx")))


@pytest.mark.parametrize(
    "tamper",
    [
        _edit_deck,
        _lose_a_page,
        _overwrite_a_page,
        _overwrite_the_pdf,
        _ask_for_a_finer_render,
        _change_how_decks_render,
        _install_a_face_the_deck_names,
        _ask_for_a_copy_under_another_name,
    ],
)
def test_a_render_that_no_longer_matches_is_not_reused(rendered, monkeypatch, tamper):
    deck, out, images = rendered
    asked = tamper(deck, out, images, monkeypatch)
    assert render_mod.reuse_render(asked, out) is None


def test_a_coarser_request_reuses_a_finer_render(rendered):
    """So `render --dpi 200` then `qa` keeps the finer pages rather than replacing them."""
    deck, out, images = rendered
    assert render_mod.reuse_render(deck, out, dpi=72) == images
