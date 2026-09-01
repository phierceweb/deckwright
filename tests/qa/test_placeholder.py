import pytest

from deckwright.qa.model import Finding, Severity
from deckwright.qa.placeholder import check_placeholder

_DETAIL = "reads like copy nobody meant to ship"


def _manifest(*, lines=(), text=None, notes=None):
    shape = {"name": "s1.p1.bullets", "box": {"x": 1.0, "y": 2.0, "w": 3.0, "h": 4.0}}
    if lines:
        shape["lines"] = list(lines)
    if text is not None:
        shape["text"] = text
    slide = {"index": 1, "shapes": [shape]}
    if notes:
        slide["notes"] = notes
    return {"slides": [slide]}


def test_scaffold_copy_that_survived_the_build_is_reported():
    findings = check_placeholder(
        _manifest(lines=["Three things are broken", "Revenue grew 12%"]), None
    )
    assert [f.check for f in findings] == ["placeholder"]
    assert findings[0].severity is Severity.WARN
    assert findings[0].slide == 1
    assert "Three things are broken" in findings[0].detail
    assert findings[0].shape == "s1.p1.bullets"
    assert findings[0].box == (1.0, 2.0, 3.0, 4.0)


@pytest.mark.parametrize(
    "line, word",
    [
        ("LOREM ipsum dolor", "LOREM"),
        ("FixMe before Friday", "FixMe"),
        ("[INSERT client name]", "[INSERT"),
        ("@todo replace with the real figure", "@todo"),
        ("@TODO replace with the real figure", "@TODO"),
    ],
)
def test_every_case_insensitive_needle_is_reported(line, word):
    findings = check_placeholder(_manifest(lines=[line]), None)
    assert [f.detail for f in findings] == [f"{word!r} {_DETAIL}"]


@pytest.mark.parametrize(
    "line, word",
    [
        ("TODO: check this number", "TODO:"),
        ("TODO add the chart", "TODO"),
        ("TODO - replace", "TODO"),
        ("(TODO)", "TODO"),
        ("Revenue grew 12% TODO", "TODO"),
        ("TODO Añadir el gráfico", "TODO"),
        ("todo: check this number", "todo:"),
    ],
)
def test_every_marker_form_of_todo_is_reported(line, word):
    findings = check_placeholder(_manifest(lines=[line]), None)
    assert [f.detail for f in findings] == [f"{word!r} {_DETAIL}"]


def test_a_todo_in_the_speaker_notes_is_reported():
    findings = check_placeholder(_manifest(lines=["Fine"], notes="TODO: check this number"), None)
    assert findings == [
        Finding(
            slide=1,
            check="placeholder",
            severity=Severity.WARN,
            detail=f"'TODO:' in the speaker notes {_DETAIL}",
        )
    ]


def test_a_lowercase_todo_opening_a_later_notes_line_is_reported():
    findings = check_placeholder(_manifest(lines=["Fine"], notes="Say hello.\ntodo: confirm"), None)
    assert [f.detail for f in findings] == [f"'todo:' in the speaker notes {_DETAIL}"]


def test_a_shape_that_recorded_only_text_is_reported():
    """Every chrome kicker, title and subtitle records `text` and no `lines`."""
    assert len(check_placeholder(_manifest(text="A KICKER"), None)) == 1


def test_a_shape_recording_both_lines_and_text_reports_once():
    manifest = _manifest(lines=["A KICKER"], text="A KICKER")
    assert len(check_placeholder(manifest, None)) == 1


@pytest.mark.parametrize(
    "line",
    [
        "Thank you",
        "Problem",
        "Solution",
        "Adoption climbs every quarter",
        "The first thing we noticed was the churn",
        "Three moves that changed the quarter",
        "What we learned. What we changed.",
        "The first thing",
        "The second thing",
        "The third thing",
        "What is going wrong",
        "Date: TBD",
        "Venue: TBD",
    ],
)
def test_ordinary_deck_copy_is_not_reported(line):
    assert check_placeholder(_manifest(lines=[line]), None) == []


@pytest.mark.parametrize(
    "line",
    [
        "Todo el equipo creció un 12%",
        "todo lo que necesitas saber",
        "TODO EL EQUIPO",
        "Es todo: gracias",
    ],
)
def test_the_spanish_word_todo_is_not_reported(line):
    """An all-caps line that goes on in capitals is a Spanish kicker, not a marker."""
    assert check_placeholder(_manifest(lines=[line]), None) == []


@pytest.mark.parametrize(
    "line",
    [
        "https://tracker.example.com/todo:123",
        "def f(todo: str):",
    ],
)
def test_a_lowercase_todo_colon_inside_a_line_is_not_reported(line):
    """The lowercase form is a marker only as a line's prefix."""
    assert check_placeholder(_manifest(lines=[line]), None) == []


@pytest.mark.parametrize(
    "line, word",
    [
        ("Growth of xxx percent", "xxx"),
        ("Growth of XXX percent", "XXX"),
        ("Card ending XXXX 4242", "XXXX"),
        ("Roman numeral section XXX", "XXX"),
    ],
)
def test_a_bare_run_of_x_is_reported_whatever_it_was_meant_to_say(line, word):
    """A masked identifier and a Roman numeral are spelled like the fill marker."""
    findings = check_placeholder(_manifest(lines=[line]), None)
    assert [f.detail for f in findings] == [f"{word!r} {_DETAIL}"]


@pytest.mark.parametrize("line", ["Xxx Air took 12% share", "xXx"])
def test_a_mixed_case_run_of_x_is_not_reported(line):
    assert check_placeholder(_manifest(lines=[line]), None) == []


@pytest.mark.parametrize("line", ["Mastodon adoption, all told", "Maxxx Air took 12% share"])
def test_a_needle_inside_a_longer_word_is_not_reported(line):
    assert check_placeholder(_manifest(lines=[line]), None) == []
