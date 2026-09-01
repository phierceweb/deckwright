"""Finding a glyph by name, and refusing the things that are not one. A deck asking for an
icon that was never drawn and one with a typo look identical, and both have to say so."""

from __future__ import annotations

import pytest

from deckwright.errors import SpecError, ThemeError
from deckwright.icons.load import VENDORED, available, load, roots
from deckwright.theme import load_theme

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path d="M 2 2 H 22 V 22 H 2 Z"/></svg>'
)


def test_the_shipped_set_is_not_empty():
    """`icon:` is documented as working with no configuration, so something must ship."""
    assert len(available()) >= 3000
    assert "check" in available()


def test_a_shipped_glyph_carries_its_view_and_its_paths():
    glyph = load("check")
    assert glyph.view == (0.0, -960.0, 960.0, 960.0)
    assert glyph.subpaths and glyph.subpaths[0].startswith("m")


def test_a_theme_directory_is_searched_before_the_shipped_set(tmp_path, synthetic_template):
    """A brand overriding 'check' with its own drawing must not get ours."""
    icons = tmp_path / "icons"
    icons.mkdir()
    (icons / "check.svg").write_text(SVG)
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "t.pptx").write_bytes(synthetic_template.read_bytes())
    theme_file = tmp_path / "t.yaml"
    theme_file.write_text("name: t\ntemplate: assets/t.pptx\nicons: icons\n")

    theme = load_theme(theme_file)
    assert roots(theme)[0] == icons
    assert load("check", theme=theme).subpaths == ("M 2 2 H 22 V 22 H 2 Z",)
    assert load("check").subpaths != ("M 2 2 H 22 V 22 H 2 Z",)


def test_an_env_directory_outranks_the_theme(tmp_path, monkeypatch):
    override = tmp_path / "override"
    override.mkdir()
    monkeypatch.setenv("DECKWRIGHT_ICON_DIR", str(override))
    assert roots(None)[0] == override


def test_an_unknown_name_says_where_it_looked():
    """Thousands of names make listing them useless; the directories are the help."""
    with pytest.raises(SpecError, match="no icon 'qzxwvu' in .*glyphs/material"):
        load("qzxwvu")


@pytest.mark.parametrize("name", ["Check", "check.svg", "../check", "", "a b"])
def test_a_name_that_is_not_a_slug_is_rejected(name):
    """It names a file, so an uppercase letter or a path separator is not a typo to
    resolve — it is a traversal or a case-sensitivity bug waiting on another machine."""
    with pytest.raises(SpecError, match="must be lowercase letters"):
        load(name)


def test_an_svg_without_a_viewbox_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_ICON_DIR", str(tmp_path))
    (tmp_path / "flat.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><path d="M 0 0 H 1"/></svg>'
    )
    with pytest.raises(SpecError, match="no usable viewBox"):
        load("flat")


def test_an_svg_of_shapes_rather_than_paths_is_rejected(tmp_path, monkeypatch):
    """<circle>/<rect> are not read; saying so beats drawing an empty shape."""
    monkeypatch.setenv("DECKWRIGHT_ICON_DIR", str(tmp_path))
    (tmp_path / "shapes.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        '<circle cx="5" cy="5" r="4"/></svg>'
    )
    with pytest.raises(SpecError, match="holds no <path>"):
        load("shapes")


def test_unreadable_svg_names_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_ICON_DIR", str(tmp_path))
    (tmp_path / "broken.svg").write_text("<svg><path")
    with pytest.raises(SpecError, match="not readable SVG"):
        load("broken")


def test_a_theme_naming_a_missing_icons_directory_is_rejected(tmp_path, synthetic_template):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "t.pptx").write_bytes(synthetic_template.read_bytes())
    theme_file = tmp_path / "t.yaml"
    theme_file.write_text("name: t\ntemplate: assets/t.pptx\nicons: nowhere\n")
    with pytest.raises(ThemeError, match="icons directory not found"):
        load_theme(theme_file)


def test_every_shipped_glyph_parses_into_geometry():
    """A glyph that ships broken is a deck that fails at build time on our own asset."""
    for name in available():
        assert load(name).drawingml().startswith("<a:moveTo>"), name


def test_the_shipped_directory_is_inside_the_package():
    """It ships in the wheel; a path outside the package would resolve only in a checkout."""
    assert VENDORED.is_dir()
    assert VENDORED.parents[1].name == "icons"


def test_search_finds_names_containing_the_term():
    from deckwright.icons.load import search

    assert "globe_asia" in search("globe")


def test_search_returns_the_alias_an_author_would_write():
    """`arrow-left` resolves through OVERRIDES to `arrow_back`. Returning only the
    vendored name would send the author to a word that draws a different glyph."""
    from deckwright.icons.load import search

    assert "arrow-left" in search("arrow-left")


def test_search_matches_across_the_hyphen_underscore_spelling():
    """Both spellings must reach the vendored underscore name, so neither side can be
    computed with the other."""
    from deckwright.icons.load import search

    assert "keyboard_arrow_left" in search("arrow_left")
    assert "keyboard_arrow_left" in search("arrow-left")


def test_search_for_nothing_returns_empty():
    from deckwright.icons.load import search

    assert search("zzzznotaglyph") == ()
