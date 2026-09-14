"""`[words](address)` markup: what it parses to, and what a line shows once drawn."""

from deckwright.utils.links import addresses, plain, spans
from deckwright.utils.text import overlong_word, text_em, wrapped_lines


def test_a_line_splits_into_runs_around_each_link():
    assert spans("Read [the guide](https://x.io/g) and [mail](mailto:a@b.c).") == [
        ("Read ", None),
        ("the guide", "https://x.io/g"),
        (" and ", None),
        ("mail", "mailto:a@b.c"),
        (".", None),
    ]


def test_an_escaped_bracket_is_text_and_not_a_link():
    assert spans(r"see \[1](x) here") == [("see [1](x) here", None)]
    assert plain(r"see \[1](x) here") == "see [1](x) here"


def test_a_line_shows_its_words_without_the_markup():
    assert plain("Read [the guide](https://x.io/g) first") == "Read the guide first"
    assert addresses("[a](https://a.io) and [b](https://b.io)") == ["https://a.io", "https://b.io"]


def test_brackets_with_a_space_in_the_address_are_not_a_link():
    assert plain("a [note](see below) here") == "a [note](see below) here"


def test_a_link_is_measured_by_its_words():
    """An address is never drawn, so it can neither widen a line nor be an overlong word."""
    marked = "Read [the guide](https://example.com/a/very/long/address/indeed) first"
    shown = "Read the guide first"
    assert text_em(marked, "Calibri") == text_em(shown, "Calibri")
    assert wrapped_lines(marked, width_in=2.0, size_pt=18, face="Calibri") == wrapped_lines(
        shown, width_in=2.0, size_pt=18, face="Calibri"
    )
    assert overlong_word(marked, width_in=2.0, size_pt=18, face="Calibri") is None


_ADDRESS = "https://example.com/reference/" + "a" * 80


def test_an_escaped_bracket_is_measured_as_the_markup_it_draws():
    """`\\[1](…)` draws its whole address, so it must not be measured as a link's words."""
    escaped = wrapped_lines(rf"\[1]({_ADDRESS})", width_in=2, size_pt=18, face="Calibri")
    braces = wrapped_lines(f"{{1}}({_ADDRESS})", width_in=2, size_pt=18, face="Calibri")
    assert escaped == braces > 1


def test_shown_text_is_measured_as_written_when_links_are_off():
    """qa measures a manifest line, already the words shown or a literal code line."""
    literal = f"See [docs]({_ADDRESS})"
    assert wrapped_lines(literal, width_in=2, size_pt=18, links=False) == wrapped_lines(
        f"See {{docs}}({_ADDRESS})", width_in=2, size_pt=18
    )
    assert text_em(literal, links=False) == text_em(rf"See \[docs]({_ADDRESS})")


def test_an_address_may_hold_balanced_parentheses_and_words_may_hold_brackets():
    assert spans("See [Mercury](https://en.wikipedia.org/wiki/Mercury_(planet)).") == [
        ("See ", None),
        ("Mercury", "https://en.wikipedia.org/wiki/Mercury_(planet)"),
        (".", None),
    ]
    assert spans("note [[1]](https://example.com/n1)") == [
        ("note ", None),
        ("[1]", "https://example.com/n1"),
    ]
