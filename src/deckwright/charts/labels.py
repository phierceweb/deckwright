"""A chart's data labels: the theme's settings, the ink a fill needs, the room an edge needs."""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING

from lxml import etree
from pptx.chart.chart import Chart
from pptx.oxml.ns import qn
from pptx.util import Pt

from deckwright.charts._native_types import (
    _CONNECTED_LABEL_POSITION,
    _GAP_WIDTH_CHART_TYPES,
    _INSIDE_END_CHART_TYPES,
    _LABEL_POSITIONS,
    _PERCENT_AXIS_CHART_TYPES,
    _PIE_FAMILY_CHART_TYPES,
    _POINT_LABEL_CHART_TYPES,
)
from deckwright.charts._dlbls import fill_stops, set_ink
from deckwright.charts._shared import label_number_format, label_text, value_decimals
from deckwright.charts.model import ChartSpec
from deckwright.theme.palette import Palette
from deckwright.utils.color import contrast_ratio
from deckwright.utils.text import text_em

if TYPE_CHECKING:
    from deckwright.layouts.registry import SlideCtx

_ON_FILL_CHART_TYPES = _PIE_FAMILY_CHART_TYPES | frozenset(
    {
        "area",
        "area-stacked",
        "area-stacked-100",
        "column-stacked",
        "column-stacked-100",
        "bar-stacked",
        "bar-stacked-100",
    }
)
# Children CT_DLbls allows and CT_DLbl does not: a c:dLbl carrying one fails the schema.
_NOT_IN_A_DLBL = frozenset(
    {qn("c:dLbl"), qn("c:showLeaderLines"), qn("c:leaderLines"), qn("c:extLst")}
)


_AREA_CHART_TYPES = frozenset({"area", "area-stacked", "area-stacked-100"})
# Room between a moved label and the plot edge, in ems of the label's own size.
_EDGE_PAD_EM = 0.5
_C15 = "http://schemas.microsoft.com/office/drawing/2012/chart"
_LEADER_LINES_EXT = "{CE6537A1-D6FC-4f65-9D91-7224C49458BB}"
_GROUP_BEFORE_LEADER_LINES = tuple(
    qn(f"c:{name}")
    for name in (
        "numFmt",
        "spPr",
        "txPr",
        "dLblPos",
        "showLegendKey",
        "showVal",
        "showCatName",
        "showSerName",
        "showPercent",
        "showBubbleSize",
        "separator",
    )
)


def _label_decimals(spec: ChartSpec) -> int:
    """Places the labels print: what ``decimals:`` asked for, else what the data needs.

    A 100% type is no exception. Its *axis* shows the computed share, but each label
    still prints that series' own authored value.
    """
    if spec.decimals is not None:
        return spec.decimals
    plotted = [v for s in spec.series for v in (s.values or ())]
    plotted += [p[1] for s in spec.series for p in (s.points or ())]
    return value_decimals(plotted)


def label_format(ctx: SlideCtx, spec: ChartSpec) -> str | None:
    """The code the chart's numbers print in, or ``None`` to leave python-pptx's default."""
    # A 100% type is already a percentage, so a series unit of "%" would print a second sign.
    unit = None if spec.type in _PERCENT_AXIS_CHART_TYPES else spec.series[0].unit
    return label_number_format(
        unit, thousands_sep=ctx.theme.chart.thousands_sep, decimals=_label_decimals(spec)
    )


