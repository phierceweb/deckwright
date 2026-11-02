"""A binary that is not installed and a binary that ran and failed are different facts,
and only one of them is fixed by installing something."""

from __future__ import annotations

import subprocess

import pytest

from deckwright.errors import MissingToolError, RenderError
from deckwright.services import render


def test_a_missing_soffice_names_the_install_and_the_knob_that_overrides_it(
    tmp_path, monkeypatch, synthetic_template
):
    monkeypatch.setattr(render.platform, "system", lambda: "Linux")
    monkeypatch.setenv("DECKWRIGHT_SOFFICE", "/nonexistent/soffice")
    with pytest.raises(MissingToolError) as exc:
        render.render_to_images(synthetic_template, tmp_path / "out")
    message = str(exc.value)
    assert "/nonexistent/soffice" in message
    assert "DECKWRIGHT_SOFFICE" in message
    assert "sudo apt-get install libreoffice-impress" in message


def test_a_soffice_that_ran_and_failed_is_not_reported_as_missing(
    tmp_path, monkeypatch, synthetic_template
):
    """Installing LibreOffice is no fix for a LibreOffice that refused the file."""

    def refuse(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="cannot open")

    monkeypatch.setattr(render.subprocess, "run", refuse)
    with pytest.raises(RenderError) as exc:
        render.render_to_images(synthetic_template, tmp_path / "out")
    assert str(exc.value) == "LibreOffice PDF conversion failed"
