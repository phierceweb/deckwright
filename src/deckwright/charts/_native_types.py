"""Per-kind lookup tables for the python-pptx renderer.

Maps the kind names in ``charts/_kinds.py`` onto OOXML enums, and records which
kinds accept each styling treatment — markers, gap width, percent axes, fills.
"""

from __future__ import annotations

from pptx.enum.chart import XL_CHART_TYPE, XL_DATA_LABEL_POSITION, XL_MARKER_STYLE

_CHART_TYPES: dict[str, XL_CHART_TYPE] = {
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "column-stacked": XL_CHART_TYPE.COLUMN_STACKED,
    "column-stacked-100": XL_CHART_TYPE.COLUMN_STACKED_100,
    "bar-stacked": XL_CHART_TYPE.BAR_STACKED,
    "bar-stacked-100": XL_CHART_TYPE.BAR_STACKED_100,
    "line": XL_CHART_TYPE.LINE,
    "line-markers": XL_CHART_TYPE.LINE_MARKERS,
    "line-stacked": XL_CHART_TYPE.LINE_STACKED,
    "line-stacked-100": XL_CHART_TYPE.LINE_STACKED_100,
    "line-markers-stacked": XL_CHART_TYPE.LINE_MARKERS_STACKED,
    "line-markers-stacked-100": XL_CHART_TYPE.LINE_MARKERS_STACKED_100,
    "area": XL_CHART_TYPE.AREA,
    "area-stacked": XL_CHART_TYPE.AREA_STACKED,
    "area-stacked-100": XL_CHART_TYPE.AREA_STACKED_100,
    "radar": XL_CHART_TYPE.RADAR,
    "radar-filled": XL_CHART_TYPE.RADAR_FILLED,
    "radar-markers": XL_CHART_TYPE.RADAR_MARKERS,
    "pie": XL_CHART_TYPE.PIE,
    "doughnut": XL_CHART_TYPE.DOUGHNUT,
    "pie-exploded": XL_CHART_TYPE.PIE_EXPLODED,
    "doughnut-exploded": XL_CHART_TYPE.DOUGHNUT_EXPLODED,
    "xy-scatter": XL_CHART_TYPE.XY_SCATTER,
    "xy-scatter-lines": XL_CHART_TYPE.XY_SCATTER_LINES,
    "xy-scatter-lines-no-markers": XL_CHART_TYPE.XY_SCATTER_LINES_NO_MARKERS,
    "xy-scatter-smooth": XL_CHART_TYPE.XY_SCATTER_SMOOTH,
    "xy-scatter-smooth-no-markers": XL_CHART_TYPE.XY_SCATTER_SMOOTH_NO_MARKERS,
    "bubble": XL_CHART_TYPE.BUBBLE,
    "bubble-3d": XL_CHART_TYPE.BUBBLE_THREE_D_EFFECT,
}
# Pie/doughnut/pie-exploded/doughnut-exploded carry no category/value axis in the
# OOXML — styling them raises ValueError.
_AXIS_CHART_TYPES = frozenset(
    {
        "bar",
        "column",
        "column-stacked",
        "column-stacked-100",
        "bar-stacked",
        "bar-stacked-100",
        "line",
        "line-markers",
        "line-stacked",
        "line-stacked-100",
        "line-markers-stacked",
        "line-markers-stacked-100",
        "area",
        "area-stacked",
        "area-stacked-100",
        "radar",
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
)
# LinePlot/AreaPlot/PiePlot/DoughnutPlot/RadarPlot expose no gap_width in python-pptx —
# only the bar/column family does.
_GAP_WIDTH_CHART_TYPES = frozenset(
    {
        "bar",
        "column",
        "column-stacked",
        "column-stacked-100",
        "bar-stacked",
        "bar-stacked-100",
    }
)
# One series, coloured per point, named by label rather than legend/axis.
_PIE_FAMILY_CHART_TYPES = frozenset({"pie", "doughnut", "pie-exploded", "doughnut-exploded"})
# Radar's major gridlines are the rings and spokes the data is plotted against, so they
# stay at their default instead of following theme.chart.grid.
_STRUCTURAL_GRIDLINE_CHART_TYPES = frozenset({"radar", "radar-filled", "radar-markers"})
# Set explicitly on all of them: area-stacked-100 otherwise leaves the format linked to
# the source data and renders 0.4 instead of 40%.
_PERCENT_AXIS_CHART_TYPES = frozenset(
    {
        "column-stacked-100",
        "bar-stacked-100",
        "line-stacked-100",
        "line-markers-stacked-100",
        "area-stacked-100",
    }
)
# python-pptx never wires up CT_ScatterChart's c:dLbls descriptor, so plot.has_data_labels
# raises AttributeError for every xy-scatter variant. Bubble is unaffected.
_NO_DATA_LABEL_CHART_TYPES = frozenset(
    {
        "xy-scatter",
        "xy-scatter-lines",
        "xy-scatter-lines-no-markers",
        "xy-scatter-smooth",
        "xy-scatter-smooth-no-markers",
    }
)
# "outside_end" leaves position unset: PowerPoint's own default. "none" is handled
# separately, by turning data labels off.
_LABEL_POSITIONS: dict[str, XL_DATA_LABEL_POSITION] = {
    "inside_end": XL_DATA_LABEL_POSITION.INSIDE_END,
}
# A line has no bar end to sit outside of, so `outside_end` lands the label on the point
# it names. Above the marker is the position that reads for the whole connected family.
_CONNECTED_LABEL_POSITION = XL_DATA_LABEL_POSITION.ABOVE
# The types whose series both exposes `.marker` and renders one. The rest carry an
# explicit `<c:symbol val="none"/>`, and CT_BubbleSer's schema has no marker child at all —
# forcing one there is a schema mismatch.
_MARKER_CHART_TYPES = frozenset(
    {
        "line-markers",
        "line-markers-stacked",
        "line-markers-stacked-100",
        "radar-markers",
        "xy-scatter",
        "xy-scatter-lines",
        "xy-scatter-smooth",
    }
)
# Every type drawn as a connected stroke. `xy-scatter` is excluded: theming its noFill
# line would make it identical to `xy-scatter-lines`.
_CONNECTED_CHART_TYPES = frozenset(set(_CHART_TYPES) - {"xy-scatter"})
_MARKER_STYLES: dict[str, XL_MARKER_STYLE] = {
    "circle": XL_MARKER_STYLE.CIRCLE,
    "square": XL_MARKER_STYLE.SQUARE,
    "diamond": XL_MARKER_STYLE.DIAMOND,
    "none": XL_MARKER_STYLE.NONE,
}
# A horizontal bar grows along x, so the theme's gradient angle — which means "down a
# column" — rotates a quarter turn or it crosses the bar's thin dimension and reads flat.
_HORIZONTAL_BAR_CHART_TYPES = frozenset({"bar", "bar-stacked", "bar-stacked-100"})
# One shape across every category, so gradient and shadow go on the series; applied
# per-point they land on shapes the renderer never draws.
_SERIES_FILL_CHART_TYPES = frozenset(
    {
        "area",
        "area-stacked",
        "area-stacked-100",
        "radar-filled",
    }
)
# A point here is a stroke and maybe a marker, with no fillable shape — a dPt/spPr
# gradient is invisible on all of them. Bubble is excluded: its point is a filled circle.
_STROKE_CHART_TYPES = frozenset(
    {
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
    }
)
# PowerPoint offers no data-label position on a radar plot, and a `c:dLblPos` written
# into one is what makes it ask to repair the file.
_RADAR_CHART_TYPES = frozenset({"radar", "radar-filled", "radar-markers"})
_POINT_LABEL_CHART_TYPES = _STROKE_CHART_TYPES - _RADAR_CHART_TYPES
# `inEnd` is a position only the bar family and a pie offer. Written into any other
# chart group it is the `c:dLblPos` PowerPoint asks to repair the file over — which a
# doughnut, an area, a line and a radar all are.
_INSIDE_END_CHART_TYPES = _GAP_WIDTH_CHART_TYPES | frozenset({"pie", "pie-exploded"})