def style_data_labels(
    ctx: SlideCtx, chart: Chart, spec: ChartSpec, *, frame_width: float, ink: str
) -> None:
    """The plot's data labels from the theme in ``ink``, then each series' own where its fill
    or its place on the plot edge needs them."""
    style = ctx.theme.chart
    plot = chart.plots[0]
    if style.label_position == "none":
        plot.has_data_labels = False
        return

    plot.has_data_labels = True
    # The value is the point of the chart, so it outranks the axis scale that frames it.
    value_style = ctx.style("kicker")
    labels = plot.data_labels
    # python-pptx pre-writes showVal=0 for area, doughnut and bubble.
    labels.show_value = True
    labels.font.size = Pt(value_style.size)
    labels.font.bold = True
    labels.font.italic = value_style.italic
    labels.font.name = ctx.theme.face
    labels.font.color.rgb = ctx.rgb(ink)
    if style.label_position in _LABEL_POSITIONS and spec.type in _INSIDE_END_CHART_TYPES:
        labels.position = _LABEL_POSITIONS[style.label_position]
    elif spec.type in _POINT_LABEL_CHART_TYPES:
        labels.position = _CONNECTED_LABEL_POSITION
    number_format = label_format(ctx, spec)
    if number_format is not None:
        labels.number_format = number_format
    if spec.type in _PIE_FAMILY_CHART_TYPES:
        # A pie's single series gets no legend, so the label is all that names a wedge.
        labels.show_category_name = True
    _hide_series_labels(chart, spec)
    if labels_sit_on_fill(spec.type, style.label_position):
        ink_labels_on_fills(chart, spec, ctx.theme.palette)
    pull_edge_labels_in(
        chart,
        spec,
        frame_width=frame_width,
        size_pt=value_style.size,
        face=ctx.theme.face,
        label_text=label_texter(ctx, spec),
    )


def label_texter(ctx: SlideCtx, spec: ChartSpec) -> Callable[[float], str]:
    """A value as this chart's data labels print it."""
    return partial(
        label_text,
        unit=None if spec.type in _PERCENT_AXIS_CHART_TYPES else spec.series[0].unit,
        thousands_sep=ctx.theme.chart.thousands_sep,
        decimals=_label_decimals(spec),
    )


def _hide_series_labels(chart: Chart, spec: ChartSpec) -> None:
    """Silence the series that asked for no labels.

    A series' own ``c:dLbls`` overrides the plot's, which is the only way one series can
    drop its labels while the rest keep theirs.
    """
    for series, wanted in zip(chart.series, spec.series, strict=True):
        if not wanted.labels:
            series.data_labels.show_value = False


def labels_sit_on_fill(chart_type: str, label_position: str) -> bool:
    """Whether this kind draws its data labels inside the series' own shapes."""
    if chart_type in _ON_FILL_CHART_TYPES:
        return True
    return label_position == "inside_end" and chart_type in _GAP_WIDTH_CHART_TYPES


def ink_labels_on_fills(chart: Chart, spec: ChartSpec, palette: Palette) -> None:
    """Give each labelled series, and each point filled apart from it, an ink that reads.

    A series' own ``c:dLbls`` replaces the plot's outright, so it starts as a copy of the
    plot's and only the colour changes.
    """
    plot = chart.plots[0]._element
    template = plot.find(qn("c:dLbls"))
    if template is None:
        return
    for ser, wanted in zip(plot.findall(qn("c:ser")), spec.series, strict=True):
        if not wanted.labels:
            continue
        points = {
            str(dpt.find(qn("c:idx")).get("val")): fill_stops(dpt.find(qn("c:spPr")))
            for dpt in ser.findall(qn("c:dPt"))
        }
        inks = {idx: _ink(palette, stops) for idx, stops in points.items() if stops}
        base = fill_stops(ser.find(qn("c:spPr")))
        if base:
            series_ink = _ink(palette, base)
        elif inks:
            series_ink = Counter(inks.values()).most_common(1)[0][0]
        else:
            continue
        own = ser.get_or_add_dLbls()
        for child in list(own):
            own.remove(child)
        for child in template:
            own.append(copy.deepcopy(child))
        set_ink(own, series_ink)
        position = 0
        for idx in sorted(inks, key=int):
            if inks[idx] == series_ink:
                continue
            own.insert(position, _point_label(template, idx, inks[idx]))
            position += 1


