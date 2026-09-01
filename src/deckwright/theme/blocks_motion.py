"""The theme's ``motion:`` block — how a brand paces a reveal, and how slides arrive."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deckwright.errors import LayoutError, ThemeError
from deckwright.motion import transition_xml
from deckwright.motion.builds import ENTRANCES
from deckwright.theme.blocks import mapping, number
from deckwright.theme.model import DEFAULT_MOTION_ROLES, Motion, Transition

MOTION_KEYS = ("stagger_ms", "advance", "beat_ms", "roles", "transition")
TRANSITION_KEYS = ("kind", "dir", "speed")
ADVANCE = ("on_click", "after_previous")


def motion(cfg: Any, *, path: Path) -> Motion:
    """How the brand paces a reveal: a deck spec says how many beats, this says what
    a beat looks like."""
    where = f"theme {path}"
    cfg = mapping(cfg, "motion", where=where)
    unknown = sorted(set(cfg) - set(MOTION_KEYS))
    if unknown:
        raise ThemeError(
            f"{where}: unknown motion key {unknown[0]!r}; known keys: {', '.join(MOTION_KEYS)}"
        )
    stagger = number(
        cfg.get("stagger_ms", 0),
        "motion stagger_ms",
        where=where,
        cast=int,
        expected="a whole number of milliseconds",
    )
    if stagger < 0:
        raise ThemeError(
            f"{where}: motion stagger_ms is {stagger}, which would schedule an "
            f"item before the click that reveals it; use 0 or more"
        )
    advance = str(cfg.get("advance", "on_click"))
    if advance not in ADVANCE:
        raise ThemeError(
            f"{where}: motion advance must be one of {', '.join(ADVANCE)}, got {advance!r}"
        )
    beat = number(
        cfg.get("beat_ms", 400),
        "motion beat_ms",
        where=where,
        cast=int,
        expected="a whole number of milliseconds",
    )
    if beat < 0:
        raise ThemeError(
            f"{where}: motion beat_ms is {beat}; a pause between groups cannot be negative"
        )
    return Motion(
        stagger_ms=stagger,
        advance=advance,
        beat_ms=beat,
        roles=_roles(cfg.get("roles"), path=path),
        transition=_transition(cfg.get("transition"), path=path),
    )


def _roles(cfg: Any, *, path: Path) -> dict[str, str]:
    """Bind each motion role to a wire-format entrance kind, over the defaults."""
    roles = dict(DEFAULT_MOTION_ROLES)
    if cfg is None:
        return roles
    if not isinstance(cfg, dict):
        raise ThemeError(
            f"theme {path}: motion roles must be a mapping of role to kind, got {cfg!r}"
        )
    for role, value in cfg.items():
        if role not in DEFAULT_MOTION_ROLES:
            raise ThemeError(
                f"theme {path}: unknown motion role {role!r}; "
                f"known roles: {', '.join(sorted(DEFAULT_MOTION_ROLES))}"
            )
        kind = value.get("kind") if isinstance(value, dict) else value
        if kind not in ENTRANCES:
            raise ThemeError(
                f"theme {path}: motion role {role!r} names unknown entrance {kind!r}; "
                f"known entrances: {', '.join(sorted(ENTRANCES))}"
            )
        roles[role] = str(kind)
    return roles


def _transition(cfg: Any, *, path: Path) -> Transition:
    """The deck's default slide transition, checked here rather than at slide 40."""
    if cfg is None:
        return Transition()
    if not isinstance(cfg, dict):
        raise ThemeError(
            f"theme {path}: motion transition must be a mapping with 'kind:', got {cfg!r}"
        )
    unknown = sorted(set(cfg) - set(TRANSITION_KEYS))
    if unknown:
        raise ThemeError(
            f"theme {path}: unknown transition key {unknown[0]!r}; "
            f"known keys: {', '.join(TRANSITION_KEYS)}"
        )
    kind = str(cfg.get("kind", "none"))
    direction = str(cfg.get("dir", ""))
    speed = str(cfg.get("speed", "fast"))
    if kind == "none":
        return Transition()
    # Build one now so a bad kind/dir/speed is a load error naming the theme file,
    # not a LayoutError from the middle of a build.
    try:
        transition_xml(kind, direction=direction, speed=speed)
    except LayoutError as exc:
        raise ThemeError(f"theme {path}: {exc}") from None
    return Transition(kind=kind, direction=direction, speed=speed)
