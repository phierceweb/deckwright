"""Smoke test: the CLI wires up and runs."""

from __future__ import annotations

from typer.testing import CliRunner

from deckwright.cli import app

runner = CliRunner()


def test_help_runs():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_render_help_runs():
    result = runner.invoke(app, ["render", "--help"])
    assert result.exit_code == 0


def test_shot_help_runs():
    result = runner.invoke(app, ["shot", "--help"])
    assert result.exit_code == 0
