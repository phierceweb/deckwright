"""Every creatable chart kind, with the data shape each one demands."""

from __future__ import annotations

from typing import Any

from deckwright.charts.model import _BUBBLE_CHART_TYPES, _XY_CHART_TYPES
from deckwright.charts.native import _CHART_TYPES

CATEGORY_ROWS: list[dict[str, Any]] = [
    {"category": "Q1", "value": 12},
    {"category": "Q2", "value": 34},
    {"category": "Q3", "value": 58},
    {"category": "Q4", "value": 91},
]
_XY_ROWS = [{"x": 1, "y": 12}, {"x": 2, "y": 34}, {"x": 3, "y": 58}, {"x": 4, "y": 91}]
_BUBBLE_ROWS = [
    {"x": 1, "y": 12, "size": 4},
    {"x": 2, "y": 34, "size": 9},
    {"x": 3, "y": 58, "size": 6},
]


def chart_slides() -> dict[str, dict[str, Any]]:
    """Every exercise in this family, keyed by name."""
    out = {}
    for kind in sorted(_CHART_TYPES):
        rows = (
            _BUBBLE_ROWS
            if kind in _BUBBLE_CHART_TYPES
            else _XY_ROWS
            if kind in _XY_CHART_TYPES
            else CATEGORY_ROWS
        )
        out[f"chart-{kind}"] = {
            "title": f"A {kind} chart",
            "place": [
                {
                    "at": {"cols": "full", "rows": {"from": 0, "to": 9}},
                    "chart": {"kind": kind, "data": [dict(r) for r in rows]},
                }
            ],
        }
    return out


def chart_legend_slides() -> dict[str, dict[str, Any]]:
    """Two series on kinds whose legend and labels have to clear the plot."""
    return {
        "chart-line-two-series": {
            "title": "A line chart whose labels clear their markers",
            "place": [
                {
                    "at": {"cols": "full", "rows": "top-two-thirds"},
                    "chart": {
                        "kind": "line-markers",
                        "unit": "%",
                        "data": [
                            {"category": "W1", "values": {"Ours": 11.2, "Platform average": 7.0}},
                            {"category": "W2", "values": {"Ours": 9.6, "Platform average": 7.0}},
                            {"category": "W3", "values": {"Ours": 5.1, "Platform average": 7.0}},
                        ],
                    },
                }
            ],
        },
        "chart-reference-series": {
            "title": "A reference line that does not repeat its own number",
            "place": [
                {
                    "at": {"cols": "full", "rows": "top-two-thirds"},
                    "chart": {
                        "kind": "line-markers",
                        "unit": "%",
                        "labels": {"Platform average": False},
                        "data": [
                            {"category": "W1", "values": {"Ours": 11.2, "Platform average": 7.0}},
                            {"category": "W2", "values": {"Ours": 9.6, "Platform average": 7.0}},
                            {"category": "W3", "values": {"Ours": 5.1, "Platform average": 7.0}},
                            {"category": "W4", "values": {"Ours": 4.8, "Platform average": 7.0}},
                        ],
                    },
                }
            ],
        },
        "chart-column-two-series": {
            "title": "A clustered column chart with a legend",
            "place": [
                {
                    "at": {"cols": "full", "rows": "top-two-thirds"},
                    "chart": {
                        "kind": "column",
                        "data": [
                            {"category": "Atlas", "values": {"Direct": 6140, "Partner": 3070}},
                            {"category": "Beacon", "values": {"Direct": 6930, "Partner": 2410}},
                        ],
                    },
                }
            ],
        },
    }


def chart_intro_slides() -> dict[str, dict[str, Any]]:
    """The chart slides the corpus meets first: one per common shape."""
    return {
        "chart-column": {
            "title": "A column chart",
            "place": [
                {
                    "at": {"cols": "full", "rows": "top-two-thirds"},
                    "chart": {
                        "kind": "column",
                        "data": [
                            {"category": "Q1", "value": 12},
                            {"category": "Q2", "value": 34},
                            {"category": "Q3", "value": 58},
                            {"category": "Q4", "value": 91, "highlight": True},
                        ],
                    },
                }
            ],
        },
        "chart-bar-pct": {
            "title": "A bar chart in per cent",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 10}, "rows": "top-half"},
                    "chart": {
                        "kind": "bar",
                        "unit": "%",
                        "data": [
                            {"category": "Remote", "value": 18},
                            {"category": "Urban", "value": 36},
                            {"category": "Suburban", "value": 52},
                            {"category": "Rural", "value": 64, "highlight": True},
                        ],
                    },
                }
            ],
        },
        "chart-stacked-100-legend": {
            "title": "A stacked bar whose legend needs its own column",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 10}, "rows": "top-half"},
                    "chart": {
                        "kind": "bar-stacked-100",
                        "data": [
                            {
                                "category": "Enterprise",
                                "values": {
                                    "Resolved within one business day": 62,
                                    "Escalated to engineering": 38,
                                },
                            },
                            {
                                "category": "Small business",
                                "values": {
                                    "Resolved within one business day": 81,
                                    "Escalated to engineering": 19,
                                },
                            },
                        ],
                    },
                }
            ],
        },
        "chart-decimals": {
            "title": "A rate chart that needs its decimal place",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 10}, "rows": "top-half"},
                    "chart": {
                        "kind": "column",
                        "unit": "%",
                        "data": [
                            {"category": "W1", "value": 11.2},
                            {"category": "W2", "value": 9.6},
                            {"category": "W3", "value": 5.1},
                            {"category": "W4", "value": 4.8, "highlight": True},
                        ],
                    },
                }
            ],
        },
    }
