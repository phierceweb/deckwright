import dataclasses
import re

from lxml import etree

import pytest
from pptx.enum.chart import XL_DATA_LABEL_POSITION, XL_LEGEND_POSITION, XL_MARKER_STYLE
from pptx.enum.dml import MSO_FILL
from pptx.oxml.ns import qn
from pptx.util import Pt

from deckwright.charts.model import _BUBBLE_CHART_TYPES, _XY_CHART_TYPES, ChartSpec, Series
from deckwright.charts.native import add_native_chart
from deckwright.errors import ThemeError
from deckwright.theme.chartstyle import ChartStyle
from deckwright.theme.palette import build_palette

# A non-default style exercising every knob this task wires up, so a chart
# built from it differs from today's flat look in every dimension at once.
STYLED = ChartStyle(
    gap_width=80,
    gradient=True,
    gradient_angle=90.0,
    shadow=True,
    shadow_blur_pt=6.0,
    shadow_dist_pt=5.0,
    shadow_dir_deg=90.0,
    shadow_alpha=0.5,
    marker_size=11,
    marker_style="diamond",
    grid="horizontal",
    label_position="inside_end",
    thousands_sep=True,
)


def _styled_ctx(ctx_factory, theme):
    styled_theme = dataclasses.replace(theme, chart=STYLED)
    return ctx_factory({"title": "T"}, theme_override=styled_theme)


def _plain_ctx(ctx_factory, theme):
    """Digit grouping off, so a number-format assertion says what it means to say."""
    plain = dataclasses.replace(theme, chart=ChartStyle(thousands_sep=False))
    return ctx_factory({"title": "T"}, theme_override=plain)


def test_it_creates_a_real_chart_part(ctx_factory, chart_spec):
    ctx = ctx_factory({"title": "T"})
    frame = add_native_chart(ctx, chart_spec, ctx.body_rect)
    assert frame.has_chart
    assert frame.chart.plots[0].categories[0] == "Q1"


def test_bars_take_their_colour_from_the_theme(ctx_factory, chart_spec):
    ctx = ctx_factory({"title": "T"})
    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart
    fill = chart.series[0].format.fill
    assert str(fill.fore_color.rgb) == ctx.theme.palette.role(ctx.theme.palette.accents[0])


def test_a_single_series_chart_has_no_legend(ctx_factory, chart_spec):
    ctx = ctx_factory({"title": "T"})
    assert add_native_chart(ctx, chart_spec, ctx.body_rect).chart.has_legend is False


def test_the_frame_lands_inside_the_given_rect(ctx_factory, chart_spec):
    ctx = ctx_factory({"title": "T"})
    rect = ctx.body_rect
    frame = add_native_chart(ctx, chart_spec, rect)
    assert frame.left / 914400 == pytest.approx(rect.left)
    assert frame.width / 914400 == pytest.approx(rect.width)


def test_a_single_series_highlight_isolates_the_marked_point(ctx_factory, chart_spec_highlighted):
    """Emphasis by isolation: the marked point keeps the accent and every other point goes
    muted, so a second hue never reads as a second category."""
    ctx = ctx_factory({"title": "T"})
    chart = add_native_chart(ctx, chart_spec_highlighted, ctx.body_rect).chart
    points = chart.series[0].points
    accent = ctx.theme.palette.role(ctx.theme.palette.accents[0])
    muted = ctx.theme.palette.role("muted")
    assert str(points[1].format.fill.fore_color.rgb) == accent
    assert str(points[0].format.fill.fore_color.rgb) == muted


