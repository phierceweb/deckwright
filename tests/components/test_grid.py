"""What a successful `grid` build never reaches."""

import pytest

import deckwright.components  # noqa: F401 — registers the built-ins
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component
from deckwright.theme.model import Rect


def test_a_grid_in_a_placement_with_no_height_is_refused(ctx_factory):
    ctx = ctx_factory({"grid": {}})
    ctx.rect = Rect(ctx.rect.left, ctx.rect.top, ctx.rect.width, 0.0)
    with pytest.raises(
        LayoutError, match=r"the placement is 0\.00in tall, too short to draw a grid in"
    ):
        get_component("grid")(ctx)
