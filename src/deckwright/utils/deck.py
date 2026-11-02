"""Slide-collection operations python-pptx doesn't expose directly."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn

from deckwright.errors import ThemeError


def open_presentation(
    path: str | Path, *, what: str = "template", error: type[Exception] = ThemeError
):
    """Open ``path`` as a ``Presentation``, naming the file when it will not read.

    python-pptx surfaces an unreadable package as any of ``PackageNotFoundError``,
    ``KeyError``, ``ValueError`` or ``XMLSyntaxError`` — classes sharing no base.

    Raises:
        ThemeError: (or whatever ``error`` names) the file is not a readable ``.pptx``.
    """
    try:
        return Presentation(str(path))
    except Exception as e:  # noqa: BLE001 — python-pptx shares no base for these
        raise error(f"{what} {path} is not a readable .pptx: {type(e).__name__}: {e}") from e


def delete_slide(prs, index: int) -> None:
    """Remove the slide at ``index`` from ``prs``.

    python-pptx has no public slide delete.

    Args:
        prs: The ``Presentation`` to mutate in place.
        index: Zero-based position of the slide to remove.
    """
    sld_id_lst = prs.slides._sldIdLst
    sld_id = list(sld_id_lst)[index]
    rid = sld_id.get(qn("r:id"))
    try:
        prs.part.drop_rel(rid)
    except Exception:  # noqa: BLE001 — the relationship may already be gone
        pass
    sld_id_lst.remove(sld_id)


def register_notes_master(prs) -> None:
    """Declare the notes master in ``p:notesMasterIdLst``.

    python-pptx creates the notes master and its relationship the first time a
    slide's notes are touched, but never registers it on the presentation. The
    element is optional in the schema, so nothing downstream objects until
    Keynote, which refuses to read the package at all.
    """
    rid = next((r.rId for r in prs.part.rels.values() if r.reltype == RT.NOTES_MASTER), None)
    root = prs._element
    if rid is None or root.find(qn("p:notesMasterIdLst")) is not None:
        return
    lst = root.makeelement(qn("p:notesMasterIdLst"), {})
    lst.append(root.makeelement(qn("p:notesMasterId"), {qn("r:id"): rid}))
    root.find(qn("p:sldMasterIdLst")).addnext(lst)
