"""The fill every chart mark resolves to, against real palettes' literal colours."""

from __future__ import annotations

from deckwright.charts.fills import chart_fills
from deckwright.charts.model import ChartSpec, Series
from deckwright.theme.defaults import DEFAULT_PAIRS
from deckwright.theme.palette import Palette, build_palette
from deckwright.utils.color import contrast_ratio, delta_e, stands_off

_ACCENTS = ("accent-1", "accent-2", "accent-3", "accent-4")


def _base(*accents: str) -> Palette:
    """The built-in theme's roles, written out rather than loaded, under these accents."""
    return build_palette(
        {
            "page": "FFFFFF",
            "ink": "1A1D21",
            "muted": "5F6672",
            "line": "E3E6EA",
            "surface": "F2F4F7",
            "surface-ink": "1A1D21",
            "inverse": "12161B",
            "inverse-ink": "FFFFFF",
            **dict(zip(_ACCENTS, accents, strict=True)),
        },
        pairs=DEFAULT_PAIRS,
    )


BASE = _base("1F5FA8", "0F6E63", "A8431C", "6A3FA0")
# Pale accents on a dark green page.
DARK_GROUND = build_palette(
    {
        "page": "1D4D44",
        "ink": "FFFFFF",
        "muted": "B0C1BE",
        "line": "E3E6EA",
        "surface": "2E796B",
        "surface-ink": "FFFFFF",
        "inverse": "FFFFFF",
        "inverse-ink": "273D40",
        **dict(zip(_ACCENTS, ("F9CB9C", "FFE599", "B6D7A8", "A4C2F4"), strict=True)),
    },
    pairs=DEFAULT_PAIRS,
)


def _fills(spec: ChartSpec, palette: Palette = BASE):
    return chart_fills(
        spec,
        accents=tuple(palette.role(name) for name in palette.accents),
        muted=palette.role("muted"),
        ground=palette.role("page"),
        legible=palette.has_ink_for,
    )


def _pie(count: int, highlight: int | None = None) -> ChartSpec:
    return ChartSpec(
        type="pie",
        categories=tuple("ABCDEFG"[:count]),
        series=(Series(name="", values=tuple(float(10 + i) for i in range(count))),),
        highlight=highlight,
    )


def _two_series(highlight: int) -> ChartSpec:
    return ChartSpec(
        type="column-stacked",
        categories=("Q1", "Q2", "Q3", "Q4"),
        series=(
            Series(name="North", values=(12.0, 18.0, 22.0, 30.0)),
            Series(name="South", values=(10.0, 14.0, 19.0, 21.0)),
        ),
        highlight=highlight,
    )


def test_a_pie_with_more_wedges_than_accents_keeps_its_last_wedge_off_the_first():
    assert _fills(_pie(5)).points == (("1F5FA8", "0F6E63", "A8431C", "6A3FA0", "0F6E63"),)


def test_a_highlighted_pie_isolates_its_wedge_among_fades_of_itself_that_never_touch_alike():
    assert _fills(_pie(5, highlight=1)).points == (
        ("8FAFD4", "1F5FA8", "5787BE", "8FAFD4", "5787BE"),
    )


# A mid-tone page and a near-black first accent: fading halfway toward the page, as
# `_RECEDE` alone would, lands too close to the page to tell the fill apart from it.
MID_PAGE_DARK_ACCENT = build_palette(
    {
        "page": "3282BE",
        "ink": "000000",
        "muted": "050D13",
        "surface": "5A9FD3",
        "surface-ink": "000000",
        "inverse": "000000",
        "inverse-ink": "FFFFFF",
        **dict(zip(_ACCENTS, ("262626", "28608C", "262626", "262626"), strict=True)),
    },
    pairs=DEFAULT_PAIRS,
)


def test_a_highlighted_pie_on_a_mid_tone_page_still_lets_its_wedge_stand_out():
    fills = _fills(_pie(5, highlight=1), MID_PAGE_DARK_ACCENT)
    assert fills.points == (("2A4254", "262626", "28343D", "2A4254", "28343D"),)

    ground = MID_PAGE_DARK_ACCENT.role("page")
    marked = fills.points[0][1]
    quiet = set(fills.points[0]) - {marked}
    assert len(quiet) == 2  # touching wedges never repeat the same level
    for fade in quiet:
        assert stands_off(fade, ground)
        assert contrast_ratio(fade, ground) < contrast_ratio(marked, ground)
        assert delta_e(fade, ground) < delta_e(marked, ground)


