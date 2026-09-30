"""A deckwright slide's motion, read back off the timing its build wrote."""

from __future__ import annotations

from pptx.oxml.ns import qn

from deckwright.motion.read import sequences
from deckwright.motion.transition import read_kind
from deckwright.spec._origin import origin_of


def read_reveals(slide, *, keys: set[str]) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Each revealed placement's trigger, where a spec can say so, and a note, by placement,
    on each reveal it cannot: a part of a placement, a second trigger, a trigger outside
    ``keys`` (the placements drafted), a ring."""
    timing = slide._element.find(qn("p:timing"))
    if timing is None:
        return {}, []
    interactive, _ = sequences(timing)
    owner: dict[int, str] = {}
    for element in slide._element.iter(qn("p:cNvPr")):
        found = origin_of(str(element.get("name", "")))
        if found is not None and str(element.get("id")).isdigit():
            owner[int(str(element.get("id")))] = found.placement
    hidden: dict[str, dict[str, set[int]]] = {}  # target -> trigger -> the shapes it reveals
    for trigger, targets in interactive:
        source = owner.get(trigger) if trigger is not None else None
        if source is None:
            continue
        for spid in targets:
            if (target := owner.get(spid)) is not None and target != source:
                hidden.setdefault(target, {}).setdefault(source, set()).add(spid)
    wanted: dict[str, str] = {}
    notes: list[tuple[str, str]] = []
    for target, by in hidden.items():
        whole = {spid for spid, key in owner.items() if key == target}
        for source, revealed in by.items():
            if source not in keys:
                why = f"its reveal by {source} is left out, since {source} is not drafted"
            elif revealed != whole:
                why = f"part of it is revealed by {source}, and a spec reveals whole placements"
            elif target in wanted:
                why = f"it is also revealed by {source}, and a spec takes one trigger"
            elif _waits_on(wanted, source, target):
                why = f"its reveal by {source} is left out, since it would close a ring of reveals"
            else:
                wanted[target] = source
                continue
            notes.append((target, why))
    return wanted, notes


def _waits_on(wanted: dict[str, str], start: str, goal: str) -> bool:
    """Whether ``start`` is hidden until ``goal``, directly or down a chain of reveals."""
    while start in wanted:
        start = wanted[start]
        if start == goal:
            return True
    return False


def read_animate(slide) -> str | None:
    """The slide's ``animate:``, read off the main sequence its build wrote."""
    timing = slide._element.find(qn("p:timing"))
    if timing is None:
        return None
    chart = next(timing.iter(qn("a:bldChart")), None)
    if chart is not None:
        return "by_series" if str(chart.get("bld", "")).startswith("series") else "by_category"
    main = next((c for c in timing.iter(qn("p:cTn")) if c.get("nodeType") == "mainSeq"), None)
    if main is None:
        return None
    beats = sum(
        1 for c in main.iter(qn("p:cTn")) if c.get("nodeType") in ("clickEffect", "afterEffect")
    )
    if beats > 1:
        return "one_at_a_time"
    return "together" if beats == 1 else None


def read_transition(slide) -> str | None:
    """``morph`` when the slide arrives on one; the one transition a spec states per slide."""
    return "morph" if read_kind(slide._element) == "morph" else None
