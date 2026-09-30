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
    # PowerPoint's own shape: cancelBubble and a next-condition on the trigger's click keep a
    # click anywhere else on the slide from stepping every trigger forward.
    for trig, targ in pairs:
        s0, s1, s2, s3, s4 = cid, cid + 1, cid + 2, cid + 3, cid + 4
        cid += 10
        listen = (
            f'<p:cond evt="onClick" delay="0"><p:tgtEl><p:spTgt spid="{trig}"/></p:tgtEl></p:cond>'
        )
        seqs += (
            f'<p:seq concurrent="1" nextAc="seek">'
            f'<p:cTn id="{s0}" restart="whenNotActive" fill="hold" evtFilter="cancelBubble" nodeType="interactiveSeq">'
            f"<p:stCondLst>{listen}</p:stCondLst>"
            f'<p:endSync evt="end" delay="0"><p:rtn val="all"/></p:endSync>'
            f'<p:childTnLst><p:par><p:cTn id="{s1}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
            f'<p:par><p:cTn id="{s2}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
            f'<p:par><p:cTn id="{s3}" presetID="1" presetClass="entr" presetSubtype="0" fill="hold" nodeType="clickEffect">'
            f'<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst><p:set><p:cBhvr>'
            f'<p:cTn id="{s4}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
            f'<p:tgtEl><p:spTgt spid="{targ}"/></p:tgtEl>'
            f"<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>"
            f'<p:to><p:strVal val="visible"/></p:to></p:set></p:childTnLst></p:cTn></p:par>'
            f"</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn>"
            f"<p:nextCondLst>{listen}</p:nextCondLst></p:seq>"
        )
    # No main sequence at all: these triggers spend no slide advance, and an empty
    # <p:childTnLst/> on a mainSeq is schema-invalid (CT_TimeNodeList needs a child).
    xml = (
        f'<p:timing xmlns:p="{P}" xmlns:a="{A}"><p:tnLst><p:par>'
        f'<p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
        f"{seqs}</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>"
    )
    attach(slide, xml)
