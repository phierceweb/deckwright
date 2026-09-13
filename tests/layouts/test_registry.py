import dataclasses
import textwrap

import pytest

from deckwright.errors import LayoutError, ThemeError
from deckwright.theme.defaults import DEFAULT_PALETTE
from deckwright.layouts.components import registered_components
from deckwright.layouts.registry import SlideCtx, load_extension
from deckwright.spec.model import Background, SlideSpec
from deckwright.theme.media import resolve_media
from deckwright.theme.model import Rect
from deckwright.utils.color import AA_LARGE, AA_NORMAL, contrast_ratio
from deckwright.utils.shapes import ALIGN, ANCHOR


def _ctx(theme, *, spec=None, **over):
    return SlideCtx(
        slide=object(), theme=theme, spec=spec or SlideSpec(index=1), manifest=None, **over
    )


def test_an_extension_module_registers_its_components(tmp_path):
    mod = tmp_path / "custom.py"
    mod.write_text(
        textwrap.dedent("""
        from deckwright.layouts.components import component

        @component("t-from-extension")
        def custom(ctx):
            return []
    """)
    )
    load_extension(mod)
    assert "t-from-extension" in registered_components()


def test_missing_extension_file_is_rejected(tmp_path):
    with pytest.raises(LayoutError, match="extension module not found"):
        load_extension(tmp_path / "absent.py")


def test_extension_that_fails_to_import_is_reported(tmp_path):
    mod = tmp_path / "broken.py"
    mod.write_text("this is not python(\n")
    with pytest.raises(LayoutError, match="failed to import"):
        load_extension(mod)


def test_loading_the_same_extension_twice_is_a_no_op(tmp_path):
    mod = tmp_path / "idempotent.py"
    mod.write_text(
        textwrap.dedent("""
        from deckwright.layouts.components import component

        @component("t-idempotent")
        def custom(ctx):
            return []
    """)
    )
    load_extension(mod)
    load_extension(mod)  # would raise "already registered" without the idempotency guard
    assert "t-idempotent" in registered_components()


def test_loading_two_different_extensions_both_register(tmp_path):
    for name in ("a", "b"):
        mod = tmp_path / f"ext_{name}.py"
        mod.write_text(
            textwrap.dedent(f"""
            from deckwright.layouts.components import component

            @component("t-ext-{name}")
            def custom(ctx):
                return []
        """)
        )
        load_extension(mod)
    assert {"t-ext-a", "t-ext-b"} <= set(registered_components())


def test_ctx_resolves_a_colour_role(theme):
    assert str(_ctx(theme).color("ink")) == theme.palette.role("ink")


def test_ctx_resolves_a_type_rung(theme):
    assert _ctx(theme).style("title").size == theme.ramp["title"].size


def test_unknown_colour_role_raises_from_the_theme(theme):
    with pytest.raises(ThemeError, match="no colour role"):
        _ctx(theme).color("nonesuch")


def test_ctx_sections_defaults_to_empty_and_is_assignable(theme):
    ctx = _ctx(theme)
    assert ctx.sections == ()
    ctx.sections = ("One", "Two")
    assert ctx.sections == ("One", "Two")


def test_a_ctx_outside_a_placement_carries_no_component(theme):
    ctx = _ctx(theme)
    assert ctx.component is None and ctx.body == {} and ctx.placements == {}


def test_body_rect_is_the_placement_rect_when_one_is_set(theme):
    rect = Rect(1.0, 2.0, 3.0, 4.0)
    assert _ctx(theme, rect=rect).body_rect is rect


def test_body_rect_outside_a_placement_is_an_error_naming_the_slide(theme):
    """A component only ever runs inside a placement; a missing rect is a compiler bug."""
    with pytest.raises(LayoutError, match="slide 1: no placement rect is set"):
        _ = _ctx(theme).body_rect


def test_an_image_beside_the_deck_spec_is_found_though_the_template_lacks_it(
    theme, synthetic_template, tmp_path
):
    """This template holds no media, so the photograph resolves only via the deck's own directory
    — deliberately not the template's, or an empty ``media_roots`` would find it anyway."""
    deck_dir = tmp_path / "deck"
    deck_dir.mkdir()
    photo = deck_dir / "photo.png"
    photo.write_bytes(b"not-really-a-png")
    themed = dataclasses.replace(theme, template=synthetic_template)
    ctx = _ctx(themed, base=deck_dir)

    found = resolve_media("photo.png", template=themed.template, roots=ctx.media_roots)

    assert found == photo


def test_a_rect_hanging_off_a_panel_is_measured_against_whichever_half_reads_worse(theme):
    """A line crossing a panel edge sits on two surfaces, and both single answers are wrong in
    opposite directions — so the worse of the two rejects both."""
    ctx = _ctx(theme, painted=[(Rect(0.0, 0.0, 6.0, 4.0), "2D0937")])

    contained = Rect(1.0, 1.0, 2.0, 0.5)
    over_the_right_edge = Rect(1.0, 1.0, 8.0, 0.5)
    over_the_bottom_edge = Rect(1.0, 1.0, 2.0, 5.0)

    # Wholly on the panel: the page beneath it is not a surface this line ever touches.
    assert ctx.behind(contained, ink="FFFFFF") == "2D0937"
    assert ctx.behind(contained, ink="000000") == "2D0937"

    for straddling in (over_the_right_edge, over_the_bottom_edge):
        assert ctx.behind(straddling, ink="FFFFFF") == "FFFFFF"  # white is lost on the page
        assert ctx.behind(straddling, ink="000000") == "2D0937"  # black is lost on the panel


def test_the_live_pair_follows_the_slides_background(theme):
    inverse = SlideSpec(index=1, background=Background(kind="inverse"))
    assert _ctx(theme, spec=inverse).pair == theme.palette.pair("inverse")
    assert _ctx(theme).pair == theme.palette.pair("page")


