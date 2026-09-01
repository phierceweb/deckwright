from deckwright.qa.model import Severity
from deckwright.qa.textflow import check_overflow, normalise


def _manifest(*slides):
    return {"deck": "d.pptx", "slides": list(slides)}


def _slide(index, *records, layout="content"):
    return {"index": index, "layout": layout, "shapes": list(records)}


def _rec(text=None, lines=None, rendered="native"):
    return {
        "shape_id": 2,
        "name": "Box",
        "box": dict(zip("xywh", (1, 1, 2, 1), strict=True)),
        "text": text,
        "lines": lines or [],
        "font_pt": None,
        "fg": None,
        "bg": None,
        "rendered": rendered,
    }


def test_normalise_collapses_whitespace_and_case():
    assert normalise("  Hello   WORLD \n") == "hello world"


def test_text_present_on_the_page_is_clean():
    m = _manifest(_slide(1, _rec(lines=["Alpha", "Beta"])))
    assert check_overflow(m, ["alpha beta gamma"]) == []


def test_a_missing_line_is_an_error():
    m = _manifest(_slide(1, _rec(lines=["Alpha", "Beta"])))
    findings = check_overflow(m, ["Alpha only"])
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert findings[0].check == "overflow"
    assert "Beta" in findings[0].detail


def test_whitespace_differences_do_not_trip_it():
    m = _manifest(_slide(1, _rec(lines=["Complexity  ·  Consistency"])))
    assert check_overflow(m, ["Complexity · Consistency"]) == []


def test_image_rendered_records_are_skipped():
    m = _manifest(_slide(1, _rec(lines=["inside a panel"], rendered="image")))
    assert check_overflow(m, ["nothing here"]) == []


def test_a_record_with_only_text_falls_back_to_it():
    m = _manifest(_slide(1, _rec(text="Solo")))
    assert check_overflow(m, ["nothing"])[0].detail.count("Solo") == 1


def test_empty_and_whitespace_lines_are_ignored():
    m = _manifest(_slide(1, _rec(lines=["", "   "])))
    assert check_overflow(m, [""]) == []


def test_each_slide_is_matched_to_its_own_page():
    m = _manifest(_slide(1, _rec(lines=["one"])), _slide(2, _rec(lines=["two"])))
    assert check_overflow(m, ["one", "two"]) == []
    findings = check_overflow(m, ["two", "one"])
    assert {f.slide for f in findings} == {1, 2}


def test_a_page_count_mismatch_is_reported_once():
    m = _manifest(_slide(1, _rec(lines=["one"])), _slide(2, _rec(lines=["two"])))
    findings = check_overflow(m, ["one"])
    assert len(findings) == 1
    assert findings[0].slide == 0
    assert findings[0].check == "page-count"
    # A page-count mismatch means the render and the manifest disagree about how many
    # slides exist, so every later per-slide finding is aligned against the wrong page.
    assert findings[0].severity is Severity.ERROR


def test_a_duplicate_line_is_reported_once_per_record():
    m = _manifest(_slide(1, _rec(lines=["gone", "gone"])))
    assert len(check_overflow(m, ["nothing"])) == 2


def test_normalise_preserves_punctuation_and_glyphs():
    assert normalise("•  Alpha") == "•  alpha".replace("  ", " ")
    assert normalise("A · B") == "a · b"


def test_a_swapped_glyph_is_still_detected():
    m = _manifest(_slide(1, _rec(lines=["•  Alpha"])))
    assert len(check_overflow(m, ["※  Alpha"])) == 1


def test_text_found_only_in_the_alternate_extraction_is_not_flagged():
    """Each pdftotext mode splits lines the other keeps whole; either alone false-positives."""
    manifest = _manifest(_slide(1, _rec(lines=["wrapped label here"])))
    assert (
        check_overflow(manifest, ["wrapped label\nother column\nhere"], ["wrapped label here"])
        == []
    )


def test_text_missing_from_both_extractions_is_flagged():
    manifest = _manifest(_slide(1, _rec(lines=["gone"])))
    findings = check_overflow(manifest, ["nothing"], ["nothing either"])
    assert [f.check for f in findings] == ["overflow"]
    assert findings[0].severity is Severity.ERROR


def test_a_missing_alternate_extraction_is_tolerated():
    manifest = _manifest(_slide(1, _rec(lines=["present"])))
    assert check_overflow(manifest, ["present"]) == []


