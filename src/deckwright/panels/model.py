"""A panel: HTML to render, and the regions it can be cut into."""

from __future__ import annotations

from dataclasses import dataclass

from deckwright.errors import LayoutError


@dataclass(frozen=True)
class Region:
    """A named rectangle in a rendered panel, in CSS pixels."""

    name: str
    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise LayoutError(f"region {self.name!r} has no area")
        # The name becomes a cache filename component — never a path segment.
        if "/" in self.name or "\\" in self.name or ".." in self.name:
            raise LayoutError(f"region name {self.name!r} is not filesystem-safe")


@dataclass(frozen=True)
class Panel:
    """HTML plus the regions it may be sliced into for independent animation."""

    html: str
    width: int
    regions: tuple[Region, ...] = ()

    def __post_init__(self) -> None:
        if self.width <= 0:
            raise LayoutError(f"panel width must be positive, got {self.width}")
        names = [r.name for r in self.regions]
        if len(names) != len(set(names)):
            raise LayoutError(f"duplicate region names: {names}")

    def region_names(self) -> tuple[str, ...]:
        return tuple(r.name for r in self.regions)
