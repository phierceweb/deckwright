"""The block exercises: a swatch wall, a grid, set prose and a code listing."""

from __future__ import annotations

from typing import Any


def block_slides() -> dict[str, dict[str, Any]]:
    """Every exercise in this family, keyed by name."""
    return {
        "swatches": {
            "kicker": "THEME",
            "title": "Every role, and the hex it resolved to",
            "subtitle": "Read from the theme this deck was built against",
            "place": [
                {
                    "at": {"cols": "full"},
                    "swatches": {
                        "caption": "A role a theme leaves unbound keeps the design "
                        "system's own default, so a theme that binds "
                        "nothing still renders."
                    },
                }
            ],
        },
        "grid": {
            "kicker": "THEME",
            "title": "A grid, and any polygon it has to respect",
            "subtitle": "The columns every placement resolves against",
            "place": [{"at": {"cols": "full"}, "grid": {}}],
        },
        "prose": {
            "kicker": "COPY",
            "title": "Paragraphs at a readable measure",
            "subtitle": "Dense copy without a costume of bullets",
            "place": [
                {
                    "at": {"cols": "left-half"},
                    "prose": {
                        "paragraphs": [
                            "A paragraph set at the measure a reader can track, not the width the "
                            "canvas happens to offer.",
                            "And a second one, so the spacing between paragraphs is exercised too.",
                        ]
                    },
                },
                {
                    "at": {"cols": "right-half"},
                    "align": "center",
                    "prose": {
                        "cite": "A named speaker",
                        "paragraphs": [
                            "A quotation reads as one voice, with its attribution set smaller beneath it."
                        ],
                    },
                },
            ],
        },
        "code": {
            "kicker": "SPEC",
            "title": "A listing, drawn rather than screenshotted",
            "subtitle": "Real text: selectable, themed, and measurable in the manifest",
            "place": [
                {
                    "at": {"cols": "full"},
                    "split": [
                        {
                            "code": {
                                "heading": "the spec",
                                "accent": ["theme:", "place:"],
                                "lines": [
                                    "theme: brand",
                                    "---",
                                    "place:",
                                    "  - at: {cols: full}",
                                    "    code:",
                                    "      lines: [...]",
                                ],
                            }
                        },
                        {
                            "callouts": {
                                "heading": "what it buys",
                                "items": [
                                    {
                                        "head": "No browser in the loop",
                                        "body": "A `document:` card rasterizes through headless Chrome; this does not.",
                                    },
                                    {
                                        "head": "QA can read it",
                                        "body": "The lines land in the manifest, so overflow is measurable.",
                                    },
                                ],
                            }
                        },
                    ],
                }
            ],
        },
    }