def test_a_multi_series_highlight_keeps_its_row_and_fades_every_other_toward_the_ground():
    fills = _fills(_two_series(highlight=3))
    assert fills.series == ("1F5FA8", "0F6E63")
    assert fills.points == (
        ("8FAFD4", "8FAFD4", "8FAFD4", "1F5FA8"),
        ("87B6B1", "87B6B1", "87B6B1", "0F6E63"),
    )


def test_on_a_dark_ground_a_faded_mark_goes_on_until_an_ink_reads_on_it():
    """Halfway between a pale accent and a dark page is a mid-tone no declared ink reads on."""
    fills = _fills(_two_series(highlight=3), DARK_GROUND)
    assert fills.points == (
        ("6A7963", "6A7963", "6A7963", "F9CB9C"),
        ("617B5E", "617B5E", "617B5E", "FFE599"),
    )
    pie = _fills(_pie(3, highlight=0), DARK_GROUND)
    assert pie.points == (("F9CB9C", "D8B88F", "B7A582"),)


# Every step from 0.50 to 0.80 toward the ground lands on a mid-tone `has_ink_for` refuses;
# only fading on to 0.90 finds one it accepts. The old, shorter `_RECEDE` stopped at 0.80
# regardless and returned that mid-tone anyway.
DEAD_ZONE = build_palette(
    {
        "page": "FFFFFF",
        "ink": "646464",
        "muted": "080808",
        **dict(zip(_ACCENTS, ("080808",) * 4, strict=True)),
    },
    pairs={"page": ("ink", "page")},
)


def test_a_fade_stuck_below_the_old_cap_keeps_going_until_legible():
    """No fade at 0.05 steps from 0.50 through 0.80 clears AA here, so a cap stopping at
    0.80 falls back to that unread mid-tone; fading on to 0.90 is the first one that reads."""
    fills = _fills(_two_series(highlight=3), DEAD_ZONE)
    assert fills.points == (
        ("E6E6E6", "E6E6E6", "E6E6E6", "080808"),
        ("E6E6E6", "E6E6E6", "E6E6E6", "080808"),
    )
    assert fills.points[0][0] != "CECECE"


# A theme's `muted` role is vetted against its own pair, never against a highlighted
# chart's label ink — so it can itself land in a mid-tone no ink reads on.
MUTED_UNREAD = build_palette({**BASE.roles, "muted": "7A7A7A"}, pairs=DEFAULT_PAIRS)


def test_a_grey_that_is_not_itself_legible_fades_before_it_is_used():
    """A single series mutes the rest to `muted` outright, which may not hand it out unread."""
    single = _fills(
        ChartSpec(
            type="column",
            categories=("Q1", "Q2", "Q3", "Q4"),
            series=(Series(name="Only", values=(12.0, 18.0, 22.0, 30.0)),),
            highlight=3,
        ),
        MUTED_UNREAD,
    )
    assert single.points == (("BCBCBC", "BCBCBC", "BCBCBC", "1F5FA8"),)


def test_a_pie_never_reads_the_muted_role_at_all():
    """A pie's quiet wedges fade the marked wedge's own accent, not `muted` — so a theme
    whose `muted` role is itself unread against its ground cannot affect a pie's isolation."""
    assert (
        _fills(_pie(5, highlight=1), MUTED_UNREAD).points
        == _fills(_pie(5, highlight=1), BASE).points
    )


def test_two_accent_roles_bound_to_one_colour_count_once_round_the_ring():
    """A derived theme can bind one brand colour to several accent slots; cycling the roles
    would put that colour on two touching wedges."""
    palette = _base("1F5FA8", "1F5FA8", "0F6E63", "A8431C")
    assert _fills(_pie(5), palette).points == (("1F5FA8", "0F6E63", "A8431C", "1F5FA8", "0F6E63"),)


def test_an_odd_pie_on_two_accents_closes_its_ring_on_a_tint_clear_of_both_neighbours():
    """Two colours alternate, so a third wedge would meet the first in the same one."""
    palette = _base("1F5FA8", "0F6E63", "1F5FA8", "0F6E63")
    assert _fills(_pie(3), palette).points == (("1F5FA8", "0F6E63", "8FAFD4"),)


def test_one_accent_goes_round_with_a_tint_and_closes_on_a_shade_clear_of_both():
    """The tint the second wedge takes is the first fade the third tries, and it touches it."""
    palette = _base("A8431C", "A8431C", "A8431C", "A8431C")
    assert _fills(_pie(3), palette).points == (("A8431C", "D4A18E", "4C1E0D"),)
