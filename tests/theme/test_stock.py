import pytest
from pptx import Presentation

from deckwright.theme.clrscheme import parse_color_scheme, read_theme_xml
from deckwright.theme.stock import is_stock_accent

SLOTS = ("accent1", "accent2", "accent3", "accent4", "accent5", "accent6")

# The six accents of each Office theme, in slot order, as PowerPoint ships them.
GENERATIONS = {
    "2007": ("4F81BD", "C0504D", "9BBB59", "8064A2", "4BACC6", "F79646"),
    "2013-2021": ("4472C4", "ED7D31", "A5A5A5", "FFC000", "5B9BD5", "70AD47"),
    "2024": ("156082", "E97132", "196B24", "0F9ED5", "A02B93", "4EA72E"),
}


def test_an_unedited_office_accent_is_stock():
    assert is_stock_accent("4F81BD") is True
    assert is_stock_accent("70AD47") is True


@pytest.mark.parametrize("generation", sorted(GENERATIONS))
def test_every_accent_of_a_shipped_office_theme_is_stock(generation):
    """A partial generation is the failure mode: miss accent1/accent2 and the two slots
    a theme most often binds are adopted as the brand ramp."""
    missed = [c for c in GENERATIONS[generation] if not is_stock_accent(c)]
    assert missed == [], f"Office {generation} accents not recognised: {missed}"


def test_a_brand_colour_is_not_stock():
    assert is_stock_accent("27B94C") is False
    assert is_stock_accent("FB0304") is False


def test_the_check_ignores_case_and_a_leading_hash():
    assert is_stock_accent("#4f81bd") is True


def test_the_whole_stock_office_scheme_is_stock(synthetic_template):
    """python-pptx's default template ships the untouched Office 2007 accents."""
    master = Presentation(str(synthetic_template)).slide_masters[0]
    scheme = parse_color_scheme(read_theme_xml(master))
    assert all(is_stock_accent(scheme[slot]) for slot in SLOTS)


def test_a_theme_slot_that_is_not_an_accent_is_never_stock():
    """dk2's 1F497D is Office's own, but only accent slots are subject to the check."""
    assert is_stock_accent("1F497D") is False
