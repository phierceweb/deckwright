import logging

import pytest

from deckwright.errors import ThemeError
from deckwright.theme.palette import AUTO_INK, Pair, Palette, build_palette

_ROLES = {
    "page": "FFFFFF",
    "ink": "111111",
    "muted": "5A5A5A",
    "inverse": "2D0937",
    "inverse-ink": "FFFFFF",
    "accent-1": "FB0304",
}


def _palette(**overrides):
    kwargs = {
        "roles": dict(_ROLES),
        "pairs": {"page": Pair("111111", "FFFFFF"), "inverse": Pair("FFFFFF", "2D0937")},
        "accents": ("accent-1",),
    }
    kwargs.update(overrides)
    return Palette(**kwargs)


def _channels(hex_colour):
    return tuple(int(hex_colour[i : i + 2], 16) for i in (0, 2, 4))


# --- Pair -------------------------------------------------------------------


def test_a_pair_normalizes_both_hexes():
    pair = Pair("#27b94c", "ffffff")
    assert (pair.fg, pair.bg) == ("27B94C", "FFFFFF")


def test_a_pair_reports_its_wcag_ratio():
    assert Pair("000000", "FFFFFF").contrast() == pytest.approx(21.0, abs=0.01)


# --- roles ------------------------------------------------------------------


def test_a_declared_role_resolves_to_its_hex():
    assert _palette().role("accent-1") == "FB0304"


def test_role_hexes_are_normalized_at_construction():
    assert _palette(roles={"page": "#ffffff"}, pairs={}, accents=()).role("page") == "FFFFFF"


def test_an_undeclared_role_is_rejected_and_lists_what_is_declared():
    with pytest.raises(ThemeError, match="no colour role 'brand-red'"):
        _palette().role("brand-red")


# --- pairs ------------------------------------------------------------------


def test_a_declared_pair_resolves():
    assert _palette().pair("inverse") == Pair("FFFFFF", "2D0937")


def test_an_undeclared_pair_is_rejected():
    with pytest.raises(ThemeError, match="no colour pair 'surface'"):
        _palette().pair("surface")


def test_a_pair_below_aa_is_built_and_reported(caplog):
    """Built, not refused: `deckwright qa` decides this against what was really painted, and
    refusing here as well would make a brand's own palette unloadable over a weaker check."""
    with caplog.at_level(logging.WARNING):
        palette = _palette(pairs={"page": Pair("CCCCCC", "FFFFFF")})
    assert palette.pair("page").fg == "CCCCCC"
    assert "theme_pair_below_aa" in caplog.text


def test_a_pair_just_over_aa_is_accepted():
    pair = Pair("767676", "FFFFFF")
    assert pair.contrast() >= 4.5
    assert _palette(pairs={"page": pair}).pair("page") is pair


# --- accents ----------------------------------------------------------------


def test_an_accent_naming_an_undeclared_role_is_rejected():
    with pytest.raises(ThemeError, match="accent 'accent-9' names no declared colour role"):
        _palette(accents=("accent-1", "accent-9"))


def test_build_palette_orders_accents_numerically_not_lexically():
    roles = dict(_ROLES, **{"accent-2": "0F6E3F", "accent-10": "123456"})
    palette = build_palette(roles, pairs={"page": ("ink", "page")})
    assert palette.accents == ("accent-1", "accent-2", "accent-10")


def test_build_palette_binds_no_accent_when_no_role_names_one():
    palette = build_palette({"page": "FFFFFF", "ink": "111111"}, pairs={})
    assert palette.accents == ()


def test_a_pair_names_roles_so_rebinding_one_moves_the_pair():
    """Hex in a pair would drift from the role it copied the moment a bind changed it."""
    light = build_palette(dict(_ROLES), pairs={"page": ("ink", "page")})
    assert light.pair("page") == Pair("111111", "FFFFFF")

    dark = build_palette(dict(_ROLES, ink="2D0937"), pairs={"page": ("ink", "page")})
    assert dark.pair("page") == Pair("2D0937", "FFFFFF")


def test_a_pair_naming_an_undeclared_role_is_rejected():
    with pytest.raises(ThemeError, match="colour pair 'page' names unknown role 'inkk'"):
        build_palette(dict(_ROLES), pairs={"page": ("inkk", "page")})


def test_build_palette_keeps_an_unreadable_pair_rather_than_dropping_it(caplog):
    with caplog.at_level(logging.WARNING):
        palette = build_palette(dict(_ROLES, faint="CCCCCC"), pairs={"page": ("faint", "page")})
    assert palette.pair("page").fg == "CCCCCC"
    assert "theme_pair_below_aa" in caplog.text


# --- automatic ink ----------------------------------------------------------


def _auto(brand: str, **roles):
    """A palette whose only pair is ``brand`` on itself, foreground chosen for it."""
    return build_palette(dict(_ROLES, brand=brand, **roles), pairs={"brand": (AUTO_INK, "brand")})


def test_an_auto_pair_takes_page_when_ink_cannot_be_read_on_the_background():
    # ink 111111 on 1F5FA8 is 2.93:1; page FFFFFF is 6.44:1.
    assert _auto("1F5FA8").pair("brand") == Pair("FFFFFF", "1F5FA8")


