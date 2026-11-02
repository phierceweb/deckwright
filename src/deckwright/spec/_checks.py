"""Cross-slide checks: section order, goto targets, and links within a slide."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deckwright.errors import SpecError
from deckwright.spec.model import GOTO_JUMPS, SlideSpec
from deckwright.utils.links import LINK, web_address_problem


def _check_section_runs(
    slides: tuple[SlideSpec, ...], *, sections: tuple[str, ...], source: Path
) -> None:
    """Refuse a chapter that resumes, or that runs out of the order ``sections:`` lists.

    A slide with no section of its own sits inside the run it falls in and does not
    break it.

    Raises:
        SpecError: a section's slides are not contiguous, or its run begins before one
            ``sections:`` lists ahead of it.
    """
    ended: dict[str, int] = {}
    current: str | None = None
    last = 0
    for slide in slides:
        name = slide.section
        if name is None or name == current:
            if name is not None:
                last = slide.index
            continue
        if current is not None:
            ended[current] = last
        if name in ended:
            raise SpecError(
                f"{source.name}: slide {slide.index} resumes section {name!r}, which "
                f"ended at slide {ended[name]} when {current!r} began — a chapter runs "
                f"once, so 'sections:' cannot describe this order. Move the slide back "
                f"into its run, or give it the section it now sits in"
            )
        if (
            current in sections
            and name in sections
            and sections.index(name) < sections.index(current)
        ):
            raise SpecError(
                f"{source.name}: slide {slide.index} begins section {name!r} after "
                f"{current!r}, but 'sections:' lists {', '.join(sections)} — reorder the "
                f"slides or the list, so a nav drawn from it names the chapters in order"
            )
        current = name
        last = slide.index


def _check_gotos(slides: tuple[SlideSpec, ...], *, source: Path) -> None:
    """Refuse a ``goto:`` that has nowhere to go, and a slide id two slides share.

    Raises:
        SpecError: a duplicate slide id; a goto naming no slide, or the slide it is on; a
            goto on a placement another placement's ``reveals:`` makes a trigger.
    """
    ids: dict[str, int] = {}
    for slide in slides:
        if slide.id is None:
            continue
        if slide.id in ids:
            raise SpecError(
                f"{source.name}: slide {slide.index}: duplicate id {slide.id!r} — slide "
                f"{ids[slide.id]} already has it, so a goto could not say which it means"
            )
        ids[slide.id] = slide.index
    for slide in slides:
        triggers = {p.reveals for p in slide.place if p.reveals}
        for n, placement in enumerate(slide.place, start=1):
            target = placement.goto
            if target is None:
                continue
            where = placement.where or f"{source.name}: slide {slide.index}: placement {n}"
            if placement.id is not None and placement.id in triggers:
                raise SpecError(
                    f"{where}: 'goto: {target}' is on {placement.id!r}, which another "
                    f"placement's 'reveals:' makes a trigger — one click cannot both reveal "
                    f"and leave the slide. Put the goto on a placement of its own"
                )
            if target in GOTO_JUMPS:
                continue
            if target not in ids:
                named = ", ".join(sorted(ids)) or "none — give the target slide an 'id:'"
                raise SpecError(
                    f"{where}: 'goto: {target}' names no slide. Slide ids in this deck: "
                    f"{named}; or jump with {', '.join(GOTO_JUMPS)}"
                )
            if ids[target] == slide.index:
                raise SpecError(
                    f"{where}: 'goto: {target}' is the slide it is on, so the click goes nowhere"
                )


# A listing shows markup as written; a chart's labels are not runs a link can sit on.
_LITERAL_COMPONENTS = frozenset({"code"})
_UNLINKABLE_COMPONENTS = frozenset({"chart"})


def _check_morphs(slides: tuple[SlideSpec, ...], *, source: Path) -> None:
    """Refuse a ``morph:`` name PowerPoint could not pair the way the author means.

    Raises:
        SpecError: a name on a chart, on two placements of one slide, or on two different
            components on consecutive slides.
    """
    before: dict[str, str] = {}
    for slide in slides:
        here: dict[str, tuple[int, str]] = {}
        for n, placement in enumerate(slide.place, start=1):
            name = placement.morph
            if name is None:
                continue
            where = f"{source.name}: slide {slide.index}: placement {n}"
            if placement.component == "chart":
                raise SpecError(
                    f"{where}: 'morph' on a chart — deckwright pairs no chart across slides; "
                    f"morph a card, panel, image or icon"
                )
            if name in here:
                raise SpecError(
                    f"{where}: 'morph: {name}' is already placement {here[name][0]} — a name "
                    f"pairs one placement with its namesake on the next slide"
                )
            if name in before and before[name] != placement.component:
                raise SpecError(
                    f"{where}: 'morph: {name}' is a {before[name]} on slide {slide.index - 1} "
                    f"and a {placement.component} here — PowerPoint pairs shapes in the order "
                    f"they were drawn, so the two must be the same component"
                )
            here[name] = (n, placement.component)
        before = {name: component for name, (_, component) in here.items()}


def _check_links(slide: SlideSpec, *, where: str) -> None:
    """Refuse a ``[words](address)`` whose address a click could not open.

    Raises:
        SpecError: a link to anything but an http, https or mailto address, or a link in a
            component whose text cannot carry one.
    """
    for field in ("kicker", "title", "subtitle"):
        _refuse_bad_links(getattr(slide, field), where=f"{where}: {field}")
    for n, placement in enumerate(slide.place, start=1):
        spot = f"{where}: placement {n} ({placement.component})"
        if placement.component in _LITERAL_COMPONENTS:
            continue
        for text in _strings(placement.body):
            found = LINK.search(text)
            if found is not None and placement.component in _UNLINKABLE_COMPONENTS:
                raise SpecError(
                    f"{spot}: {found.group(0)!r} — a chart's labels are drawn by the chart, "
                    f"not set as runs, so a link has nowhere to go. Put it in the slide's "
                    f"own text beside the chart"
                )
            _refuse_bad_links(text, where=spot)


def _refuse_bad_links(text: str | None, *, where: str) -> None:
    for match in LINK.finditer(text or ""):
        problem = web_address_problem(match["address"])
        if problem is not None:
            raise SpecError(
                f"{where}: the link {match.group(0)!r} — {problem}. Put a backslash before "
                f"the bracket to show it as text"
            )


def _strings(value: Any):
    """Every string inside a component body, however deep."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)
