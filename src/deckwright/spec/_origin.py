"""A deckwright shape's name, read back into the placement that drew it.

The build names each shape ``s<slide>.<id or pN>.<component>`` — ``m.<name>.<component>``
for a morph placement — with ``#k`` for the k-th shape it drew or ``.<part>`` for a record
such as a table cell. Chrome and the background are named too, but belong to no placement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from deckwright.layouts.components import registered_components

_HEAD = re.compile(r"^(?:s(\d+)|(m))\.(.+)$")


@dataclass(frozen=True)
class Origin:
    """Which slide, placement and component drew a shape, and which of its parts it is."""

    slide: int | None  # None for a morph placement, whose name carries no slide
    placement: str  # the placement's id, its ``pN``, or its morph name
    component: str
    part: str | None = None

    @property
    def morph(self) -> bool:
        return self.slide is None

    @property
    def token(self) -> str:
        """The name's origin prefix, shared by every shape the placement drew."""
        head = "m" if self.slide is None else f"s{self.slide}"
        return f"{head}.{self.placement}.{self.component}"


def origin_of(name: str) -> Origin | None:
    """The placement ``name`` belongs to, or None for chrome, a background or a stranger."""
    match = _HEAD.match(name)
    if match is None:
        return None
    slide, rest = match.group(1), match.group(3)
    rest, _, number = rest.partition("#")
    segments = rest.split(".")
    known = set(registered_components())
    for at in range(len(segments) - 1, 0, -1):
        if segments[at] in known:
            part = number or ".".join(segments[at + 1 :]) or None
            return Origin(
                slide=int(slide) if slide else None,
                placement=".".join(segments[:at]),
                component=segments[at],
                part=part,
            )
    return None
