"""What a deck's chart parts say about the charts — not whether the file opens, which is
:mod:`deckwright.qa.package`."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

from deckwright.qa.model import Finding, Severity
from deckwright.utils.xml import fromstring as parse_xml

_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
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
        return _unverifiable_bar_charts(archive, names, owner) + _thin_charts(archive, owner)


def _charts_by_slide(archive, names: set[str]) -> dict[str, int]:
    """Which slide each chart part hangs off, so a finding can name it.

    A graphicFrame chart is named directly in its slide's rels; nothing deeper is walked.
    """
    owner: dict[str, int] = {}
    slides = {n: m for n in names if (m := _SLIDE.match(n))}
    for part in sorted(slides):
        index = int(slides[part].group(1))
        rels = f"{part.rsplit('/', 1)[0]}/_rels/{part.rsplit('/', 1)[1]}.rels"
        if rels not in names:
            continue
        for rel in parse_xml(archive.read(rels)):
            target = _resolve(part, str(rel.get("Target")))
            if _CHART.match(target):
                owner.setdefault(target, index)
    return owner


def _resolve(part: str, target: str) -> str:
    base = part.rsplit("/", 1)[0].split("/")
    for step in target.split("/"):
        if step == "..":
            base = base[:-1]
        elif step not in ("", "."):
            base = [*base, step]
    return "/".join(base)


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
