"""The running-text exercises: lists, columns, cards and figures set as copy."""

from __future__ import annotations

from typing import Any


def text_slides() -> dict[str, dict[str, Any]]:
    """Every exercise in this family, keyed by name."""
    return {
        "bullets": {
            "title": "A list of points",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 7}},
                    "bullets": {
                        "items": [
                            "The first point",
                            "The second point, [with a link](https://example.com/point)",
                            "The third point",
                        ]
                    },
                }
            ],
        },
        "two-column": {
            "title": "Two things side by side",
            "place": [
                {"at": {"cols": "left-half"}, "bullets": {"items": ["Left", "Column"]}},
                {"at": {"cols": "right-half"}, "bullets": {"items": ["Right", "Column"]}},
            ],
        },
        "cards": {
            "title": "Three cards across",
            "place": [
                {
                    "at": {"cols": "left-third", "rows": {"from": 0, "to": 5}},
                    "card": {"heading": "One", "body": "A plate with a heading and a line."},
                },
                {
                    "at": {"cols": "mid-third", "rows": {"from": 0, "to": 5}},
                    "card": {"heading": "Two", "body": "The same again, beside it."},
                },
                {
                    "at": {"cols": "right-third", "rows": {"from": 0, "to": 5}},
                    "card": {
                        "heading": "Three",
                        "body": "And a third, [to fill the row](https://example.com/row).",
                    },
                },
            ],
        },
        "stats": {
            "title": "Numbers worth reading",
            "place": [
                {
                    "at": {"cols": "full", "rows": "top-third"},
                    "stats": {
                        "items": [
                            {"value": "42", "label": "first measure"},
                            {"value": "68", "label": "second measure"},
                            {"value": "91", "label": "third measure"},
                        ]
                    },
                }
            ],
        },
    }
