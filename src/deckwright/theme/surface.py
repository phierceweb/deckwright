"""What a template already paints behind a slide, before deckwright paints anything.

A slide composed onto a master inherits the master's background, so ink chosen against
the palette's nominal page — rather than against this — is ink chosen against a colour
that is not on the slide.
"""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

from deckwright.theme.clrscheme import parse_clr_map, resolve_colour
from deckwright.utils.xml import fromstring as parse_xml

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# bgRef indices below this select a fill style; at or above, a background fill style.
_BG_STYLE_BASE = 1000


@dataclass(frozen=True)
class Surface:
    """The background a composed slide inherits from the template it composes on."""

    fills: tuple[str, ...] = ()  # every flat colour it shows; several for a gradient
    media: str | None = None  # ``ppt/media`` filename, when it stretches a picture

    @property
    def flat(self) -> str | None:
        """The one colour this surface is, or None if it is a picture or a gradient."""
        if self.media is not None or len(self.fills) != 1:
            return None
        return self.fills[0]


def inherited_surface(layout) -> Surface | None:
    """The background ``layout`` inherits, resolved through its master and theme.

    Resolution follows OOXML: the layout's own ``p:bg`` wins, else the master's. A
    ``p:bgPr`` carries its fill directly; a ``p:bgRef`` indexes the theme's fill-style
    lists with its own colour standing in for ``phClr``.

    Returns:
        The resolved surface, or None when neither declares one (nothing is painted,
        so the renderer's own default — white — is what shows).
    """
    from deckwright.theme.clrscheme import parse_color_scheme, read_theme_xml

    master = layout.slide_master
    for source in (layout, master):
        bg = source._element.find(f"{{{_P}}}cSld/{{{_P}}}bg")
        if bg is None:
            continue
        theme_xml = read_theme_xml(master)
        scheme = parse_color_scheme(theme_xml)
        clrmap = parse_clr_map(master)
        props = bg.find(f"{{{_P}}}bgPr")
        if props is not None:
            return _from_fill(props, source, scheme=scheme, clrmap=clrmap)
        ref = bg.find(f"{{{_P}}}bgRef")
        if ref is not None:
            return _from_ref(ref, theme_xml, scheme=scheme, clrmap=clrmap)
    return None


def _from_ref(
    ref, theme_xml: bytes, *, scheme: dict[str, str], clrmap: dict[str, str]
) -> Surface | None:
    """Resolve a ``bgRef`` through the theme's fill-style lists."""
    phclr = resolve_colour(ref, scheme=scheme, clrmap=clrmap)
    try:
        idx = int(ref.get("idx", "0"))
    except ValueError:
        return None
    if idx < 1:
        return None
    fmt = parse_xml(theme_xml).find(f".//{{{_A}}}fmtScheme")
    if fmt is None:
        return None
    which = "bgFillStyleLst" if idx >= _BG_STYLE_BASE else "fillStyleLst"
    styles = fmt.find(f"{{{_A}}}{which}")
    position = (idx - _BG_STYLE_BASE if idx >= _BG_STYLE_BASE else idx) - 1
    if styles is None or not 0 <= position < len(styles):
        return None
    # A picture fill reached this way embeds its blip in the theme part, whose
    # relationships are not walkable from here; it resolves to no known surface.
    return _flat(styles[position], scheme=scheme, clrmap=clrmap, phclr=phclr)


def _from_fill(props, source, *, scheme: dict[str, str], clrmap: dict[str, str]) -> Surface | None:
    """Resolve a ``bgPr``'s direct fill, naming the media part of a picture fill."""
    for child in props:
        if etree.QName(child).localname == "blipFill":
            name = _media_name(child, source)
            return None if name is None else Surface(media=name)
        surface = _flat(child, scheme=scheme, clrmap=clrmap, phclr=None)
        if surface is not None:
            return surface
    return None


def _flat(
    fill, *, scheme: dict[str, str], clrmap: dict[str, str], phclr: str | None
) -> Surface | None:
    """A solid or gradient fill as the set of flat colours it shows."""
    tag = etree.QName(fill).localname
    if tag == "solidFill":
        colour = resolve_colour(fill, scheme=scheme, clrmap=clrmap, phclr=phclr)
        return None if colour is None else Surface(fills=(colour,))
    if tag == "gradFill":
        stops = [
            resolve_colour(stop, scheme=scheme, clrmap=clrmap, phclr=phclr)
            for stop in fill.findall(f"{{{_A}}}gsLst/{{{_A}}}gs")
        ]
        found = tuple(dict.fromkeys(s for s in stops if s))
        return Surface(fills=found) if found else None
    return None


def _media_name(blip_fill, source) -> str | None:
    """The ``ppt/media`` filename a ``blipFill`` embeds, via its part's relationships."""
    blip = blip_fill.find(f"{{{_A}}}blip")
    if blip is None:
        return None
    rid = blip.get(f"{{{_R}}}embed")
    if not rid:
        return None
    try:
        return str(source.part.related_part(rid).partname).rsplit("/", 1)[-1]
    except KeyError:
        return None
