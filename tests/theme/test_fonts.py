import dataclasses

from deckwright.compile.build import resolve_theme
from deckwright.theme import load_theme
from deckwright.theme.fonts import installed_families, missing_faces, theme_faces
from deckwright.theme.model import Theme


def _base() -> Theme:
    return load_theme(resolve_theme("base"))


def _fake_fc_list(tmp_path, stdout: str, *, code: int = 0):
    """A stand-in fc-list that prints fixed families."""
    script = tmp_path / "fake_fc_list"
    script.write_text("#!/bin/sh\n" + f"printf '%b' \"{stdout}\"\n" + f"exit {code}\n")
    script.chmod(0o755)
    return str(script)


def test_theme_faces_lists_body_heading_and_mono_without_duplicates():
    """base sets body and headings in the same face, so a second Helvetica would mean
    the de-duplication is gone."""
    assert theme_faces(_base()) == ("Helvetica", "Courier New")


def test_theme_faces_includes_a_face_named_only_by_a_type_rung():
    theme = _base()
    display = dataclasses.replace(theme.ramp["display"], face="Bookman Old Style")
    theme = dataclasses.replace(theme, ramp={**theme.ramp, "display": display})
    assert "Bookman Old Style" in theme_faces(theme)


def test_installed_families_splits_alias_lists_and_casefolds(tmp_path):
    fc = _fake_fc_list(tmp_path, "Helvetica Neue,Helvetica\\nCalibri\\n")
    assert installed_families(fc_list=fc) == frozenset({"helvetica neue", "helvetica", "calibri"})


def test_installed_families_is_none_when_fontconfig_is_absent(tmp_path):
    assert installed_families(fc_list=str(tmp_path / "nope")) is None


def test_installed_families_is_none_when_fontconfig_fails(tmp_path):
    fc = _fake_fc_list(tmp_path, "", code=2)
    assert installed_families(fc_list=fc) is None


def test_missing_faces_names_the_face_the_machine_lacks():
    assert missing_faces(_base(), frozenset({"courier new"})) == ("Helvetica",)


def test_missing_faces_reports_nothing_when_the_machine_cannot_be_asked():
    assert missing_faces(_base(), None) == ()
