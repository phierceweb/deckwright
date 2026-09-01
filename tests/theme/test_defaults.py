import re
import zipfile

import pytest

from deckwright.layouts.resolve import pick_compose_layout
from deckwright.theme import load_theme
from deckwright.theme.defaults import (
    DEFAULT_ACCENTS,
    DEFAULT_PAIRS,
    DEFAULT_PALETTE,
    DEFAULT_RAMP,
    blank_presentation,
    default_grid,
    default_ramp,
    default_theme,
)
from deckwright.theme.palette import AUTO_INK
from deckwright.theme.scale import Scale

_EMU_PER_INCH = 914400


def test_the_built_in_palette_defines_every_semantic_role():
    assert set(DEFAULT_PALETTE.roles) == {
        "page",
        "ink",
        "muted",
        "line",
        "surface",
        "surface-ink",
        "inverse",
        "inverse-ink",
        "accent-1",
        "accent-2",
        "accent-3",
        "accent-4",
    }


def test_every_built_in_pair_clears_wcag_aa():
    assert set(DEFAULT_PALETTE.pairs) == {
        "page",
        "page-muted",
        "surface",
        "inverse",
        "accent-1",
        "accent-2",
        "accent-3",
        "accent-4",
    }
    for name, pair in DEFAULT_PALETTE.pairs.items():
        assert pair.contrast() >= 4.5, f"pair {name!r} is only {pair.contrast():.2f}:1"


def test_accents_are_role_names_so_a_binding_can_repoint_them():
    assert DEFAULT_PALETTE.accents == DEFAULT_ACCENTS
    assert all(name in DEFAULT_PALETTE.roles for name in DEFAULT_PALETTE.accents)
    assert set(DEFAULT_ACCENTS) <= set(DEFAULT_PAIRS)


def test_a_pair_holds_no_stale_copy_of_a_role_it_names():
    """Pairs are built from role names, so a rebind cannot leave a hex behind."""
    for name, (fg, bg) in DEFAULT_PAIRS.items():
        pair = DEFAULT_PALETTE.pair(name)
        assert pair.bg == DEFAULT_PALETTE.role(bg)
        if fg != AUTO_INK:
            assert pair.fg == DEFAULT_PALETTE.role(fg)


def test_the_ramp_defines_a_rung_for_every_name_the_spec_may_use():
    assert set(DEFAULT_RAMP) == {
        "kicker",
        "caption",
        "body",
        "lead",
        "subtitle",
        "head",
        "title",
        "stat",
        "display",
        "hero",
    }


def test_body_type_is_sixteen_points_on_a_seven_and_a_half_inch_canvas():
    ramp = default_ramp(Scale(slide_w=13.333, slide_h=7.5))
    assert ramp["body"].size == pytest.approx(16.0, abs=0.1)


def test_a_caption_is_set_larger_than_a_kicker():
    """A kicker is bold and set in caps; a caption is neither, so one shared step left the
    caption the smaller of the two to read."""
    ramp = default_ramp(Scale(slide_w=13.333, slide_h=7.5))
    assert ramp["caption"].size > ramp["kicker"].size


def test_doubling_the_canvas_height_doubles_every_rung():
    small = default_ramp(Scale(slide_w=13.333, slide_h=7.5))
    large = default_ramp(Scale(slide_w=26.666, slide_h=15.0))
    for name, style in small.items():
        assert large[name].size == pytest.approx(style.size * 2), name


def test_the_display_rungs_ask_for_the_heading_face():
    ramp = default_ramp(Scale(slide_w=13.333, slide_h=7.5), heading_face="Georgia")
    assert ramp["title"].face == "Georgia"
    assert ramp["body"].face is None


def test_margins_stay_the_same_fraction_of_any_canvas():
    small = default_grid(Scale(slide_w=13.333, slide_h=7.5))
    large = default_grid(Scale(slide_w=26.666, slide_h=15.0))
    assert large.left / large.slide_w == pytest.approx(small.left / small.slide_w)
    assert large.top / large.slide_h == pytest.approx(small.top / small.slide_h)
    assert large.gutter / large.slide_w == pytest.approx(small.gutter / small.slide_w)
    assert large.col_w == pytest.approx(small.col_w * 2)