def test_a_line_wrapped_at_its_hyphen_survives_dehyphenation():
    """Reading order rejoins a word wrapped at its hyphen by deleting the hyphen."""
    m = _manifest(_slide(1, _rec(lines=["it must clear the 3:1 non-text minimum."])))
    assert check_overflow(m, ["it must clear the 3:1 nontext minimum."]) == []


def test_a_hyphen_kept_at_a_row_break_in_the_alternate_extraction():
    """-layout keeps the wrap hyphen at the row end, with a break where the wrap was."""
    m = _manifest(_slide(1, _rec(lines=["it must clear the 3:1 non-text minimum."])))
    assert (
        check_overflow(
            m, ["unrelated reading-order text"], ["it must clear the 3:1 non-\ntext minimum."]
        )
        == []
    )


def test_a_line_clipped_at_its_hyphen_is_still_flagged():
    """Real overflow that truncates at the hyphen is loss, not a wrap artifact."""
    m = _manifest(_slide(1, _rec(lines=["it must clear the 3:1 non-text minimum."])))
    findings = check_overflow(m, ["it must clear the 3:1 non-"])
    assert [f.check for f in findings] == ["overflow"]


def _two_column_page():
    """A page pdftotext merged row-wise, splicing the right column into the left line."""
    return "Left line one RIGHT LINE ONE left line two"


def test_a_line_the_page_splices_is_clean_when_its_own_box_holds_it(monkeypatch):
    """The false positive a multi-column slide produces: the page interleaves, the box does not."""
    import deckwright.qa.textflow as tf

    monkeypatch.setattr(tf, "crop_text", lambda *a, **k: "Left line one left line two")
    m = _manifest(_slide(1, _rec(lines=["Left line one left line two"])))
    assert check_overflow(m, [_two_column_page()], pdf_path="d.pdf") == []


def test_a_line_absent_from_its_own_box_is_still_an_error(monkeypatch):
    """The negative control: the crop must not become a way for real overflow to pass."""
    import deckwright.qa.textflow as tf

    monkeypatch.setattr(tf, "crop_text", lambda *a, **k: "Left line one")
    m = _manifest(_slide(1, _rec(lines=["Left line one left line two"])))
    findings = check_overflow(m, [_two_column_page()], pdf_path="d.pdf")
    assert len(findings) == 1
    assert findings[0].check == "overflow"


def test_without_a_pdf_path_the_box_is_never_consulted(monkeypatch):
    import deckwright.qa.textflow as tf

    def _boom(*a, **k):
        raise AssertionError("crop_text must not run without pdf_path")

    monkeypatch.setattr(tf, "crop_text", _boom)
    m = _manifest(_slide(1, _rec(lines=["Left line one left line two"])))
    assert len(check_overflow(m, [_two_column_page()])) == 1


def test_a_failed_crop_reports_the_finding_rather_than_swallowing_it(monkeypatch):
    import deckwright.qa.textflow as tf
    from deckwright.errors import RenderError

    def _fail(*a, **k):
        raise RenderError("pdftotext died")

    monkeypatch.setattr(tf, "crop_text", _fail)
    m = _manifest(_slide(1, _rec(lines=["Left line one left line two"])))
    assert len(check_overflow(m, [_two_column_page()], pdf_path="d.pdf")) == 1


def test_crop_text_converts_inches_to_points_and_pads(monkeypatch):
    """A real prose box: the inches it records, and the points they crop to."""
    import deckwright.qa.textflow as tf

    seen = {}

    def _capture(argv, pdf_path, timeout_s):
        seen["argv"] = argv
        return "text"

    monkeypatch.setattr(tf, "_run_pdftotext", _capture)
    tf.crop_text("d.pdf", 25, (0.8, 1.758, 5.767, 1.178))
    argv = seen["argv"]
    assert argv[argv.index("-f") + 1] == "25"
    assert argv[argv.index("-l") + 1] == "25"
    assert argv[argv.index("-x") + 1] == "53"
    assert argv[argv.index("-y") + 1] == "122"
    assert argv[argv.index("-W") + 1] == "423"
    assert argv[argv.index("-H") + 1] == "92"


def test_a_crop_at_the_slide_edge_does_not_ask_for_a_negative_offset(monkeypatch):
    import deckwright.qa.textflow as tf

    seen = {}
    monkeypatch.setattr(
        tf, "_run_pdftotext", lambda argv, p, t: seen.setdefault("argv", argv) and ""
    )
    tf.crop_text("d.pdf", 1, (0.0, 0.0, 1.0, 1.0))
    argv = seen["argv"]
    assert argv[argv.index("-x") + 1] == "0"
    assert argv[argv.index("-y") + 1] == "0"
