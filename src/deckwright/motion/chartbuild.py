"""A native chart's own build — ``<p:bldGraphic>``/``<a:bldChart>``.

The two mix namespaces (presentationml and drawingml) on purpose — swapping them
produces XML that parses fine and does nothing, the same failure mode as a missing
bldLst.
"""

from __future__ import annotations

from deckwright.errors import LayoutError
from deckwright.motion._tree import _EFFECTS, attach, timing_xml
from deckwright.motion.builds import _fade_entrance_xml

# "element" collapses to the category-grouped variant of the per-point builds.
_CHART_BUILDS = {
    "category": "category",
    "series": "series",
    "element": "categoryEl",
    "all": "allAtOnce",
}


def _chart_part_xml(
    spid: int, parts: int, *, by_series: bool, start_id: int, kind: str = "wipeup"
) -> str:
    """One click-triggered entrance per chart element, plus the axes/grid first.

    ``<a:bldChart>`` alone only declares which build the UI offers; the stagger has to
    exist as one node per element targeting a ``<p:graphicEl>`` rather than the whole
    frame, or the chart fades in as one piece. The background element always fades —
    wiping gridlines upward reads as a glitch.
    """
    preset, subtype, filt, dur = _EFFECTS[kind]
    cid = start_id
    nodes = ""
    # -1 in the unused axis means "every series"/"every category"; the background
    # element (both -1) carries the plot area, axes and gridlines.
    targets = [(-1, -1)] + [(i, -1) if by_series else (-1, i) for i in range(parts)]
    for index, (series_idx, cat_idx) in enumerate(targets):
        e, cset, canim = cid, cid + 1, cid + 2
        cid += 3
        is_background = index == 0
        # bldStep is use="required" — omitting it fails XSD validation, and no
        # render shows that.
        step = "gridLegend" if is_background else ("series" if by_series else "category")
        target = (
            f'<p:tgtEl><p:spTgt spid="{spid}"><p:graphicEl>'
            f'<a:chart seriesIdx="{series_idx}" categoryIdx="{cat_idx}" bldStep="{step}"/>'
            f"</p:graphicEl></p:spTgt></p:tgtEl>"
        )
        p_id, p_sub = (10, 0) if is_background else (preset, subtype)
        p_filt, p_dur = ("fade", 500) if is_background else (filt, dur)
        nodes += (
            f'<p:par><p:cTn id="{e}" presetID="{p_id}" presetClass="entr"'
            f' presetSubtype="{p_sub}" fill="hold" grpId="{index}" nodeType="clickEffect">'
            f'<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
            f'<p:set><p:cBhvr><p:cTn id="{cset}" dur="1" fill="hold">'
            f'<p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>{target}'
            f"<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>"
            f'<p:to><p:strVal val="visible"/></p:to></p:set>'
            f'<p:animEffect transition="in" filter="{p_filt}"><p:cBhvr>'
            f'<p:cTn id="{canim}" dur="{p_dur}"/>{target}</p:cBhvr></p:animEffect>'
            f"</p:childTnLst></p:cTn></p:par>"
        )
    return nodes


def add_chart_build(slide, spid: int, by: str, *, parts: int = 0, kind: str = "wipeup") -> None:
    """Make a native chart's own build reveal it one ``by`` unit at a time on click.

    Args:
        slide: The slide the chart is on.
        spid: The chart's ``graphicFrame`` shape id (``frame.shape_id``) —
            pointing this at any other shape is the classic cause of a
            PowerPoint "needs repair" prompt.
        by: ``"category"``, ``"series"``, ``"element"`` or ``"all"``.
        kind: Entrance for each element — ``"wipeup"`` (the default) grows a bar
            out of the axis; ``"fade"`` is the flatter alternative.
        parts: How many categories (or series) to stagger. Without it the whole
            chart fades on one click.

    Raises:
        LayoutError: ``by`` is not one of the values above.
    """
    try:
        bld = _CHART_BUILDS[by]
    except KeyError:
        raise LayoutError(
            f"chart build 'by' must be one of {', '.join(_CHART_BUILDS)}, got {by!r}"
        ) from None
    if bld == "allAtOnce" or parts < 1:
        effects = _fade_entrance_xml([spid], start_id=5)
        groups = 1
    else:
        effects = _chart_part_xml(spid, parts, by_series=bld == "series", start_id=5, kind=kind)
        groups = parts + 1  # the background element takes the first click
    builds = "".join(
        f'<p:bldGraphic spid="{spid}" grpId="{i}"><p:bldSub>'
        f'<a:bldChart bld="{bld}"/></p:bldSub></p:bldGraphic>'
        for i in range(groups)
    )
    attach(slide, timing_xml(effects, builds))
