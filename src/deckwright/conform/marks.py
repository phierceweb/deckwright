"""The icon exercises: a glyph on its own, and beside other things.

A mark is drawn as real geometry rather than pasted as a picture, so every component
that can carry one is exercised carrying one.
"""

from __future__ import annotations

from typing import Any


def mark_slides() -> dict[str, dict[str, Any]]:
    """Every exercise in this family, keyed by name."""
    slides: dict[str, dict[str, Any]] = {}
    slides["icons"] = {
        "title": "Marks drawn as geometry",
        "place": [
            {"at": {"cols": {"from": 0, "to": 3}, "rows": "top-third"}, "icon": {"name": "target"}},
            {
                "at": {"cols": {"from": 3, "to": 6}, "rows": "top-third"},
                "icon": {"name": "chart-bar"},
            },
            {"at": {"cols": {"from": 6, "to": 9}, "rows": "top-third"}, "icon": {"name": "users"}},
            {"at": {"cols": {"from": 9, "to": 12}, "rows": "top-third"}, "icon": {"name": "globe"}},
        ],
    }
    slides["icon-sizes"] = {
        "title": "One mark at four sizes",
        "subtitle": "size: is a fraction of the placement's short side, not of the canvas",
        "place": [
            {
                "at": {"cols": {"from": 0, "to": 3}, "rows": "top-third"},
                "align": "center",
                "anchor": "middle",
                "icon": {"name": "target", "size": 0.4},
            },
            {
                "at": {"cols": {"from": 3, "to": 6}, "rows": "top-third"},
                "align": "center",
                "anchor": "middle",
                "icon": {"name": "target", "size": 0.6},
            },
            {
                "at": {"cols": {"from": 6, "to": 9}, "rows": "top-third"},
                "align": "center",
                "anchor": "middle",
                "icon": {"name": "target", "size": 0.8},
            },
            {
                "at": {"cols": {"from": 9, "to": 12}, "rows": "top-third"},
                "align": "center",
                "anchor": "middle",
                "icon": {"name": "target", "size": 1.0},
            },
            {
                "at": {"cols": {"from": 0, "to": 4}, "rows": "mid-third"},
                "icon": {"name": "chart-bar", "size": 0.5},
            },
            {
                "at": {"cols": {"from": 4, "to": 8}, "rows": "mid-third"},
                "align": "center",
                "anchor": "middle",
                "icon": {"name": "chart-bar", "size": 0.5},
            },
            {
                "at": {"cols": {"from": 8, "to": 12}, "rows": "mid-third"},
                "align": "right",
                "anchor": "bottom",
                "icon": {"name": "chart-bar", "size": 0.5},
            },
        ],
    }
    slides["cards-with-icons"] = {
        "title": "Three cards, each with its mark",
        "place": [
            {
                "at": {"cols": "left-third", "rows": "top-half"},
                "card": {
                    "icon": "shield",
                    "heading": "Secure",
                    "body": "A plate with a mark above its heading.",
                },
            },
            {
                "at": {"cols": "mid-third", "rows": "top-half"},
                "card": {"icon": "bolt", "heading": "Fast", "body": "The same again, beside it."},
            },
            {
                "at": {"cols": "right-third", "rows": "top-half"},
                "card": {
                    "icon": "globe",
                    "heading": "Everywhere",
                    "body": "And a third, to fill the row.",
                },
            },
        ],
    }
    slides["flow-with-icons"] = {
        "title": "A run of steps, each marked",
        "place": [
            {
                "at": {"cols": "full", "rows": "top-two-thirds"},
                "flow": {
                    "items": [
                        {"head": "Collect", "body": "Gather the inputs.", "icon": "folder"},
                        {"head": "Measure", "body": "Read what is there.", "icon": "chart-line"},
                        {"head": "Decide", "body": "Pick the direction.", "icon": "target"},
                    ]
                },
            }
        ],
    }
    slides["stats-with-icons"] = {
        "title": "Numbers, each with its mark",
        "place": [
            {
                "at": {"cols": "full", "rows": "top-half"},
                "stats": {
                    "items": [
                        {"value": "42", "label": "first measure", "icon": "users"},
                        {"value": "68", "label": "second measure", "icon": "globe"},
                        {"value": "91", "label": "third measure", "icon": "chart-line"},
                    ]
                },
            }
        ],
    }
    slides["callouts-with-icons"] = {
        "title": "A list marked by glyph, not by dot",
        "place": [
            {
                "at": {"cols": "left-two-thirds"},
                "callouts": {
                    "items": [
                        {"head": "Secure", "body": "Every request is checked.", "icon": "lock"},
                        {"head": "Fast", "body": "Answers land in milliseconds.", "icon": "bolt"},
                        {"head": "Measured", "body": "Nothing ships unread.", "icon": "chart-bar"},
                    ]
                },
            }
        ],
    }
    slides["icon-on-inverse"] = {
        "title": "A mark on the dark side",
        "background": "inverse",
        "place": [{"at": {"cols": "mid-third", "rows": "top-half"}, "icon": {"name": "lightbulb"}}],
    }
    slides["icons-vendored"] = {
        # Every route into the vendored set, and glyphs whose counters are the point.
        "title": "Marks from the vendored set",
        "place": [
            {
                "at": {"cols": {"from": 0, "to": 3}, "rows": "top-third"},
                "icon": {"name": "settings"},
            },
            {
                "at": {"cols": {"from": 3, "to": 6}, "rows": "top-third"},
                "icon": {"name": "rocket-launch"},
            },
            {
                "at": {"cols": {"from": 6, "to": 9}, "rows": "top-third"},
                "icon": {"name": "account_circle"},
            },
            {
                "at": {"cols": {"from": 9, "to": 12}, "rows": "top-third"},
                "icon": {"name": "deploy"},
            },
            {
                "at": {"cols": {"from": 0, "to": 3}, "rows": "mid-third"},
                "icon": {"name": "psychology"},
            },
            {
                "at": {"cols": {"from": 3, "to": 6}, "rows": "mid-third"},
                "icon": {"name": "looks_3"},
            },
            {
                "at": {"cols": {"from": 6, "to": 9}, "rows": "mid-third"},
                "icon": {"name": "chart-donut"},
            },
            {
                "at": {"cols": {"from": 9, "to": 12}, "rows": "mid-third"},
                "icon": {"name": "auto_awesome"},
            },
        ],
    }
    return slides
