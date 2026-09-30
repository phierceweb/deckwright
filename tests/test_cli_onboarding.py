"""`new`, `demo`, `sample` and `doctor` as a terminal shows them."""

from __future__ import annotations

from typer.testing import CliRunner

from deckwright.cli import app

runner = CliRunner()


def _said(result) -> str:
    return result.output + str(result.exception or "")


def test_new_writes_a_spec_builds_it_and_says_where(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "Quarterly Review", "--root", "authoring"])
    assert result.exit_code == 0, _said(result)
    lines = result.stdout.splitlines()
    assert lines[0].startswith("spec    -> authoring/")
    assert lines[1].startswith("deck    -> ") and lines[1].endswith(".pptx")
    assert lines[2].startswith("words   -> ") and lines[2].endswith(".content.md")
    assert lines[3].startswith("edit the spec, then: deckwright build authoring/")


def test_new_without_a_build_names_only_the_spec(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "Draft", "--root", "authoring", "--no-build"])
    assert result.exit_code == 0, _said(result)
    assert [line.split()[0] for line in result.stdout.splitlines()] == ["spec", "edit"]


def test_demo_builds_the_capability_deck_where_it_is_told(tmp_path):
    result = runner.invoke(app, ["demo", "--out", str(tmp_path / "demo")])
    assert result.exit_code == 0, _said(result)
    deck, words = (line.split("-> ", 1)[1] for line in result.stdout.splitlines())
    assert deck.endswith(".pptx") and words.endswith(".content.md")
    assert (tmp_path / "demo").joinpath(deck.rsplit("/", 1)[1]).is_file()


def test_sample_refuses_to_replace_a_file_without_force(tmp_path):
    target = tmp_path / "sample.pptx"
    target.write_bytes(b"")
    result = runner.invoke(app, ["sample", str(target)])
    assert result.exit_code != 0
    assert "sample.pptx already exists — pass --force to replace it" in _said(result)


def test_sample_written_outside_the_theme_directory_says_how_to_adopt_it(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path / "themes"))
    result = runner.invoke(app, ["sample", str(tmp_path / "elsewhere" / "sample.pptx")])
    assert result.exit_code == 0, _said(result)
    assert result.stdout.splitlines()[1].startswith("to adopt it: mkdir -p ")


def test_doctor_exits_with_its_own_verdict():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)
    assert "deckwright doctor" in result.stdout
