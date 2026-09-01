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
