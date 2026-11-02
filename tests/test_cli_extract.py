"""`deckwright extract` refuses before it reads or writes anything."""

import pytest
from typer.testing import CliRunner

from deckwright.cli import app

runner = CliRunner()

EDITED = "# hours of editing\ntheme: base\n---\ntitle: Mine\n"


def _said(result) -> str:
    """What the run reported. `run_cli` prints a `SpecError` and exits 1; `CliRunner`
    invokes the app below that boundary and holds it as the exception instead."""
    return result.output + str(result.exception or "")


def _deck(tmp_path, synthetic_template):
    """A readable deck, and the spec path `extract` writes beside it by default."""
    deck = tmp_path / "Q3 Review.pptx"
    deck.write_bytes(synthetic_template.read_bytes())
    return deck, tmp_path / "Q3 Review.deck.yaml"


def test_a_destination_that_already_holds_a_spec_is_refused(tmp_path, synthetic_template):
    """The second extract of a deck lands on the draft edited after the first. Drop the
    exists check and that file is silently replaced."""
    deck, spec = _deck(tmp_path, synthetic_template)
    spec.write_text(EDITED, encoding="utf-8")

    result = runner.invoke(app, ["extract", str(deck)])

    assert result.exit_code != 0
    assert "already exists" in _said(result)
    assert spec.read_text(encoding="utf-8") == EDITED


def test_force_replaces_the_destination(tmp_path, synthetic_template):
    """The escape hatch has to actually write, or the refusal is a wall."""
    deck, spec = _deck(tmp_path, synthetic_template)
    spec.write_text(EDITED, encoding="utf-8")

    result = runner.invoke(app, ["extract", str(deck), "--force"])

    assert result.exit_code == 0, result.output
    assert spec.read_text(encoding="utf-8").startswith("# Drafted by `deckwright extract`")


def test_an_out_that_already_holds_a_file_is_refused(tmp_path, synthetic_template):
    """Guard only the default destination and this one writes."""
    deck, _ = _deck(tmp_path, synthetic_template)
    dest = tmp_path / "elsewhere" / "draft.deck.yaml"
    dest.parent.mkdir()
    dest.write_text(EDITED, encoding="utf-8")

    result = runner.invoke(app, ["extract", str(deck), "--out", str(dest)])

    assert result.exit_code != 0
    assert dest.read_text(encoding="utf-8") == EDITED


def test_a_transcript_destination_is_refused_under_its_own_suffix(tmp_path, synthetic_template):
    """`--as md` writes `<deck>.md`, so that is the path the guard has to be testing —
    compute the suffix after the check and this compares against the wrong file."""
    deck, _ = _deck(tmp_path, synthetic_template)
    transcript = tmp_path / "Q3 Review.md"
    transcript.write_text("notes I typed\n", encoding="utf-8")

    result = runner.invoke(app, ["extract", str(deck), "--as", "md"])

    assert result.exit_code != 0
    assert transcript.read_text(encoding="utf-8") == "notes I typed\n"


def test_an_existing_destination_is_refused_before_the_deck_is_read(tmp_path):
    """Both refusals precede the harvest, and an unreadable deck is how that is visible:
    read first and the message is about the .pptx instead."""
    deck = tmp_path / "Q3 Review.pptx"
    deck.write_text("not a pptx", encoding="utf-8")
    (tmp_path / "Q3 Review.deck.yaml").write_text(EDITED, encoding="utf-8")

    result = runner.invoke(app, ["extract", str(deck)])

    assert "already exists" in _said(result)
    assert "not a readable" not in _said(result)


def test_an_unknown_as_is_refused_before_the_deck_is_read(tmp_path):
    """Same ordering, for the flag: harvest first and a whole deck is parsed to reject a
    four-letter string."""
    deck = tmp_path / "Q3 Review.pptx"
    deck.write_text("not a pptx", encoding="utf-8")

    result = runner.invoke(app, ["extract", str(deck), "--as", "txt"])

    assert "--as must be 'yaml' or 'md'" in _said(result)
    assert "not a readable" not in _said(result)


@pytest.mark.parametrize("arg", [".", "", "/"], ids=["dot", "empty", "root"])
def test_a_deck_path_with_no_name_is_refused_by_name(arg):
    """The default destination is derived with `Path.with_name`, which raises ValueError on
    a path whose name is empty. Drop the is_file check and these three print a traceback."""
    result = runner.invoke(app, ["extract", arg])

    assert result.exit_code != 0
    assert "is not a readable .pptx" in _said(result)
    assert "Traceback" not in result.output


def test_a_missing_deck_names_the_deck_not_the_destination(tmp_path):
    """A typo in the deck path, with a draft where the correct spelling would write. Check
    the destination first and the message names a file the author did not type."""
    (tmp_path / "Q3 Review.deck.yaml").write_text(EDITED, encoding="utf-8")

    result = runner.invoke(app, ["extract", str(tmp_path / "Q3 Review.pptx")])

    assert "is not a readable .pptx" in _said(result)
    assert "already exists" not in _said(result)


def test_a_file_that_is_not_a_pptx_still_reaches_the_reader(tmp_path):
    """The cheap check is existence, not format — a real file keeps the richer message
    python-pptx supplies. Widen it to a suffix test and this one loses that."""
    deck = tmp_path / "Q3 Review.pptx"
    deck.write_text("not a pptx", encoding="utf-8")

    result = runner.invoke(app, ["extract", str(deck)])

    assert "no file at that path" not in _said(result)
    assert "is not a readable .pptx" in _said(result)
