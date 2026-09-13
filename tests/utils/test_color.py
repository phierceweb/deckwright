import pytest

from deckwright.errors import ThemeError
from deckwright.utils.color import contrast_ratio, normalize_hex, relative_luminance


def test_white_has_full_luminance():
    assert relative_luminance("FFFFFF") == pytest.approx(1.0)


def test_black_has_zero_luminance():
    assert relative_luminance("000000") == pytest.approx(0.0)


def test_black_on_white_is_the_maximum_ratio():
    assert contrast_ratio("000000", "FFFFFF") == pytest.approx(21.0, abs=0.01)


def test_the_ratio_is_symmetric():
    assert contrast_ratio("2D0937", "FFFFFF") == pytest.approx(contrast_ratio("FFFFFF", "2D0937"))


def test_a_dark_aubergine_on_white_passes_aa():
    assert contrast_ratio("2D0937", "FFFFFF") > 4.5


def test_a_leading_hash_is_tolerated():
    assert relative_luminance("#FFFFFF") == pytest.approx(1.0)


def test_a_lowercase_hex_normalizes_to_uppercase():
    assert normalize_hex("#27b94c") == "27B94C"


def test_a_three_digit_hex_is_rejected():
    with pytest.raises(ThemeError, match="not a 6-digit hex colour"):
        normalize_hex("#fff")


def test_a_non_hex_string_is_rejected():
    with pytest.raises(ThemeError, match="not a 6-digit hex colour"):
        normalize_hex("cornflower")


def test_the_channel_weights_are_the_wcag_ones():
    """Named coefficients, not a re-derivation: a flat average also maps white to 1.0
    and black to 0.0, so the existing extremes tests cannot tell the two apart."""
    assert relative_luminance("FF0000") == pytest.approx(0.2126, abs=1e-4)
    assert relative_luminance("00FF00") == pytest.approx(0.7152, abs=1e-4)
    assert relative_luminance("0000FF") == pytest.approx(0.0722, abs=1e-4)


def test_colour_difference_is_zero_for_one_colour_and_a_hundred_from_black_to_white():
    from deckwright.utils.color import delta_e

    assert delta_e("3282BE", "3282BE") == 0.0
    assert delta_e("000000", "FFFFFF") == pytest.approx(100.0, abs=0.01)