def _ink(palette: Palette, stops: list[str]) -> str:
    """The declared ink reading best across every stop, judged by its weakest one."""
    candidates = dict.fromkeys(palette.ink_for(stop) for stop in stops)
    return max(candidates, key=lambda ink: min(contrast_ratio(ink, stop) for stop in stops))


def _point_label(template: etree._Element, idx: str, ink: str) -> etree._Element:
    label = etree.Element(qn("c:dLbl"))
    etree.SubElement(label, qn("c:idx")).set("val", idx)
    for child in template:
        if child.tag not in _NOT_IN_A_DLBL:
            label.append(copy.deepcopy(child))
    set_ink(label, ink)
    return label


def pull_edge_labels_in(
    chart: Chart,
    spec: ChartSpec,
    *,
    frame_width: float,
    size_pt: float,
    face: str | None,
    label_text: Callable[[float], str],
) -> None:
    """Move an area chart's first and last labels in off the plot edges their points sit on.

    Each moves by half its own width plus a pad, so it clears the axis without leaving its band.
    """
    if spec.type not in _AREA_CHART_TYPES:
        return
    plot = chart.plots[0]._element
    for ser, wanted in zip(plot.findall(qn("c:ser")), spec.series, strict=True):
        own = ser.find(qn("c:dLbls"))
        values = wanted.values or ()
        if not wanted.labels or own is None or len(values) < 2:
            continue
        for idx, direction in ((0, 1), (len(values) - 1, -1)):
            width_in = text_em(label_text(values[idx]), face) * size_pt / 72
            offset = direction * (width_in / 2 + _EDGE_PAD_EM * size_pt / 72) / frame_width
            _set_offset(_label_at(own, idx), offset)
        _no_leader_lines(own)


def _label_at(labels: etree._Element, idx: int) -> etree._Element:
    """The series' own ``c:dLbl`` for point ``idx``, made from its settings if there is none."""
    existing = labels.findall(qn("c:dLbl"))
    for label in existing:
        found = label.find(qn("c:idx"))
        if found is not None and found.get("val") == str(idx):
            return label
    label = etree.Element(qn("c:dLbl"))
    etree.SubElement(label, qn("c:idx")).set("val", str(idx))
    for child in labels:
        if child.tag not in _NOT_IN_A_DLBL:
            label.append(copy.deepcopy(child))
    labels.insert(len(existing), label)
    return label


def _set_offset(label: etree._Element, x: float) -> None:
    for old in label.findall(qn("c:layout")):
        label.remove(old)
    layout = etree.Element(qn("c:layout"))
    manual = etree.SubElement(layout, qn("c:manualLayout"))
    etree.SubElement(manual, qn("c:x")).set("val", f"{x:.4f}")
    etree.SubElement(manual, qn("c:y")).set("val", "0")
    label.insert(1, layout)


def _no_leader_lines(labels: etree._Element) -> None:
    """Turn leader lines off, in the element and in the Office 2013 extension renderers read."""
    for old in labels.findall(qn("c:showLeaderLines")):
        labels.remove(old)
    flag = etree.Element(qn("c:showLeaderLines"))
    flag.set("val", "0")
    before = [i for i, child in enumerate(labels) if child.tag in _GROUP_BEFORE_LEADER_LINES]
    labels.insert(before[-1] + 1 if before else len(labels), flag)
    ext_lst = labels.find(qn("c:extLst"))
    if ext_lst is None:
        ext_lst = etree.SubElement(labels, qn("c:extLst"))
    if not any(e.get("uri") == _LEADER_LINES_EXT for e in ext_lst):
        ext = etree.SubElement(ext_lst, qn("c:ext"), nsmap={"c15": _C15})
        ext.set("uri", _LEADER_LINES_EXT)
        etree.SubElement(ext, f"{{{_C15}}}showLeaderLines").set("val", "0")
