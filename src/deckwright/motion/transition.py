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

from lxml import etree
from pptx.oxml import parse_xml

from deckwright.errors import LayoutError

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_P159 = "http://schemas.microsoft.com/office/powerpoint/2015/09/main"

# Not one of the base schema's effects: an extension behind a fallback. See `morph_xml`.
MORPH = "morph"

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


def morph_xml(speed: str) -> str:
    """PowerPoint's own morph: a ``p159`` Choice and a fade Fallback, where ``p:transition`` goes.

    Morph pairs shapes that carry one name on both slides; a reader without ``p159`` fades.

    Raises:
        LayoutError: unknown speed.
    """
    if speed not in SPEEDS:
        raise LayoutError(f"transition speed must be one of {', '.join(SPEEDS)}, got {speed!r}")
    return (
        f'<mc:AlternateContent xmlns:mc="{_MC}" xmlns:p="{_P}">'
        f'<mc:Choice xmlns:p159="{_P159}" Requires="p159">'
        f'<p:transition spd="{speed}"><p159:morph option="byObject"/></p:transition></mc:Choice>'
        f'<mc:Fallback><p:transition spd="{speed}"><p:fade/></p:transition></mc:Fallback>'
        f"</mc:AlternateContent>"
    )


def _carried(slide_element):
    """The slide's ``p:transition``, read through a markup-compatibility wrapper's Choice."""
    direct = slide_element.find(f"{{{_P}}}transition")
    if direct is not None:
        return direct
    return slide_element.find(f"{{{_MC}}}AlternateContent/{{{_MC}}}Choice/{{{_P}}}transition")


def read_kind(slide_element) -> str:
    """The transition kind a slide carries, ``"none"`` when it carries none."""
    node = _carried(slide_element)
    if node is None:
        return "none"
    kinds = [etree.QName(child).localname for child in node]
    return next((k for k in kinds if k not in ("sndAc", "extLst")), "none")


def add_transition(slide, kind: str, *, direction: str = "", speed: str = "fast") -> None:
    """Give ``slide`` the transition the show uses to arrive at it.

    Inserted ahead of ``<p:timing>`` and ``<p:extLst>`` so the child order stays legal
    whether or not the slide already carries an animation.

    Raises:
        LayoutError: the arguments are invalid, or the slide already has a transition.
    """
    if _carried(slide._element) is not None:
        raise LayoutError("this slide already carries a transition")
    if kind == MORPH:
        xml = morph_xml(speed)
    else:
        xml = transition_xml(kind, direction=direction, speed=speed)
    slide._element.insert_element_before(parse_xml(xml), "p:timing", "p:extLst")
