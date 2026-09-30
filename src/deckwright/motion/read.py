"""Read a slide's timing tree back: what each sequence reveals and how many clicks it spends."""

from __future__ import annotations

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"


def entrance_targets(node) -> set[int]:
    """Shape ids an entrance effect under ``node`` makes visible."""
    out: set[int] = set()
    for ctn in node.iter(f"{{{_P}}}cTn"):
        if ctn.get("presetClass") != "entr":
            continue
        for target in ctn.iter(f"{{{_P}}}spTgt"):
            if (spid := str(target.get("spid", ""))).isdigit():
                out.add(int(spid))
    return out


def sequences(root) -> tuple[list[tuple[int | None, set[int]]], set[int]]:
    """Each interactive ``(trigger, targets)``, and what the main sequence reveals."""
    interactive: list[tuple[int | None, set[int]]] = []
    main: set[int] = set()
    for seq in root.iter(f"{{{_P}}}seq"):
        ctn = seq.find(f"{{{_P}}}cTn")
        if ctn is None:
            continue
        if ctn.get("nodeType") == "mainSeq":
            main |= entrance_targets(ctn)
            continue
        if ctn.get("nodeType") != "interactiveSeq":
            continue
        trigger = None
        conds = ctn.find(f"{{{_P}}}stCondLst")
        if conds is not None:
            target = conds.find(f".//{{{_P}}}spTgt")
            if target is not None and str(target.get("spid", "")).isdigit():
                trigger = int(str(target.get("spid")))
        body = ctn.find(f"{{{_P}}}childTnLst")
        interactive.append((trigger, entrance_targets(body) if body is not None else set()))
    return interactive, main


def clicks(root) -> int:
    """Clicks the main sequence spends: each click's first effect is a ``clickEffect``."""
    for seq in root.iter(f"{{{_P}}}seq"):
        ctn = seq.find(f"{{{_P}}}cTn")
        if ctn is not None and ctn.get("nodeType") == "mainSeq":
            return sum(
                1 for node in ctn.iter(f"{{{_P}}}cTn") if node.get("nodeType") == "clickEffect"
            )
    return 0
