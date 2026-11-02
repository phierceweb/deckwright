"""Reading and writing the colours on a chart part's data-label and fill elements."""

from __future__ import annotations

from lxml import etree
from pptx.oxml.ns import qn


def fill_stops(sppr: etree._Element | None) -> list[str]:
    """The hex colours of a solid or gradient fill, or none for any other fill."""
    if sppr is None:
        return []
    for fill in ("a:solidFill", "a:gradFill"):
        found = sppr.find(qn(fill))
        if found is not None:
            return [str(c.get("val")) for c in found.iter(qn("a:srgbClr"))]
    return []


def _own_colours(labels: etree._Element) -> list[etree._Element]:
    """The ``a:srgbClr`` of a label element's own text, not of any label nested in it."""
    txpr = labels.find(qn("c:txPr"))
    if txpr is None:
        return []
    return [
        colour
        for rpr in txpr.iter(qn("a:defRPr"))
        for colour in rpr.findall(f"{qn('a:solidFill')}/{qn('a:srgbClr')}")
    ]


def read_ink(labels: etree._Element) -> str | None:
    colours = _own_colours(labels)
    return str(colours[0].get("val")) if colours else None


def set_ink(labels: etree._Element, ink: str) -> None:
    for colour in _own_colours(labels):
        colour.set("val", ink)