def test_a_multi_series_chart_has_a_legend(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="column",
        categories=("Q1", "Q2"),
        series=(
            Series(name="A", values=(1.0, 2.0)),
            Series(name="B", values=(3.0, 4.0)),
        ),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.has_legend is True


def _two_series_spec():
    return ChartSpec(
        type="column",
        categories=("Q1", "Q2"),
        series=(Series(name="Ads", values=(1.0, 2.0)), Series(name="Organic", values=(3.0, 4.0))),
    )


def test_chart_text_defaults_to_the_ink_of_the_background_it_sits_on(ctx_factory, chart_spec):
    ctx = ctx_factory({"title": "T"}, background="inverse")
    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart
    assert str(chart.font.color.rgb) == ctx.theme.palette.pair("inverse").fg


def test_chart_text_on_the_page_takes_the_page_ink(ctx_factory, chart_spec):
    ctx = ctx_factory({"title": "T"})
    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart
    assert str(chart.font.color.rgb) == ctx.theme.palette.pair("page").fg


def test_a_legend_on_a_dark_slide_is_written_in_that_slides_ink(ctx_factory):
    ctx = ctx_factory({"title": "T"}, background="inverse")
    chart = add_native_chart(ctx, _two_series_spec(), ctx.body_rect).chart
    assert str(chart.legend.font.color.rgb) == ctx.theme.palette.pair("inverse").fg


def test_a_legend_is_sized_off_the_caption_rung(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    chart = add_native_chart(ctx, _two_series_spec(), ctx.body_rect).chart
    assert chart.legend.font.size == Pt(ctx.style("caption").size)


def test_a_legend_takes_the_themes_typeface(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    chart = add_native_chart(ctx, _two_series_spec(), ctx.body_rect).chart
    assert chart.legend.font.name == ctx.theme.face


def test_axis_lines_take_their_colour_from_the_theme(ctx_factory, chart_spec):
    ctx = ctx_factory({"title": "T"})
    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart
    assert str(chart.category_axis.format.line.color.rgb) == ctx.theme.palette.role("line")
    assert str(chart.value_axis.format.line.color.rgb) == ctx.theme.palette.role("line")


def test_the_values_outrank_the_axis_scale_that_frames_them(ctx_factory, chart_spec):
    """Untouched, tick labels inherit the template's size and dwarf the values."""
    ctx = ctx_factory({"title": "T"})
    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart
    labels = chart.plots[0].data_labels
    ticks = chart.value_axis.tick_labels

    assert labels.font.size.pt == pytest.approx(ctx.theme.style("kicker").size)
    assert labels.font.bold is True
    assert str(labels.font.color.rgb) == ctx.theme.palette.role("ink")
    assert ticks.font.size.pt == pytest.approx(ctx.theme.style("caption").size)
    assert str(ticks.font.color.rgb) == ctx.theme.palette.role("muted")
    assert labels.font.size.pt > ticks.font.size.pt


def test_every_spec_type_is_renderable_natively():
    """Catches a type added to ChartSpec and never wired into native.py's mapping."""
    from deckwright.charts.model import _TYPES
    from deckwright.charts.native import _CHART_TYPES

    assert set(_TYPES) <= set(_CHART_TYPES)


def test_y_min_and_y_max_set_the_value_axis_scale(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="column",
        categories=("Q1", "Q2"),
        series=(Series(name="A", values=(1.0, 2.0)),),
        y_min=0.0,
        y_max=100.0,
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.value_axis.minimum_scale == 0.0
    assert chart.value_axis.maximum_scale == 100.0


def test_without_y_min_max_the_value_axis_stays_automatic(ctx_factory, chart_spec):
    ctx = ctx_factory({"title": "T"})
    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart
    assert chart.value_axis.minimum_scale is None
    assert chart.value_axis.maximum_scale is None


def test_a_line_chart_takes_its_stroke_colour_and_weight_from_the_theme(ctx_factory, chart_spec):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(type="line", categories=chart_spec.categories, series=chart_spec.series)
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    line = chart.series[0].format.line
    assert str(line.color.rgb) == ctx.theme.palette.role(ctx.theme.palette.accents[0])
    assert line.width.pt == pytest.approx(ctx.theme.line_weight)


def test_a_four_category_pie_gets_four_distinct_wedge_colours(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="pie",
        categories=("Q1", "Q2", "Q3", "Q4"),
        series=(Series(name="Share", values=(10.0, 20.0, 30.0, 40.0)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    colours = {str(p.format.fill.fore_color.rgb) for p in chart.series[0].points}
    assert len(colours) == 4


def test_a_three_series_column_gets_three_distinct_series_colours(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="column",
        categories=("Q1", "Q2"),
        series=(
            Series(name="A", values=(1.0, 2.0)),
            Series(name="B", values=(3.0, 4.0)),
            Series(name="C", values=(5.0, 6.0)),
        ),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    colours = {str(s.format.fill.fore_color.rgb) for s in chart.series}
    assert len(colours) == 3


def test_a_single_series_column_still_paints_accent(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="column", categories=("Q1", "Q2"), series=(Series(name="Revenue", values=(1.0, 2.0)),)
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert str(chart.series[0].format.fill.fore_color.rgb) == ctx.theme.palette.role(
        ctx.theme.palette.accents[0]
    )


def test_highlight_wins_over_the_categorical_colour(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="column",
        categories=("Q1", "Q2"),
        series=(Series(name="A", values=(1.0, 2.0)), Series(name="B", values=(3.0, 4.0))),
        highlight=1,
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    highlight = ctx.theme.palette.role(ctx.theme.palette.accents[1])
    for series in chart.series:
        assert str(series.points[1].format.fill.fore_color.rgb) == highlight
    # Only of the first series: the second series' own cycle colour *is* the highlight.
    assert str(chart.series[0].points[0].format.fill.fore_color.rgb) != highlight


def test_highlight_wins_over_the_pie_palette_too(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="pie",
        categories=("Q1", "Q2", "Q3"),
        series=(Series(name="Share", values=(1.0, 2.0, 3.0)),),
        highlight=1,
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    points = chart.series[0].points
    assert str(points[1].format.fill.fore_color.rgb) == ctx.theme.palette.role(
        ctx.theme.palette.accents[1]
    )
    assert str(points[0].format.fill.fore_color.rgb) != ctx.theme.palette.role(
        ctx.theme.palette.accents[1]
    )


def test_a_pie_chart_shows_category_name_labels(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="pie", categories=("Q1", "Q2"), series=(Series(name="Share", values=(40.0, 60.0)),)
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].data_labels.show_category_name is True


def test_the_default_theme_applies_the_design_systems_chart_look(ctx_factory, chart_spec):
    """Literal values, not `ChartStyle()` fields, which would agree with any edit to it."""
    ctx = ctx_factory({"title": "T"})
    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart

    assert chart.plots[0].gap_width == 60

    point = chart.series[0].points[0]
    assert point.format.fill.type == MSO_FILL.SOLID
    spPr = point.format.element.get_or_add_spPr()
    assert spPr.find(qn("a:effectLst")) is None

    # grid: horizontal — rules across the value axis only, never down the categories.
    assert chart.value_axis.has_major_gridlines is True
    assert chart.category_axis.has_major_gridlines is False

    labels = chart.plots[0].data_labels
    assert labels.position is None
    assert labels.number_format == "#,##0"


def test_gap_width_is_read_from_the_theme(ctx_factory, theme, chart_spec):
    ctx = _styled_ctx(ctx_factory, theme)
    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart
    assert chart.plots[0].gap_width == STYLED.gap_width


def test_gradient_point_has_two_stops_from_the_categorical_colour(ctx_factory, theme, chart_spec):
    ctx = _styled_ctx(ctx_factory, theme)
    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart
    point = chart.series[0].points[0]

    assert point.format.fill.type == MSO_FILL.GRADIENT
    stops = point.format.fill.gradient_stops
    assert len(stops) == 2
    stop0, stop1 = stops[0].color.rgb, stops[1].color.rgb
    assert str(stop0) == ctx.theme.palette.role(ctx.theme.palette.accents[0])
    assert stop1 != stop0
    assert stop1[0] >= stop0[0] and stop1[1] >= stop0[1] and stop1[2] >= stop0[2]


@pytest.mark.parametrize(
    ("chart_type", "expected"),
    [
        ("column", 90.0),
        ("column-stacked", 90.0),
        ("bar", 0.0),
        ("bar-stacked", 0.0),
        ("bar-stacked-100", 0.0),
    ],
)
def test_the_gradient_runs_along_the_bar_not_across_it(ctx_factory, theme, chart_type, expected):
    """The theme's angle means "down a column"; a horizontal bar has to rotate a quarter
    turn or the gradient crosses its thin dimension and reads as flat."""
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type=chart_type, categories=("A", "B"), series=(Series(name="S", values=(3.0, 6.0)),)
    )
    fill = add_native_chart(ctx, spec, ctx.body_rect).chart.series[0].points[0].format.fill
    assert fill.gradient_angle == pytest.approx(expected)


def test_pie_points_also_get_the_gradient_when_enabled(ctx_factory, theme):
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="pie", categories=("Q1", "Q2"), series=(Series(name="Share", values=(40.0, 60.0)),)
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.series[0].points[0].format.fill.type == MSO_FILL.GRADIENT


def test_shadow_effect_lst_carries_the_themes_blur_dist_dir_alpha(ctx_factory, theme, chart_spec):
    ctx = _styled_ctx(ctx_factory, theme)
    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart
    spPr = chart.series[0].points[0].format.element.get_or_add_spPr()

    shadow = spPr.find(qn("a:effectLst")).find(qn("a:outerShdw"))
    assert shadow is not None
    assert shadow.get("blurRad") == str(round(STYLED.shadow_blur_pt * 12700))
    assert shadow.get("dist") == str(round(STYLED.shadow_dist_pt * 12700))
    assert shadow.get("dir") == str(round(STYLED.shadow_dir_deg * 60000))
    alpha = shadow.find(qn("a:srgbClr")).find(qn("a:alpha"))
    assert alpha.get("val") == str(round(STYLED.shadow_alpha * 100000))


def test_percent_unit_sets_the_data_labels_number_format(ctx_factory, theme, spec_highlighted_pct):
    ctx = _plain_ctx(ctx_factory, theme)
    chart = add_native_chart(ctx, spec_highlighted_pct, ctx.body_rect).chart
    assert chart.plots[0].data_labels.number_format == '0"%"'


def test_thousands_sep_formats_large_values_with_commas(ctx_factory, theme):
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column", categories=("Q1",), series=(Series(name="Revenue", values=(1000000.0,)),)
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].data_labels.number_format == "#,##0"


def test_percent_and_thousands_sep_combine_in_the_number_format(ctx_factory, theme):
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column",
        categories=("Q1",),
        series=(Series(name="Adoption", values=(1234.0,), unit="%"),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].data_labels.number_format == '#,##0"%"'


def test_horizontal_gridlines_appear_in_the_rule_colour_when_enabled(ctx_factory, theme):
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column", categories=("Q1", "Q2"), series=(Series(name="A", values=(1.0, 2.0)),)
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.value_axis.has_major_gridlines is True
    assert chart.category_axis.has_major_gridlines is False
    assert str(chart.value_axis.major_gridlines.format.line.color.rgb) == ctx.theme.palette.role(
        "line"
    )


def test_inside_end_label_position_is_applied(ctx_factory, theme, chart_spec):
    ctx = _styled_ctx(ctx_factory, theme)
    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart
    assert chart.plots[0].data_labels.position == XL_DATA_LABEL_POSITION.INSIDE_END


def test_none_label_position_hides_data_labels(ctx_factory, theme, chart_spec):
    no_labels = dataclasses.replace(STYLED, label_position="none")
    styled_theme = dataclasses.replace(theme, chart=no_labels)
    ctx = ctx_factory({"title": "T"}, theme_override=styled_theme)
    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart
    assert chart.plots[0].has_data_labels is False


_ALL_CHART_TYPES = (
    "bar",
    "column",
    "column-stacked",
    "column-stacked-100",
    "line",
    "line-markers",
    "area",
    "pie",
    "doughnut",
    "bar-stacked",
    "bar-stacked-100",
    "area-stacked",
    "radar",
    "pie-exploded",
    "area-stacked-100",
    "doughnut-exploded",
    "line-stacked",
    "line-stacked-100",
    "line-markers-stacked",
    "line-markers-stacked-100",
    "radar-filled",
    "radar-markers",
    "xy-scatter",
    "xy-scatter-lines",
    "xy-scatter-lines-no-markers",
    "xy-scatter-smooth",
    "xy-scatter-smooth-no-markers",
    "bubble",
    "bubble-3d",
)


def _spec_for(chart_type: str, y_values: tuple[float, ...] = (12.0, 34.0)) -> ChartSpec:
    """A minimal valid spec for any of the 29 types; y reads back through the same
    ``series[0].values`` whatever the shape, so one assertion covers all."""
    if chart_type in _XY_CHART_TYPES:
        points = tuple((float(i + 1), y) for i, y in enumerate(y_values))
        return ChartSpec(type=chart_type, categories=(), series=(Series(name="A", points=points),))
    if chart_type in _BUBBLE_CHART_TYPES:
        points = tuple((float(i + 1), y, 5.0 + i) for i, y in enumerate(y_values))
        return ChartSpec(type=chart_type, categories=(), series=(Series(name="A", points=points),))
    categories = tuple(f"Q{i + 1}" for i in range(len(y_values)))
    return ChartSpec(
        type=chart_type, categories=categories, series=(Series(name="A", values=y_values),)
    )


@pytest.mark.parametrize("chart_type", _ALL_CHART_TYPES)
def test_every_type_builds_a_chart_and_its_values_reach_the_worksheet(ctx_factory, chart_type):
    ctx = ctx_factory({"title": "T"})
    spec = _spec_for(chart_type)
    frame = add_native_chart(ctx, spec, ctx.body_rect)
    assert frame.has_chart
    assert list(frame.chart.series[0].values) == [12.0, 34.0]


def test_a_four_category_doughnut_gets_four_distinct_segment_colours(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="doughnut",
        categories=("Q1", "Q2", "Q3", "Q4"),
        series=(Series(name="Share", values=(10.0, 20.0, 30.0, 40.0)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    colours = {str(p.format.fill.fore_color.rgb) for p in chart.series[0].points}
    assert len(colours) == 4


def test_a_doughnut_chart_shows_category_name_labels(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="doughnut",
        categories=("Q1", "Q2"),
        series=(Series(name="Share", values=(40.0, 60.0)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].data_labels.show_category_name is True


def test_a_stacked_column_gets_the_themes_gap_width(ctx_factory, theme):
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column-stacked",
        categories=("Q1", "Q2"),
        series=(Series(name="Ads", values=(1.0, 2.0)), Series(name="Organic", values=(3.0, 4.0))),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].gap_width == STYLED.gap_width


def test_an_area_chart_builds_and_does_not_touch_gap_width(ctx_factory, theme):
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="area",
        categories=("Q1", "Q2", "Q3"),
        series=(Series(name="Revenue", values=(10.0, 20.0, 15.0)),),
    )
    frame = add_native_chart(ctx, spec, ctx.body_rect)
    assert frame.has_chart


def test_non_bar_column_chart_types_are_excluded_from_gap_width_types():
    """Assigning gap_width to AreaPlot/LinePlot/DoughnutPlot/RadarPlot/PiePlot is a silent
    no-op in python-pptx, so the frozenset itself is the enforced contract."""
    from deckwright.charts.native import _GAP_WIDTH_CHART_TYPES

    assert (
        not {
            "area",
            "line-markers",
            "doughnut",
            "area-stacked",
            "radar",
            "pie-exploded",
            "area-stacked-100",
            "doughnut-exploded",
            "line-stacked",
            "line-stacked-100",
            "line-markers-stacked",
            "line-markers-stacked-100",
            "radar-filled",
            "radar-markers",
            "xy-scatter",
            "xy-scatter-lines",
            "xy-scatter-lines-no-markers",
            "xy-scatter-smooth",
            "xy-scatter-smooth-no-markers",
            "bubble",
            "bubble-3d",
        }
        & _GAP_WIDTH_CHART_TYPES
    )


def test_a_four_category_pie_exploded_gets_four_distinct_wedge_colours(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="pie-exploded",
        categories=("Q1", "Q2", "Q3", "Q4"),
        series=(Series(name="Share", values=(10.0, 20.0, 30.0, 40.0)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    colours = {str(p.format.fill.fore_color.rgb) for p in chart.series[0].points}
    assert len(colours) == 4


def test_radar_keeps_major_gridlines_on_both_axes_after_styling(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="radar",
        categories=("Speed", "Range", "Comfort", "Price"),
        series=(Series(name="Model A", values=(3.0, 4.0, 2.0, 5.0)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.category_axis.has_major_gridlines is True
    assert chart.value_axis.has_major_gridlines is True


def test_a_stacked_bar_gets_the_themes_gap_width(ctx_factory, theme):
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="bar-stacked",
        categories=("Q1", "Q2"),
        series=(Series(name="Ads", values=(1.0, 2.0)), Series(name="Organic", values=(3.0, 4.0))),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].gap_width == STYLED.gap_width


def test_an_area_stacked_chart_builds_and_does_not_touch_gap_width(ctx_factory, theme):
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="area-stacked",
        categories=("Q1", "Q2", "Q3"),
        series=(
            Series(name="Ads", values=(10.0, 20.0, 15.0)),
            Series(name="Organic", values=(5.0, 8.0, 12.0)),
        ),
    )
    frame = add_native_chart(ctx, spec, ctx.body_rect)
    assert frame.has_chart


def test_a_four_category_doughnut_exploded_gets_four_distinct_wedge_colours(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="doughnut-exploded",
        categories=("Q1", "Q2", "Q3", "Q4"),
        series=(Series(name="Share", values=(10.0, 20.0, 30.0, 40.0)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    colours = {str(p.format.fill.fore_color.rgb) for p in chart.series[0].points}
    assert len(colours) == 4


@pytest.mark.parametrize("chart_type", ("radar-filled", "radar-markers"))
def test_radar_variants_keep_major_gridlines_on_both_axes_after_styling(ctx_factory, chart_type):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type=chart_type,
        categories=("Speed", "Range", "Comfort", "Price"),
        series=(Series(name="Model A", values=(3.0, 4.0, 2.0, 5.0)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.category_axis.has_major_gridlines is True
    assert chart.value_axis.has_major_gridlines is True


@pytest.mark.parametrize(
    "chart_type",
    sorted(
        [
            "column-stacked-100",
            "bar-stacked-100",
            "line-stacked-100",
            "line-markers-stacked-100",
            "area-stacked-100",
        ]
    ),
)
def test_a_hundred_percent_type_reads_as_a_percentage(ctx_factory, chart_type):
    """area-stacked-100 leaves the format linked to the source and renders 0.4, not 40%;
    the others inherit a per-type default. Set it rather than depend on which is which."""
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type=chart_type,
        categories=("Q1", "Q2"),
        series=(Series(name="A", values=(1.0, 2.0)), Series(name="B", values=(3.0, 2.0))),
    )
    ticks = add_native_chart(ctx, spec, ctx.body_rect).chart.value_axis.tick_labels
    assert ticks.number_format == "0%"
    assert ticks.number_format_is_linked is False


# CT_ScatterChart lists c:dLbls in its tag sequence but python-pptx never wires up the
# descriptor, so plot.has_data_labels raises AttributeError on the five xy-scatter types.

_XY_TYPES = (
    "xy-scatter",
    "xy-scatter-lines",
    "xy-scatter-lines-no-markers",
    "xy-scatter-smooth",
    "xy-scatter-smooth-no-markers",
)
_BUBBLE_TYPES = ("bubble", "bubble-3d")


@pytest.mark.parametrize("chart_type", _BUBBLE_TYPES)
def test_bubble_types_get_the_themes_data_labels(ctx_factory, chart_type):
    """Bubble's CT_BubbleChart does define dLbls, so it must keep labels. Asserted on the
    styling deckwright writes — ``has_data_labels`` is already True on a fresh bubble plot."""
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type=chart_type,
        categories=(),
        series=(Series(name="A", points=((1.0, 2.0, 10.0), (2.0, 4.0, 20.0))),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    labels = chart.plots[0].data_labels
    assert labels.font.size.pt == ctx.style("kicker").size
    assert labels.font.bold is True
    assert labels.font.name == ctx.theme.face
    assert labels.font.color.rgb == ctx.fg()


@pytest.mark.parametrize("chart_type", _BUBBLE_TYPES)
def test_a_bubble_point_takes_its_fill_from_the_theme(ctx_factory, chart_type):
    """xy-scatter is out: its point is a stroke and a marker, which the series colours."""
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type=chart_type, categories=(), series=(Series(name="A", points=((1.0, 2.0, 10.0),)),)
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    fill = chart.series[0].points[0].format.fill
    assert str(fill.fore_color.rgb) == ctx.theme.palette.role(ctx.theme.palette.accents[0])


def test_a_highlighted_point_on_a_marker_chart_fills_its_marker(ctx_factory):
    """The one dPt a stroke series may carry — and it wraps the fill in `c:marker`,
    which is what keeps LibreOffice from misassigning it."""
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="line-markers",
        categories=("a", "b", "c"),
        series=(Series(name="A", values=(1.0, 2.0, 3.0)),),
        highlight=1,
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    xml = chart.series[0]._element.xml
    assert xml.count("<c:dPt>") == 1
    import re

    dpt = re.search(r"<c:dPt>.*?</c:dPt>", xml, re.S).group(0)
    assert "<c:marker>" in dpt


def test_y_min_and_y_max_set_the_value_axis_scale_on_an_xy_chart(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="xy-scatter",
        categories=(),
        series=(Series(name="A", points=((1.0, 2.0), (2.0, 4.0))),),
        y_min=0.0,
        y_max=10.0,
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.value_axis.minimum_scale == 0.0
    assert chart.value_axis.maximum_scale == 10.0


def test_a_multi_series_bubble_chart_has_a_legend(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="bubble",
        categories=(),
        series=(
            Series(name="A", points=((1.0, 2.0, 10.0),)),
            Series(name="B", points=((2.0, 3.0, 20.0),)),
        ),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.has_legend is True


# Markers apply only to the stroke-based types that carry one — see _MARKER_CHART_TYPES's
# own comment for why the rest are excluded.

_MARKER_STYLE_MAP = {
    "circle": XL_MARKER_STYLE.CIRCLE,
    "square": XL_MARKER_STYLE.SQUARE,
    "diamond": XL_MARKER_STYLE.DIAMOND,
    "none": XL_MARKER_STYLE.NONE,
}


def test_a_line_markers_series_marker_takes_the_themes_size_and_style(ctx_factory, theme):
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="line-markers", categories=("Q1", "Q2"), series=(Series(name="A", values=(1.0, 2.0)),)
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    marker = chart.series[0].marker
    assert marker.size == STYLED.marker_size
    assert marker.style == _MARKER_STYLE_MAP[STYLED.marker_style]


def test_a_line_markers_marker_fill_matches_the_series_palette_colour(ctx_factory, theme):
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="line-markers", categories=("Q1", "Q2"), series=(Series(name="A", values=(1.0, 2.0)),)
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    marker_fill = chart.series[0].marker.format.fill
    assert marker_fill.type == MSO_FILL.SOLID
    assert str(marker_fill.fore_color.rgb) == ctx.theme.palette.role(ctx.theme.palette.accents[0])


def test_an_xy_scatter_gets_a_marker_element_at_all(ctx_factory):
    """Without an explicit <c:marker>, an xy-scatter renders PowerPoint's own tiny default dot."""
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="xy-scatter",
        categories=(),
        series=(Series(name="A", points=((1.0, 2.0), (2.0, 4.0))),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.series[0].marker.style is not None


def test_xy_scatter_marker_takes_the_themes_size_and_default_style(ctx_factory, theme):
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="xy-scatter",
        categories=(),
        series=(Series(name="A", points=((1.0, 2.0), (2.0, 4.0))),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    marker = chart.series[0].marker
    assert marker.size == STYLED.marker_size
    assert marker.style == _MARKER_STYLE_MAP[STYLED.marker_style]


@pytest.mark.parametrize(
    "chart_type", ("line", "xy-scatter-lines-no-markers", "xy-scatter-smooth-no-markers")
)
def test_a_no_markers_type_does_not_get_markers_forced_on(ctx_factory, theme, chart_type):
    """These three explicitly render with no markers; forcing the theme's marker
    onto them would fight the type's own declared identity."""
    ctx = _styled_ctx(ctx_factory, theme)
    spec = _spec_for(chart_type)
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.series[0].marker.style == XL_MARKER_STYLE.NONE


@pytest.mark.parametrize("chart_type", ("radar", "radar-filled"))
def test_radar_and_radar_filled_do_not_get_markers_forced_on(ctx_factory, theme, chart_type):
    """Only radar-markers is a markers type by name; plain radar renders with an
    explicit no-marker symbol and radar-filled's whole point is a filled polygon."""
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type=chart_type,
        categories=("Speed", "Range", "Comfort", "Price"),
        series=(Series(name="Model A", values=(3.0, 4.0, 2.0, 5.0)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.series[0].marker.style != _MARKER_STYLE_MAP[STYLED.marker_style]


@pytest.mark.parametrize("chart_type", ("bubble", "bubble-3d"))
def test_bubble_types_do_not_get_a_marker_forced_on(ctx_factory, theme, chart_type):
    """CT_BubbleSer has no marker slot in the real schema, so forcing one on is a schema
    mismatch, not just an unneeded flourish."""
    ctx = _styled_ctx(ctx_factory, theme)
    spec = _spec_for(chart_type)
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.series[0].marker.style is None


def test_radar_markers_gets_themed_too(ctx_factory, theme):
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="radar-markers",
        categories=("Speed", "Range", "Comfort", "Price"),
        series=(Series(name="Model A", values=(3.0, 4.0, 2.0, 5.0)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    marker = chart.series[0].marker
    assert marker.size == STYLED.marker_size
    assert marker.style == _MARKER_STYLE_MAP[STYLED.marker_style]
    assert str(marker.format.fill.fore_color.rgb) == ctx.theme.palette.role(
        ctx.theme.palette.accents[0]
    )


def test_marker_chart_types_never_include_a_type_without_the_marker_mixin():
    """BarSeries/AreaSeries/PieSeries/BubbleSeries expose no usable ``.marker``; the
    frozenset is the only thing between a wrong entry and a schema-mismatched write."""
    from deckwright.charts.native import _MARKER_CHART_TYPES

    assert (
        not {
            "bar",
            "column",
            "column-stacked",
            "column-stacked-100",
            "bar-stacked",
            "bar-stacked-100",
            "area",
            "area-stacked",
            "area-stacked-100",
            "pie",
            "doughnut",
            "pie-exploded",
            "doughnut-exploded",
            "bubble",
            "bubble-3d",
        }
        & _MARKER_CHART_TYPES
    )


def test_marker_chart_types_excludes_the_no_marker_variants():
    from deckwright.charts.native import _MARKER_CHART_TYPES

    assert (
        not {
            "line",
            "line-stacked",
            "line-stacked-100",
            "radar",
            "radar-filled",
            "xy-scatter-lines-no-markers",
            "xy-scatter-smooth-no-markers",
        }
        & _MARKER_CHART_TYPES
    )


@pytest.mark.parametrize(
    "chart_type",
    (
        "line",
        "line-markers",
        "line-stacked",
        "line-stacked-100",
        "line-markers-stacked",
        "line-markers-stacked-100",
        "radar",
        "radar-filled",
        "radar-markers",
        "xy-scatter",
        "xy-scatter-lines",
        "xy-scatter-lines-no-markers",
        "xy-scatter-smooth",
        "xy-scatter-smooth-no-markers",
    ),
)
def test_stroke_chart_types_write_no_bare_point_fill(ctx_factory, theme, chart_type):
    """A point here has no fillable shape, and a bare `c:dPt` fill on a stroke series is
    what LibreOffice misassigns to the neighbouring series' marks. The bubble test below
    is the positive control: its point IS a filled shape and keeps its dPt."""
    ctx = _styled_ctx(ctx_factory, theme)
    spec = _spec_for(chart_type, y_values=(10.0, 20.0, 15.0))
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert "<c:dPt>" not in chart.series[0]._element.xml


def test_bubble_points_still_get_the_gradient_when_enabled(ctx_factory, theme):
    """Unlike line/radar/scatter, a bubble's point IS its own visible filled shape,
    so the gradient-vs-solid cleanup must not touch it."""
    ctx = _styled_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="bubble", categories=(), series=(Series(name="A", points=((1.0, 2.0, 10.0),)),)
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.series[0].points[0].format.fill.type == MSO_FILL.GRADIENT


def test_a_scatter_has_no_connecting_line(ctx_factory):
    """python-pptx gives XY_SCATTER a noFill line because a scatter is points only.
    Theming the stroke anyway made it identical to xy-scatter-lines."""
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="xy-scatter",
        categories=(),
        series=(Series(name="S", points=((1.0, 4.5), (2.0, 8.1))),),
    )
    xml = etree.tostring(
        add_native_chart(ctx, spec, ctx.body_rect).chart.series[0]._element
    ).decode()
    line = xml.split("<a:ln")[1].split("</a:ln>")[0]
    assert "noFill" in line and "solidFill" not in line


def test_xy_scatter_and_xy_scatter_lines_differ(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    pts = ((1.0, 4.5), (2.0, 8.1))
    out = {}
    for kind in ("xy-scatter", "xy-scatter-lines"):
        spec = ChartSpec(type=kind, categories=(), series=(Series(name="S", points=pts),))
        xml = etree.tostring(
            add_native_chart(ctx, spec, ctx.body_rect).chart.series[0]._element
        ).decode()
        out[kind] = xml.split("<c:spPr>")[1].split("</c:spPr>")[0]
    assert out["xy-scatter"] != out["xy-scatter-lines"]


@pytest.mark.parametrize("chart_type", ["area", "area-stacked", "area-stacked-100", "radar-filled"])
def test_a_series_shaped_fill_gradients_on_the_series(ctx_factory, theme, chart_type):
    """An area band and a filled radar are one shape across every category — a per-point
    gradient lands on shapes the renderer never draws, so these looked flat."""
    styled = dataclasses.replace(theme, chart=dataclasses.replace(theme.chart, gradient=True))
    ctx = ctx_factory({"title": "T"}, theme_override=styled)
    spec = ChartSpec(
        type=chart_type,
        categories=("A", "B", "C"),
        series=(Series(name="S", values=(3.0, 6.0, 4.0)),),
    )
    ser = add_native_chart(ctx, spec, ctx.body_rect).chart.series[0]
    spPr = etree.tostring(ser._element).decode().split("<c:spPr>")[1].split("</c:spPr>")[0]
    assert "gradFill" in spPr


def test_a_bar_still_gradients_per_point_not_per_series(ctx_factory, theme):
    """Each bar is its own shape, so the gradient belongs on the point."""
    styled = dataclasses.replace(theme, chart=dataclasses.replace(theme.chart, gradient=True))
    ctx = ctx_factory({"title": "T"}, theme_override=styled)
    spec = ChartSpec(
        type="column", categories=("A", "B"), series=(Series(name="S", values=(3.0, 6.0)),)
    )
    xml = etree.tostring(
        add_native_chart(ctx, spec, ctx.body_rect).chart.series[0]._element
    ).decode()
    series_spPr = xml.split("<c:spPr>")[1].split("</c:spPr>")[0]
    assert "gradFill" not in series_spPr
    assert "gradFill" in xml.split("<c:dPt>", 1)[1]


@pytest.mark.parametrize(
    "chart_type", ["column-stacked-100", "bar-stacked-100", "line-stacked-100", "area-stacked-100"]
)
def test_a_hundred_percent_type_ignores_a_redundant_unit(ctx_factory, theme, chart_type):
    """The type already renders percentages; a series unit of "%" prints a second sign."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type=chart_type,
        categories=("A", "B"),
        series=(
            Series(name="S", values=(60.0, 40.0), unit="%"),
            Series(name="T", values=(40.0, 60.0), unit="%"),
        ),
    )
    labels = add_native_chart(ctx, spec, ctx.body_rect).chart.plots[0].data_labels
    # Paired with something `_style_data_labels` writes unconditionally: the absence
    # assertion alone stays green when that function returns immediately.
    assert labels.font.bold is True
    assert labels.number_format == "General"


def test_a_normal_type_still_honours_its_unit(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="column",
        categories=("A", "B"),
        series=(Series(name="S", values=(60.0, 40.0), unit="%"),),
    )
    labels = add_native_chart(ctx, spec, ctx.body_rect).chart.plots[0].data_labels
    assert '"%"' in labels.number_format


def test_a_one_accent_palette_refuses_to_paint_a_highlight(
    ctx_factory, theme, chart_spec_highlighted
):
    """No theme YAML can reach this: ``theme/blocks.py`` always carries accent-1..4. The
    library-consumer path — a Palette built in Python — can."""
    palette = build_palette(
        {
            "page": "FFFFFF",
            "ink": "2D0937",
            "muted": "573C65",
            "line": "EDEDED",
            "surface": "F5F6F8",
            "surface-ink": "2D0937",
            "inverse": "2D0937",
            "inverse-ink": "FFFFFF",
            "accent-1": "27B94C",
        },
        pairs={
            "page": ("ink", "page"),
            "surface": ("surface-ink", "surface"),
            "inverse": ("inverse-ink", "inverse"),
        },
    )
    ctx = ctx_factory({"title": "T"}, theme_override=dataclasses.replace(theme, palette=palette))

    with pytest.raises(ThemeError, match="declares 1 accent role"):
        add_native_chart(ctx, chart_spec_highlighted, ctx.body_rect)


def test_a_one_accent_palette_still_paints_a_chart_that_asked_for_no_highlight(
    ctx_factory, theme, chart_spec
):
    """The refusal above is about `highlight:`, not about short palettes. Resolving the
    highlight colour for every chart would let it refuse a chart nobody marked."""
    palette = build_palette(
        {
            "page": "FFFFFF",
            "ink": "2D0937",
            "muted": "573C65",
            "line": "EDEDED",
            "surface": "F5F6F8",
            "surface-ink": "2D0937",
            "inverse": "2D0937",
            "inverse-ink": "FFFFFF",
            "accent-1": "27B94C",
        },
        pairs={
            "page": ("ink", "page"),
            "surface": ("surface-ink", "surface"),
            "inverse": ("inverse-ink", "inverse"),
        },
    )
    ctx = ctx_factory({"title": "T"}, theme_override=dataclasses.replace(theme, palette=palette))

    chart = add_native_chart(ctx, chart_spec, ctx.body_rect).chart

    assert str(chart.series[0].format.fill.fore_color.rgb) == "27B94C"


def test_a_bubble_keeps_the_size_that_is_its_third_dimension(ctx_factory):
    """Size is the only reason to choose a bubble over a scatter, so it must survive."""
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="bubble",
        categories=(),
        series=(Series(name="s", points=((1.0, 10.0, 4.0), (2.0, 20.0, 9.0), (3.0, 30.0, 6.0))),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    xml = etree.tostring(chart._chartSpace).decode()
    sizes = xml.split("<c:bubbleSize>")[1].split("</c:bubbleSize>")[0]
    assert ["4" in sizes, "9" in sizes, "6" in sizes] == [True, True, True]


def test_a_currency_unit_prefixes_the_data_labels(ctx_factory, theme):
    """`$900`, not `900$` — a currency sign reads before the number."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column",
        categories=("Q1",),
        series=(Series(name="Budget", values=(900.0,), unit="$"),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].data_labels.number_format == '"$"0'


def test_a_decimal_series_keeps_its_places_in_the_data_labels(ctx_factory, theme):
    """The bug this fixes: 11.2 and 9.6 both printed as whole numbers, and a refund
    rate of 5.1 against 4.8 collapsed into two identical labels."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column",
        categories=("W1", "W2", "W3", "W4"),
        series=(Series(name="Refunds", values=(11.2, 9.6, 5.1, 4.8), unit="%"),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].data_labels.number_format == '0.0"%"'


def test_whole_numbers_get_no_decimal_point(ctx_factory, theme):
    """ "General" is python-pptx's untouched state: inference found nothing to write.
    A spurious place would make this "0.0"."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column",
        categories=("Atlas", "Beacon"),
        series=(Series(name="Tickets", values=(6140.0, 6930.0)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].data_labels.number_format == "General"


def test_decimals_overrides_what_the_data_would_infer(ctx_factory, theme):
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column",
        categories=("W1", "W2"),
        series=(Series(name="Refunds", values=(11.25, 9.6), unit="%"),),
        decimals=1,
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].data_labels.number_format == '0.0"%"'


def test_decimals_zero_forces_whole_numbers_back(ctx_factory, theme):
    """The escape hatch for a noisy series: the author asked for no places at all."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column",
        categories=("W1", "W2"),
        series=(Series(name="Refunds", values=(11.2, 9.6), unit="%"),),
        decimals=0,
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].data_labels.number_format == '0"%"'


def test_a_series_that_asked_for_no_labels_writes_its_own_show_val_off(ctx_factory):
    """Plot-level data labels are all-or-nothing; only the series' own `c:dLbls` dissents."""
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec(
        type="line-markers",
        categories=("W1", "W2", "W3"),
        series=(
            Series(name="Ours", values=(11.2, 9.6, 5.1), unit="%"),
            Series(name="Platform average", values=(7.0, 7.0, 7.0), unit="%", labels=False),
        ),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].has_data_labels is True
    assert chart.series[0]._element.find(qn("c:dLbls")) is None
    reference = chart.series[1]._element.find(qn("c:dLbls"))
    assert reference is not None
    assert reference.find(qn("c:showVal")).get("val") == "0"


def test_a_unit_reaches_the_value_axis_as_well_as_the_labels(ctx_factory, theme):
    """The axis read 0-12 while every label on the line read 11.2% — the scale and the
    values it framed disagreed about what the numbers were."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="line",
        categories=("Jan", "Feb", "Mar", "Apr"),
        series=(Series(name="Refunds", values=(11.2, 9.6, 5.1, 4.8), unit="%"),),
    )
    ticks = add_native_chart(ctx, spec, ctx.body_rect).chart.value_axis.tick_labels
    assert ticks.number_format == '0.0"%"'
    assert ticks.number_format_is_linked is False


def test_a_currency_unit_prefixes_the_value_axis_too(ctx_factory, theme):
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column",
        categories=("Q1", "Q2"),
        series=(Series(name="Budget", values=(900.0, 1200.0), unit="$"),),
    )
    ticks = add_native_chart(ctx, spec, ctx.body_rect).chart.value_axis.tick_labels
    assert ticks.number_format == '"$"0'


def test_a_chart_with_no_unit_leaves_its_value_axis_automatic(ctx_factory, theme):
    """The ticks are the renderer's to choose; only the unit is something it cannot know.
    Pinning a format here would print 12.0 for a tick of 12."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column",
        categories=("Q1", "Q2"),
        series=(Series(name="Tickets", values=(11.2, 9.6)),),
    )
    axis = add_native_chart(ctx, spec, ctx.body_rect).chart.value_axis
    # Paired with something `_style_axes` writes unconditionally, so the absence
    # assertion cannot stay green on a function that returned early.
    assert axis.has_minor_gridlines is False
    assert axis.tick_labels.number_format == "General"


def test_a_hundred_percent_type_keeps_its_percent_axis_over_a_redundant_unit(ctx_factory, theme):
    """`0%` is the share the renderer computed. A decimal in the data is what makes the
    unit branch produce a code at all, so that is what a wrong branch order would use."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column-stacked-100",
        categories=("A", "B"),
        series=(
            Series(name="S", values=(60.5, 39.5), unit="%"),
            Series(name="T", values=(39.5, 60.5), unit="%"),
        ),
    )
    ticks = add_native_chart(ctx, spec, ctx.body_rect).chart.value_axis.tick_labels
    assert ticks.number_format == "0%"


def _plot_box(chart):
    layout = chart._chartSpace.find(qn("c:chart")).find(qn("c:plotArea")).find(qn("c:layout"))
    manual = layout.find(qn("c:manualLayout"))
    return float(manual.find(qn("c:x")).get("val")), float(manual.find(qn("c:w")).get("val"))


def test_a_bar_chart_with_a_legend_leaves_the_legend_a_column(ctx_factory, theme):
    """The plot ran to 98% of the frame whatever the legend needed, so the legend was
    drawn over the bars and its longest name clipped."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="bar-stacked-100",
        categories=("Enterprise", "Small business"),
        series=(
            Series(name="Resolved within one business day", values=(62.0, 81.0)),
            Series(name="Escalated to engineering", values=(38.0, 19.0)),
        ),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    x, w = _plot_box(chart)
    assert 1.0 - (x + w) > 0.15  # a real column, not the bare 2% frame margin
    assert chart.legend.include_in_layout is False


def test_a_single_series_bar_chart_still_uses_the_full_width(ctx_factory, theme):
    """No legend, so nothing to reserve — the plot keeps everything but the margin."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="bar",
        categories=("Enterprise", "Small business"),
        series=(Series(name="Resolved", values=(62.0, 81.0)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    x, w = _plot_box(chart)
    assert 1.0 - (x + w) == pytest.approx(0.02)


def test_a_long_category_and_a_long_series_name_still_leave_the_bars_room(ctx_factory, theme):
    """Both columns come out of one budget, so neither can squeeze the plot away."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="bar-stacked-100",
        categories=("An extremely long category label that runs on and on",),
        series=(
            Series(name="A series name that is also absurdly long indeed", values=(62.0,)),
            Series(name="Another very long series name for good measure", values=(38.0,)),
        ),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    _, w = _plot_box(chart)
    assert w >= 0.45


def test_a_stacked_100_chart_keeps_its_decimal_places(ctx_factory, theme):
    """The axis shows the computed share; each label still prints its own series value.
    Excluding these kinds from inference reproduced the exact collapse — 11.2 and 88.8
    labelled 11 and 89."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="bar-stacked-100",
        categories=("A", "B"),
        series=(
            Series(name="Resolved", values=(11.2, 9.6)),
            Series(name="Escalated", values=(88.8, 90.4)),
        ),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].data_labels.number_format == "0.0"


def test_a_non_bar_legend_goes_under_the_plot(ctx_factory, theme):
    """Only the bar family reserves a side column for it; everywhere else a mid-right
    legend takes a quarter of the width and crowds the plot."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="column",
        categories=("Atlas", "Beacon"),
        series=(
            Series(name="Direct signups", values=(6140.0, 6930.0)),
            Series(name="Partner referrals", values=(3070.0, 2410.0)),
        ),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.legend.position == XL_LEGEND_POSITION.BOTTOM


def test_a_bar_legend_keeps_its_own_column(ctx_factory, theme):
    """Its plot area is pinned by hand, so a bottom legend would waste the column the
    manual layout already measured."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="bar",
        categories=("Atlas", "Beacon"),
        series=(Series(name="One", values=(1.0, 2.0)), Series(name="Two", values=(3.0, 4.0))),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.legend.position != XL_LEGEND_POSITION.BOTTOM


@pytest.mark.parametrize(
    "chart_type,expected",
    [
        # `inEnd` is a position only the bar family and a pie offer.
        ("column", "inEnd"),
        ("bar", "inEnd"),
        ("pie", "inEnd"),
        # These groups offer none; a `c:dLblPos` in one is what asks to repair the file.
        ("doughnut", None),
        ("area", None),
        ("radar", None),
        ("radar-filled", None),
        ("radar-markers", None),
        # A line has its own position and keeps it rather than taking an illegal one.
        ("line-markers", "t"),
    ],
)
def test_a_theme_position_is_written_only_where_the_chart_group_offers_it(
    ctx_factory, theme, chart_type, expected
):
    """`label_position: inside_end` is authorable on any theme, and it was written into
    every kind — including the groups PowerPoint offers no position for at all."""
    styled = dataclasses.replace(
        theme, chart=ChartStyle(thousands_sep=False, label_position="inside_end")
    )
    ctx = ctx_factory({"title": "T"}, theme_override=styled)
    spec = ChartSpec(
        type=chart_type,
        categories=("W1", "W2", "W3"),
        series=(Series(name="Ours", values=(11.2, 9.6, 5.1)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    xml = etree.tostring(chart._chartSpace, encoding="unicode")
    found = re.findall(r'<c:dLblPos val="(\w+)"', xml)
    assert found == ([expected] if expected else [])


@pytest.mark.parametrize("chart_type", ("radar", "radar-filled", "radar-markers"))
def test_a_radar_series_carries_no_smooth(ctx_factory, theme, chart_type):
    """python-pptx writes `c:smooth` for every connected kind, but `CT_RadarSer` has no
    such child and a radar part carrying it does not validate."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type=chart_type,
        categories=("W1", "W2", "W3"),
        series=(Series(name="Ours", values=(11.2, 9.6, 5.1)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert "smooth" not in etree.tostring(chart._chartSpace, encoding="unicode")


def test_a_line_series_keeps_its_smooth(ctx_factory, theme):
    """The strip is scoped to radar: a line chart's own `c:smooth` is legal and load-bearing."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="line-markers",
        categories=("W1", "W2"),
        series=(Series(name="Ours", values=(1.0, 2.0)),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert "smooth" in etree.tostring(chart._chartSpace, encoding="unicode")


def test_a_line_chart_sets_its_labels_above_the_marker(ctx_factory, theme):
    """`outside_end` has no meaning on a line: it lands the label on the point it names,
    which is how 11.2%, 5.1% and 4.8% all ended up drawn through the line."""
    ctx = _plain_ctx(ctx_factory, theme)
    spec = ChartSpec(
        type="line-markers",
        categories=("W1", "W2"),
        series=(Series(name="Ours", values=(11.2, 9.6), unit="%"),),
    )
    chart = add_native_chart(ctx, spec, ctx.body_rect).chart
    assert chart.plots[0].data_labels.position == XL_DATA_LABEL_POSITION.ABOVE
