"""One slide per capability, written the way a real deck would use it.

Ordered by how often the shape appears across the sample corpus, so a template that
fails early fails on something that matters. Each family lives in its own module and
is assembled here; the order of these calls is the order of the deck.
"""

from __future__ import annotations

from typing import Any

from deckwright.conform.blocks import block_slides
from deckwright.conform.charts import chart_intro_slides, chart_legend_slides, chart_slides
from deckwright.conform.diagrams import diagram_slides
from deckwright.conform.figures import figure_slides
from deckwright.conform.layout import document_slides, layout_slides
from deckwright.conform.marks import mark_slides
from deckwright.conform.motion import build_slides, motion_slides
from deckwright.conform.photos import photo_slides
from deckwright.conform.scripts import script_slides
from deckwright.conform.tables import table_slides
from deckwright.conform.text import text_slides
from deckwright.conform.titles import title_slides

EXERCISE: dict[str, dict[str, Any]] = {}
for _family in (
    title_slides,
    text_slides,
    chart_intro_slides,
    diagram_slides,
    block_slides,
    chart_slides,
    chart_legend_slides,
    motion_slides,
    build_slides,
    layout_slides,
    table_slides,
    document_slides,
    mark_slides,
    figure_slides,
    photo_slides,
    script_slides,
):
    EXERCISE.update(_family())
del _family
