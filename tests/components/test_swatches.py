"""`swatches`: how many chips sit in a row, and where each row lands."""

import pytest

import deckwright.components  # noqa: F401 — registers the built-in components
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component

_FIVE = ["ink", "accent-1", "accent-2", "muted", "line"]


def _chips(ctx):
    """Each chip's recorded left, top and width: the only records carrying no text."""
    return [(r.box.x, r.box.y, r.box.w) for r in ctx.manifest.slides[0].shapes if r.text is None]


def test_columns_sets_how_many_chips_share_a_row(ctx_factory):
    """Three across the fixture's 12.10in rect, 0.18in apart, is 3.91in a chip; the fourth
    starts a row 1.84in down — chip, label gap, label and gutter."""
    ctx = ctx_factory({"swatches": {"roles": _FIVE, "columns": 3}})
    get_component("swatches")(ctx)
    assert _chips(ctx) == [
        (0.62, 1.7, 3.914),
        (4.714, 1.7, 3.914),
        (8.809, 1.7, 3.914),
        (0.62, 3.538, 3.914),
        (4.714, 3.538, 3.914),
    ]


def test_more_columns_than_roles_gives_each_role_its_share_of_the_row(ctx_factory):
    ctx = ctx_factory({"swatches": {"roles": ["ink", "line"], "columns": 6}})
    get_component("swatches")(ctx)
    assert _chips(ctx) == [(0.62, 1.7, 5.961), (6.761, 1.7, 5.961)]


@pytest.mark.parametrize("value", ["3", 2.5, True])
def test_a_columns_that_is_not_a_whole_number_is_refused(ctx_factory, value):
    ctx = ctx_factory({"swatches": {"roles": _FIVE, "columns": value}})
    with pytest.raises(
        LayoutError,
        match=r"slide 1 \(component 'swatches'\): 'columns' is how many chips sit in a "
        r"row, so it must be a whole number",
    ):
        get_component("swatches")(ctx)


@pytest.mark.parametrize("value", [0, 9])
def test_a_columns_outside_one_to_eight_is_refused(ctx_factory, value):
    ctx = ctx_factory({"swatches": {"roles": _FIVE, "columns": value}})
    with pytest.raises(LayoutError, match=rf"'columns' is {value}; it must be between 1 and 8"):
        get_component("swatches")(ctx)
