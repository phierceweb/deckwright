"""Drop the slide layouts and masters no slide is built on."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pf_core.log import get_logger

if TYPE_CHECKING:
    from pptx.presentation import Presentation

logger = get_logger(__name__)


@dataclass(frozen=True)
class PruneResult:
    """What the prune pass removed."""

    layouts: int
    masters: int


def prune_unused_layouts(prs: Presentation) -> PruneResult:
    """Remove every layout no slide references, then every master left holding none.

    python-pptx serialises only the parts its relationship graph reaches, so dropping
    the relationship is also what drops each layout's images, theme and hyperlinks.

    Args:
        prs: A fully populated presentation — run this last, immediately before saving.

    Returns:
        A :class:`PruneResult` counting the layouts and masters removed.
    """
    # Partnames, not object ids: an lxml proxy's address is reused once it is dropped,
    # so an id() set can report a layout as used that no slide references — or worse,
    # miss one that is, and remove the layout out from under it.
    used = {slide.slide_layout.part.partname for slide in prs.slides}
    layouts = 0
    for master in list(prs.slide_masters):
        for layout in list(master.slide_layouts):
            if layout.part.partname in used:
                continue
            master.slide_layouts.remove(layout)
            layouts += 1
    masters = _drop_empty_masters(prs)
    logger.info("layouts_pruned", layouts=layouts, masters=masters)
    return PruneResult(layouts=layouts, masters=masters)


def _drop_empty_masters(prs: Presentation) -> int:
    """Drop each layout-less master from ``p:sldMasterIdLst`` *and* the presentation rels.

    Either one alone leaves a dangling ``r:id`` and PowerPoint offers to repair the file.
    """
    id_list = prs._element.get_or_add_sldMasterIdLst()
    dropped = 0
    for entry in list(id_list.sldMasterId_lst):
        if len(prs.part.related_slide_master(entry.rId).slide_layouts):
            continue
        id_list.remove(entry)
        prs.part.drop_rel(entry.rId)
        dropped += 1
    return dropped
