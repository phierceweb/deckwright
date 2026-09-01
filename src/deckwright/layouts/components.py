"""Body-component registration.

A component returns a :class:`BodyResult`: one reveal group per revealable unit — shape
ids, or ``(shape_id, kind)`` tuples for a specific entrance — plus the vertical extent it
consumed. A component that does not report height may return a bare group list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from pf_core.log import get_logger

from deckwright.errors import LayoutError

logger = get_logger(__name__)

RevealItem = int | tuple[int, str]


def shape_id(item: RevealItem) -> int:
    """The shape id in a reveal item, whether or not it carries an entrance kind."""
    return item[0] if isinstance(item, tuple) else item


Component = Callable[..., "BodyResult | list[list[RevealItem]]"]


@dataclass(frozen=True)
class BodyResult:
    """What a component tells its layout: how to reveal it, and how tall it came out."""

    groups: list[list[RevealItem]] = field(default_factory=list)
    height: float | None = None


def as_body_result(value: BodyResult | list[list[RevealItem]] | None) -> BodyResult:
    """Accept a bare group list from a component that does not report its height."""
    if isinstance(value, BodyResult):
        return value
    return BodyResult(groups=list(value or []))


_REGISTRY: dict[str, Component] = {}


def component(name: str) -> Callable[[Component], Component]:
    """Register the decorated function as the body component called ``name``."""

    def decorate(fn: Component) -> Component:
        if name in _REGISTRY:
            raise LayoutError(f"body component {name!r} is already registered")
        _REGISTRY[name] = fn
        return fn

    return decorate


def get_component(name: str) -> Component:
    """Look up a body component by name."""
    try:
        return _REGISTRY[name]
    except KeyError:
        raise LayoutError(
            f"unknown body component {name!r}; available: {', '.join(registered_components())}"
        ) from None


def registered_components() -> tuple[str, ...]:
    """Every registered component name, sorted."""
    return tuple(sorted(_REGISTRY))
