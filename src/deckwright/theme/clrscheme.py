"""Extract the colour and font schemes from a presentation's theme part.

python-pptx exposes no theme API, so the part is fetched through the slide master's
relationships and parsed directly.
"""

from __future__ import annotations

from lxml import etree
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

from deckwright.errors import ThemeError
from deckwright.utils.xml import fromstring as parse_xml

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def read_theme_xml(master) -> bytes:
    """Return the raw XML of the theme part related to ``master``.

    Per-master: a template may carry several masters with different themes, and the
    palette must come from the one slides are actually composed on.
    """
    try:
        return master.part.part_related_by(RT.THEME).blob
    except KeyError as e:
        raise ThemeError("slide master has no theme part") from e


def parse_color_scheme(xml: bytes) -> dict[str, str]:
    """Map each ``clrScheme`` slot name to an uppercase 6-digit hex string.

    Slots may carry either an ``srgbClr`` or a ``sysClr``; the latter's resolved
    value lives in ``@lastClr``.
    """
    scheme = parse_xml(xml).find(f"{{{_A}}}themeElements/{{{_A}}}clrScheme")
    if scheme is None:
        raise ThemeError("template theme has no clrScheme")
    out: dict[str, str] = {}
    for child in scheme:
        slot = etree.QName(child).localname
        srgb = child.find(f"{{{_A}}}srgbClr")
        sysc = child.find(f"{{{_A}}}sysClr")
        if srgb is not None:
            out[slot] = str(srgb.get("val")).upper()
        elif sysc is not None:
            out[slot] = str(sysc.get("lastClr")).upper()
    return out


def parse_clr_map(master) -> dict[str, str]:
    """Map the ``bg1``/``tx1``/``bg2``/``tx2`` aliases onto the slots they name.

    A template is free to swap them, so a ``schemeClr val="bg1"`` cannot be read as
    ``lt1`` without consulting this.
    """
    el = master._element.find("{http://schemas.openxmlformats.org/presentationml/2006/main}clrMap")
    return {} if el is None else {k: str(v) for k, v in el.attrib.items()}


def resolve_colour(
    el, *, scheme: dict[str, str], clrmap: dict[str, str], phclr: str | None = None
) -> str | None:
    """The hex a DrawingML colour element resolves to, transforms applied.

    ``el`` is the parent holding one of the colour choices (``a:srgbClr``,
    ``a:schemeClr``, ``a:sysClr``) — a fill, a gradient stop, a ``bgRef``.

    Returns:
        Uppercase 6-digit hex, or None when the element carries no colour choice.
    """
    for child in el:
        base = _base_colour(child, scheme=scheme, clrmap=clrmap, phclr=phclr)
        if base is not None:
            return _transform(base, child)
    return None


def _base_colour(
    child, *, scheme: dict[str, str], clrmap: dict[str, str], phclr: str | None
) -> str | None:
    tag = etree.QName(child).localname
    if tag == "srgbClr":
        return str(child.get("val", "")).upper() or None
    if tag == "sysClr":
        return str(child.get("lastClr", "")).upper() or None
    if tag != "schemeClr":
        return None
    val = str(child.get("val", ""))
    if val == "phClr":
        return phclr
    return scheme.get(clrmap.get(val, val))


_SCALE = 100000.0


def _transform(hex_colour: str, el) -> str:
    """Apply the ``lumMod``/``lumOff``/``shade``/``tint`` children of a colour element."""
    from deckwright.theme.palette import lum  # circular at module scope: palette imports colour

    factor, offset = 1.0, 0.0
    out = hex_colour
    for mod in el:
        name = etree.QName(mod).localname
        try:
            val = float(mod.get("val", "")) / _SCALE
        except ValueError:
            continue
        if name == "lumMod":
            factor = val
        elif name == "lumOff":
            offset = val
        elif name == "shade":
            out = _channels(out, val, 0.0)
        elif name == "tint":
            out = _channels(out, val, 255 * (1 - val))
    if (factor, offset) != (1.0, 0.0):
        out = lum(out, factor, offset)
    return out


def _channels(hex_colour: str, gain: float, bias: float) -> str:
    """Every channel scaled by ``gain`` then lifted by ``bias``, clamped to a byte."""
    return "".join(
        f"{min(255, max(0, round(int(hex_colour[i : i + 2], 16) * gain + bias))):02X}"
        for i in (0, 2, 4)
    )


# The fontScheme's own script codes for the CJK scripts a theme's `type.ea` names.
_SCRIPT_CODES = {"Jpan": "ja", "Hang": "ko", "Hans": "zh-Hans", "Hant": "zh-Hant"}


def parse_script_fonts(xml: bytes) -> dict[str, str]:
    """The minor font's CJK typeface per script, keyed as ``type.ea`` keys them.

    A template sets these in ``a:font script="Jpan"`` entries; its ``a:ea`` slot is almost
    always empty, and names no script when it is not.
    """
    root = parse_xml(xml)
    minor = root.find(f"{{{_A}}}themeElements/{{{_A}}}fontScheme/{{{_A}}}minorFont")
    if minor is None:
        return {}
    out = {}
    for font in minor.iterfind(f"{{{_A}}}font"):
        key = _SCRIPT_CODES.get(str(font.get("script")))
        if key and font.get("typeface"):
            out[key] = str(font.get("typeface"))
    return out


def parse_font_scheme(xml: bytes) -> tuple[str, str]:
    """Return the ``(major, minor)`` latin typefaces from the theme's fontScheme."""
    root = parse_xml(xml)
    scheme = root.find(f"{{{_A}}}themeElements/{{{_A}}}fontScheme")
    if scheme is None:
        raise ThemeError("template theme has no fontScheme")

    def _face(kind: str) -> str:
        el = scheme.find(f"{{{_A}}}{kind}Font/{{{_A}}}latin")
        if el is None or not el.get("typeface"):
            raise ThemeError(f"template fontScheme has no {kind} latin typeface")
        return str(el.get("typeface"))

    return _face("major"), _face("minor")
