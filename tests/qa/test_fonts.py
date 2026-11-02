"""The font-substituted check speaks for the machine that rendered."""

import dataclasses

from deckwright.compile.build import resolve_theme
from deckwright.qa.fonts import check_faces
from deckwright.qa.model import Severity
from deckwright.theme import load_theme


def _theme_missing_one_face():
    """The base theme with a face nobody has, so exactly one face is absent."""
    return dataclasses.replace(load_theme(resolve_theme("base")), face="Brandish Grotesk")


def test_a_face_the_machine_lacks_is_reported_once_by_name(monkeypatch):
    monkeypatch.setattr(
        "deckwright.qa.fonts.installed_families",
        lambda: frozenset({"helvetica", "courier new"}),
    )
    findings = check_faces({"slides": [{"index": 1, "shapes": []}]}, _theme_missing_one_face())
    assert [f.check for f in findings] == ["font-substituted"]
    assert findings[0].severity is Severity.WARN
    assert findings[0].slide == 0
    assert "Brandish Grotesk" in findings[0].detail


def test_nothing_is_reported_when_fontconfig_cannot_be_asked(monkeypatch):
    monkeypatch.setattr("deckwright.qa.fonts.installed_families", lambda: None)
    assert check_faces({"slides": []}, _theme_missing_one_face()) == []
