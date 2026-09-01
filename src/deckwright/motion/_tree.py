"""The ``<p:timing>`` skeleton every main-sequence build is wrapped in."""

from __future__ import annotations

from pptx.oxml import parse_xml
from pptx.oxml.ns import qn

from deckwright.errors import LayoutError

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"

# (presetID, presetSubtype, animEffect filter, duration ms) per effect kind.
# The wipe filters are inverted on purpose: PowerPoint reveals *opposite* the named
# direction, so "wipeup" carries "wipe(down)".
_EFFECTS = {
    "fade": (10, 0, "fade", 500),
    "wipeup": (22, 1, "wipe(down)", 900),
    "wiperight": (22, 2, "wipe(left)", 800),
}


def attach(slide, xml: str) -> None:
    """Add a ``<p:timing>`` in schema order, refusing a second one.

    ``CT_Slide`` allows exactly one timing tree, before ``extLst``. LibreOffice repairs
    both violations silently on import, so no render or round trip can show them.

    Raises:
        LayoutError: the slide already carries a timing tree.
    """
    if slide._element.find(qn("p:timing")) is not None:
        raise LayoutError(
            "this slide already carries an animation timeline, and a slide can hold "
            "only one. Two charts both building, or a chart build beside another "
            "animation, produce this — give one a slide of its own, or drop it to "
            "'animate: together'."
        )
    slide._element.insert_element_before(parse_xml(xml), "p:extLst")


def text_bearing(slide, spids) -> set[int]:
    """Which of ``spids`` are ``<p:sp>`` shapes that actually carry text.

    PowerPoint requires a ``<p:bldP>``'s ``spid`` to name an ``sp`` holding real text
    (``[MS-OI29500]`` §19.5.16(c)); pictures, frames and text-free autoshapes have no
    paragraph build, so a ``bldP`` naming one is a claim the shape cannot honour.
    """
    want = {int(s) for s in spids}
    found: set[int] = set()
    for sp in slide._element.iter(qn("p:sp")):
        nv = sp.find(f"{{{_P}}}nvSpPr/{{{_P}}}cNvPr")
        if nv is None:
            continue
        spid = int(nv.get("id"))
        if spid in want and any((t.text or "").strip() for t in sp.iter(qn("a:t"))):
            found.add(spid)
    return found


def bld_p_list(slide, spids) -> str:
    """``<p:bldP>`` entries for only the spids that may legally carry one."""
    keep = text_bearing(slide, spids)
    return "".join(
        f'<p:bldP spid="{spid}" grpId="0" animBg="1"/>' for spid in spids if spid in keep
    )


def timing_xml(effects_xml: str, bld_lst_xml: str) -> str:
    """Wrap main-sequence ``effects_xml`` and ``<p:bldLst>`` content into one ``<p:timing>``.

    An empty ``bld_lst_xml`` writes no ``<p:bldLst>`` at all: ``CT_BuildList`` requires a
    child, so ``<p:bldLst/>`` is schema-invalid. The effect nodes then carry no
    ``grpId``, whose only job is to name a build-list entry.
    """
    P, A = _P, _A
    bld = f"<p:bldLst>{bld_lst_xml}</p:bldLst>" if bld_lst_xml else ""
    return (
        f'<p:timing xmlns:p="{P}" xmlns:a="{A}"><p:tnLst><p:par>'
        f'<p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
        f'<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
        f'<p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst><p:childTnLst>'
        f'<p:par><p:cTn id="4" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
        f"{effects_xml}"
        f"</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>"
        f"</p:childTnLst></p:cTn>"
        f'<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
        f'<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>'
        f"</p:seq></p:childTnLst></p:cTn></p:par></p:tnLst>"
        f"{bld}</p:timing>"
    )
