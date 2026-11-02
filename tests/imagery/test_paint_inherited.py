"""The page path: what a slide does with the background its template already paints. The
picture branch records that the template's art is showing, so the render check measures it."""

from __future__ import annotations

import dataclasses

from deckwright.imagery.paint import paint_inherited
from deckwright.theme.model import Rect
from deckwright.theme.surface import Surface


def _ctx_on(ctx_factory, theme, tmp_path, surface):
    """A ctx whose theme inherits ``surface`` from a template beside a real image."""
    template = tmp_path / "brand.pptx"
    template.write_bytes(b"")
    (tmp_path / "photo.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    )  # never opened: nothing samples it here
    return ctx_factory(
        {"title": "T"},
        theme_override=dataclasses.replace(theme, surface=surface, template=template),
    )


def test_a_slide_on_the_templates_own_picture_is_marked_for_the_render_check(
    ctx_factory, theme, tmp_path
):
    """The one line that carries M7 into a real build. Nothing else observes it: the
    picture is the template's, so no shape is drawn and no manifest row is written."""
    ctx = _ctx_on(ctx_factory, theme, tmp_path, Surface(media="photo.png"))

    paint_inherited(ctx, Rect(0.0, 0.0, ctx.grid.slide_w, ctx.grid.slide_h))

    assert ctx.manifest.slides[0].backdrop is True


def test_a_slide_on_a_flat_template_colour_is_not_marked(ctx_factory, theme, tmp_path):
    """The negative control: without it, marking every slide would pass the test above."""
    page = theme.palette.pair("page").bg
    ctx = _ctx_on(ctx_factory, theme, tmp_path, Surface(fills=(page,)))

    paint_inherited(ctx, Rect(0.0, 0.0, ctx.grid.slide_w, ctx.grid.slide_h))

    assert ctx.manifest.slides[0].backdrop is False
