"""A chart's text recorded against the frame, so QA's contrast and type-size checks see it.

Read back from the chart part as written: the ink each label element carries and the fill
or paper it sits on. No text is recorded: a renderer scatters a chart's labels, so a
joined string is never on the page for the overflow check to find.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lxml import etree
from pptx.oxml.ns import qn
from pptx.shapes.graphfrm import GraphicFrame

from deckwright.charts._dlbls import fill_stops, read_ink
from deckwright.charts._native_types import _AXIS_CHART_TYPES
from deckwright.charts.labels import labels_sit_on_fill
from deckwright.charts.model import ChartSpec
from deckwright.theme.model import Rect
from deckwright.utils.color import contrast_ratio

if TYPE_CHECKING:
    from deckwright.layouts.registry import SlideCtx

_EMU_PER_INCH = 914400


@dataclass(frozen=True)
class _Part:
    """The frame's geometry under a part name, without renaming the frame itself."""

    shape_id: int
    name: str
    left: int
    top: int
    width: int
    height: int


def record_chart_text(ctx: SlideCtx, frame: GraphicFrame, spec: ChartSpec) -> None:
    part = _Part(frame.shape_id, frame.name, frame.left, frame.top, frame.width, frame.height)
    rect = Rect(*(v / _EMU_PER_INCH for v in (frame.left, frame.top, frame.width, frame.height)))
    caption = ctx.style("caption").size
    chart = frame.chart
    space = chart._chartSpace
    _record_labels(ctx, part, chart, spec, paper=lambda ink: ctx.behind(rect, ink=ink))
    if spec.type in _AXIS_CHART_TYPES:
        axis = space.find(f".//{qn('c:valAx')}")
        ink = (read_ink(axis) if axis is not None else None) or str(ctx.dim())
        ctx.manifest.record(
            part, part="axis", font_pt=caption, fg=ink, bg=ctx.behind(rect, ink=ink)
        )
    if chart.has_legend:
        ink = read_ink(space.find(f".//{qn('c:legend')}")) or ctx.pair.fg
        ctx.manifest.record(
            part, part="legend", font_pt=caption, fg=ink, bg=ctx.behind(rect, ink=ink)
        )


def _record_labels(
    ctx: SlideCtx, part: _Part, chart, spec: ChartSpec, *, paper: Callable[[str], str]
) -> None:
    plot = chart.plots[0]._element
    template = plot.find(qn("c:dLbls"))
    if template is None or _flag(template, "showVal") != "1":
        return
    on_fill = labels_sit_on_fill(spec.type, ctx.theme.chart.label_position)
    size = ctx.style("kicker").size
    many = len(spec.series) > 1
    for number, (ser, wanted) in enumerate(
        zip(plot.findall(qn("c:ser")), spec.series, strict=True), start=1
    ):
        if not wanted.labels:
            continue
        count = len(wanted.values or wanted.points or ())
        own = ser.find(qn("c:dLbls"))
        labels = own if own is not None else template
        series_ink = read_ink(labels) or ctx.pair.fg
        series_fill = fill_stops(ser.find(qn("c:spPr")))
        point_fill = {
            int(dpt.find(qn("c:idx")).get("val")): fill_stops(dpt.find(qn("c:spPr")))
            for dpt in ser.findall(qn("c:dPt"))
        }
        point_ink = {
            int(label.find(qn("c:idx")).get("val")): read_ink(label)
            for label in labels.findall(qn("c:dLbl"))
        }
        grounds: dict[tuple[str, str], None] = {}
        for idx in range(count):
            ink = point_ink.get(idx) or series_ink
            stops = point_fill.get(idx) or series_fill
            ground = (
                min(stops, key=lambda s: contrast_ratio(ink, s))
                if on_fill and stops
                else paper(ink)
            )
            grounds[(ink, ground)] = None
        base = f"labels.s{number}" if many else "labels"
        for k, (ink, ground) in enumerate(grounds, start=1):
            ctx.manifest.record(
                part,
                part=base if k == 1 else f"{base}.{k}",
                font_pt=size,
                fg=ink,
                bg=ground,
            )


def _flag(labels: etree._Element, name: str) -> str | None:
    found = labels.find(qn(f"c:{name}"))
    return None if found is None else found.get("val")
