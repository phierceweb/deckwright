"""The exercises that need a photograph — the corpus's largest archetype.

Separated because these are the only slides that name run-time assets: ``{photo}``
and ``{portrait}`` are filled in by the runner, not by the spec author.
"""

from __future__ import annotations

from typing import Any

SLIDES: dict[str, dict[str, Any]] = {}

SLIDES["photo"] = {
    "title": "A photograph carrying its own line",
    "place": [
        {
            "at": {"cols": "full", "rows": "top-two-thirds"},
            "image": {"src": "{photo}", "over": [{"text": "Reversed out of the picture"}]},
        }
    ],
}
SLIDES["photo-background"] = {
    "title": "A title over a full-bleed photograph",
    "subtitle": "And the line beneath it",
    "background": {"image": "{photo}", "fit": "cover", "scrim": {"opacity": 0.6}},
}
SLIDES["photo-gradient"] = {
    "title": "A caption under a fading scrim",
    "place": [
        {
            "at": {"cols": "full", "rows": "top-two-thirds"},
            "anchor": "bottom",
            "image": {
                "src": "{photo}",
                "scrim": {"gradient": "bottom"},
                "over": [{"text": "A caption in the dark end", "rung": "lead"}],
            },
        }
    ],
}
SLIDES["photo-crop"] = {
    "title": "A portrait shot cropped to a band",
    "place": [
        {
            "at": {"cols": "full", "rows": "top-third"},
            "image": {"src": "{portrait}", "crop": "16:9"},
        }
    ],
}
SLIDES["photo-circles"] = {
    "title": "Three circular portraits",
    "place": [
        {
            "at": {"cols": "left-third", "rows": "top-half"},
            "image": {"src": "{portrait}", "mask": "circle"},
        },
        {
            "at": {"cols": "mid-third", "rows": "top-half"},
            "image": {"src": "{portrait}", "mask": "circle"},
        },
        {
            "at": {"cols": "right-third", "rows": "top-half"},
            "image": {"src": "{portrait}", "mask": "circle"},
        },
    ],
}
SLIDES["photo-rounded"] = {
    "title": "A rounded plate of a picture",
    "place": [
        {
            "at": {"cols": "left-two-thirds", "rows": "top-half"},
            "image": {"src": "{photo}", "mask": "rounded", "radius": 0.06},
        }
    ],
}
SLIDES["photo-contain"] = {
    "title": "The whole frame, letterboxed",
    "place": [
        {
            "at": {"cols": "full", "rows": {"from": 0, "to": 7}},
            "image": {"src": "{portrait}", "fit": "contain"},
        }
    ],
}
SLIDES["photo-bleed"] = {
    "title": "A picture off the right edge",
    "chrome": {"title": {"at": {"box": {"x": "6%", "y": "36%", "w": "42%", "h": "16%"}}}},
    "place": [
        {
            "at": {"box": {"x": "55%", "y": "0%", "w": "45%", "h": "100%"}},
            "bleed": True,
            "image": {"src": "{portrait}"},
        }
    ],
}


def photo_slides() -> dict[str, dict[str, Any]]:
    """Every picture exercise, keyed by name."""
    return dict(SLIDES)
