"""ChartStyle: the theme's chart aesthetics block — that the vocabulary round-trips from YAML, and
that its defaults reproduce a flat, un-styled chart exactly."""

from __future__ import annotations

import textwrap

import pytest

from deckwright.errors import ThemeError
from deckwright.theme import load_theme
from deckwright.theme.chartstyle import ChartStyle

# Literal on purpose: `ChartStyle()` here would agree with any edit to the dataclass,
# which is the one thing this file exists to catch.
DEFAULTS = ChartStyle(
    gap_width=60,
    gradient=False,
    gradient_angle=90.0,
    shadow=False,
    shadow_blur_pt=4.0,
    shadow_dist_pt=3.0,
    shadow_dir_deg=45.0,
    shadow_alpha=0.4,
    marker_size=8,
    marker_style="circle",
    grid="horizontal",
    label_position="outside_end",
    thousands_sep=True,
)


def _write(tmp_path, template, body: str):
    (tmp_path / "assets").mkdir(exist_ok=True)
    dest = tmp_path / "assets" / "t.pptx"
    dest.write_bytes(template.read_bytes())
    path = tmp_path / "t.yaml"
    path.write_text(textwrap.dedent(body))
    return path


BASE = """
    name: testtheme
    template: assets/t.pptx
    bind: {page: lt1, ink: dk1, inverse: dk1, line: lt2}
    type:
      ramp:
        title: {pt: 32, bold: true}
        body: {pt: 13.5}
      min_pt: 10.5
    scale:
      margin: {top: 4%, right: 4.5751%, bottom: 6.6667%, left: 4.6501%}
      columns: 12
      gutter: 1.35%
      body_top: 22.6667%
"""


def test_omitted_chart_block_yields_defaults(tmp_path, synthetic_template):
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.chart == DEFAULTS


