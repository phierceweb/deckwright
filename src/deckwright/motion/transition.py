"""Write a slide's ``<p:transition>`` — how the deck arrives *at* this slide.

**The transition belongs to the destination slide**: it says how the show moves *to*
this slide, not away from it. Reading it the other way puts every transition in a deck
one slide out.

Two hazards, both invisible to the render loop because LibreOffice repairs them
silently on import:

- ``CT_Slide`` is an ``xsd:sequence`` — ``transition`` precedes ``timing``, so a bare
  ``append`` after an animation lands it in the wrong place.
- Direction vocabularies are **per element**, not shared, so one generic direction list
  produces a file that is invalid the moment it meets ``strips``.
"""

from __future__ import annotations

from pptx.oxml import parse_xml

from deckwright.errors import LayoutError

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"

_EDGES = ("l", "u", "r", "d")
_CORNERS = ("lu", "ru", "ld", "rd")
_AXES = ("horz", "vert")

# Every effect the base schema allows, mapped to the directions *that element* accepts;
# an empty tuple takes no direction at all.
EFFECTS: dict[str, tuple[str, ...]] = {
    "blinds": _AXES,
    "checker": _AXES,
    "circle": (),
    "comb": _AXES,
    "cover": _EDGES + _CORNERS,
    "cut": (),
    "diamond": (),
    "dissolve": (),
    "fade": (),
    "newsflash": (),
    "plus": (),
    "pull": _EDGES + _CORNERS,
    "push": _EDGES,
    "random": (),
    "randomBar": _AXES,
    "split": ("out", "in"),
    "strips": _CORNERS,
    "wedge": (),
    "wheel": (),
    "wipe": _EDGES,
    "zoom": ("out", "in"),
}

SPEEDS = ("slow", "med", "fast")


def transition_xml(kind: str, *, direction: str = "", speed: str = "fast") -> str:
    """The ``<p:transition>`` element for one slide.

    Args:
        kind: An effect name from :data:`EFFECTS`.
        direction: A direction that *this* effect accepts, or ``""`` for its default.
        speed: ``slow``, ``med`` or ``fast``.

    Raises:
        LayoutError: unknown kind, unknown speed, or a direction this effect refuses.
    """
    try:
        allowed = EFFECTS[kind]
    except KeyError:
        raise LayoutError(
            f"unknown transition {kind!r}; known transitions: {', '.join(sorted(EFFECTS))}"
        ) from None
    if speed not in SPEEDS:
        raise LayoutError(f"transition speed must be one of {', '.join(SPEEDS)}, got {speed!r}")
    if direction and not allowed:
        raise LayoutError(f"transition {kind!r} takes no direction, got {direction!r}")
    if direction and direction not in allowed:
        raise LayoutError(
            f"transition {kind!r} has no direction {direction!r}; it accepts: {', '.join(allowed)}"
        )
    attr = f' dir="{direction}"' if direction else ""
    return f'<p:transition xmlns:p="{_P}" spd="{speed}"><p:{kind}{attr}/></p:transition>'


def add_transition(slide, kind: str, *, direction: str = "", speed: str = "fast") -> None:
    """Give ``slide`` the transition the show uses to arrive at it.

    Inserted ahead of ``<p:timing>`` and ``<p:extLst>`` so the child order stays legal
    whether or not the slide already carries an animation.

    Raises:
        LayoutError: the arguments are invalid, or the slide already has a transition.
    """
    if slide._element.find(f"{{{_P}}}transition") is not None:
        raise LayoutError("this slide already carries a transition")
    xml = transition_xml(kind, direction=direction, speed=speed)
    slide._element.insert_element_before(parse_xml(xml), "p:timing", "p:extLst")
