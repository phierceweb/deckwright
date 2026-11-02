"""An equation as one line of UnicodeMath (Unicode Technical Note 28): what a reader with
no Office Math shows."""

from __future__ import annotations

from deckwright.components._mathtree import (
    RELATIONS,
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

_SPACED = frozenset("+−±∓×⋅") | RELATIONS
_OPENING = frozenset("([{,")
_CLOSING = frozenset(")]}")
_SUPERSCRIPT = str.maketrans("0123456789−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
_SUBSCRIPT = str.maketrans("0123456789−", "₀₁₂₃₄₅₆₇₈₉₋")
_ROOTS = {"3": "∛", "4": "∜"}


def linear(node: Node) -> str:
    """``node`` as one line of UnicodeMath."""
    return " ".join(_line(node, compact=False).split())


def _line(node: Node, *, compact: bool) -> str:
    if isinstance(node, Sym):
        return node.text
    if isinstance(node, Text):
        return node.words
    if isinstance(node, Seq):
        return _joined(node.items, compact=compact)
    if isinstance(node, Frac):
        return f"{_wrapped(node.num)}/{_wrapped(node.den)}"
    if isinstance(node, Root):
        body = _wrapped(node.body)
        if node.degree is None:
            return f"√{body}"
        degree = _line(node.degree, compact=True)
        if degree in _ROOTS:
            return f"{_ROOTS[degree]}{body}"
        return f"√({degree}&{_line(node.body, compact=True)})"
    if isinstance(node, Sup):
        return _line(node.base, compact=compact) + _script(node.exp, "^", _SUPERSCRIPT)
    if isinstance(node, Sub):
        return _line(node.base, compact=compact) + _script(node.sub, "_", _SUBSCRIPT)
    if isinstance(node, SubSup):
        return (
            _line(node.base, compact=compact)
            + _script(node.sub, "_", _SUBSCRIPT)
            + _script(node.sup, "^", _SUPERSCRIPT)
        )
    if isinstance(node, Big):
        limits = "".join(
            f"{mark}{_wrapped(part, compact=True)}"
            for mark, part in (("_", node.lower), ("^", node.upper))
            if part is not None
        )
        body = "" if node.body is None else f" {_line(node.body, compact=compact)}"
        return f"{node.op}{limits}{body}"
    if isinstance(node, Fenced):
        return f"{node.open}{_line(node.body, compact=compact)}{node.close}"
    raise TypeError(f"not a tex node: {node!r}")


def _joined(items: tuple[Node, ...], *, compact: bool) -> str:
    out: list[str] = []
    before: str | None = None
    for item in items:
        text = _line(item, compact=compact)
        # A fraction or an operator run against a neighbour reads as part of it: `2 1/2`,
        # not `21/2`; `1/N ∑`, not `1/N∑`.
        joins = isinstance(item, Sym) and item.text in _SPACED | _CLOSING | {","}
        if (
            out
            and not joins
            and before not in _SPACED | _OPENING
            and (isinstance(item, (Frac, Big)) or before == "frac")
        ):
            out.append(" ")
        if isinstance(item, Sym) and item.text in _SPACED:
            unary = before is None or before in _SPACED or before in _OPENING
            out.append(text if unary or compact else f" {text} ")
        elif isinstance(item, Sym) and item.text == ",":
            out.append("," if compact else ", ")
        else:
            out.append(text)
        before = item.text if isinstance(item, Sym) else "frac" if isinstance(item, Frac) else "x"
    return "".join(out)


def _wrapped(node: Node, *, compact: bool = False) -> str:
    """``node`` in brackets where a reader could not otherwise tell where it ends.

    ``compact`` sets its operators unspaced, as a script or a limit is.
    """
    text = _line(node, compact=compact)
    alone = isinstance(node, (Sym, Sup, Sub, SubSup, Root, Fenced)) or _number(node)
    return text if alone else f"({text})"


def _number(node: Node) -> bool:
    return isinstance(node, Seq) and all(
        isinstance(item, Sym) and (item.text.isdigit() or item.text == ".") for item in node.items
    )


def _script(node: Node, mark: str, glyphs: dict[int, int]) -> str:
    text = _line(node, compact=True)
    if text and all(c.isdigit() or c == "−" for c in text) and not text.endswith("−"):
        return text.translate(glyphs)
    return f"{mark}{_wrapped(node, compact=True)}"
