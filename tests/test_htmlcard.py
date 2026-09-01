"""Tests for the HTML window-card renderer."""

from __future__ import annotations

import pathlib
import re

from deckwright.services.htmlcard import markdown_card, window_card


def test_window_card_has_chrome_and_body():
    html = window_card("<p>hi</p>", filename="FOO.md", max_width=640)
    assert "<!doctype html>" in html
    assert 'class="dot r"' in html and 'class="dot g"' in html  # traffic lights
    assert ">FOO.md<" in html  # titlebar filename
    assert "max-width: 640px" in html
    assert "<p>hi</p>" in html


def test_window_card_body_class_and_extra_css():
    html = window_card("x", filename="f", extra_css=".content{color:red}", body_class="tree")
    assert 'class="tree"' in html
    assert ".content{color:red}" in html


def test_markdown_card_renders_markdown():
    html = markdown_card("# Title\n\nsome **bold** text", filename="DOC.md")
    assert "<h1>Title</h1>" in html
    assert "<strong>bold</strong>" in html
    assert ">DOC.md<" in html
    assert ".content h1" in html  # default typography present


def test_markdown_card_renders_fenced_code():
    html = markdown_card("```\ncode\n```", filename="s")
    assert "<pre>" in html


def test_the_card_paints_with_theme_colours(theme):
    import dataclasses

    from deckwright.panels.css import panel_css

    odd = dataclasses.replace(
        theme,
        palette=dataclasses.replace(
            theme.palette, roles={**theme.palette.roles, "muted": "AB12CD"}
        ),
    )
    html = markdown_card("# T\n\ntext\n", filename="d.md", content_css=panel_css(odd))
    assert "#AB12CD" in html


def test_a_card_without_a_theme_falls_back_to_its_own_literals(theme):
    """The fallbacks in var(--c-role, #hex) are what every themeless caller renders with."""
    from deckwright.panels.css import panel_css

    plain = markdown_card("# T\n\ntext\n", filename="d.md")
    themed = markdown_card("# T\n\ntext\n", filename="d.md", content_css=panel_css(theme))
    assert "var(--c-ink, #1f2328)" in plain
    assert plain == themed.replace(panel_css(theme), "")


def test_every_css_variable_the_card_reads_is_a_role_the_theme_declares():
    """A card styles itself from `panel_css`, which emits `--c-<role>` for the roles the palette
    really has. Ask for a name that is not one and CSS silently takes the fallback."""
    from deckwright.services import htmlcard
    from deckwright.theme.defaults import DEFAULT_ROLES

    source = pathlib.Path(htmlcard.__file__).read_text()
    used = set(re.findall(r"var\(--c-([a-z0-9-]+)", source))
    assert used, "no CSS variables found — the stylesheet shape changed"
    assert used <= set(DEFAULT_ROLES), (
        f"variables no palette declares: {sorted(used - set(DEFAULT_ROLES))}"
    )


def test_no_card_colour_is_a_palette_colour():
    """A fallback is what a card wears with no theme, so it has to be anonymous: none of the fixture
    palette's literals may reappear as a default."""
    from deckwright.services import htmlcard

    source = pathlib.Path(htmlcard.__file__).read_text()
    leaked = re.findall(r"(?i)#(?:2d0937|27b94c|18ceda|573c65|4db6ac|a78bd0)", source)
    assert leaked == [], f"palette colours hardcoded in a shipped stylesheet: {leaked}"


def test_the_render_canvas_is_never_themed():
    """`htmlshot._autocrop` crops by difference-from-white, so a `body` that takes a colour makes
    the whole 4000px canvas count as content and the card comes out canvas-height."""
    from deckwright.services import htmlcard

    source = pathlib.Path(htmlcard.__file__).read_text()
    body = re.search(r"^body \{[^}]*\}", source, re.S | re.M)
    assert body, "the body rule moved — this guard reads it by shape"
    assert "var(--c-" not in body.group(0), f"the canvas takes a theme colour: {body.group(0)}"
