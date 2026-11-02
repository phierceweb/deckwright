"""LibreOffice's shared user profile, and why each render needs its own. soffice locks one profile
directory: a second conversion starting while the first holds it exits 0 having converted nothing,
so it surfaces as a missing PDF. Asserted on the argv rather than by racing real conversions."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from deckwright.errors import RenderError
from deckwright.services import render as render_mod


@pytest.fixture
def captured(monkeypatch, tmp_path):
    """Run render_to_images against a fake soffice, returning the argv it was given."""
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        # The converter is expected to leave a PDF behind; make one so the code
        # under test proceeds to the point we are asserting about.
        (tmp_path / "deck.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(render_mod.subprocess, "run", fake_run)
    return calls


def _render(tmp_path):
    """Drive one render. Both subprocesses are faked, so it produces no images —
    the argv is what these tests read, not the output."""
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"not really a deck")
    render_mod.render_to_images(deck, tmp_path)


def test_each_conversion_gets_a_user_profile_of_its_own(captured, tmp_path):
    _render(tmp_path)
    assert captured, "soffice was never invoked"
    profiles = [a for a in captured[0] if a.startswith("-env:UserInstallation=")]
    assert profiles, captured[0]


def test_two_conversions_do_not_share_a_profile(captured, tmp_path):
    """Sharing is the whole failure: one directory, one lock, one silent no-op."""
    _render(tmp_path)
    _render(tmp_path)
    # `captured` holds the rasterizer's argv too; only the converter takes a profile.
    used = [a for call in captured for a in call if a.startswith("-env:UserInstallation=")]
    assert len(used) == 2 and used[0] != used[1], used


def test_the_profile_is_a_file_url(captured, tmp_path):
    """soffice ignores a bare path here, silently falling back to the shared profile."""
    _render(tmp_path)
    profile = next(a for a in captured[0] if a.startswith("-env:UserInstallation="))
    assert profile.startswith("-env:UserInstallation=file://"), profile


def test_the_profile_directory_does_not_outlive_the_render(captured, tmp_path):
    """A temp profile per render leaks a directory per render unless it is cleaned."""
    import pathlib

    _render(tmp_path)
    profile = next(a for a in captured[0] if a.startswith("-env:UserInstallation="))
    path = pathlib.Path(profile.split("file://", 1)[1])
    assert not path.exists(), path


def test_a_relative_outdir_is_resolved_before_soffice_sees_it(tmp_path, monkeypatch):
    """soffice runs in its own profile directory, so a relative --outdir would resolve
    inside a temp dir that is deleted on exit — the PDF lands nowhere and the render
    reports it was never produced. Survived a release and two bake-offs."""
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"not really a deck")
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        if "--convert-to" in argv:
            # Write where soffice was actually told to, so a relative path that resolved
            # somewhere unexpected shows up as a missing PDF rather than passing.
            Path(argv[argv.index("--outdir") + 1]).mkdir(parents=True, exist_ok=True)
            (Path(argv[argv.index("--outdir") + 1]) / "deck.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(render_mod.subprocess, "run", fake_run)
    monkeypatch.chdir(tmp_path)

    render_mod.render_to_images(deck, "relout")

    outdir = calls[0][calls[0].index("--outdir") + 1]
    assert Path(outdir).is_absolute(), f"soffice was handed a relative --outdir: {outdir}"
    assert Path(outdir) == (tmp_path / "relout").resolve()


def test_a_conversion_that_writes_no_pdf_cannot_rasterise_the_last_run(monkeypatch, tmp_path):
    """LibreOffice exits 0 without converting when another process holds its profile.
    With the previous run's PDF still on disk that failure is invisible: its pages come
    back as this deck's, which is how a 13-slide deck reported 12."""
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"not really a deck")
    stale = tmp_path / "deck.pdf"
    stale.write_bytes(b"%PDF-1.4\n%%EOF\n")

    def no_op(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(render_mod.subprocess, "run", no_op)

    with pytest.raises(RenderError, match="wrote no PDF"):
        render_mod.render_to_images(deck, tmp_path)
    assert not stale.exists(), "the previous run's PDF was left where it could be rasterised"


def test_a_relative_input_path_is_resolved_before_soffice_sees_it(tmp_path, monkeypatch):
    """The outdir half was fixed first; soffice resolves the input against its profile
    too, so a relative deck path converted nothing and reported no PDF."""
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"not really a deck")
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        if "--convert-to" in argv:
            # Only convert when handed a path that exists from soffice's own cwd, which
            # is the profile — the condition the resolve exists to satisfy.
            given = Path(argv[-1])
            if given.is_absolute() and given.is_file():
                (Path(argv[argv.index("--outdir") + 1]) / "deck.pdf").write_bytes(
                    b"%PDF-1.4\n%%EOF\n"
                )
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(render_mod.subprocess, "run", fake_run)
    monkeypatch.chdir(tmp_path)

    render_mod.render_to_images("deck.pptx", tmp_path / "out")

    assert Path(calls[0][-1]).is_absolute(), f"soffice got a relative input: {calls[0][-1]}"


def test_an_input_that_is_not_there_is_named(tmp_path):
    """The no-PDF error used to assert a leftover soffice process as the cause; during
    the run-3 reproduction pgrep found none and the real cause was the path."""
    with pytest.raises(RenderError, match=r"no deck to render at .*absent\.pptx"):
        render_mod.render_to_images(tmp_path / "absent.pptx", tmp_path)
