"""Raw OOXML effect injection python-pptx exposes no API for."""

from __future__ import annotations

from pptx.oxml import parse_xml

from deckwright.theme.chartstyle import ChartStyle

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_EMU_PER_PT = 12700  # OOXML length units per point
_ANGLE_UNITS_PER_DEGREE = 60000  # OOXML angle units per degree
_ALPHA_UNITS_PER_FRACTION = 100000  # OOXML alpha units per 0.0-1.0 opacity fraction
_SHADOW_COLOR = "000000"


def apply_shadow(spPr, style: ChartStyle) -> None:
    """Add a black drop shadow to ``spPr`` (a data point's shape properties).

    A wrong unit factor here is silent: PowerPoint just renders a shadow that looks off.
    """
    blur = round(style.shadow_blur_pt * _EMU_PER_PT)
    dist = round(style.shadow_dist_pt * _EMU_PER_PT)
    direction = round(style.shadow_dir_deg * _ANGLE_UNITS_PER_DEGREE)
    alpha = round(style.shadow_alpha * _ALPHA_UNITS_PER_FRACTION)
    xml = (
        f'<a:outerShdw xmlns:a="{_A}" blurRad="{blur}" dist="{dist}" dir="{direction}">'
        f'<a:srgbClr val="{_SHADOW_COLOR}"><a:alpha val="{alpha}"/></a:srgbClr>'
        f"</a:outerShdw>"
    )
    spPr.get_or_add_effectLst().append(parse_xml(xml))
