"""The title exercises: what a cover and a heading carry, and where they sit."""

from __future__ import annotations

from typing import Any


def title_slides() -> dict[str, dict[str, Any]]:
    """Every exercise in this family, keyed by name."""
    return {
        "cover": {
            "kicker": "A COVER",
            "title": "The words a title carries",
            "subtitle": "And the line beneath it",
            "chrome": {
                "kicker": {"at": {"box": {"x": "6%", "y": "50%", "w": "50%", "h": "5%"}}},
                "title": {
                    # `auto`: the hero rung wraps to a different depth at each aspect,
                    # and a pinned percentage only ever fits the one it was measured on.
                    "at": {"box": {"x": "6%", "y": "56%", "w": "74%", "h": "auto"}},
                    "rung": "hero",
                },
                "subtitle": {
                    "at": {"box": {"x": "6%", "y": "76%", "w": "60%", "h": "6%"}},
                    "rung": "lead",
                },
            },
        },
        "cover-brand": {
            "kicker": "A BRAND COVER",
            "title": "Reversed out of the brand's own colour",
            "subtitle": "The accent a template actually owns",
            "background": "accent-1",
        },
        "cover-inverse": {
            "kicker": "A DARK COVER",
            "title": "Reversed out of the dark surface",
            "subtitle": "And the line beneath it",
            "background": "inverse",
        },
        "titled": {
            "kicker": "PLAIN",
            "title": "A title over the page surface",
            "subtitle": "Chrome on the light side of the palette",
        },
        "centred-title": {
            "title": "Centred on the canvas",
            "chrome": {
                "title": {
                    "at": {"box": {"x": "10%", "y": "36%", "w": "80%", "h": "14%"}},
                    "align": "center",
                }
            },
        },
        "low-title": {
            "kicker": "LOW",
            "title": "A title low on the canvas",
            "chrome": {
                "kicker": {"at": {"box": {"x": "6%", "y": "58%", "w": "50%", "h": "4%"}}},
                "title": {"at": {"box": {"x": "6%", "y": "63%", "w": "70%", "h": "13%"}}},
            },
        },
    }
