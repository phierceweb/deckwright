"""Office Math (ECMA-376 Part 1 §22.1) for an ``equation:``, as PowerPoint stores it.

The maths sits in ``a14:m``, and each run carries DrawingML run properties where Word
would carry its own: PowerPoint reads its size, ink and face from them.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from deckwright.components._mathtree import (
    Big,
    Fenced,
    Frac,
    Node,
    Root,
    Seq,
    Sub,
    SubSup,
    Sup,
    Sym,
    Text,
)

_A14 = "http://schemas.microsoft.com/office/drawing/2010/main"
_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
MATH_FACE = "Cambria Math"
_JC = {"left": "left", "center": "center", "right": "right"}
_LIMITS_BESIDE = frozenset("∫")


def omml(node: Node, *, size_pt: float, ink: str, align: str = "left") -> str:
    """``node`` as an ``a14:m`` element, set at ``size_pt`` in ``ink`` and justified as
    ``align`` says."""
    props = (
        f'<a:rPr sz="{round(size_pt * 100)}"><a:solidFill><a:srgbClr val="{ink}"/></a:solidFill>'
        f'<a:latin typeface="{MATH_FACE}"/></a:rPr>'
    )
    return (
        f'<a14:m xmlns:a14="{_A14}" xmlns:m="{_M}" xmlns:a="{_A}"><m:oMathPara>'
        f'<m:oMathParaPr><m:jc m:val="{_JC[align]}"/></m:oMathParaPr>'
        f"<m:oMath>{_Writer(props).write(node)}</m:oMath></m:oMathPara></a14:m>"
    )


class _Writer:
    def __init__(self, props: str) -> None:
        self.props = props

    def run(self, text: str, *, style: str = "") -> str:
        space = ' xml:space="preserve"' if text != text.strip() else ""
        return f"<m:r>{style}{self.props}<m:t{space}>{escape(text)}</m:t></m:r>"

    def arg(self, tag: str, node: Node | None) -> str:
        return f"<m:{tag}/>" if node is None else f"<m:{tag}>{self.write(node)}</m:{tag}>"

    def write(self, node: Node) -> str:
        if isinstance(node, Sym):
            return self.run(node.text)
        if isinstance(node, Text):
            return self.run(node.words, style="<m:rPr><m:nor/></m:rPr>")
        if isinstance(node, Seq):
            return self.sequence(node.items)
        if isinstance(node, Sup):
            return f"<m:sSup>{self.arg('e', node.base)}{self.arg('sup', node.exp)}</m:sSup>"
        if isinstance(node, Sub):
            return f"<m:sSub>{self.arg('e', node.base)}{self.arg('sub', node.sub)}</m:sSub>"
        if isinstance(node, SubSup):
            return (
                f"<m:sSubSup>{self.arg('e', node.base)}{self.arg('sub', node.sub)}"
                f"{self.arg('sup', node.sup)}</m:sSubSup>"
            )
        if isinstance(node, Frac):
            return f"<m:f>{self.arg('num', node.num)}{self.arg('den', node.den)}</m:f>"
        if isinstance(node, Root):
            if node.degree is None:
                hidden = '<m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/>'
                return f"<m:rad>{hidden}{self.arg('e', node.body)}</m:rad>"
            return f"<m:rad>{self.arg('deg', node.degree)}{self.arg('e', node.body)}</m:rad>"
        if isinstance(node, Big):
            return self.big(node)
        if isinstance(node, Fenced):
            return (
                f'<m:d><m:dPr><m:begChr m:val="{escape(node.open)}"/>'
                f'<m:endChr m:val="{escape(node.close)}"/></m:dPr>'
                f"{self.arg('e', node.body)}</m:d>"
            )
        raise TypeError(f"not a tex node: {node!r}")

    def sequence(self, items: tuple[Node, ...]) -> str:
        """Adjacent symbols share one run, as PowerPoint writes them."""
        out: list[str] = []
        pending = ""
        for item in items:
            if isinstance(item, Sym):
                pending += item.text
                continue
            if pending:
                out.append(self.run(pending))
                pending = ""
            out.append(self.write(item))
        if pending:
            out.append(self.run(pending))
        return "".join(out)

    def big(self, node: Big) -> str:
        if node.op == "lim":
            name = self.run("lim", style='<m:rPr><m:sty m:val="p"/></m:rPr>')
            if node.lower is not None:
                name = f"<m:limLow><m:e>{name}</m:e>{self.arg('lim', node.lower)}</m:limLow>"
            return f"<m:func><m:fName>{name}</m:fName>{self.arg('e', node.body)}</m:func>"
        where = "subSup" if node.op in _LIMITS_BESIDE else "undOvr"
        hide = ('<m:subHide m:val="1"/>' if node.lower is None else "") + (
            '<m:supHide m:val="1"/>' if node.upper is None else ""
        )
        return (
            f'<m:nary><m:naryPr><m:chr m:val="{node.op}"/><m:limLoc m:val="{where}"/>{hide}'
            f"</m:naryPr>{self.arg('sub', node.lower)}{self.arg('sup', node.upper)}"
            f"{self.arg('e', node.body)}</m:nary>"
        )
