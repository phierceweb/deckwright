"""The content view: the manifest rendered as the deck's words."""

from __future__ import annotations

import pytest

from deckwright.compile.content import render_content, split_name, write_content


def _manifest(shapes, **slide):
    return {
        "deck": "out/Demo.pptx",
        "theme": "base",
        "build_id": "abc123",
        "slides": [{"index": 1, "shapes": shapes, **slide}],
    }


def _shape(name, **over):
    return {"shape_id": 2, "name": name, "box": {"x": 0, "y": 0, "w": 1, "h": 1}, **over}


@pytest.mark.parametrize(
    "name, expected",
    [
        ("s4.p1.bullets#1", ("s4.p1.bullets", None)),
        ("s4.chrome.title", ("s4.chrome", "title")),
        ("s2.p1.table.r1c1", ("s2.p1.table", "r1c1")),
        ("s4.bg#12", ("s4.bg", None)),
    ],
)
def test_a_shape_name_splits_into_its_origin_and_part(name, expected):
    assert split_name(name) == expected


def test_the_chrome_becomes_the_slides_headings():
    out = render_content(
        _manifest(
            [
                _shape("s1.chrome.kicker", text="JULY 2026"),
                _shape("s1.chrome.title", text="Smoke Test"),
                _shape("s1.chrome.subtitle", text="Proving it end to end"),
            ]
        )
    )
    assert "**JULY 2026**" in out
    assert "### Smoke Test" in out
    assert "Proving it end to end" in out


def test_chrome_is_written_in_reading_order_whatever_order_it_was_drawn():
    """Compose draws the chrome stack in its own order; a reader wants the slide's."""
    out = render_content(
        _manifest(
            [
                _shape("s1.chrome.subtitle", text="third"),
                _shape("s1.chrome.title", text="second"),
                _shape("s1.chrome.kicker", text="first"),
            ]
        )
    )
    assert out.index("first") < out.index("second") < out.index("third")


def test_a_placements_lines_are_listed_under_the_origin_that_drew_them():
    out = render_content(
        _manifest(
            [
                _shape("s1.p1.bullets#1", lines=["•  Alpha", "•  Beta"]),
            ]
        )
    )
    assert "`s1.p1.bullets`" in out
    assert "- Alpha" in out and "- Beta" in out


def test_a_recorded_table_is_written_as_a_table():
    out = render_content(
        _manifest(
            [
                _shape("s1.p1.table.r1c1", lines=["Dish"]),
                _shape("s1.p1.table.r1c2", lines=["Price"]),
                _shape("s1.p1.table.r2c1", lines=["Tiramisu"]),
                _shape("s1.p1.table.r2c2", lines=["$9"]),
            ]
        )
    )
    assert "| Dish | Price |" in out
    assert "|---|---|" in out
    assert "| Tiramisu | $9 |" in out


def test_speaker_notes_are_carried_as_a_quote():
    """They are content, and reach the manifest for no other reason."""
    out = render_content(_manifest([], notes="Remember the framing."))
    assert "> Remember the framing." in out


def test_a_shape_holding_no_words_still_says_it_is_there():
    """A chart slide would otherwise read as an empty one."""
    out = render_content(_manifest([_shape("s1.p1.chart#1")]))
    assert "*(chart)*" in out


def test_a_divider_is_structure_and_says_nothing():
    out = render_content(_manifest([_shape("s1.p1.rule#1"), _shape("s1.bg#1")]))
    assert "rule" not in out and "bg" not in out


def test_a_photograph_is_named_rather_than_quoted():
    out = render_content(_manifest([_shape("s1.p1.image#1", rendered="picture")]))
    assert "*(picture)*" in out


def test_text_rasterised_into_a_panel_is_marked_as_such():
    """It is in the deck but no PDF extractor will find it; a reader should know."""
    out = render_content(
        _manifest(
            [
                _shape("s1.p1.document#1", lines=["A heading"], rendered="image"),
            ]
        )
    )
    assert "A heading *(rendered as an image)*" in out


def test_the_section_appears_beside_the_slide_number():
    out = render_content(_manifest([], section="Charts"))
    assert "## Slide 1 · Charts" in out


def test_write_content_puts_the_markdown_where_it_was_told(tmp_path):
    out = tmp_path / "nested" / "Demo.content.md"
    write_content(_manifest([_shape("s1.chrome.title", text="Demo")]), out)
    assert "### Demo" in out.read_text()
