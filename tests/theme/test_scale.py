import textwrap
from pathlib import Path

import pytest
import yaml

from deckwright.errors import ThemeError
from deckwright.theme import Grid, Scale, blocks, load_theme
from deckwright.theme.defaults import DEFAULT_RAMP, default_grid

import deckwright.theme as _theme_pkg

_SHIPPED = Path(_theme_pkg.__file__).parent / "builtin" / "base.yaml"


def test_a_fraction_of_the_width_resolves_to_inches():
    assert Scale(13.333, 7.5).x(0.5) == pytest.approx(6.6665)


def test_a_fraction_of_the_height_resolves_to_inches():
    assert Scale(13.333, 7.5).y(0.2) == pytest.approx(1.5)


def test_a_rung_resolves_to_points_per_inch_of_height():
    assert Scale(13.333, 7.5).pt(1.8) == pytest.approx(13.5)


def test_the_same_rung_is_bigger_on_a_taller_canvas():
    assert Scale(26.666, 15.0).pt(1.8) == pytest.approx(2 * Scale(13.333, 7.5).pt(1.8))


def test_width_does_not_move_a_rung():
    """Height is the normalizer: a 4:3 and a 16:9 deck of the same height take the same type."""
    assert Scale(10.0, 7.5).pt(1.8) == pytest.approx(Scale(13.333, 7.5).pt(1.8))


def test_a_zero_width_canvas_is_rejected():
    with pytest.raises(ThemeError, match="slide size must be positive"):
        Scale(0.0, 7.5)


def test_a_negative_height_canvas_is_rejected():
    with pytest.raises(ThemeError, match="slide size must be positive"):
        Scale(13.333, -7.5)


SCALE = Scale(13.333, 7.5)


def _shipped_yaml() -> dict:
    """The shipped theme, read as data rather than loaded — no template is opened."""
    return yaml.safe_load(_SHIPPED.read_text())


def _shipped_grid_kwargs() -> dict:
    """The shipped theme's own grid, parsed through ``blocks.grid`` rather than hand-fed from the
    YAML: the file states percents, and reading them raw would measure a theme nobody has."""
    grid = blocks.grid(_shipped_yaml()["scale"], SCALE)
    return dict(
        scale=SCALE,
        top_frac=grid.top_frac,
        right_frac=grid.right_frac,
        bottom_frac=grid.bottom_frac,
        left_frac=grid.left_frac,
        columns=grid.columns,
        rows=grid.rows,
        gutter_frac=grid.gutter_frac,
        body_top_frac=grid.body_top_frac,
    )


SHIPPED = _shipped_grid_kwargs()


def test_the_shipped_theme_sets_its_caption_larger_than_its_kicker():
    """base.yaml states its own ramp, so DEFAULT_RAMP's step never reaches it — the rung
    has to be raised in both places or no deck on `base` moves."""
    ramp = _shipped_yaml()["type"]["ramp"]
    assert ramp["caption"]["pt"] > ramp["kicker"]["pt"]


def test_the_shipped_fractions_still_land_on_their_inch_geometry():
    g = Grid(**SHIPPED)
    assert (g.top, g.right, g.bottom, g.left, g.gutter, g.body_top) == pytest.approx(
        (0.375, 0.80, 0.45, 0.80, 0.20, 1.65), abs=1e-3
    )


def test_the_grid_reports_the_canvas_it_resolves_against():
    g = Grid(**SHIPPED)
    assert (g.slide_w, g.slide_h) == pytest.approx((13.333, 7.5))


def test_content_width_is_slide_minus_margins():
    g = Grid(**SHIPPED)
    assert g.content_w == pytest.approx(13.333 - 0.80 - 0.80, abs=1e-3)


def test_column_width_accounts_for_gutters():
    g = Grid(**SHIPPED)
    assert g.col_w == pytest.approx((g.content_w - g.gutter * 11) / 12)


def test_first_column_starts_at_the_left_margin():
    assert Grid(**SHIPPED).col_x(0) == pytest.approx(0.80, abs=1e-3)


def test_full_span_equals_content_width():
    g = Grid(**SHIPPED)
    assert g.span_w(12) == pytest.approx(g.content_w)


def test_last_column_ends_at_the_right_edge():
    g = Grid(**SHIPPED)
    assert g.col_x(11) + g.col_w == pytest.approx(g.right_edge)


def test_a_column_out_of_range_is_rejected():
    with pytest.raises(ThemeError, match="out of range"):
        Grid(**SHIPPED).col_x(12)


def test_zero_columns_is_rejected():
    with pytest.raises(ThemeError, match="columns"):
        Grid(**{**SHIPPED, "columns": 0})


def test_margins_wider_than_the_slide_are_rejected():
    with pytest.raises(ThemeError, match="content width"):
        Grid(**{**SHIPPED, "left_frac": 0.55, "right_frac": 0.55})


def test_a_negative_gutter_is_rejected():
    with pytest.raises(ThemeError, match="gutter"):
        Grid(**{**SHIPPED, "gutter_frac": -0.01})


BASE = """
    name: testtheme
    template: assets/t.pptx
    bind: {page: lt1, ink: dk1, inverse: dk1, line: lt2}
    type:
      min_pt: 10.5
      ramp:
        title: {pt: 32, bold: true}
        body: {pt: 13.5}
    scale:
      margin: {top: 4%, right: 4.5751%, bottom: 6.6667%, left: 4.6501%}
      columns: 12
      gutter: 1.35%
      body_top: 22.6667%
"""


def _theme_at(where, template, body=BASE):
    (where / "assets").mkdir(parents=True)
    (where / "assets" / "t.pptx").write_bytes(template.read_bytes())
    path = where / "t.yaml"
    path.write_text(textwrap.dedent(body))
    return load_theme(path)


