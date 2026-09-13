"""What a stranger sees when an external tool is missing.

Driven through a subprocess: the noise these guard against is written by the logging
handlers pf-core installs, which an in-process runner never exercises.
"""

from __future__ import annotations

import os
import subprocess
import sys
import shlex
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deckwright.cli import app


@pytest.fixture
def qa_without_libreoffice(clean_manifest_deck, tmp_path):
    deck, manifest = clean_manifest_deck
    env = {**os.environ, "COLUMNS": "300", "DECKWRIGHT_SOFFICE": "/nonexistent/soffice"}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "deckwright.cli",
            "qa",
            str(deck),
            "--manifest",
            str(manifest),
            "--outdir",
            str(tmp_path / "qa"),
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def test_a_missing_tool_prints_its_message_and_nothing_else(qa_without_libreoffice):
    output = qa_without_libreoffice.stdout + qa_without_libreoffice.stderr
    assert qa_without_libreoffice.returncode == 1
    assert "soffice not found (/nonexistent/soffice)" in output
    assert "Traceback" not in output
    assert "locals" not in output


def test_qa_names_the_flag_that_runs_without_the_tool(qa_without_libreoffice):
    """Every check but overflow and render contrast needs no binary at all."""
    assert "--no-render" in qa_without_libreoffice.stdout + qa_without_libreoffice.stderr


def test_the_version_flag_prints_the_installed_version():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("deckwright ")


def test_sample_writes_where_adopt_will_accept_it(tmp_path, monkeypatch):
    """`sample` prints a `conform ... --adopt` line as the next step, and adopt refuses
    a template outside the theme directory (test_conform_adopt.py) — so writing beside
    the caller would print a command that always exits 1."""
    monkeypatch.chdir(tmp_path)
    theme_root = tmp_path / "brand kit"
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(theme_root))

    result = CliRunner().invoke(app, ["sample"])

    assert result.exit_code == 0, result.stdout
    written = theme_root / "sample.pptx"
    assert written.is_file()

    hint = [ln for ln in result.stdout.splitlines() if "--adopt" in ln]
    assert hint, result.stdout
    words = shlex.split(hint[0].split(":", 1)[1])
    assert words[:2] == ["deckwright", "conform"]
    assert Path(words[2]).resolve().parent == theme_root.resolve()


def test_glyphs_find_prints_matching_names():
    result = CliRunner().invoke(app, ["glyphs", "find", "globe"])
    assert result.exit_code == 0
    assert "globe_asia" in result.stdout


def test_glyphs_find_exits_nonzero_when_nothing_matches():
    """A miss is a failed lookup, not an empty success — a script piping this needs
    the status to say so."""
    result = CliRunner().invoke(app, ["glyphs", "find", "zzzznotaglyph"])
    assert result.exit_code == 1
    assert "no glyph name contains" in result.stdout


def test_glyphs_find_caps_its_output_and_says_how_much_it_dropped():
    result = CliRunner().invoke(app, ["glyphs", "find", "arrow", "--limit", "3"])
    assert result.exit_code == 0
    assert len([ln for ln in result.stdout.splitlines() if ln and not ln.startswith("...")]) == 3
    assert "more — narrow the term" in result.stdout
