"""Main-sequence shape builds — reveal as the slide is advanced.

Both emit a ``<p:bldLst>`` alongside the timing. Omitting the bldLst is what makes
PowerPoint open the file with "needs repair" and strip the timing.
"""

from __future__ import annotations

from deckwright.motion._tree import (
    _A,
    _EFFECTS,
    _P,
    attach,
    bld_p_list,
    text_bearing,
    timing_xml,
)

#: The entrance kinds a motion role may bind to.
ENTRANCES = tuple(sorted(_EFFECTS))


def _fade_entrance_xml(
    target_spids, *, start_id: int, stagger_ms: int = 0, grouped: set[int] | None = None
) -> str:
    """One ``clickEffect``/``withEffect`` fade-in node per spid, sharing one click.

    ``grouped`` names the spids that got a build-list entry, and only those may carry
    ``grpId`` — the attribute's only job is to name such an entry. ``None`` means all.
    """
    effects = ""
    cid = start_id
    for i, spid in enumerate(target_spids):
        grp = ' grpId="0"' if grouped is None or int(spid) in grouped else ""
        node = "clickEffect" if i == 0 else "withEffect"
        e, cset, canim = cid, cid + 1, cid + 2
        cid += 3
        effects += (
            f'<p:par><p:cTn id="{e}" presetID="10" presetClass="entr" presetSubtype="0" fill="hold"{grp} nodeType="{node}">'
            f'<p:stCondLst><p:cond delay="{i * stagger_ms}"/></p:stCondLst><p:childTnLst>'
            f'<p:set><p:cBhvr><p:cTn id="{cset}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
            f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'
            f"<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>"
            f'<p:to><p:strVal val="visible"/></p:to></p:set>'
            f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{canim}" dur="500"/>'
            f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect>'
            f"</p:childTnLst></p:cTn></p:par>"
        )
    return effects


def add_click_build(slide, target_spids, stagger_ms: int = 0) -> None:
    """Reveal all ``target_spids`` on one click, each with a fade entrance.

    ``stagger_ms`` cascades them in list order on that click; ``0`` keeps them
    simultaneous.
    """
    builds = bld_p_list(slide, target_spids)
    effects = _fade_entrance_xml(
        target_spids, start_id=5, stagger_ms=stagger_ms, grouped=text_bearing(slide, target_spids)
    )
    attach(slide, timing_xml(effects, builds))


def add_click_sequence(slide, groups, stagger_ms: int = 0, *, beat_ms: int | None = None) -> None:
    """Reveal ``groups`` one per click.

    Each group is a list whose items are ``spid`` (default fade) or ``(spid, kind)``
    with ``kind`` in :data:`ENTRANCES`; items in a group reveal together.
    ``stagger_ms`` cascades a group's items in list order on its single click.
    ``beat_ms`` instead chains every group onto **one** click, each starting that
    many milliseconds after the previous finishes.
    """
    P, A = _P, _A
    EFFECTS = _EFFECTS
    all_spids = [
        item[0] if isinstance(item, (tuple, list)) else item for group in groups for item in group
    ]
    builds = bld_p_list(slide, all_spids)
    built = text_bearing(slide, all_spids)
    chained = beat_ms is not None
    cid = 3
    clickgroups = ""
    for gi, group in enumerate(groups):
        g_ind, g_zero = cid, cid + 1
        cid += 2
        auto = chained and gi > 0
        gate = f"{beat_ms}" if auto else "indefinite"
        effects = ""
        for i, item in enumerate(group):
            spid, kind = item if isinstance(item, (tuple, list)) else (item, "fade")
            pid, psub, filt, dur = EFFECTS[kind]
            grp = ' grpId="0"' if int(spid) in built else ""
            first = "afterEffect" if auto else "clickEffect"
            node = first if i == 0 else "withEffect"
            delay = i * stagger_ms
            e, cset, canim = cid, cid + 1, cid + 2
            cid += 3
            effects += (
                f'<p:par><p:cTn id="{e}" presetID="{pid}" presetClass="entr" presetSubtype="{psub}" fill="hold"{grp} nodeType="{node}">'
                f'<p:stCondLst><p:cond delay="{delay}"/></p:stCondLst><p:childTnLst>'
                f'<p:set><p:cBhvr><p:cTn id="{cset}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
                f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'
                f"<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>"
                f'<p:to><p:strVal val="visible"/></p:to></p:set>'
                f'<p:animEffect transition="in" filter="{filt}"><p:cBhvr><p:cTn id="{canim}" dur="{dur}"/>'
                f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect>'
                f"</p:childTnLst></p:cTn></p:par>"
            )
        clickgroups += (
            f'<p:par><p:cTn id="{g_ind}" fill="hold"><p:stCondLst><p:cond delay="{gate}"/></p:stCondLst><p:childTnLst>'
            f'<p:par><p:cTn id="{g_zero}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
            f"{effects}"
            f"</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>"
        )
    bld = f"<p:bldLst>{builds}</p:bldLst>" if builds else ""
    xml = (
        f'<p:timing xmlns:p="{P}" xmlns:a="{A}"><p:tnLst><p:par>'
        f'<p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
        f'<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
        f"{clickgroups}"
        f"</p:childTnLst></p:cTn>"
        f'<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
        f'<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>'
        f"</p:seq></p:childTnLst></p:cTn></p:par></p:tnLst>"
        f"{bld}</p:timing>"
    )
    attach(slide, xml)
