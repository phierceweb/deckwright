import pytest
from typer.testing import CliRunner

from pf_core.cli import run_cli

from deckwright.cli import app

runner = CliRunner()


def test_qa_reports_a_clean_deck(tmp_path, theme_file, clean_manifest_deck):
    deck, manifest = clean_manifest_deck
    result = runner.invoke(
        app,
        ["qa", str(deck), "--manifest", str(manifest), "--no-render", "--outdir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert "no findings" in result.output.lower()


def test_qa_exits_non_zero_when_fail_on_is_met(tmp_path, dirty_manifest_deck):
    deck, manifest = dirty_manifest_deck
    result = runner.invoke(
        app,
        [
            "qa",
            str(deck),
            "--manifest",
            str(manifest),
            "--no-render",
            "--outdir",
            str(tmp_path),
            "--fail-on",
            "error",
        ],
    )
    assert result.exit_code != 0


def test_qa_exits_zero_without_fail_on(tmp_path, dirty_manifest_deck):
    deck, manifest = dirty_manifest_deck
    result = runner.invoke(
        app,
        ["qa", str(deck), "--manifest", str(manifest), "--no-render", "--outdir", str(tmp_path)],
    )
    assert result.exit_code == 0


def test_inspect_lists_shapes(synthetic_template):
    result = runner.invoke(app, ["inspect", str(synthetic_template)])
    assert result.exit_code == 0, result.output
    assert "slide" in result.output.lower()


def test_qa_rejects_an_invalid_fail_on(tmp_path, dirty_manifest_deck, capsys):
    """CliRunner swallows run_cli's exception mapping, so this drives run_cli directly."""
    deck, manifest = dirty_manifest_deck
    with pytest.raises(SystemExit) as exc_info:
        run_cli(
            app,
            args=[
                "qa",
                str(deck),
                "--manifest",
                str(manifest),
                "--no-render",
                "--outdir",
                str(tmp_path),
                "--fail-on",
                "bogus",
            ],
        )
    assert exc_info.value.code != 0
    err = capsys.readouterr().err.lower()
    assert "fail-on" in err
    assert "bogus" in err
