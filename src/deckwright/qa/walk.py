"""Walking a build manifest: its slides, and a slide's recorded rows."""

from __future__ import annotations

from typing import Any, Iterator

from deckwright.compile.record import box_of


def slides(manifest: dict[str, Any]) -> Iterator[dict[str, Any]]:
    return iter(manifest.get("slides", []))


def unique_shapes(slide: dict[str, Any]) -> list[dict[str, Any]]:
    """One entry per distinct shape+box — for geometry checks only, where one box is
    one geometry regardless of how many paragraph records share it."""
    seen: set[tuple[Any, tuple[float, float, float, float] | None]] = set()
    out = []
    for shape in slide.get("shapes", []):
        key = (shape.get("shape_id"), box_of(shape))
        if key in seen:
            continue
        seen.add(key)
        out.append(shape)
    return out


def all_shapes(slide: dict[str, Any]) -> list[dict[str, Any]]:
    """Every recorded row, not one per shape — deduplicating would drop typography rows.

    A component row carries only its dominant size and colours, so the rest of that
    shape's text goes unchecked (``docs/qa.md``).
    """
    return list(slide.get("shapes", []))
