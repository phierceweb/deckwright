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


def _set(*words, top=80.0, glyph=6.0):
    """``words`` laid left to right from 80pt — inside a ``_rec`` box, which spans 72–216pt
    across — ``glyph`` points a character and one apart, as ``page_words`` reports them."""
    out, left = [], 80.0
    for word in words:
        out.append((left, top, left + glyph * len(word), top + 14.0, word))
        left += glyph * (len(word) + 1)
    return out


def _words_are(monkeypatch, *pages):
    import deckwright.qa.textflow as tf

    calls = []

    def fake(pdf_path, **_):
        calls.append(pdf_path)
        return list(pages)

    monkeypatch.setattr(tf, "page_words", fake)
    return calls


def _two_column_page():
    """A page pdftotext merged row-wise, splicing the right column into the left line."""
    return "Left line one RIGHT LINE ONE left line two"


def test_a_line_the_page_splices_is_clean_when_its_own_box_holds_it(monkeypatch):
    """The false positive a multi-column slide produces: the page interleaves, the box does not."""
    right = [(300.0, 80.0, 330.0, 94.0, "RIGHT")]
    _words_are(
        monkeypatch, _set("Left", "line", "one") + right + _set("left", "line", "two", top=100.0)
    )
    m = _manifest(_slide(1, _rec(lines=["Left line one left line two"])))
    assert check_overflow(m, [_two_column_page()], pdf_path="d.pdf") == []


def test_a_line_absent_from_its_own_box_is_still_an_error(monkeypatch):
    """The negative control: the box must not become a way for real overflow to pass."""
    _words_are(monkeypatch, _set("Left", "line", "one"))
    m = _manifest(_slide(1, _rec(lines=["Left line one left line two"])))
    findings = check_overflow(m, [_two_column_page()], pdf_path="d.pdf")
    assert len(findings) == 1
    assert findings[0].check == "overflow"


def _plated(lines):
    return {**_rec(lines=lines), "plate": True}


def test_a_plated_line_on_the_page_but_off_its_plate_is_an_error(monkeypatch):
    """A listing run past its plate is still on the page; only the plate's own box shows it.
    Of ``beta=2)``, set from 212pt, only the glyphs starting before 220pt are inside."""
    _words_are(monkeypatch, _set("return", "build(alpha=1,", "beta=2)"))
    m = _manifest(_slide(1, _plated(["return build(alpha=1, beta=2)"])))
    findings = check_overflow(m, ["return build(alpha=1, beta=2)"], pdf_path="d.pdf")
    assert [f.detail for f in findings] == [
        "'return build(alpha=1, beta=2)' was not found inside its plate"
    ]


def test_a_plated_line_its_plate_holds_is_clean(monkeypatch):
    _words_are(monkeypatch, _set("return", "build(a=1)"))
    m = _manifest(_slide(1, _plated(["return build(a=1)"])))
    assert check_overflow(m, ["return build(a=1)"], pdf_path="d.pdf") == []


def test_the_render_is_read_once_however_many_boxes_ask(monkeypatch):
    calls = _words_are(monkeypatch, _set("one", "two"), _set("three", "four"))
    m = _manifest(
        _slide(1, _plated(["one"]), _plated(["two"])),
        _slide(2, _plated(["three"]), _rec(lines=["four"])),
    )
    assert check_overflow(m, ["one two", "three"], pdf_path="d.pdf") == []
    assert calls == ["d.pdf"]


def test_no_box_is_read_while_the_page_holds_every_line(monkeypatch):
    calls = _words_are(monkeypatch)
    m = _manifest(_slide(1, _rec(lines=["Left line one"])))
    assert check_overflow(m, ["Left line one"], pdf_path="d.pdf") == []
    assert calls == []


def test_a_plated_line_is_judged_on_the_page_when_its_words_cannot_be_read(monkeypatch):
    import deckwright.qa.textflow as tf
    from deckwright.errors import RenderError

    def unreadable(*a, **k):
        raise RenderError("pdftotext failed on d.pdf")

    monkeypatch.setattr(tf, "page_words", unreadable)
    m = _manifest(_slide(1, _plated(["kept line"]), _plated(["lost line"])))
    findings = check_overflow(m, ["kept line"], pdf_path="d.pdf")
    assert [f.detail for f in findings] == ["'lost line' was not found in the rendered slide"]


def test_text_within_a_box_counts_a_glyph_any_of_which_is_inside():
    """The box ends at 220pt with its pad: of the word set from 110pt, only the glyphs
    starting before it count. A neighbour beside the box and a word below it do not."""
    from deckwright.qa.textflow import text_within

    box = (1.0, 1.0, 2.0, 1.0)
    beside = [(300.0, 80.0, 330.0, 94.0, "neighbour")]
    below = [(80.0, 150.0, 110.0, 164.0, "under")]
    words = _set("kept", "straddling" + "x" * 20) + beside + below
    assert text_within(words, box) == "kept straddling" + "x" * 9


def test_page_words_reads_every_page_from_one_bbox_pass(monkeypatch):
    """A page with no words is still a page, so the next keeps its number."""
    import deckwright.qa.textflow as tf

    seen = []

    def fake_run(argv, pdf_path, timeout_s):
        seen.append(argv)
        return (
            '<doc>\n<page width="960.000000" height="540.000000">\n'
            '<word xMin="1.500000" yMin="2.000000" xMax="10.000000" yMax="12.000000">a&amp;b</word>\n'
            '<word xMin="12.000000" yMin="2.000000" xMax="20.000000" yMax="12.000000">c</word>\n'
            '</page>\n<page width="960.000000" height="540.000000">\n</page>\n'
            '<page width="960.000000" height="540.000000">\n'
            '<word xMin="3.000000" yMin="4.000000" xMax="5.000000" yMax="6.000000">d</word>\n'
            "</page>\n</doc>"
        )

    monkeypatch.setattr(tf, "_run_pdftotext", fake_run)
    assert tf.page_words("d.pdf") == [
        [(1.5, 2.0, 10.0, 12.0, "a&b"), (12.0, 2.0, 20.0, 12.0, "c")],
        [],
        [(3.0, 4.0, 5.0, 6.0, "d")],
    ]
    assert seen == [[seen[0][0], "-bbox", "d.pdf", "-"]]


def test_without_a_pdf_path_the_box_is_never_consulted(monkeypatch):
    import deckwright.qa.textflow as tf

    def _boom(*a, **k):
        raise AssertionError("page_words must not run without pdf_path")

    monkeypatch.setattr(tf, "page_words", _boom)
    m = _manifest(_slide(1, _rec(lines=["Left line one left line two"])))
    assert len(check_overflow(m, [_two_column_page()])) == 1


def test_unreadable_word_boxes_report_the_finding_rather_than_swallowing_it(monkeypatch):
    import deckwright.qa.textflow as tf
    from deckwright.errors import RenderError

    def _fail(*a, **k):
        raise RenderError("pdftotext died")

    monkeypatch.setattr(tf, "page_words", _fail)
    m = _manifest(_slide(1, _rec(lines=["Left line one left line two"])))
    assert len(check_overflow(m, [_two_column_page()], pdf_path="d.pdf")) == 1
