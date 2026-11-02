"""What a deck's chart parts say about the charts — not whether the file opens, which is
:mod:`deckwright.qa.package`."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

from deckwright.qa._parts import rels_part, resolve
from deckwright.qa.model import Finding, Severity
from deckwright.theme.clrscheme import parse_color_scheme
from deckwright.utils.xml import fromstring as parse_xml

_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_THEME = "ppt/theme/theme1.xml"
_CHART = re.compile(r"^ppt/charts/chart\d+\.xml$")
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_SLIDE = re.compile(r"ppt/slides/slide(\d+)\.xml$")
# `choosing.md`: fewer than this and the chart is usually a `stats` row in disguise.
_MIN_DATAPOINTS = 4


def check_charts(deck: str | Path) -> list[Finding]:
    """Every chart-content finding for ``deck``."""
    deck = Path(deck)
    try:
        archive = zipfile.ZipFile(deck)
    except (OSError, zipfile.BadZipFile):
        return []  # qa.package reports an unreadable package; one finding is enough
    with archive:
        names = set(archive.namelist())
        owner = _charts_by_slide(archive, names)
        return (
            _unverifiable_bar_charts(archive, names, owner)
            + _thin_charts(archive, owner)
            + _shared_fills(archive, names, owner)
        )


def _charts_by_slide(archive, names: set[str]) -> dict[str, int]:
    """Which slide each chart part hangs off, so a finding can name it.

    A graphicFrame chart is named directly in its slide's rels; nothing deeper is walked.
    """
    owner: dict[str, int] = {}
    slides = {n: m for n in names if (m := _SLIDE.match(n))}
    for part in sorted(slides):
        index = int(slides[part].group(1))
        rels = rels_part(part)
        if rels not in names:
            continue
        for rel in parse_xml(archive.read(rels)):
            target = resolve(part, str(rel.get("Target")))
            if _CHART.match(target):
                owner.setdefault(target, index)
    return owner


def _unverifiable_bar_charts(archive, names: set[str], owner: dict[str, int]) -> list[Finding]:
    """Warn on a bar or column chart carrying a negative value.

    The file is correct; LibreOffice — which `render` and `qa` both go through — plots and
    labels the *absolute* value for a `barChart` series, so the deck is flagged
    unverifiable rather than wrong. Line and scatter series are unaffected.
    """
    findings: list[Finding] = []
    for part in sorted(n for n in names if _CHART.match(n)):
        try:
            root = parse_xml(archive.read(part))
        except etree.XMLSyntaxError:
            continue  # a malformed chart part is not this check's business
        for bar in root.iter(f"{{{_C}}}barChart"):
            values = [
                float(v.text)
                for v in bar.iter(f"{{{_C}}}v")
                if v.text and _NUMBER.match(v.text.strip())
            ]
            if any(value < 0 for value in values):
                findings.append(
                    Finding(
                        slide=owner.get(part, 0),
                        check="chart-negative",
                        severity=Severity.WARN,
                        detail=(
                            "this is a bar or column chart with a "
                            "negative value. The file is right, but the render this "
                            "check and `deckwright render` both go through draws it as "
                            "positive — so neither can verify this chart. Use the "
                            "'diverge' component, or confirm it in PowerPoint by eye"
                        ),
                    )
                )
                break
    return findings


def _series_length(ser) -> int:
    """How many values one series plots, read off its cached worksheet."""
    values = ser.find(f"{{{_C}}}val")
    if values is None:
        return 0
    count = values.find(f".//{{{_C}}}ptCount")
    if count is None:
        return len(list(values.iter(f"{{{_C}}}pt")))
    try:
        return int(count.get("val", ""))
    except ValueError:
        return 0


def _thin_charts(archive, owner: dict[str, int]) -> list[Finding]:
    """Warn on a bar or column chart plotting fewer than four values.

    Only that family. A line reads as a direction between ordered points, a pie's slices are
    the composition itself, and an XY mark already carries two numbers — none is a `stats`
    row in disguise.
    """
    findings: list[Finding] = []
    for part in sorted(owner):
        try:
            root = parse_xml(archive.read(part))
        except etree.XMLSyntaxError:
            continue
        plots = list(root.iter(f"{{{_C}}}barChart"))
        if not plots:
            continue
        drawn = sum(_series_length(s) for plot in plots for s in plot.iter(f"{{{_C}}}ser"))
        if not drawn or drawn >= _MIN_DATAPOINTS:
            continue
        direction = plots[0].find(f"{{{_C}}}barDir")
        shape = "bar" if direction is not None and direction.get("val") == "bar" else "column"
        findings.append(
            Finding(
                slide=owner[part],
                check="chart-datapoints",
                severity=Severity.WARN,
                detail=(
                    f"this {shape} chart plots {drawn} "
                    f'{"datapoint" if drawn == 1 else "datapoints"} — choosing.md: "A '
                    f"chart with fewer than four datapoints is almost always one of these "
                    f"three in disguise\": a 'stats' tile for one number, a 'stats' row for "
                    f"two or three unrelated ones, 'bullets' or 'callouts' for three "
                    f"claims. Read the slide title aloud — if it already states every "
                    f"number this chart draws, the chart is decoration"
                ),
            )
        )
    return findings


def _shared_fills(archive, names: set[str], owner: dict[str, int]) -> list[Finding]:
    """One finding per chart in which two series draw in the same fill."""
    scheme = parse_color_scheme(archive.read(_THEME)) if _THEME in names else {}
    findings: list[Finding] = []
    for part, index in sorted(owner.items()):
        try:
            root = parse_xml(archive.read(part))
        except etree.XMLSyntaxError:
            continue
        seen: dict[str, str] = {}
        for ser in root.iter(f"{{{_C}}}ser"):
            fill = _series_fill(ser, scheme)
            if fill is None:
                continue
            name = _series_name(ser)
            if fill in seen:
                findings.append(
                    Finding(
                        slide=index,
                        check="series-colour",
                        severity=Severity.WARN,
                        detail=(
                            f"series {seen[fill]} and {name} share the fill {fill} — the theme's "
                            f"{len(seen)} accent(s) ran out and the palette cycled, so a reader "
                            f"cannot tell them apart. Drop a series, split the chart, or bind "
                            f"more accents in the theme"
                        ),
                    )
                )
                break
            seen[fill] = name
    return findings


def _series_name(ser) -> str:
    node = ser.find(f"{{{_C}}}tx//{{{_C}}}v")
    if node is not None and node.text:
        return node.text
    index = ser.find(f"{{{_C}}}idx")
    return f"#{index.get('val')}" if index is not None else "?"


def _series_fill(ser, scheme: dict[str, str]) -> str | None:
    """The solid fill a series draws in, a scheme reference resolved through the theme."""
    fill = ser.find(f"{{{_C}}}spPr/{{{_A}}}solidFill")
    if fill is None:
        return None
    if (literal := fill.find(f"{{{_A}}}srgbClr")) is not None:
        return str(literal.get("val")).upper()
    if (ref := fill.find(f"{{{_A}}}schemeClr")) is not None:
        return scheme.get(str(ref.get("val")))
    return None
