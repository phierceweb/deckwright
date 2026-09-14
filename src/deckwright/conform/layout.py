"""The layout exercises: a row divided into shares, and a document placed in one."""

from __future__ import annotations

from typing import Any


def layout_slides() -> dict[str, dict[str, Any]]:
    """Every exercise in this family, keyed by name."""
    return {
        "split": {
            "title": "A row divided, not measured",
            "subtitle": "Four cards across, and no span written anywhere",
            "place": [
                {
                    "at": {"rows": {"from": 0, "to": 6}},
                    "split": [
                        {"card": {"heading": "One", "body": "A share of the band."}},
                        {"card": {"heading": "Two", "body": "The same again."}},
                        {"card": {"heading": "Three", "body": "And a third."}},
                        {"card": {"heading": "Four", "body": "And a fourth."}},
                    ],
                }
            ],
        },
        "split-uneven": {
            "title": "One share wider than its neighbours",
            "place": [
                {
                    "at": {"rows": {"from": 0, "to": 6}},
                    "split": [
                        {"span": 2, "card": {"heading": "Twice", "body": "Two shares of four."}},
                        {"card": {"heading": "Once", "body": "One."}},
                        {"card": {"heading": "Once more", "body": "And one."}},
                    ],
                }
            ],
        },
    }


def document_slides() -> dict[str, dict[str, Any]]:
    """The markdown-document exercise."""
    return {
        "document": {
            "title": "A markdown document",
            "place": [
                {
                    "at": {"cols": "left-two-thirds", "rows": {"from": 0, "to": 9}},
                    "document": {"source": "{notes}", "alt": "The exercise notes, rendered"},
                }
            ],
        },
    }
