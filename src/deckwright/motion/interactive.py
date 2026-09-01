"""Interactive triggers — reveal on clicking a specific shape.

An ``interactiveSeq`` fires on clicking a named shape, in any order, without consuming
a slide advance.
"""

from __future__ import annotations

from deckwright.errors import LayoutError
from deckwright.motion._tree import _A, _P, attach


def add_click_reveals(slide, pairs) -> None:
    """Wire click-to-reveal interactions onto ``slide``.

    Each item in ``pairs`` is a ``(trigger_spid, target_spid)`` tuple: the target
    stays hidden until its trigger shape is clicked, and may appear under several.

    Raises:
        LayoutError: ``pairs`` is empty. The tree would then hold an empty
            ``<p:childTnLst/>``, which ``CT_TimeNodeList`` forbids.
    """
    if not pairs:
        raise LayoutError(
            "add_click_reveals needs at least one (trigger, target) pair — a timing "
            "tree with no interaction in it is schema-invalid"
        )
    P, A = _P, _A
    seqs = ""
    cid = 3
    for trig, targ in pairs:
        s0, s1, s2, s3 = cid, cid + 1, cid + 2, cid + 3
        cid += 10
        seqs += (
            f'<p:seq concurrent="1" nextAc="seek"><p:cTn id="{s0}" restart="whenNotActive" fill="hold" nodeType="interactiveSeq">'
            f'<p:stCondLst><p:cond evt="onClick" delay="0"><p:tgtEl><p:spTgt spid="{trig}"/></p:tgtEl></p:cond></p:stCondLst>'
            f'<p:childTnLst><p:par><p:cTn id="{s1}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
            f'<p:par><p:cTn id="{s2}" presetID="1" presetClass="entr" presetSubtype="0" fill="hold" nodeType="clickEffect">'
            f'<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst><p:set><p:cBhvr>'
            f'<p:cTn id="{s3}" dur="1" fill="hold"/><p:tgtEl><p:spTgt spid="{targ}"/></p:tgtEl>'
            f"<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>"
            f'<p:to><p:strVal val="visible"/></p:to></p:set></p:childTnLst></p:cTn></p:par>'
            f"</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn>"
            f'<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
            f'<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>'
        )
    # No main sequence at all: these triggers spend no slide advance, and an empty
    # <p:childTnLst/> on a mainSeq is schema-invalid (CT_TimeNodeList needs a child).
    xml = (
        f'<p:timing xmlns:p="{P}" xmlns:a="{A}"><p:tnLst><p:par>'
        f'<p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
        f"{seqs}</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>"
    )
    attach(slide, xml)