def test_the_same_theme_doubles_every_inch_on_a_double_size_canvas(
    tmp_path, synthetic_template, wide_template
):
    std = _theme_at(tmp_path / "std", synthetic_template)
    wide = _theme_at(tmp_path / "wide", wide_template)
    assert wide.grid.slide_h == pytest.approx(2 * std.grid.slide_h)
    assert wide.grid.left == pytest.approx(2 * std.grid.left)
    assert wide.grid.body_top == pytest.approx(2 * std.grid.body_top)
    assert wide.grid.gutter == pytest.approx(2 * std.grid.gutter)
    assert wide.grid.col_w == pytest.approx(2 * std.grid.col_w)


def test_a_theme_that_declares_no_scale_block_gets_the_built_in_grid(tmp_path, synthetic_template):
    body = BASE[: BASE.index("    scale:\n")]
    theme = _theme_at(tmp_path / "nogrid", synthetic_template, body)
    built_in = default_grid(theme.grid.scale)
    assert (theme.grid.top, theme.grid.right, theme.grid.bottom, theme.grid.left) == (
        pytest.approx((built_in.top, built_in.right, built_in.bottom, built_in.left))
    )
    assert (theme.grid.gutter, theme.grid.body_top, theme.grid.columns) == (
        pytest.approx((built_in.gutter, built_in.body_top, built_in.columns))
    )


def test_a_theme_may_override_one_margin_and_default_the_rest(tmp_path, synthetic_template):
    body = BASE[: BASE.index("    scale:\n")] + "    scale:\n      margin: {left: 20%}\n"
    theme = _theme_at(tmp_path / "onemargin", synthetic_template, body)
    built_in = default_grid(theme.grid.scale)
    assert theme.grid.left == pytest.approx(theme.grid.scale.x(0.2))
    assert theme.grid.right == pytest.approx(built_in.right)


def test_a_grid_key_names_what_replaced_it(tmp_path, synthetic_template):
    body = BASE.replace("    scale:\n", "    grid:\n")
    with pytest.raises(ThemeError, match=r"'grid' was replaced by 'scale'"):
        _theme_at(tmp_path / "legacy", synthetic_template, body)


def test_the_default_rungs_still_land_on_their_point_sizes():
    """The conversion must not resize a word: edit the modular scale and this fails. Pinned against
    ``DEFAULT_RAMP``, which is exactly what a theme naming no ``type:`` takes."""
    sizes = {
        name: SCALE.pt(DEFAULT_RAMP[name])
        for name in ("body", "caption", "head", "title", "kicker", "hero")
    }
    assert sizes == pytest.approx(
        {
            "body": 15.975,
            "caption": 14.2882,
            "head": 24.9608,
            "title": 31.2015,
            "kicker": 12.78,
            "hero": 48.7515,
        },
        abs=1e-3,
    )


def test_the_same_theme_doubles_every_point_size_on_a_double_size_canvas(
    tmp_path, synthetic_template, wide_template
):
    std = _theme_at(tmp_path / "std", synthetic_template)
    wide = _theme_at(tmp_path / "wide", wide_template)
    assert std.style("body").size == pytest.approx(13.5)
    assert wide.style("body").size == pytest.approx(27.0)
    assert wide.style("title").size == pytest.approx(2 * std.style("title").size)
    assert wide.min_pt == pytest.approx(2 * std.min_pt)


def test_a_min_size_key_names_what_replaced_it(tmp_path, synthetic_template):
    """The replacement the message names has to be a key the loader reads — `theme/load.py` reads
    `type.min_pt`, so anything else sends the reader to write a key that is ignored as unknown."""
    body = BASE.replace("min_pt: 10.5", "min_size: 10.5")
    with pytest.raises(ThemeError, match=r"'type.min_size' was replaced by 'min_pt'"):
        _theme_at(tmp_path / "legacy_min", synthetic_template, body)
    # The named key is one a theme can actually set: BASE already uses it.
    assert "min_pt:" in BASE


def test_a_ramp_size_key_names_what_replaced_it(tmp_path, synthetic_template):
    body = BASE.replace("body: {pt: 13.5}", "body: {size: 13.5}")
    with pytest.raises(ThemeError, match=r"'size' .* was replaced by 'pt'"):
        _theme_at(tmp_path / "legacy_ramp", synthetic_template, body)


def test_a_ramp_rung_key_names_what_replaced_it(tmp_path, synthetic_template):
    """Every theme written before the cutover states rungs; each hits this once."""
    body = BASE.replace("body: {pt: 13.5}", "body: {rung: 1.8}")
    with pytest.raises(ThemeError, match=r"'rung' .* was replaced by 'pt'"):
        _theme_at(tmp_path / "legacy_rung", synthetic_template, body)


def test_a_bare_number_in_the_scale_block_is_refused(tmp_path, synthetic_template):
    """0.015 and 1.5% differ by a hundred, and a theme that means one and writes the
    other lays out every slide wrong without erroring."""
    body = BASE.replace("gutter: 1.35%", "gutter: 0.0135")
    with pytest.raises(ThemeError, match=r"gutter is a percent of the canvas, got 0.0135"):
        _theme_at(tmp_path / "bare_gutter", synthetic_template, body)


def test_a_bare_margin_is_refused_too(tmp_path, synthetic_template):
    body = BASE.replace("top: 4%", "top: 0.04")
    with pytest.raises(ThemeError, match=r"top is a percent of the canvas, got 0.04"):
        _theme_at(tmp_path / "bare_margin", synthetic_template, body)