def test_ink_and_paper_come_from_the_one_live_pair(theme):
    ctx = _ctx(theme, spec=SlideSpec(index=1, background=Background(kind="inverse")))
    pair = theme.palette.pair("inverse")
    assert (str(ctx.fg()), str(ctx.paper())) == (pair.fg, pair.bg)


def test_secondary_text_is_muted_on_the_page_and_the_pairs_ink_elsewhere(theme):
    assert str(_ctx(theme).dim()) == theme.palette.role("muted")
    inverse = SlideSpec(index=1, background=Background(kind="inverse"))
    assert str(_ctx(theme, spec=inverse).dim()) == theme.palette.pair("inverse").fg


def test_an_accent_that_cannot_be_read_on_a_dark_slide_becomes_that_slides_ink(theme):
    themed = dataclasses.replace(theme, palette=DEFAULT_PALETTE)
    inverse = SlideSpec(index=1, background=Background(kind="inverse"))
    assert _ctx(themed, spec=inverse).accent(size_pt=24) == DEFAULT_PALETTE.pair("inverse").fg


def test_an_accent_the_page_cannot_carry_gives_way_to_the_pages_ink(theme):
    """An accent can be a fill and still fail as text; the page's ink takes over."""
    accent = theme.palette.role("accent-1")
    assert contrast_ratio(accent, theme.palette.pair("page").bg) < AA_LARGE
    assert _ctx(theme).accent(size_pt=24) == theme.palette.pair("page").fg


def test_the_ratio_an_accent_must_clear_falls_with_the_type_size(theme):
    """A 24pt accent that clears the large-text bar is refused at body size."""
    dark = dataclasses.replace(theme, palette=DEFAULT_PALETTE)
    inverse = SlideSpec(index=1, background=Background(kind="inverse"))
    ctx = _ctx(dark, spec=inverse)
    ratio = contrast_ratio(DEFAULT_PALETTE.role("accent-3"), DEFAULT_PALETTE.pair("inverse").bg)
    assert AA_LARGE <= ratio < AA_NORMAL
    assert ctx.accent(size_pt=24, name="accent-3") == DEFAULT_PALETTE.role("accent-3")
    assert ctx.accent(size_pt=12, name="accent-3") == DEFAULT_PALETTE.pair("inverse").fg


def test_an_accent_measured_against_a_tile_not_the_slide_gives_way_on_the_tile(theme):
    inverse = SlideSpec(index=1, background=Background(kind="inverse"))
    ctx = _ctx(theme, spec=inverse)
    tile = theme.palette.role("line")
    assert ctx.accent(size_pt=30) == theme.palette.role("accent-1")
    assert ctx.accent_on(tile, size_pt=30) == ctx.ink_on(tile)


def test_a_placements_align_and_anchor_reach_the_drawing_helpers(theme):
    ctx = _ctx(theme, align="center", anchor="bottom")
    assert (ctx.text_align(), ctx.text_anchor()) == (ALIGN["center"], ANCHOR["bottom"])


def test_a_placement_aligns_left_from_the_top_unless_it_says_otherwise(theme):
    ctx = _ctx(theme)
    assert (ctx.text_align(), ctx.text_anchor()) == (ALIGN["left"], ANCHOR["top"])


def test_an_accent_gives_way_to_the_ink_where_it_cannot_be_read(ctx_factory, theme):
    """Named colours, not a re-run of contrast_ratio: asking the code under test
    whether the code is right passes however the selection behaves."""
    import dataclasses

    from deckwright.theme.palette import build_palette

    # accent-1 is a mid turquoise: 1.9:1 on white, 9.0:1 on near-black.
    palette = build_palette(
        {
            "page": "FFFFFF",
            "ink": "2D0937",
            "muted": "5A5A5A",
            "line": "EDEDED",
            "surface": "F2F4F7",
            "surface-ink": "2D0937",
            "inverse": "2D0937",
            "inverse-ink": "FFFFFF",
            "accent-1": "18CEDA",
        },
        pairs={
            "page": ("ink", "page"),
            "surface": ("surface-ink", "surface"),
            "inverse": ("inverse-ink", "inverse"),
        },
    )
    ctx = ctx_factory({"title": "T"}, theme_override=dataclasses.replace(theme, palette=palette))

    assert ctx.accent_on("FFFFFF", size_pt=12) == "2D0937"  # unreadable -> the ink
    assert ctx.accent_on("2D0937", size_pt=12) == "18CEDA"  # readable -> the accent


class _Picture:
    """A backdrop reading one flat colour: ordering is under test, not pixel sampling."""

    def __init__(self, colour):
        self.colour = colour

    def behind(self, rect, *, ink):
        return self.colour


def test_a_picture_laid_over_a_panel_is_what_text_on_that_rect_sits_on(theme):
    """Paint order decides what shows, not whether the surface is a fill or a picture."""
    rect = Rect(1.0, 1.0, 2.0, 0.5)
    whole = Rect(0.0, 0.0, 6.0, 4.0)
    ctx = _ctx(theme, painted=[(whole, "12161B"), (whole, _Picture("FFFFFF"))])
    assert ctx.behind(rect, ink="FFFFFF") == "FFFFFF"


def test_a_panel_laid_over_a_picture_is_what_text_on_that_rect_sits_on(theme):
    rect = Rect(1.0, 1.0, 2.0, 0.5)
    whole = Rect(0.0, 0.0, 6.0, 4.0)
    ctx = _ctx(theme, painted=[(whole, _Picture("FFFFFF")), (whole, "12161B")])
    assert ctx.behind(rect, ink="FFFFFF") == "12161B"