def test_the_blank_canvas_carries_no_slides_and_the_size_it_was_asked_for():
    prs = blank_presentation(slide_w=26.666, slide_h=15.0)
    assert len(prs.slides) == 0
    assert prs.slide_width / _EMU_PER_INCH == pytest.approx(26.666, abs=1e-3)
    assert prs.slide_height / _EMU_PER_INCH == pytest.approx(15.0, abs=1e-3)


def test_the_saved_canvas_declares_no_slide_size_type_to_contradict_its_dimensions(tmp_path):
    """python-pptx's stock template is 4:3 and its size setters leave `type` behind."""
    out = tmp_path / "canvas.pptx"
    blank_presentation().save(out)
    xml = zipfile.ZipFile(out).read("ppt/presentation.xml").decode()
    assert re.search(r"<p:sldSz[^/>]*/>", xml).group(0) == '<p:sldSz cx="12191695" cy="6858000"/>'


def test_a_four_by_three_canvas_is_not_stamped_sixteen_by_nine(tmp_path):
    """The canvas is the caller's, so no enumerated `type` can be hardcoded for it."""
    out = tmp_path / "narrow.pptx"
    blank_presentation(slide_w=10.0, slide_h=7.5).save(out)
    xml = zipfile.ZipFile(out).read("ppt/presentation.xml").decode()
    assert re.search(r"<p:sldSz[^/>]*/>", xml).group(0) == '<p:sldSz cx="9144000" cy="6858000"/>'


def test_the_blank_canvas_offers_a_layout_to_compose_on():
    """Nothing else in a template-free Presentation is safe to build a slide on."""
    assert pick_compose_layout(blank_presentation()).name == "Blank"


def test_a_theme_constructs_with_no_template_at_all():
    theme = default_theme()
    assert theme.template is None
    assert theme.grid.slide_w == pytest.approx(13.333, abs=1e-3)
    assert theme.palette.role("ink") == "1A1D21"


def test_the_caller_chooses_the_canvas():
    assert default_theme(slide_w=10.0, slide_h=7.5).grid.slide_w == pytest.approx(10.0, abs=1e-3)


def test_the_grid_measures_the_canvas_the_saved_file_will_really_hold():
    """Inches() rounds through EMU; the grid must agree with the file, not the argument."""
    assert default_theme().grid.slide_w == blank_presentation().slide_width / _EMU_PER_INCH


def test_the_minimum_is_resolved_points_not_a_rung():
    assert default_theme().min_pt == pytest.approx(10.5)


def test_no_rung_of_the_built_in_ramp_falls_below_the_built_in_minimum():
    theme = default_theme()
    for name, style in theme.ramp.items():
        assert style.size >= theme.min_pt, f"{name} is {style.size}pt"


def test_series_colours_cycle_the_accent_ramp_rather_than_six_stock_slots():
    assert default_theme().palette.accents == DEFAULT_PALETTE.accents


def test_the_built_in_identity_tracks_the_canvas():
    assert default_theme().hash == default_theme().hash
    assert default_theme().hash != default_theme(slide_w=26.666, slide_h=15.0).hash


def test_load_theme_with_no_path_yields_the_built_in_system():
    theme = load_theme()
    assert theme.name == "default"
    assert theme.template is None


def test_type_scales_with_the_canvas_height_when_the_theme_is_loaded():
    small = load_theme(slide_w=13.333, slide_h=7.5)
    large = load_theme(slide_w=26.666, slide_h=15.0)
    assert small.style("body").size == pytest.approx(16.0, abs=0.1)
    assert large.style("body").size == pytest.approx(small.style("body").size * 2)
    assert large.grid.left == pytest.approx(small.grid.left * 2)


def test_the_defaults_are_reachable_from_the_theme_package():
    from deckwright.theme import DEFAULT_ROLES as Exported
    from deckwright.theme import default_theme as exported_theme

    assert set(Exported) == set(DEFAULT_PALETTE.roles)
    assert exported_theme().name == "default"
