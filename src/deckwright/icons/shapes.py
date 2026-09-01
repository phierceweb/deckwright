"""Plain geometric marks, drawn as preset geometry rather than as icon art.

Only marks whose name *is* their geometry belong here; `star` and `flag` are icons.
"""

from __future__ import annotations

from pptx.enum.shapes import MSO_SHAPE

SHAPES = {
    "circle": MSO_SHAPE.OVAL,
    "square": MSO_SHAPE.RECTANGLE,
    "triangle": MSO_SHAPE.ISOSCELES_TRIANGLE,
    "diamond": MSO_SHAPE.DIAMOND,
    "ring": MSO_SHAPE.DONUT,
}
"""``icon:`` names that resolve to a preset instead of a glyph."""
