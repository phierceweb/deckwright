"""Paragraphs at a readable measure — copy that is neither a list nor a chart."""

from __future__ import annotations

from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, component
from deckwright.layouts.registry import SlideCtx
from deckwright.utils.shapes import ANCHOR, para, textbox
from deckwright.utils.text import LINE_HEIGHT, estimate_caveat, wrapped_lines

from deckwright.components._shape import anchored, known_fields

_FIELDS = ("paragraphs", "cite")
# A full 16:9 content band sets a ~120-character line nobody can track back to the next
# one; the frame is capped near the classic 66-character measure instead.
_MEASURE_EM = 30.0
_PARA_SPACE_PT = 8
_CITE_GAP_PT = 6


@component("prose")
def prose(ctx: SlideCtx) -> BodyResult:
    """Set ``paragraphs`` at body size on a capped measure; ``cite`` makes it a quote."""
    known_fields(ctx, _FIELDS)
    raw = ctx.body.get("paragraphs")
    if (
        not isinstance(raw, list)
        or not raw
        or not all(isinstance(p, str) and p.strip() for p in raw)
    ):
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'prose'): 'paragraphs' is a non-empty "
            f"list of strings, one per paragraph"
        )
    paragraphs = [str(p) for p in raw]
    cite = str(ctx.body.get("cite", "")) or None

    rect = ctx.body_rect
    style = ctx.style("body")
    face = ctx.theme.font_for(style)
    width = min(rect.width, _MEASURE_EM * style.size / 72)

    line_h = style.size * LINE_HEIGHT / 72
    needed = (
        sum(wrapped_lines(p, width_in=width, size_pt=style.size, face=face) for p in paragraphs)
        * line_h
    )
    needed += (len(paragraphs) - 1) * _PARA_SPACE_PT / 72
    caption = ctx.style("caption")
    if cite:
        needed += _CITE_GAP_PT / 72 + caption.size * LINE_HEIGHT / 72
    if needed > rect.height:
        raise LayoutError(
            f"slide {ctx.spec.index} (component 'prose'): {len(paragraphs)} paragraph(s) "
            f"need {needed:.2f}in at this measure but the body rect is only "
            f"{rect.height:.2f}in — split the slide or shorten the copy{estimate_caveat(face)}"
        )

    box = anchored(rect, width, needed, align=ctx.align, anchor="top")
    tf = textbox(ctx.slide, box.left, box.top, box.width, box.height, anchor=ANCHOR["top"])
    ink, paper = ctx.text_ink(box, size_pt=style.size)
    for index, text in enumerate(paragraphs):
        para(
            tf,
            text,
            style.size,
            ctx.rgb(ink),
            italic=cite is not None,
            first=index == 0,
            space_after=_PARA_SPACE_PT,
            font=face,
        )
    if cite:
        para(
            tf,
            f"— {cite}",
            caption.size,
            ctx.rgb(ctx.text_ink(box, size_pt=caption.size, muted=True)[0]),
            space_after=0,
            font=ctx.theme.font_for(caption),
        )
    ctx.manifest.record(
        tf._parent,
        lines=paragraphs + ([f"— {cite}"] if cite else []),
        font_pt=style.size,
        line_pt=[style.size] * len(paragraphs) + ([caption.size] if cite else []),
        fg=ink,
        bg=paper,
    )
    return BodyResult(groups=[[(tf._parent.shape_id, "text")]], height=needed)
