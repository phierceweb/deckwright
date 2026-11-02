import pytest
from pptx import Presentation

import deckwright.theme.load as theme_load
from deckwright.conform import conform

SLIDE = {
    "title": "A slide",
    "place": [{"at": {"cols": "full"}, "bullets": {"items": ["One", "Two"]}}],
}
THREE = {"one": SLIDE, "two": SLIDE, "three": SLIDE}


@pytest.fixture
def template(tmp_path):
    path = tmp_path / "Brand.pptx"
    Presentation().save(str(path))
    return path


@pytest.fixture
def reads(monkeypatch):
    """Every theme file `load_theme` opens. Nothing in a run's output shows a second read."""
    seen: list = []
    resolve = theme_load.theme_file
    monkeypatch.setattr(theme_load, "theme_file", lambda ref: seen.append(ref) or resolve(ref))
    return seen


def test_a_run_reads_its_theme_once_however_many_exercises_it_builds(template, tmp_path, reads):
    result = conform(template, tmp_path / "out", exercises=THREE)

    assert result.passed == ["one", "two", "three"]
    assert result.deck is not None
    assert len(reads) == 1


def test_a_theme_that_cannot_load_fails_every_exercise_by_name_from_one_read(
    template, tmp_path, reads
):
    kept = tmp_path / "brand.theme.yaml"
    kept.write_text("name: brand\ntemplate: Brand.pptx\nbind: [lt1]\n")

    result = conform(template, tmp_path / "out", exercises=THREE, theme=kept)

    assert [name for name, _ in result.failed] == ["one", "two", "three"]
    assert all("bind is a mapping" in why for _, why in result.failed)
    assert len(reads) == 1
