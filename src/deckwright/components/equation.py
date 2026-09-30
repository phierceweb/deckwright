"""One display equation: Office Math, with one line of UnicodeMath as its fallback.

PowerPoint stores an equation as a shape inside ``mc:AlternateContent``: the Choice sets the
maths, the Fallback is the same shape for a reader that cannot. The Fallback here is the
equation as a line of text, so LibreOffice, Keynote and every check read the same words.
"""

from __future__ import annotations

import copy

from lxml import etree

from deckwright.components._omml import omml
from deckwright.components._shape import anchored, figure_text, known_fields
from deckwright.components._mathtree import Node, rows
from deckwright.components._tex import parse
from deckwright.components._unicodemath import linear
from deckwright.errors import LayoutError
from deckwright.layouts.components import BodyResult, component
from deckwright.layouts.registry import SlideCtx
from deckwright.theme.model import TypeStyle
from deckwright.utils.a11y import describe
from deckwright.utils.mce import alternate
from deckwright.utils.shapes import ALIGN, ANCHOR, para, textbox
from deckwright.utils.text import LINE_HEIGHT, estimate_caveat, text_em
from deckwright.utils.xml import fromstring as parse_xml

_FIELDS = ("tex", "rung", "alt", "decorative")
_RUNG_DEFAULT = "lead"
# A stacked row's height against the line's: the parts of a fraction sit a little apart.
_ROW = 1.1
_A14 = "http://schemas.microsoft.com/office/drawing/2010/main"


@component("equation")
def equation(ctx: SlideCtx) -> BodyResult:
    """Set ``tex`` at ``rung``, sized for the rows it stacks and never wrapped."""
    known_fields(ctx, _FIELDS)
    where = f"slide {ctx.spec.index} (component 'equation')"
    alt, decorative = figure_text(ctx)
    node = parse(_tex(ctx, where), where=where)
    line = linear(node)
    rung, style = _rung(ctx, where)
    face = ctx.theme.font_for(style)
    rect = ctx.body_rect

    width = text_em(line, face, links=False) * style.size / 72
    if width > rect.width:
        raise LayoutError(
            f"{where}: the equation needs {width:.2f}in on one line but the placement is "
            f"{rect.width:.2f}in wide — an equation does not wrap: widen the placement, set it "
            f"at a smaller 'rung', or split it in two{estimate_caveat(face)}"
        )
    stacked = rows(node)
    height = stacked * _ROW * style.size * LINE_HEIGHT / 72
    if height > rect.height:
        raise LayoutError(
            f"{where}: the equation stacks {stacked} rows, {height:.2f}in tall at {rung!r}, but "
            f"the placement is {rect.height:.2f}in — give it more rows, or a smaller 'rung'"
        )

    box = anchored(rect, width, height, align=ctx.align, anchor=ctx.anchor)
    tf = textbox(ctx.slide, box.left, box.top, box.width, box.height, ANCHOR["middle"], wrap=False)
    ink, paper = ctx.text_ink(box, size_pt=style.size)
    para(
        tf,
        line,
        style.size,
        ctx.rgb(ink),
        align=ALIGN[ctx.align],
        first=True,
        space_after=0,
        font=face,
        links=False,
    )
    shape = tf._parent
    describe(shape, alt=None if decorative else (alt or line), decorative=decorative)
    ctx.manifest.record(
        shape, text=line, lines=[line], font_pt=style.size, fg=ink, bg=paper, literal=True
    )
    _set_maths(shape._element, node, size_pt=style.size, ink=ink, align=ctx.align)
    return BodyResult(groups=[[(shape.shape_id, "text")]], height=height)


def _tex(ctx: SlideCtx, where: str) -> str:
    raw = ctx.body.get("tex")
    if isinstance(raw, (list, dict, bool)):
        raise LayoutError(
            f"{where}: 'tex' is the equation as one string, got a {type(raw).__name__}"
        )
    text = "" if raw is None else str(raw)
    if not text.strip():
        raise LayoutError(
            f"{where}: 'tex' is required — the equation, written in the LaTeX subset "
            f"docs/components.md lists"
        )
    return text


def _rung(ctx: SlideCtx, where: str) -> tuple[str, TypeStyle]:
    rung = str(ctx.body.get("rung", _RUNG_DEFAULT))
    if rung not in ctx.theme.ramp:
        raise LayoutError(
            f"{where}: 'rung' {rung!r} is not a type rung this theme has; it has "
            f"{', '.join(sorted(ctx.theme.ramp))}"
        )
    return rung, ctx.style(rung)


def _set_maths(sp, node: Node, *, size_pt: float, ink: str, align: str) -> None:
    """Wrap ``sp`` so PowerPoint reads a copy of it holding the maths, and every other
    reader reads ``sp``."""
    maths = copy.deepcopy(sp)
    paragraph = maths.find(".//{*}txBody/{*}p")
    for child in list(paragraph):
        if etree.QName(child).localname != "pPr":
            paragraph.remove(child)
    paragraph.append(parse_xml(omml(node, size_pt=size_pt, ink=ink, align=align).encode()))
    alternate(sp, maths, requires="a14", namespace=_A14)
