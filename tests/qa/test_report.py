import json

from deckwright.qa.model import Finding, QaReport, Severity
from deckwright.qa.report import write_json, write_markdown

REPORT = QaReport(
    deck="Demo.pptx",
    findings=(
        Finding(
            slide=2,
            check="reserved",
            severity=Severity.ERROR,
            detail="shape intrudes on 'logo-wedge'",
            box=[11.0, 6.0, 1.0, 0.5],
        ),
        Finding(slide=5, check="min-font", severity=Severity.WARN, detail="9.0pt below 10.5pt"),
    ),
)


def test_markdown_names_the_deck_and_every_finding(tmp_path):
    path = write_markdown(REPORT, tmp_path / "qa.md")
    text = path.read_text()
    assert "Demo.pptx" in text
    assert "logo-wedge" in text and "9.0pt" in text
    assert "slide 2" in text.lower() and "slide 5" in text.lower()


def test_markdown_states_a_clean_result_explicitly(tmp_path):
    text = write_markdown(QaReport(deck="Clean.pptx", findings=()), tmp_path / "q.md").read_text()
    assert "no findings" in text.lower()


def test_json_round_trips_every_field(tmp_path):
    data = json.loads(write_json(REPORT, tmp_path / "qa.json").read_text())
    assert data["deck"] == "Demo.pptx"
    assert len(data["findings"]) == 2
    first = data["findings"][0]
    assert first["severity"] == "error"
    assert first["check"] == "reserved"
    assert first["box"] == {"x": 11.0, "y": 6.0, "w": 1.0, "h": 0.5}


def test_json_counts_by_severity(tmp_path):
    data = json.loads(write_json(REPORT, tmp_path / "qa.json").read_text())
    assert data["counts"] == {"error": 1, "warn": 1, "info": 0}


def test_writers_create_missing_parent_directories(tmp_path):
    assert write_json(REPORT, tmp_path / "deep" / "qa.json").is_file()


def test_markdown_collapses_whitespace_in_detail(tmp_path):
    report = QaReport(
        deck="Test.pptx",
        findings=(
            Finding(
                slide=1,
                check="test",
                severity=Severity.ERROR,
                detail="line one\n## not a heading\nline three",
            ),
        ),
    )
    text = write_markdown(report, tmp_path / "qa.md").read_text()
    lines = text.split("\n")
    real_headings = [line for line in lines if line.startswith("##")]
    assert len(real_headings) == 1 and "Slide 1" in real_headings[0]
    assert "line one line three" in text or "line one" in text
