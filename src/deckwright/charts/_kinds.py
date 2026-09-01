"""The chart-kind vocabulary: which kinds exist, and what each one accepts.

Renderer-agnostic — no python-pptx here. The enum tables that map these names
onto OOXML live in ``charts/_native_types.py``.
"""

from __future__ import annotations

_TYPES = (
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
# A point is an (x, y) pair — no categories; the x-value lives in the point itself.
_XY_CHART_TYPES = frozenset(
    {
        "xy-scatter",
        "xy-scatter-lines",
        "xy-scatter-lines-no-markers",
        "xy-scatter-smooth",
        "xy-scatter-smooth-no-markers",
    }
)
# A point is an (x, y, size) triple — no categories; size must be positive to render.
_BUBBLE_CHART_TYPES = frozenset({"bubble", "bubble-3d"})
_CHART_KEYS = ("kind", "data", "unit", "decimals", "labels", "y_min", "y_max")
# A category build needs each category to be a mark of its own. A radar's categories are
# vertices of one closed outline, so the build would emit clicks that move nothing.
_BUILDABLE_BY_CATEGORY = frozenset(
    {
        "bar",
        "column",
        "column-stacked",
        "column-stacked-100",
        "bar-stacked",
        "bar-stacked-100",
        "pie",
        "doughnut",
        "pie-exploded",
        "doughnut-exploded",
        "line",
        "line-markers",
        "line-stacked",
        "line-stacked-100",
        "line-markers-stacked",
        "line-markers-stacked-100",
        "area",
        "area-stacked",
        "area-stacked-100",
    }
)

_HIGHLIGHTABLE_KINDS = frozenset(
    {
        "bar",
        "column",
        "column-stacked",
        "column-stacked-100",
        "bar-stacked",
        "bar-stacked-100",
        "pie",
        "doughnut",
        "pie-exploded",
        "doughnut-exploded",
        "bubble",
        "bubble-3d",
    }
)

_CATEGORY_ROW_KEYS = ("category", "values", "value", "highlight")
_XY_ROW_KEYS = ("x", "y", "highlight")
_BUBBLE_ROW_KEYS = ("x", "y", "size", "highlight")
_LEGACY_CHART_KEYS = {
    "type": "'type' is gone — a chart's type is now 'kind', e.g. kind: column-stacked",
    "categories": (
        "'categories' is gone — each category is a row in 'data', e.g. "
        "data: [{category: Q1, values: {Ads: 20, Organic: 15}}, ...]"
    ),
    "series": (
        "'series' is gone — series names are the keys of each row's 'values' mapping in "
        "'data', e.g. data: [{category: Q1, values: {Ads: 20, Organic: 15}}, ...]"
    ),
    "highlight": (
        "'highlight' is gone as a top-level index — it's now per-row: set "
        "'highlight: true' on the row you want highlighted"
    ),
    "annotate": (
        "'annotate' is gone — it was validated but no renderer ever drew it. For a "
        "callout on one point, place a 'callouts' or 'prose' beside the chart"
    ),
}
