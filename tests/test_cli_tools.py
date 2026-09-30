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


def test_glyphs_verify_reports_the_bundle_it_ships():
    import re

    result = CliRunner().invoke(app, ["glyphs", "verify"])
    assert result.exit_code == 0, result.stdout
    assert re.fullmatch(r"[\d,]+ glyphs, matching glyphs\.sum @ [0-9a-f]{12}\n", result.stdout)


def test_glyphs_verify_prints_each_problem_and_exits_nonzero(monkeypatch):
    from deckwright.icons import vendor

    monkeypatch.setattr(vendor, "verify", lambda: ["one is wrong", "two is wrong"])
    result = CliRunner().invoke(app, ["glyphs", "verify"])
    assert result.exit_code == 1
    assert result.stdout == "one is wrong\ntwo is wrong\n"


def test_glyphs_sync_refuses_outside_a_source_checkout(tmp_path, monkeypatch):
    from deckwright.icons import vendor

    monkeypatch.setattr(vendor, "MATERIAL", tmp_path / "nowhere" / "material")
    result = CliRunner().invoke(app, ["glyphs", "sync"])
    assert result.exit_code != 0
    assert "glyphs can only be synced from a source checkout" in str(result.exception)


def test_glyphs_sync_says_what_moved_and_caps_each_list_at_eight(monkeypatch):
    """The fetch is a network clone, so it is stood in for; the report is what is under test."""
    from deckwright.icons import vendor

    moved = {
        "ref": "0123456789abcdef0123",
        "kept": 4001,
        "dropped": 12,
        "added": [f"new_{i}" for i in range(9)],
        "removed": [],
        "changed": ["home"],
    }
    monkeypatch.setattr(vendor, "sync", lambda ref: moved)
    result = CliRunner().invoke(app, ["glyphs", "sync", "--ref", "0123456789abcdef0123"])
    assert result.exit_code == 0, result.stdout
    assert result.stdout.splitlines() == [
        "vendored 4,001 glyphs @ 0123456789ab (12 dropped — they need nonzero winding)",
        "  added       9  new_0, new_1, new_2, new_3, new_4, new_5, new_6, new_7 …",
        "  changed     1  home",
    ]


def test_glyphs_sync_that_moves_nothing_says_the_set_is_unchanged(monkeypatch):
    from deckwright.icons import vendor

    same = {
        "ref": "0123456789ab",
        "kept": 1,
        "dropped": 0,
        "added": [],
        "removed": [],
        "changed": [],
    }
    monkeypatch.setattr(vendor, "sync", lambda ref: same)
    result = CliRunner().invoke(app, ["glyphs", "sync"])
    assert result.stdout.splitlines()[-1] == "  the set is unchanged"


def test_python_m_deckwright_cli_runs_the_app(capsys, monkeypatch):
    import runpy

    monkeypatch.setattr(sys, "argv", ["deckwright", "--version"])
    try:
        runpy.run_module("deckwright.cli", run_name="__main__", alter_sys=True)
    except SystemExit as stop:
        assert stop.code in (0, None)
    assert capsys.readouterr().out.startswith("deckwright ")
