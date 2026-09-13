import pytest

from deckwright.utils.text import closest_match, text_em, wrapped_lines

# The band a 13.333x7.5in deck gives a chrome line, and the title rung on it.
WIDTH_IN = 11.87
TITLE_PT = 31.2


def test_a_close_typo_is_matched():
    assert closest_match("titel", ["title", "subtitle", "date"]) == "title"


def test_an_unrelated_name_matches_nothing():
    assert closest_match("of", ["name", "tagline"]) is None


def test_an_exact_match_returns_itself():
    assert closest_match("title", ["title", "subtitle"]) == "title"


def test_a_short_line_takes_one_line():
    assert wrapped_lines("Two placements, side by side", width_in=WIDTH_IN, size_pt=TITLE_PT) == 1


def test_a_title_wider_than_its_band_takes_two_lines():
    """LibreOffice wraps this exact string at this exact width and size."""
    assert (
        wrapped_lines(
            "Retrieval-augmented generation cut our support ticket backlog in half",
            width_in=WIDTH_IN,
            size_pt=TITLE_PT,
        )
        == 2
    )


def test_the_same_text_takes_more_lines_at_a_larger_size():
    text = "Retrieval-augmented generation cut our support ticket backlog in half"
    assert wrapped_lines(text, width_in=WIDTH_IN, size_pt=54) > wrapped_lines(
        text, width_in=WIDTH_IN, size_pt=TITLE_PT
    )


def test_narrow_glyphs_fit_more_per_line_than_wide_ones():
    assert wrapped_lines("illili " * 12, width_in=WIDTH_IN, size_pt=TITLE_PT) < wrapped_lines(
        "MWMWMW " * 12, width_in=WIDTH_IN, size_pt=TITLE_PT
    )


def test_a_word_wider_than_the_band_breaks_across_lines():
    assert wrapped_lines("W" * 200, width_in=WIDTH_IN, size_pt=TITLE_PT) > 1


def test_empty_text_takes_one_line():
    assert wrapped_lines("", width_in=WIDTH_IN, size_pt=TITLE_PT) == 1


# --- face-aware measurement -------------------------------------------------


def test_text_em_is_the_summed_table_advances_times_the_margin():
    """1.04 x (M + a) from each table: 0.874 + 0.4937 baked for Calibri,
    0.9477 + 0.668 on the ceiling. Reddens if the margin or either table moves."""
    assert text_em("Ma", "Calibri") == pytest.approx(1.4224, abs=1e-4)
    assert text_em("Ma") == pytest.approx(1.6803, abs=1e-4)


def test_a_face_the_tables_know_measures_well_under_the_ceiling():
    """The whole win of face routing; inside 8% means it collapsed to the ceiling."""
    s = "Quarterly revenue by region"
    assert text_em(s, "Calibri") < 0.92 * text_em(s, None)


def test_a_wrap_estimated_in_the_face_it_renders_in_can_need_fewer_lines():
    text = "Retrieval-augmented generation cut our support ticket backlog in half"
    assert wrapped_lines(text, width_in=WIDTH_IN, size_pt=54, face="Calibri") < wrapped_lines(
        text, width_in=WIDTH_IN, size_pt=54
    )


def test_a_fit_refusal_on_a_face_with_no_table_says_its_estimate_errs_wide():
    from deckwright.utils.text import estimate_caveat

    assert (
        estimate_caveat("Segoe UI")
        == " ('Segoe UI' has no width table, so this estimate errs wide)"
    )


def test_a_measured_face_and_an_unnamed_one_add_no_caveat():
    from deckwright.utils.text import estimate_caveat

    assert estimate_caveat("Calibri", None) == ""


def test_the_caveat_names_each_unmeasured_face_once():
    from deckwright.utils.text import estimate_caveat

    assert estimate_caveat("Segoe UI", "Calibri", "Segoe UI", "Georgia Pro") == (
        " ('Segoe UI', 'Georgia Pro' has no width table, so this estimate errs wide)"
    )


def test_the_first_word_too_wide_for_the_measure_is_named():
    from deckwright.utils.text import overlong_word

    word = overlong_word(
        "An Internationalization plan", width_in=2.0, size_pt=22.0, face="Helvetica"
    )
    assert word is not None and word[0] == "Internationalization"


@pytest.mark.parametrize(
    "text",
    [
        "business-to-business-to-consumer",
        "business—to—business—to—consumer",
        "用户体验设计原则与数据驱动",
    ],
    ids=["hyphen", "em-dash", "cjk"],
)
def test_a_run_a_renderer_can_break_inside_is_not_one_word(text):
    """LibreOffice sets 'business-to-business-to-' / 'consumer' in a 2.42in tile."""
    from deckwright.utils.text import overlong_word

    assert text_em(text, "Helvetica") * 14 / 72 > 2.42, "the whole run fits, so this proves nothing"
    assert overlong_word(text, width_in=2.42, size_pt=14.0, face="Helvetica") is None


def test_a_url_is_one_run_because_a_renderer_breaks_it_mid_word():
    """LibreOffice sets 'phierceweb/deck' / 'wright/blob', not a break after a slash."""
    from deckwright.utils.text import overlong_word

    url = "github.com/phierceweb/deckwright/blob/main/docs"
    found = overlong_word(url, width_in=2.42, size_pt=14.0, face="Helvetica")
    assert found is not None and found[0] == url


def test_the_widest_piece_between_breaks_is_what_is_named():
    from deckwright.utils.text import overlong_word

    found = overlong_word("pre-Internationalization", width_in=2.0, size_pt=22.0, face="Helvetica")
    assert found is not None and found[0] == "Internationalization"


@pytest.mark.parametrize(("width_in", "lines"), [(1.63, 1), (1.5, 2)])
def test_a_lone_word_breaks_where_its_real_width_does(width_in, lines):
    """'Reproduce' is 1.596in in Arial Bold at 22pt: the margin must not reserve it a second line."""
    assert wrapped_lines("Reproduce", width_in=width_in, size_pt=22.0, face="Helvetica") == lines


def test_a_word_that_fits_its_widest_cut_is_not_refused_for_the_sizing_margin():
    """'Reproduce' is 1.596in in Arial Bold at 22pt; a card leaving 1.63in holds it."""
    from deckwright.utils.text import overlong_word

    assert overlong_word("Reproduce", width_in=1.63, size_pt=22.0, face="Helvetica") is None


def test_an_overlong_word_reports_the_width_it_really_needs():
    from deckwright.utils.text import overlong_word

    found = overlong_word("Reproduce", width_in=1.5, size_pt=22.0, face="Helvetica")
    assert found is not None
    assert found == ("Reproduce", pytest.approx(1.596, abs=0.001))


def test_no_word_is_named_when_every_word_fits():
    from deckwright.utils.text import overlong_word

    assert (
        overlong_word("An Internationalization plan", width_in=5.0, size_pt=22.0, face="Helvetica")
        is None
    )
