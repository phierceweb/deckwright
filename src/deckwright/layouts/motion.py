"""Turn a slide's reveal groups into PowerPoint timing, and give it a transition.

Everything here runs after the last shape exists, because all of it needs shape ids. A
spec says how many beats an argument has; ``theme.motion`` says what a beat looks like.
"""

from __future__ import annotations

from deckwright.errors import LayoutError
from deckwright.layouts.components import RevealItem, shape_id
from deckwright.layouts.registry import SlideCtx
from deckwright.motion import (
    add_click_build,
    add_click_reveals,
    add_click_sequence,
    add_transition,
)
from deckwright.spec.model import Placement

_CHART_ANIMATIONS = ("by_category", "by_series")
_ANIMATIONS = ("none", "together", "one_at_a_time", *_CHART_ANIMATIONS)


def apply_click_reveals(
    ctx: SlideCtx, drawn: list[tuple[Placement, list[list[RevealItem]]]]
) -> None:
    """Keep each ``reveals:`` placement hidden until the placement it names is clicked.

    A slide holds one timing tree, so this and the main-sequence build of ``animate:``
    are mutually exclusive.

    Raises:
        LayoutError: the slide also asks for ``animate:``, a ``reveals:`` names an id
            no placement carries or its own, or either end draws nothing revealable.
    """
    if ctx.spec.animate not in (None, "none"):
        raise LayoutError(
            f"slide {ctx.spec.index}: 'reveals:' and 'animate: {ctx.spec.animate}' "
            f"cannot share a slide — a slide carries one animation timeline, and "
            f"these are different kinds. Drop one."
        )
    shapes = {
        p.id: [shape_id(g) for group in made for g in group]
        for p, made in drawn
        if p.id is not None
    }
    pairs: list[tuple[int, int]] = []
    wired: list[tuple[int, list[int]]] = []
    for placement, made in drawn:
        if not placement.reveals:
            continue
        where = f"slide {ctx.spec.index} ({placement.component})"
        if placement.reveals == placement.id:
            raise LayoutError(f"{where}: 'reveals: {placement.reveals}' names itself")
        if placement.reveals not in shapes:
            known = ", ".join(sorted(shapes)) or "none on this slide"
            raise LayoutError(
                f"{where}: 'reveals: {placement.reveals}' names no placement on this "
                f"slide; ids here: {known}"
            )
        trigger = shapes[placement.reveals]
        targets = [shape_id(g) for group in made for g in group]
        if not trigger or not targets:
            raise LayoutError(
                f"{where}: 'reveals:' needs both placements to draw something that can "
                f"be revealed, and one of them reported no shapes"
            )
        # Every shape the trigger placement drew listens: a card's plate is drawn
        # first and its words last, so wiring only the first leaves the words dead.
        pairs.extend((trig, target) for trig in trigger for target in targets)
        wired.append((trigger[0], targets))
    cycle = _reveal_cycle(
        {p.id: p.reveals for p, _ in drawn if p.id is not None and p.reveals is not None}
    )
    if cycle:
        raise LayoutError(
            f"slide {ctx.spec.index}: {' waits on '.join(cycle)} waits on {cycle[0]} — "
            f"every placement in that ring is hidden until one of the others is "
            f"clicked, so none of them can ever be. Give one of them no 'reveals:'."
        )
    add_click_reveals(ctx.slide, pairs)
    for trigger_spid, targets in wired:
        ctx.manifest.record_animation("click_reveals", [targets], clicks=0, trigger=trigger_spid)


def _reveal_cycle(reveals: dict[str, str]) -> list[str] | None:
    """The first ring in the hidden-until-clicked graph, or ``None``.

    ``reveals`` maps a placement to the one whose click reveals it, so a chain is
    legitimate staging and only a ring is unreachable.
    """
    for start in sorted(reveals):
        walked: list[str] = []
        node: str | None = start
        while node is not None and node not in walked:
            walked.append(node)
            node = reveals.get(node)
        if node is not None:
            return walked[walked.index(node) :]
    return None


def apply_reveal(ctx: SlideCtx, groups: list[list[RevealItem]]) -> None:
    """Turn reveal groups into a PowerPoint click build.

    ``by_category``/``by_series`` are chart-only: the chart component emits its own
    ``<p:bldGraphic>`` and reports back empty groups, so empty groups here mean that
    build already happened. Non-empty groups with one of those values means some
    other component reached for chart vocabulary.
    """
    animate = ctx.spec.animate
    if animate is not None and animate not in _ANIMATIONS:
        raise LayoutError(
            f"slide {ctx.spec.index}: unknown animate {animate!r}; "
            f"expected one of {', '.join(_ANIMATIONS)}"
        )
    if animate in _CHART_ANIMATIONS and groups:
        raise LayoutError(
            f"slide {ctx.spec.index}: animate {animate!r} only applies to a native chart"
        )
    if animate is None or animate == "none" or not groups:
        return
    motion = ctx.theme.motion
    if animate == "together":
        # add_click_build fades every shape onto one click, so the groups are not beats.
        flat = [shape_id(g) for group in groups for g in group]
        add_click_build(ctx.slide, flat, motion.stagger_ms)
        ctx.manifest.record_animation("click_build", [flat], clicks=1)
        return
    beat = motion.beat_ms if motion.advance == "after_previous" else None
    add_click_sequence(ctx.slide, _resolve_roles(ctx, groups), motion.stagger_ms, beat_ms=beat)
    ctx.manifest.record_animation(
        "click_sequence", groups, clicks=1 if beat is not None else len(groups)
    )


def _resolve_roles(ctx: SlideCtx, groups: list[list[RevealItem]]) -> list[list[RevealItem]]:
    """Turn each component's motion *role* into the theme's wire-format entrance.

    A component says "I am a line being drawn"; the theme decides that lines wipe, so
    neither the component nor the spec ever names an OOXML preset.

    Raises:
        LayoutError: a component reported a role the theme does not bind.
    """
    roles = ctx.theme.motion.roles
    resolved: list[list[RevealItem]] = []
    for group in groups:
        out: list[RevealItem] = []
        for item in group:
            if not isinstance(item, tuple):
                out.append(item)
                continue
            spid, role = item
            try:
                out.append((spid, roles[role]))
            except KeyError:
                raise LayoutError(
                    f"slide {ctx.spec.index}: component {ctx.component!r} reports "
                    f"motion role {role!r}, which the theme does not bind; known "
                    f"roles: {', '.join(sorted(roles))}"
                ) from None
        resolved.append(out)
    return resolved


def apply_transition(ctx: SlideCtx) -> None:
    """Give the slide the transition the show arrives on.

    Which transition is the theme's; a slide may only refuse it.

    Raises:
        LayoutError: the slide named anything other than ``none``.
    """
    asked = ctx.spec.transition
    if asked is not None and asked != "none":
        raise LayoutError(
            f"slide {ctx.spec.index}: transition {asked!r} — a slide may only say "
            f"'none', for a deliberate hard cut. Which transition a deck uses is the "
            f"theme's ('motion.transition'), so that every deck on the brand moves "
            f"the same way."
        )
    if asked == "none":
        return
    want = ctx.theme.motion.transition
    if want.kind == "none":
        return
    add_transition(ctx.slide, want.kind, direction=want.direction, speed=want.speed)
