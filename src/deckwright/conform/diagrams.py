"""The diagram exercises: badges, connectors, flows, rules and rendered panels."""

from __future__ import annotations

from typing import Any


def diagram_slides() -> dict[str, dict[str, Any]]:
    """Every exercise in this family, keyed by name."""
    return {
        "ellipses": {
            "title": "Numbered badges",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 2}, "rows": {"from": 0, "to": 3}},
                    "ellipse": {"label": "1"},
                },
                {
                    "at": {"cols": {"from": 2, "to": 4}, "rows": {"from": 0, "to": 3}},
                    "ellipse": {"label": "2"},
                },
                {
                    "at": {"cols": {"from": 4, "to": 6}, "rows": {"from": 0, "to": 3}},
                    "ellipse": {"label": "3"},
                },
            ],
        },
        "connected": {
            "title": "A flow of three steps",
            "place": [
                {
                    "id": "a",
                    "at": {"cols": {"from": 0, "to": 3}, "rows": {"from": 1, "to": 4}},
                    "card": {"heading": "First", "body": "Where it starts."},
                },
                {
                    "id": "b",
                    "at": {"cols": {"from": 4, "to": 7}, "rows": {"from": 1, "to": 4}},
                    "card": {"heading": "Then", "body": "What follows."},
                },
                {
                    "id": "c",
                    "at": {"cols": {"from": 8, "to": 11}, "rows": {"from": 1, "to": 4}},
                    "card": {"heading": "Last", "body": "Where it ends."},
                },
                {
                    "at": {"cols": {"from": 3, "to": 4}, "rows": {"from": 2, "to": 3}},
                    "connector": {"from": "a", "to": "b"},
                },
                {
                    "at": {"cols": {"from": 7, "to": 8}, "rows": {"from": 2, "to": 3}},
                    "connector": {"from": "b", "to": "c"},
                },
            ],
        },
        "flow": {
            "title": "Four steps across",
            "place": [
                {
                    "at": {"cols": "full", "rows": "top-two-thirds"},
                    "flow": {
                        "numbered": True,
                        "current": 2,
                        "items": [
                            {"head": "Read", "body": "Start with the corpus."},
                            {"head": "Name", "body": "Then the vocabulary."},
                            {"head": "Build", "body": "One shape at a time."},
                            {"head": "Check", "body": "Look at the render."},
                        ],
                    },
                }
            ],
        },
        "flow-down": {
            "title": "The same run down the page",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 7}},
                    "flow": {
                        "direction": "vertical",
                        "numbered": True,
                        "items": [
                            {"head": "Read", "body": "Start with the corpus."},
                            {"head": "Name", "body": "Then the vocabulary."},
                            {"head": "Build", "body": "One shape at a time."},
                        ],
                    },
                }
            ],
        },
        "flow-plain": {
            "title": "Three stages, unnumbered",
            "place": [
                {
                    "at": {"cols": "full", "rows": {"from": 1, "to": 7}},
                    "flow": {
                        "arrow": "none",
                        "items": [{"head": "Draft"}, {"head": "Review"}, {"head": "Ship"}],
                    },
                }
            ],
        },
        "rule": {
            "title": "A divider",
            "place": [{"at": {"cols": "full", "rows": {"from": 0, "to": 1}}, "rule": {}}],
        },
        "panel": {
            "title": "Reversed out of a panel",
            "chrome": {
                "title": {
                    "at": {"box": {"x": "6%", "y": "40%", "w": "30%", "h": "auto"}},
                    "ink": "inverse-ink",
                }
            },
            "place": [
                {
                    "at": {"box": {"x": "0%", "y": "0%", "w": "45%", "h": "100%"}},
                    "bleed": True,
                    "panel": {"pair": "inverse"},
                }
            ],
        },
        "animated": {
            "title": "Revealed on click",
            "animate": "one_at_a_time",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 7}},
                    "bullets": {"items": ["Appears first", "Appears second", "Appears third"]},
                }
            ],
        },
    }