def test_an_auto_pair_takes_ink_when_page_cannot_be_read_on_the_background():
    """A fixed white accent-ink would make a light brand accent fail to load at all."""
    # page FFFFFF on FFC000 is 1.64:1; ink 111111 is 11.50:1.
    assert _auto("FFC000").pair("brand") == Pair("111111", "FFC000")


def test_an_auto_pair_takes_the_better_of_the_two_when_both_clear_aa():
    # On C0504D, ink 000000 is 4.50:1 and page FFFFFF is 4.67:1 — both pass.
    assert _auto("C0504D", ink="000000").pair("brand").fg == "FFFFFF"


def test_a_midtone_takes_the_best_declared_ink_even_when_none_clears(caplog):
    """On 7A7A7A the theme's inks reach 4.40:1 and 4.29:1. The better one is still chosen —
    a brand's ink is never invented here, and the shortfall is reported instead."""
    with caplog.at_level(logging.WARNING):
        palette = _auto("7A7A7A")
    assert palette.pair("brand").fg == "111111"
    assert "theme_pair_below_aa" in caplog.text


def test_the_fallback_is_a_last_resort_and_not_a_preference():
    """A declared ink that clears must still win, or every pair drifts to black and white."""
    # On C0504D both declared inks clear, so neither literal is consulted.
    assert _auto("C0504D", ink="000000").pair("brand").fg == "FFFFFF"


def test_a_midtone_background_still_resolves_as_a_role():
    """The pair resolving must not change what the colour itself is."""
    assert _auto("7A7A7A").role("brand") == "7A7A7A"


def test_an_auto_pair_naming_an_undeclared_background_is_rejected():
    with pytest.raises(ThemeError, match="colour pair 'brand' names unknown role 'nope'"):
        build_palette(dict(_ROLES), pairs={"brand": (AUTO_INK, "nope")})


# --- luminance transforms ---------------------------------------------------


def test_shade_matches_the_ooxml_lummod_a_real_deck_paints():
    # A brand red painted as accent1 FB0304 under lumMod 75%.
    got, want = _channels(_palette().shade("accent-1", 25)), _channels("BC0203")
    assert all(abs(a - b) <= 1 for a, b in zip(got, want, strict=True)), got


def test_shade_at_zero_is_the_role_itself():
    assert _palette().shade("accent-1", 0) == "FB0304"


def test_shade_at_a_hundred_is_black():
    assert _palette().shade("accent-1", 100) == "000000"


def test_tint_at_zero_is_the_role_itself():
    assert _palette().tint("accent-1", 0) == "FB0304"


def test_tint_at_a_hundred_is_white():
    assert _palette().tint("ink", 100) == "FFFFFF"


def test_tint_lightens_and_shade_darkens_the_same_role():
    palette = _palette()
    assert _channels(palette.tint("muted", 40)) > _channels("5A5A5A")
    assert _channels(palette.shade("muted", 40)) < _channels("5A5A5A")


def test_tint_lifts_black_where_shade_cannot_move_it():
    palette = _palette(roles={"ink": "000000"}, pairs={}, accents=())
    assert palette.tint("ink", 40) == "666666"
    assert palette.shade("ink", 40) == "000000"


def test_a_percentage_outside_zero_to_a_hundred_is_rejected():
    with pytest.raises(ThemeError, match=r"tint percentage must be in 0\.\.100"):
        _palette().tint("accent-1", 101)
    with pytest.raises(ThemeError, match=r"shade percentage must be in 0\.\.100"):
        _palette().shade("accent-1", -1)


def test_a_transform_rejects_an_undeclared_role():
    with pytest.raises(ThemeError, match="no colour role 'nope'"):
        _palette().tint("nope", 75)


def _grounds(page, inverse):
    roles = {**_ROLES, "page": page, "inverse": inverse}
    return _palette(roles=roles, pairs={})


@pytest.mark.parametrize(
    ("page", "inverse"),
    [("1E2A3A", "1E2A3A"), ("2F7FBF", "44546A")],
    ids=["identical", "1.80"],
)
def test_an_inverse_the_page_swallows_is_reported(caplog, page, inverse):
    """A kept theme holds its binding until its template is re-adopted, so load says so."""
    with caplog.at_level(logging.WARNING):
        _grounds(page, inverse)
    assert "theme_inverse_matches_page" in caplog.text


@pytest.mark.parametrize(
    ("page", "inverse"),
    [("7E48A8", "000000"), ("FFFFFF", "2D0937")],
    ids=["3.38", "light-page"],
)
def test_an_inverse_that_stands_off_the_page_is_not_reported(caplog, page, inverse):
    """3.38:1 is a visible plate; the warning is for one that vanishes, not one below AA."""
    with caplog.at_level(logging.WARNING):
        _grounds(page, inverse)
    assert "theme_inverse_matches_page" not in caplog.text


def test_a_palette_without_an_inverse_role_is_not_checked_for_one(caplog):
    roles = {k: v for k, v in _ROLES.items() if k != "inverse"}
    with caplog.at_level(logging.WARNING):
        _palette(roles=roles, pairs={})
    assert "theme_inverse_matches_page" not in caplog.text
