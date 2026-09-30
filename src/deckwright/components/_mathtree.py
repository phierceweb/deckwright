"""The tree an ``equation:``'s TeX parses to, which its OMML and UnicodeMath writers read."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Seq:
    items: tuple[Node, ...]


@dataclass(frozen=True)
class Sym:
    text: str


@dataclass(frozen=True)
class Sup:
    base: Node
    exp: Node


@dataclass(frozen=True)
class Sub:
    base: Node
    sub: Node


@dataclass(frozen=True)
class SubSup:
    base: Node
    sub: Node
    sup: Node


@dataclass(frozen=True)
class Frac:
    num: Node
    den: Node


@dataclass(frozen=True)
class Root:
    body: Node
    degree: Node | None


@dataclass(frozen=True)
class Big:
    """A large operator, or ``lim``: its limits, and the operand it applies to."""

    op: str
    lower: Node | None
    upper: Node | None
    body: Node | None = None


@dataclass(frozen=True)
class Fenced:
    """Stretching brackets; an empty side is ``\\left.`` or ``\\right.``."""

    open: str
    body: Node
    close: str


@dataclass(frozen=True)
class Text:
    words: str


Node = Union[Seq, Sym, Sup, Sub, SubSup, Frac, Root, Big, Fenced, Text]

RELATIONS = frozenset("=<>≤≥≠≈→")


def rows(node: Node) -> int:
    """How many lines tall ``node`` stacks in Office Math: a fraction is its parts one over
    the other, and limits set under and over an operator add one."""
    if isinstance(node, Seq):
        return max((rows(item) for item in node.items), default=1)
    if isinstance(node, Frac):
        return rows(node.num) + rows(node.den)
    if isinstance(node, (Sup, Sub, SubSup)):
        return rows(node.base)
    if isinstance(node, (Root, Fenced)):
        return rows(node.body)
    if isinstance(node, Big):
        body = 1 if node.body is None else rows(node.body)
        stacked = node.op != "∫" and (node.lower is not None or node.upper is not None)
        return max(body, 2) if stacked else body
    return 1
