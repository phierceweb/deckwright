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


def test_a_source_tree_that_was_never_installed_reports_a_dev_version(monkeypatch):
    import importlib
    from importlib import metadata

    import deckwright

    def missing(name):
        raise metadata.PackageNotFoundError(name)

    with monkeypatch.context() as patched:
        patched.setattr(metadata, "version", missing)
        assert importlib.reload(deckwright).__version__ == "0.0.0.dev0"
    assert importlib.reload(deckwright).__version__ != "0.0.0.dev0"