def test_every_field_round_trips_from_yaml(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      gap_width: 80
      gradient: true
      gradient_angle: 30.0
      shadow: true
      shadow_blur_pt: 6.0
      shadow_dist_pt: 5.0
      shadow_dir_deg: 90.0
      shadow_alpha: 0.6
      marker_size: 10
      marker_style: diamond
      grid: horizontal
      label_position: inside_end
      thousands_sep: true
"""
    )
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert theme.chart == ChartStyle(
        gap_width=80,
        gradient=True,
        gradient_angle=30.0,
        shadow=True,
        shadow_blur_pt=6.0,
        shadow_dist_pt=5.0,
        shadow_dir_deg=90.0,
        shadow_alpha=0.6,
        marker_size=10,
        marker_style="diamond",
        grid="horizontal",
        label_position="inside_end",
        thousands_sep=True,
    )


def test_unknown_chart_key_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      sparkle: true
"""
    )
    with pytest.raises(ThemeError, match="sparkle"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_unknown_chart_key_error_lists_known_fields(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      nope: 1
"""
    )
    with pytest.raises(ThemeError, match="gap_width"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_negative_shadow_blur_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      shadow_blur_pt: -1.0
"""
    )
    with pytest.raises(ThemeError, match="shadow_blur_pt"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_negative_shadow_distance_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      shadow_dist_pt: -2.0
"""
    )
    with pytest.raises(ThemeError, match="shadow_dist_pt"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_shadow_alpha_above_one_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      shadow_alpha: 1.5
"""
    )
    with pytest.raises(ThemeError, match="shadow_alpha"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_shadow_alpha_below_zero_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      shadow_alpha: -0.1
"""
    )
    with pytest.raises(ThemeError, match="shadow_alpha"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_gap_width_above_500_is_rejected(tmp_path, synthetic_template):
    """python-pptx's own ST_GapAmount caps gap_width at 500 (percent)."""
    body = (
        BASE
        + """
    chart:
      gap_width: 501
"""
    )
    with pytest.raises(ThemeError, match="gap_width"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_unknown_grid_value_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      grid: vertical
"""
    )
    with pytest.raises(ThemeError, match="grid"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_unknown_label_position_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      label_position: sideways
"""
    )
    with pytest.raises(ThemeError, match="label_position"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_non_numeric_gap_width_names_the_theme_file_and_field(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      gap_width: not-a-number
"""
    )
    path = _write(tmp_path, synthetic_template, body)
    with pytest.raises(ThemeError, match="gap_width") as exc_info:
        load_theme(path)
    assert str(path) in str(exc_info.value)


def test_non_numeric_shadow_alpha_raises_theme_error_not_value_error(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      shadow_alpha: nope
"""
    )
    with pytest.raises(ThemeError, match="shadow_alpha"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_direct_construction_validates_ranges_too():
    """Backstop for a hand-built ChartStyle that skips the loader entirely."""
    with pytest.raises(ThemeError, match="shadow_alpha"):
        ChartStyle(
            gap_width=150,
            gradient=False,
            gradient_angle=90.0,
            shadow=False,
            shadow_blur_pt=4.0,
            shadow_dist_pt=3.0,
            shadow_dir_deg=45.0,
            shadow_alpha=2.0,
            marker_size=8,
            marker_style="circle",
            grid="none",
            label_position="outside_end",
            thousands_sep=False,
        )


def test_marker_size_below_2_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      marker_size: 1
"""
    )
    with pytest.raises(ThemeError, match="marker_size"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_marker_size_above_72_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      marker_size: 73
"""
    )
    with pytest.raises(ThemeError, match="marker_size"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_marker_size_2_and_72_are_accepted(tmp_path, synthetic_template):
    """The inclusive OOXML boundary — both ends of the range must round-trip."""
    for boundary in (2, 72):
        body = (
            BASE
            + f"""
    chart:
      marker_size: {boundary}
"""
        )
        theme = load_theme(_write(tmp_path, synthetic_template, body))
        assert theme.chart.marker_size == boundary


def test_unknown_marker_style_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      marker_style: star
"""
    )
    with pytest.raises(ThemeError, match="marker_style"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_unknown_marker_style_error_lists_valid_values(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      marker_style: star
"""
    )
    with pytest.raises(ThemeError, match="circle") as exc_info:
        load_theme(_write(tmp_path, synthetic_template, body))
    message = str(exc_info.value)
    assert "square" in message and "diamond" in message and "none" in message


@pytest.mark.parametrize("value", ("circle", "square", "diamond", "none"))
def test_every_marker_style_value_is_accepted(tmp_path, synthetic_template, value):
    body = (
        BASE
        + f"""
    chart:
      marker_style: {value}
"""
    )
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert theme.chart.marker_style == value


def test_non_numeric_marker_size_names_the_theme_file_and_field(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chart:
      marker_size: not-a-number
"""
    )
    path = _write(tmp_path, synthetic_template, body)
    with pytest.raises(ThemeError, match="marker_size") as exc_info:
        load_theme(path)
    assert str(path) in str(exc_info.value)


def test_direct_construction_validates_marker_size_too():
    with pytest.raises(ThemeError, match="marker_size"):
        ChartStyle(
            gap_width=150,
            gradient=False,
            gradient_angle=90.0,
            shadow=False,
            shadow_blur_pt=4.0,
            shadow_dist_pt=3.0,
            shadow_dir_deg=45.0,
            shadow_alpha=0.4,
            marker_size=1,
            marker_style="circle",
            grid="none",
            label_position="outside_end",
            thousands_sep=False,
        )


def test_direct_construction_validates_marker_style_too():
    with pytest.raises(ThemeError, match="marker_style"):
        ChartStyle(
            gap_width=150,
            gradient=False,
            gradient_angle=90.0,
            shadow=False,
            shadow_blur_pt=4.0,
            shadow_dist_pt=3.0,
            shadow_dir_deg=45.0,
            shadow_alpha=0.4,
            marker_size=8,
            marker_style="star",
            grid="none",
            label_position="outside_end",
            thousands_sep=False,
        )
