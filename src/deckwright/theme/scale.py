"""Canvas-relative geometry: fractions in, inches and points out.

A theme declares margins, gutters and type rungs as fractions of the canvas, so one
theme renders proportionally on whatever slide size its template happens to carry.
"""

from __future__ import annotations

from dataclasses import dataclass

from deckwright.errors import ThemeError


@dataclass(frozen=True)
class Scale:
    """The canvas a theme resolves against, in inches."""

    slide_w: float
    slide_h: float

    def __post_init__(self) -> None:
        if self.slide_w <= 0 or self.slide_h <= 0:
            raise ThemeError(f"slide size must be positive, got {self.slide_w}x{self.slide_h}in")

    def x(self, frac: float) -> float:
        """A fraction of the canvas width, in inches."""
        return frac * self.slide_w

    def y(self, frac: float) -> float:
        """A fraction of the canvas height, in inches."""
        return frac * self.slide_h

    def pt(self, rung: float) -> float:
        """A type rung — points per inch of canvas height — in points."""
        return rung * self.slide_h


@dataclass(frozen=True, kw_only=True)
class Grid:
    """Margins and a column grid declared in fractions; every read is inches.

    ``left``/``right``/``gutter`` are fractions of width; ``top``/``bottom``/
    ``body_top`` are fractions of height.
    """

    scale: Scale
    top_frac: float
    right_frac: float
    bottom_frac: float
    left_frac: float
    columns: int
    rows: int
    gutter_frac: float
    body_top_frac: float

    def __post_init__(self) -> None:
        if self.columns < 1:
            raise ThemeError(f"grid columns must be >= 1, got {self.columns}")
        if self.rows < 1:
            raise ThemeError(f"grid rows must be >= 1, got {self.rows}")
        if self.gutter_frac < 0:
            raise ThemeError(f"grid gutter must be >= 0, got {self.gutter_frac}")
        if self.content_w <= 0:
            raise ThemeError(
                f"grid margins leave no content width: slide {self.slide_w}in "
                f"minus left {self.left}in and right {self.right}in"
            )

    @property
    def slide_w(self) -> float:
        return self.scale.slide_w

    @property
    def slide_h(self) -> float:
        return self.scale.slide_h

    @property
    def top(self) -> float:
        return self.scale.y(self.top_frac)

    @property
    def bottom(self) -> float:
        return self.scale.y(self.bottom_frac)

    @property
    def body_top(self) -> float:
        return self.scale.y(self.body_top_frac)

    @property
    def left(self) -> float:
        return self.scale.x(self.left_frac)

    @property
    def right(self) -> float:
        return self.scale.x(self.right_frac)

    @property
    def gutter(self) -> float:
        return self.scale.x(self.gutter_frac)

    @property
    def content_w(self) -> float:
        return self.slide_w - self.left - self.right

    @property
    def right_edge(self) -> float:
        return self.slide_w - self.right

    @property
    def col_w(self) -> float:
        return (self.content_w - self.gutter * (self.columns - 1)) / self.columns

    def col_x(self, index: int) -> float:
        """Left edge of column ``index`` (0-based)."""
        if not 0 <= index < self.columns:
            raise ThemeError(f"column {index} out of range 0..{self.columns - 1}")
        return self.left + index * (self.col_w + self.gutter)

    def span_w(self, columns: int) -> float:
        """Width of a run of ``columns`` columns including the gutters between them."""
        if not 1 <= columns <= self.columns:
            raise ThemeError(f"span {columns} out of range 1..{self.columns}")
        return columns * self.col_w + (columns - 1) * self.gutter
