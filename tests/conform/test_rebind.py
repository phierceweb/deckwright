"""A kept theme's `inverse` is rebound only when it vanishes into the page, and nothing else moves."""

from __future__ import annotations

from deckwright.conform.rebind import rebound_inverse

# A dark master whose kept theme binds `inverse` to the page's own colour.
DARK = {"dk1": "273D40", "dk2": "1A4A7A", "lt1": "FFFFFF", "lt2": "DDEEF8"}


def test_an_inverse_matching_a_dark_page_is_rebound_and_given_an_ink():
    bind = {"page": "1D4D44", "ink": "lt1", "inverse": "dk1", "accent-1": "dk2"}

    rebound, change = rebound_inverse(DARK, bind)

    assert rebound == {
        "page": "1D4D44",
        "ink": "lt1",
        "inverse": "lt2",
        "accent-1": "dk2",
        "inverse-ink": "dk1",
    }
    assert change == "inverse dk1 -> lt2: 1.2:1 off the page, now 8.0:1"


def test_an_ink_kept_for_the_old_light_plate_goes_when_the_new_plate_is_dark():
    """The default inverse-ink reads on navy, so the dark ink tuned for the light plate goes."""
    scheme = {"dk1": "000000", "dk2": "44546A", "lt1": "FFFFFF", "lt2": "E7E6E6"}
    bind = {"page": "lt1", "inverse": "lt2", "inverse-ink": "dk1"}

    rebound, _ = rebound_inverse(scheme, bind)

    assert rebound == {"page": "lt1", "inverse": "dk2"}


def test_an_inverse_that_already_stands_off_the_page_is_left_alone():
    """dk2 is 4.4:1 off a white page: under AA for text, but a plate that clears 3:1 is kept."""
    scheme = {"dk1": "000000", "dk2": "8A6BB0", "lt1": "FFFFFF", "lt2": "E7E6E6"}
    assert rebound_inverse(scheme, {"page": "lt1", "inverse": "dk2"}) is None


def test_a_default_inverse_lost_in_a_dark_page_is_bound():
    """The load warning names the default 12161B too, so re-adopting has to answer it."""
    rebound, change = rebound_inverse(DARK, {"page": "1D4D44"})

    assert rebound == {"page": "1D4D44", "inverse": "lt2", "inverse-ink": "dk1"}
    assert change == "inverse 12161B (default) -> lt2: 1.9:1 off the page, now 8.0:1"


def test_a_default_inverse_on_a_light_page_is_left_unbound():
    assert rebound_inverse(DARK, {"ink": "dk1"}) is None


def test_nothing_is_rebound_when_no_slot_stands_off_the_page_either():
    grey = {"dk1": "777777", "dk2": "7A7A7A", "lt1": "858585", "lt2": "808080"}
    assert rebound_inverse(grey, {"page": "7F7F7F", "inverse": "dk1"}) is None
