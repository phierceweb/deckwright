import textwrap

import pytest
from typer.testing import CliRunner

from deckwright.cli import app

runner = CliRunner()

THEME = """
    name: cli
    template: assets/t.pptx
    bind: {page: lt1, ink: dk1, inverse: dk1, line: lt2}
    type:
      min_pt: 10.5
      ramp:
        kicker: {pt: 14, bold: true}
        caption: {pt: 12}
        body: {pt: 13.5}
        lead: {pt: 19}
        head: {pt: 18, bold: true}
        stat: {pt: 30, bold: true}
        subtitle: {pt: 15}
        title: {pt: 32, bold: true}
        display: {pt: 46, bold: true}
        hero: {pt: 52, bold: true}
    scale:
      margin: {top: 4%, right: 5%, bottom: 7%, left: 5%}
      columns: 12
      gutter: 1.5%
      body_top: 23%
"""


@pytest.fixture
def project(tmp_path, synthetic_template):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "t.pptx").write_bytes(synthetic_template.read_bytes())
    (tmp_path / "cli.yaml").write_text(textwrap.dedent(THEME))
    (tmp_path / "d.deck.yaml").write_text("theme: cli\nout: Demo.pptx\n---\ntitle: Hello\n")
    return tmp_path


def test_build_reports_the_deck_and_slide_count(project):
    result = runner.invoke(
        app, ["build", str(project / "d.deck.yaml"), "--theme", str(project / "cli.yaml")]
    )
    assert result.exit_code == 0, result.output
    assert "1 slide" in result.output
    assert (project / "Demo.pptx").is_file()


def test_build_reports_where_the_manifest_went(project):
    """The manifest path is never passed in and never printed anywhere else, so this
    line is the only thing that tells an author where `deckwright qa` should look."""
    result = runner.invoke(
        app, ["build", str(project / "d.deck.yaml"), "--theme", str(project / "cli.yaml")]
    )
    assert result.exit_code == 0, result.output
    manifest = project / "Demo.manifest.json"
    assert manifest.is_file()
    assert f"manifest -> {manifest}" in result.output


def test_build_honours_the_out_flag(project, tmp_path):
    dest = tmp_path / "custom.pptx"
    result = runner.invoke(
        app,
        [
            "build",
            str(project / "d.deck.yaml"),
            "--theme",
            str(project / "cli.yaml"),
            "--out",
            str(dest),
        ],
    )
    assert result.exit_code == 0, result.output
    assert dest.is_file()


def _stderr(capsys) -> str:
    return " ".join(capsys.readouterr().err.split())


def test_a_bad_spec_exits_1_with_a_readable_message(project, capsys):
    from pf_core.cli import run_cli

    (project / "bad.deck.yaml").write_text("title: no theme\n---\ntitle: T\n")
    with pytest.raises(SystemExit) as exit_info:
        run_cli(
            app,
            args=["build", str(project / "bad.deck.yaml"), "--theme", str(project / "cli.yaml")],
        )
    assert exit_info.value.code == 1
    assert "missing required field 'theme'" in _stderr(capsys)


def test_an_unknown_component_exits_1_with_a_readable_message(project, capsys):
    from pf_core.cli import run_cli

    (project / "bad2.deck.yaml").write_text(
        "theme: cli\nout: X.pptx\n---\nplace:\n  - at: {cols: full}\n    nonesuch: {}\n"
    )
    with pytest.raises(SystemExit) as exit_info:
        run_cli(
            app,
            args=["build", str(project / "bad2.deck.yaml"), "--theme", str(project / "cli.yaml")],
        )
    assert exit_info.value.code == 1
    assert "unknown field 'nonesuch'" in _stderr(capsys)


def test_a_missing_theme_file_exits_1_with_a_readable_message(project, capsys):
    from pf_core.cli import run_cli

    with pytest.raises(SystemExit) as exit_info:
        run_cli(
            app,
            args=["build", str(project / "d.deck.yaml"), "--theme", str(project / "absent.yaml")],
        )
    assert exit_info.value.code == 1
    assert "theme file not found" in _stderr(capsys)
