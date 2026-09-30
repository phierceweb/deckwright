"""A chart's kind and data, read back out of the cached values in its chart part."""

from __future__ import annotations

from typing import Any

from deckwright.charts._native_types import _CHART_TYPES

_KIND_OF = {chart_type: kind for kind, chart_type in _CHART_TYPES.items()}
_POINTS = ("xy-", "bubble")


def chart_block(shape) -> tuple[dict[str, Any] | None, str | None]:
    """The ``chart:`` mapping ``shape``'s chart is drawn from, or why it cannot be read back.

    Only the kind and the data: labels, axis bounds and a highlight are the build's choices,
    and they are left to the author.
    """
    chart = shape.chart
    kind = _KIND_OF.get(chart.chart_type)
    if kind is None:
        return None, f"a {chart.chart_type} chart, which deckwright has no kind for"
    if kind.startswith(_POINTS):
        return None, f"a {kind} chart, whose points are not read back"
    plot = chart.plots[0]
    categories = [str(c) for c in plot.categories]
    series = list(plot.series)
    values = [list(s.values) for s in series]
    names = [str(s.name or f"Series {i + 1}") for i, s in enumerate(series)]
    if not categories or not series or any(len(v) != len(categories) for v in values):
        return None, "a chart whose cached values do not cover its categories"
    if any(v is None for column in values for v in column):
        return None, "a chart with an empty value"
    if len(set(names)) < len(names):
        return None, "a chart whose series share a name"
    data: list[dict[str, Any]]
    if len(series) == 1:
        data = [
            {"category": c, "value": _number(v)} for c, v in zip(categories, values[0], strict=True)
        ]
    else:
        data = [
            {
                "category": c,
                "values": {n: _number(column[i]) for n, column in zip(names, values, strict=True)},
            }
            for i, c in enumerate(categories)
        ]
    return {"kind": kind, "data": data}, None


def _number(value: float) -> float | int:
    return int(value) if float(value).is_integer() else value
