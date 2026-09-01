"""The table exercises: one slide per shape a real table takes."""

from __future__ import annotations

from typing import Any


def table_slides() -> dict[str, dict[str, Any]]:
    """Every exercise in this family, keyed by name."""
    return {
        "table": {
            "title": "A table of rows",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 10}, "rows": "top-half"},
                    "table": {
                        "header": ["Item", "Where", "Count"],
                        "align": ["left", "left", "right"],
                        "widths": [2, 2, 1],
                        "rows": [
                            ["The first thing", "On the left", "12"],
                            ["The second thing", "In the middle", "34"],
                            ["The third thing", "On the right", "58"],
                        ],
                    },
                }
            ],
        },
        "table-spanned": {
            "title": "A header that spans, a total that rules",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 10}, "rows": "top-two-thirds"},
                    "table": {
                        "header": [
                            "Workstream",
                            {"text": "Effort", "across": 2, "align": "center"},
                            "Owner",
                        ],
                        "align": ["left", "center", "center", "left"],
                        "widths": [3, 1, 1, 1.4],
                        "rows": [
                            ["Spec and schema", "12", "8", "Compiler"],
                            ["Placement engine", "21", "14", "Layout"],
                        ],
                        "total": [{"text": "Total", "emphasis": True}, "33", "22", ""],
                    },
                }
            ],
        },
        "table-banded": {
            "title": "Banded rows and a marked cell",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 11}, "rows": "top-two-thirds"},
                    "table": {
                        "banding": True,
                        "header": ["Option", "Cost", "Risk", "Verdict"],
                        "align": ["left", "right", "center", "center"],
                        "rows": [
                            ["Rebuild", "120", "High", "No"],
                            [
                                "Extend",
                                "38",
                                "Low",
                                {"text": "Recommended", "pair": "accent-1", "emphasis": True},
                            ],
                            ["Buy", "64", "Medium", "No"],
                        ],
                    },
                }
            ],
        },
        "table-grid": {
            "title": "A grid whose labels reach down",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 11}, "rows": "top-two-thirds"},
                    "table": {
                        "rules": "grid",
                        "valign": "top",
                        "header": ["Stage", "Step", "Owner", "Days"],
                        "align": ["left", "left", "left", "right"],
                        "widths": [2, 3.4, 1.6, 1],
                        "rows": [
                            [
                                {
                                    "text": "Discovery",
                                    "down": 2,
                                    "valign": "middle",
                                    "emphasis": True,
                                },
                                "Interviews and a read of what exists",
                                "Ana",
                                "6",
                            ],
                            ["A written brief either side can argue with", "Ana", "3"],
                            [
                                {"text": "Build", "down": 2, "valign": "middle", "emphasis": True},
                                "The first slice, end to end",
                                "Bo",
                                "14",
                            ],
                            ["Everything the first slice deferred", "Bo", "9"],
                        ],
                    },
                }
            ],
        },
        "table-dense": {
            "title": "Unruled rows, tightened",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 10}, "rows": {"from": 0, "to": 7}},
                    "table": {
                        "rules": "none",
                        "density": 0.6,
                        "banding": True,
                        "header": ["Region", "Q1", "Q2", "Q3", "Q4"],
                        "align": ["left", "right", "right", "right", "right"],
                        "rows": [
                            ["Northern", "520", "610", "588", "640"],
                            ["Southern", "310", "356", "402", "418"],
                            ["Eastern", "180", "204", "196", "232"],
                            ["Western", "170", "170", "184", "190"],
                        ],
                        "total": [
                            {"text": "Total", "emphasis": True},
                            "1,180",
                            "1,340",
                            "1,370",
                            "1,480",
                        ],
                    },
                }
            ],
        },
        "table-stacked": {
            "title": "Two columns reaching down beside one that does not",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 9}, "rows": {"from": 0, "to": 7}},
                    "table": {
                        "rules": "header",
                        "valign": "top",
                        "density": 0.7,
                        "header": ["Phase", "What it covers", "Who"],
                        "widths": [1.4, 4, 1.2],
                        "rows": [
                            [
                                {
                                    "text": "Discovery",
                                    "down": 2,
                                    "valign": "middle",
                                    "emphasis": True,
                                },
                                {
                                    "text": "Interviews, a read of what exists, "
                                    "and a brief either side can argue with",
                                    "down": 2,
                                    "valign": "middle",
                                },
                                "Ana",
                            ],
                            ["Bea"],
                            ["Build", "The first slice, end to end", "Bo"],
                        ],
                    },
                }
            ],
        },
        "table-inverse": {
            "title": "A table on the dark side",
            "background": "inverse",
            "place": [
                {
                    "at": {"cols": "left-two-thirds", "rows": {"from": 0, "to": 5}},
                    "table": {"rows": [["No header here", "12"], ["Just body rows", "34"]]},
                }
            ],
        },
    }
