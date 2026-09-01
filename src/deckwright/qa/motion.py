"""What the timing says: how many clicks a slide costs, and whether a trigger can fire."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any, Iterator

from lxml import etree
from pf_core.utils.env import resolve_int

from deckwright.qa.model import Finding, Severity
from deckwright.theme.model import Theme
from deckwright.utils.xml import fromstring as parse_xml

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_SLIDE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
_MAX_BEAT_SHAPES_DEFAULT = 6
_MAX_BEAT_SHAPES_ENV = "DECKWRIGHT_MAX_BEAT_SHAPES"
# A build the author declared as one click is not a beat that grew too large, and a
# `reveals:` trigger is one click by construction — only `animate: one_at_a_time` stages.
_STAGED = ("click_sequence",)

_LABEL = {
    "click_build": "animate: together",
    "click_sequence": "animate: one_at_a_time",
    "click_reveals": "reveals:",
    "chart_build": "a chart's own build",
}


def _max_beat_shapes() -> int:
    n: int = resolve_int(None, _MAX_BEAT_SHAPES_ENV, default=_MAX_BEAT_SHAPES_DEFAULT)
    return n if n > 0 else _MAX_BEAT_SHAPES_DEFAULT


def check_beats(manifest: dict[str, Any], theme: Theme) -> list[Finding]:
    """Report each slide's reveal rhythm, and flag a staged beat that arrives all at once."""
    ceiling = _max_beat_shapes()
    findings: list[Finding] = []
    for slide in manifest.get("slides") or []:
        index = int(slide.get("index", 0))
        for anim in slide.get("animations") or []:
            kind = str(anim.get("kind", ""))
            steps = anim.get("steps") or []
            clicks = int(anim.get("clicks", len(steps)))
            findings.append(
                Finding(
                    slide=index,
                    check="beats",
                    severity=Severity.INFO,
                    detail=_rhythm(kind, steps, clicks),
                )
            )
            if kind not in _STAGED:
                continue
            findings.extend(
                Finding(
                    slide=index,
                    check="beat-size",
                    severity=Severity.WARN,
                    detail=(
                        f"beat {position} of {len(steps)} reveals {len(step)} shapes at "
                        f"once, over the {ceiling} this deck is checked against "
                        f"({_MAX_BEAT_SHAPES_ENV}). This slide asked for a staged build "
                        f"and one click delivers most of it — split the placement, or say "
                        f"'animate: together' and mean it"
                    ),
                )
                for position, step in enumerate(steps, 1)
                if len(step) > ceiling
            )
    return findings


def _rhythm(kind: str, steps: list[list[str]], clicks: int) -> str:
    """One slide's build, in the vocabulary the author wrote."""
    label = _LABEL.get(kind, kind)
    shapes = sum(len(step) for step in steps)
    sizes = ", ".join(str(len(step)) for step in steps)
    if kind == "chart_build":
        return f"{label} — {clicks} click(s): the chart's axes, then one per part"
    if kind == "click_reveals":
        return f"{label} — no slide advance; one trigger reveals {shapes} shape(s)"
    if kind == "click_build":
        return f"{label} — 1 click reveals {shapes} shape(s)"
    if clicks == 1 and len(steps) > 1:
        return (
            f"{label} — 1 click, {len(steps)} beats chained by "
            f"'motion.advance: after_previous'; {shapes} shapes, beats of {sizes}"
        )
    return f"{label} — {clicks} click(s), {shapes} shapes, beats of {sizes}"


def _entrance_targets(node) -> set[int]:
    """Shape ids an entrance effect under ``node`` makes visible."""
    out: set[int] = set()
    for ctn in node.iter(f"{{{_P}}}cTn"):
        if ctn.get("presetClass") != "entr":
            continue
        for target in ctn.iter(f"{{{_P}}}spTgt"):
            if (spid := str(target.get("spid", ""))).isdigit():
                out.add(int(spid))
    return out


