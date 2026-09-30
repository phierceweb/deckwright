"""What a successful `code` build never reaches."""

import pytest

import deckwright.components  # noqa: F401 — registers the built-ins
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component


def test_a_wrap_that_is_no_boolean_is_refused(ctx_factory):
    """A quoted `"no"` is text, and every string is truthy: it would wrap the listing."""
    ctx = ctx_factory({"code": {"lines": ["x = 1"], "wrap": "no"}})
    with pytest.raises(LayoutError, match=r"'wrap' must be true or false, got 'no'"):
        get_component("code")(ctx)


@pytest.mark.parametrize(
    "body, match",
    [
        ({"lines": ["x"], "text": "x"}, r"give 'lines' or 'text', not both"),
        ({"lines": []}, r"needs 'lines' \(a list\) or 'text' \(a block scalar\)"),
        ({"lines": "x = 1"}, r"needs 'lines' \(a list\) or 'text' \(a block scalar\)"),
        ({"lines": ["x"], "size": "big"}, r"'size' is a point size, got 'big'"),
        ({"lines": ["x"], "size": 1}, r"'size' 1\.0pt is below the theme's \d+\.\dpt minimum"),
        (
            {"lines": [f"line {i}" for i in range(400)]},
            r"400 lines need \d+\.\d\din but only \d+\.\d\din is left",
        ),
    ],
)
def test_code_refuses_by_name(ctx_factory, body, match):
    ctx = ctx_factory({"code": body})
    with pytest.raises(LayoutError, match=match):
        get_component("code")(ctx)


def test_code_text_is_split_into_its_lines_without_a_trailing_blank(ctx_factory):
    """A block scalar ends in a newline; kept, it draws a fourth, empty line."""
    ctx = ctx_factory({"code": {"text": "a\nb\nc\n"}})
    get_component("code")(ctx)
    assert "a\nb\nc" in [s.text_frame.text for s in ctx.slide.shapes if s.has_text_frame]
