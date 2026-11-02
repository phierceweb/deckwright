"""The shaped-argument exercises: diverge, fanout, versus, nav.

Components whose whole point is a *shape* an argument takes — two sides opposed, one
thing branching into several, where a slide sits in the deck.
"""

from __future__ import annotations

from typing import Any


def figure_slides() -> dict[str, dict[str, Any]]:
    """Every exercise in this family, keyed by name."""
    slides: dict[str, dict[str, Any]] = {}
    slides["diverge"] = {
        "title": "Signed bars either side of a centre rule",
        "subtitle": "Right is toward the target; left is away from it",
        "place": [
            {
                "at": {"cols": "full", "rows": "top-two-thirds"},
                "diverge": {
                    "peak": 300,
                    "items": [
                        {"label": "Sorted by hand", "value": 271, "note": "7 to 26"},
                        {"label": "Machine passes", "value": 92, "note": "127 to 244"},
                        {"label": "Misroutes", "value": -40, "note": "10 to 14"},
                        {"label": "Returned to sender", "value": -146, "note": "26 to 64"},
                    ],
                },
            }
        ],
    }
    slides["diverge-on-a-pair"] = {
        "title": "The same rows drawn on their own ground",
        "place": [
            {
                "at": {"cols": "full", "rows": {"from": 0, "to": 7}},
                "diverge": {
                    "pair": "inverse",
                    "label_width": 0.34,
                    "items": [
                        {"label": "Misroutes", "value": -40},
                        {"label": "Returned to sender", "value": -146},
                    ],
                },
            }
        ],
    }
    slides["diverge-in-half-the-page"] = {
        "title": "Notes clamped to a placement half the page wide",
        "subtitle": "The note column is a fixed width; here the rect is narrower than it",
        "place": [
            {
                "at": {"cols": {"from": 0, "to": 6}, "rows": {"from": 0, "to": 9}},
                "diverge": {
                    "items": [
                        {"label": "Away", "value": -40, "note": "the long side"},
                        {"label": "Toward", "value": 30, "note": "the short side"},
                    ]
                },
            }
        ],
    }
    slides["fanout"] = {
        "title": "One call and the work it sets off",
        "subtitle": "The left plate is what the call site reads; the right column is what runs",
        "place": [
            {
                "at": {"cols": "full", "rows": {"from": 0, "to": 9}},
                "fanout": {
                    "source": "publish(post)",
                    "weight": 2.0,
                    "items": [
                        {"icon": "mail", "text": "Subscriber digest"},
                        {"icon": "search", "text": "Search index update"},
                        {"icon": "image", "text": "Thumbnail rendering"},
                        {"text": "A dozen cache invalidations"},
                    ],
                },
            }
        ],
    }
    slides["versus"] = {
        "title": "Two magnitudes, opposed",
        "place": [
            {
                "at": {"cols": "full", "rows": {"from": 0, "to": 5}},
                "versus": {
                    "icon": "schedule",
                    "left": {"value": "2 days", "label": "by post"},
                    "right": {
                        "value": "1 day",
                        "label": "collected in person",
                        "highlight": True,
                    },
                },
            }
        ],
    }
    slides["versus-proportional"] = {
        "title": "Two magnitudes whose plates carry the ratio",
        "place": [
            {
                "at": {"cols": "full", "rows": {"from": 0, "to": 5}},
                "versus": {
                    "icon": "trending_up",
                    "left": {"value": "11.2%", "label": "our first week", "highlight": True},
                    "right": {"value": "7.0%", "label": "platform average"},
                },
            }
        ],
    }
    slides["nav"] = {
        "title": "Where this slide sits in the deck",
        "place": [
            {
                "at": {"cols": "full", "rows": {"from": 0, "to": 1}},
                "align": "center",
                "nav": {
                    "active": "Evidence",
                    "items": ["Problem", "Evidence", "What shipped", "Next"],
                },
            },
            {
                "at": {"cols": "full", "rows": {"from": 2, "to": 7}},
                "bullets": {
                    "items": [
                        "The eyebrow above is chrome: it draws no reveal group",
                        "so a build starts on this list, not on the furniture",
                    ]
                },
            },
        ],
    }
    slides["nav-on-a-named-colour"] = {
        # `ink`, not an accent: this runs against every template, and an author-named
        # role is honoured under AA by design.
        "title": "The active section in a colour the author named",
        "place": [
            {
                "at": {"cols": "full", "rows": {"from": 0, "to": 1}},
                "align": "right",
                "nav": {
                    "color": "ink",
                    "active": "Next",
                    "items": ["Problem", "Evidence", "What shipped", "Next"],
                },
            }
        ],
    }
    return slides