def _sequences(root) -> tuple[list[tuple[int | None, set[int]]], set[int]]:
    """Each interactive ``(trigger, targets)``, and what the main sequence reveals."""
    interactive: list[tuple[int | None, set[int]]] = []
    main: set[int] = set()
    for seq in root.iter(f"{{{_P}}}seq"):
        ctn = seq.find(f"{{{_P}}}cTn")
        if ctn is None:
            continue
        if ctn.get("nodeType") == "mainSeq":
            main |= _entrance_targets(ctn)
            continue
        if ctn.get("nodeType") != "interactiveSeq":
            continue
        trigger = None
        conds = ctn.find(f"{{{_P}}}stCondLst")
        if conds is not None:
            target = conds.find(f".//{{{_P}}}spTgt")
            if target is not None and str(target.get("spid", "")).isdigit():
                trigger = int(str(target.get("spid")))
        body = ctn.find(f"{{{_P}}}childTnLst")
        interactive.append((trigger, _entrance_targets(body) if body is not None else set()))
    return interactive, main


def _unreachable(interactive: list[tuple[int | None, set[int]]]) -> set[int]:
    """Hidden shapes whose every trigger is itself hidden.

    A finite chain either roots in something visible at slide start or loops, so what
    survives the fixpoint is exactly the rings.
    """
    hidden = {spid for _, entr in interactive for spid in entr}
    triggers: dict[int, set[int]] = {}
    for trigger, entr in interactive:
        if trigger is None:
            continue
        for spid in entr:
            triggers.setdefault(spid, set()).add(trigger)
    reachable = {s for s in hidden if any(t not in hidden for t in triggers.get(s, set()))}
    grew = True
    while grew:
        grew = False
        for spid in sorted(hidden - reachable):
            if triggers.get(spid, set()) & reachable:
                reachable.add(spid)
                grew = True
    return hidden - reachable


def check_triggers(deck: str | Path) -> list[Finding]:
    """An interactive reveal that can never fire, or that reveals what is already there."""
    deck = Path(deck)
    findings: list[Finding] = []
    try:
        archive = zipfile.ZipFile(deck)
    except (OSError, zipfile.BadZipFile):
        return []  # `package` owns that finding
    with archive:
        parts = {n: m for n in archive.namelist() if (m := _SLIDE.match(n))}
        for part in sorted(parts):
            index = int(parts[part].group(1))
            try:
                root = parse_xml(archive.read(part))
            except etree.XMLSyntaxError:
                continue  # `package` owns that finding
            names = {
                int(str(e.get("id"))): str(e.get("name", ""))
                for e in root.iter(f"{{{_P}}}cNvPr")
                if str(e.get("id", "")).isdigit()
            }
            interactive, main = _sequences(root)
            if not interactive:
                continue
            findings.extend(_already_shown(interactive, main, names, index))
            if stuck := _unreachable(interactive):
                findings.append(
                    Finding(
                        slide=index,
                        check="dead-trigger",
                        severity=Severity.ERROR,
                        detail=(
                            f"{_named(stuck, names)} can never be shown: every shape whose "
                            f"click would reveal it is itself hidden until one of them is "
                            f"clicked"
                        ),
                    )
                )
    return findings


def _already_shown(
    interactive: list[tuple[int | None, set[int]]],
    main: set[int],
    names: dict[int, str],
    index: int,
) -> Iterator[Finding]:
    for trigger, targets in interactive:
        if shown := targets & main:
            yield Finding(
                slide=index,
                check="dead-trigger",
                severity=Severity.WARN,
                detail=(
                    f"{_named(shown, names)} is revealed by this slide's main build as "
                    f"well, so it is already on screen when "
                    f"{_one(trigger, names)!r} is clicked"
                ),
                shape=names.get(trigger) if trigger is not None else None,
            )


def _one(spid: int | None, names: dict[int, str]) -> str:
    return "an unnamed shape" if spid is None else names.get(spid, str(spid))


def _named(spids: set[int], names: dict[int, str]) -> str:
    return ", ".join(sorted(names.get(s, str(s)) for s in spids))
