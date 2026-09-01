from pathlib import Path

from deckwright.paths import SCRATCH, in_checkout, render_dir, scratch


def test_a_decks_renders_go_in_a_directory_named_for_it_beside_the_deck():
    assert render_dir("out/smoke/Smoke v2.pptx") == Path("out/smoke/render/Smoke v2")


def test_two_decks_in_one_directory_do_not_share_a_render_directory():
    assert render_dir("out/smoke/Smoke v1.pptx") != render_dir("out/smoke/Smoke v2.pptx")


def test_the_scratch_directory_is_made_where_the_output_is(tmp_path):
    assert scratch(tmp_path) == tmp_path / SCRATCH
    assert (tmp_path / SCRATCH).is_dir()


def test_a_strangers_python_project_is_not_our_checkout(tmp_path, monkeypatch):
    """Testing for a bare pyproject.toml made `sample` write into a user's own repo."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "my-app"\n', encoding="utf-8")
    assert in_checkout() is False


def test_our_own_source_tree_is_recognised(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "deckwright"\n', encoding="utf-8")
    assert in_checkout() is True


def test_an_unparseable_pyproject_is_not_a_checkout(tmp_path, monkeypatch):
    """doctor exists to report problems, so it must not die reading a broken one."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("name = [unclosed", encoding="utf-8")
    assert in_checkout() is False
