"""Exercises for motion: the roles, the interactive trigger, the hard cut."""

from __future__ import annotations

from typing import Any

from deckwright.conform.charts import CATEGORY_ROWS, CHART_ALT


def motion_slides() -> dict[str, dict[str, Any]]:
    """One slide per motion capability a template has to carry."""
    slides: dict[str, dict[str, Any]] = {}
    slides["click-to-reveal"] = {
        "title": "Held back until it is asked for",
        "subtitle": "An interactive trigger spends no slide advance",
        "place": [
            {
                "at": {"cols": "left-half"},
                "id": "question",
                "card": {"heading": "What broke?", "body": "Click this card."},
            },
            {
                "at": {"cols": "right-half"},
                "reveals": "question",
                "card": {
                    "heading": "The cache key never invalidated",
                    "body": "Hidden until the question is clicked.",
                },
            },
        ],
    }
    # Relative jumps only: each exercise first builds as a one-slide deck, where a named
    # slide would not exist.
    slides["goto"] = {
        "title": "Two ways off this slide",
        "subtitle": "Each card jumps when clicked in the show",
        "place": [
            {
                "at": {"rows": {"from": 0, "to": 6}},
                "split": [
                    {
                        "goto": "first",
                        "card": {"heading": "Back to the start", "body": "The first slide."},
                    },
                    {
                        "goto": "next",
                        "card": {"heading": "Onward", "body": "The slide after this one."},
                    },
                ],
            }
        ],
    }
    slides["staged-beats"] = {
        "title": "Four beats, one claim each",
        "subtitle": "The beats view reads these back in order",
        "animate": "one_at_a_time",
        "place": [
            {
                "at": {"cols": "full", "rows": {"from": 1, "to": 10}},
                "callouts": {
                    "items": [
                        {"head": "The setup", "body": "Where the quarter started."},
                        {"head": "The turn", "body": "What changed in week three."},
                        {"head": "The cost", "body": "What it took to find it."},
                        {"head": "The fix", "body": "What ships next."},
                    ]
                },
            }
        ],
    }
    slides["line-role"] = {
        "title": "A rule that draws itself",
        "subtitle": "The component reports a motion role; the theme binds it to a wipe",
        "animate": "one_at_a_time",
        "place": [
            {"at": {"cols": "full", "rows": {"from": 0, "to": 1}}, "rule": {}},
            {
                "at": {"cols": "left-two-thirds", "rows": {"from": 1, "to": 6}},
                "bullets": {"items": ["The rule wipes", "The text fades"]},
            },
        ],
    }
    slides["transition-none"] = {
        "title": "A deliberate hard cut",
        "subtitle": "The one thing a slide may say about a transition",
        "transition": "none",
        "place": [
            {
                "at": {"cols": {"from": 0, "to": 7}},
                "bullets": {
                    "items": ["Which transition is the theme's", "A slide may only refuse it"]
                },
            }
        ],
    }
    return slides


def build_slides() -> dict[str, dict[str, Any]]:
    """The build exercises: a whole-slide reveal, and a chart built in parts."""
    return {
        "reveal-together": {
            "title": "Everything at once",
            "animate": "together",
            "place": [
                {
                    "at": {"cols": {"from": 0, "to": 7}},
                    "bullets": {"items": ["One", "Two", "Three"]},
                }
            ],
        },
        "chart-build": {
            "title": "A chart built by category",
            "animate": "by_category",
            "place": [
                {
                    "at": {"cols": "full", "rows": "top-two-thirds"},
                    "chart": {
                        "kind": "column",
                        "alt": CHART_ALT,
                        "data": [dict(r) for r in CATEGORY_ROWS],
                    },
                }
            ],
        },
        # The one animate: needing more than one series — by_series on a single-series chart
        # is one click for the whole chart.
        "chart-build-by-series": {
            "title": "A chart built one series at a time",
            "animate": "by_series",
            "place": [
                {
                    "at": {"cols": "full", "rows": "top-two-thirds"},
                    "chart": {
                        "kind": "column",
                        "alt": CHART_ALT,
                        "data": [
                            {
                                "category": row["category"],
                                "values": {"Direct": row["value"], "Partner": row["value"] // 2},
                            }
                            for row in CATEGORY_ROWS
                        ],
                    },
                }
            ],
        },
    }
