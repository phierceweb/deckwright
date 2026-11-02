"""The LaTeX subset an ``equation:`` reads, parsed to a small tree.

The subset is closed: anything outside it is refused by name, since a command half-read
would set a different equation from the one written.
"""

from __future__ import annotations

import string
from dataclasses import replace

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
from deckwright.errors import LayoutError


GREEK = {
    **{
        name: chr(0x3B1 + i)
        for i, name in enumerate(
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi "
            "omicron pi rho varsigma sigma tau upsilon phi chi psi omega".split()
        )
        if name != "varsigma"
    },
    "Gamma": "Γ",
    "Delta": "Δ",
    "Theta": "Θ",
    "Lambda": "Λ",
    "Xi": "Ξ",
    "Pi": "Π",
    "Sigma": "Σ",
    "Phi": "Φ",
    "Psi": "Ψ",
    "Omega": "Ω",
}
OPERATORS = {
    "cdot": "⋅",
    "times": "×",
    "pm": "±",
    "mp": "∓",
    "leq": "≤",
    "geq": "≥",
    "neq": "≠",
    "approx": "≈",
    "infty": "∞",
    "to": "→",
    "partial": "∂",
    "nabla": "∇",
}
BIG = {"sum": "∑", "prod": "∏", "int": "∫", "lim": "lim"}

_LETTERS = frozenset(string.ascii_letters + string.digits)
_PUNCTUATION = frozenset("+=<>,.!/|()[]")
_DELIMITERS = frozenset("()[]|.")
_SUPPORTED = (
    r"^ _ \frac \sqrt \sum \prod \int \lim \left \right \text, Greek letters, \cdot \times "
    r"\pm \mp \leq \geq \neq \approx \infty \to \partial \nabla \{ \}, letters, digits and "
    r"+ - = < > , . ! / | ( ) [ ]"
)


def parse(tex: str, *, where: str) -> Node:
    """``tex`` as a tree.

    A block scalar's closing line break is not part of the equation, so ``tex: >`` reads.

    Raises:
        LayoutError: ``tex`` holds a control character, or anything outside the subset.
    """
    tex = tex.rstrip("\n")
    bad = next((c for c in tex if c < " " or c == "\x7f"), None)
    if bad is not None:
        raise LayoutError(
            f"{where}: 'tex' contains the control character {bad!r} — a double-quoted YAML "
            rf"string reads \f, \t, \n, \b and \r as escapes, so \frac arrives as a form feed "
            rf"and \theta as a tab: single-quote the tex, or write it as a plain or folded "
            f"(>) scalar"
        )
    reader = _Reader(tex, where)
    return _seq(reader.items(stops=frozenset(), until=None, relation=False))


def _seq(items: list[Node]) -> Node:
    return items[0] if len(items) == 1 else Seq(tuple(items))


class _Reader:
    def __init__(self, tex: str, where: str) -> None:
        self.s, self.i, self.where = tex, 0, where

    def fail(self, message: str) -> LayoutError:
        return LayoutError(f"{self.where}: 'tex' {message}")

    def peek(self) -> str:
        while self.i < len(self.s) and self.s[self.i] == " ":
            self.i += 1
        return self.s[self.i] if self.i < len(self.s) else ""

    def name(self) -> str:
        """The command at the cursor, without consuming it: letters, or one symbol."""
        j = self.i + 1
        while j < len(self.s) and self.s[j] in string.ascii_letters:
            j += 1
        return self.s[self.i + 1 : j] if j > self.i + 1 else self.s[self.i + 1 : self.i + 2]

    def command(self) -> str:
        name = self.name()
        self.i += 1 + len(name)
        return name

    def at_relation(self) -> bool:
        c = self.peek()
        if c in RELATIONS:
            return True
        return c == "\\" and OPERATORS.get(self.name(), "") in RELATIONS

    def items(self, *, stops: frozenset[str], until: str | None, relation: bool) -> list[Node]:
        """Atoms to the end, a stop character, the ``until`` command, or — for an operand —
        the next relation."""
        found: list[Node] = []
        while True:
            c = self.peek()
            if c == "" or c in stops or (c == "\\" and until and self.name() == until):
                return found
            if relation and self.at_relation():
                return found
            start = self.i
            atom = self.scripts(self.atom(), start)
            if isinstance(atom, Big):
                body = self.items(stops=stops, until=until, relation=True)
                atom = replace(atom, body=_seq(body) if body else None)
            found.append(atom)

    def atom(self) -> Node:
        c = self.peek()
        if c == "{":
            return self.group()
        if c == "}":
            raise self.fail("closes a '}' it never opened")
        if c in "^_":
            raise self.fail(f"has {c!r} with nothing before it to {_verb(c)}")
        if c == "\\":
            return self.control()
        self.i += 1
        if c in _LETTERS or c in _PUNCTUATION:
            return Sym(c)
        if c == "-":
            return Sym("−")
        raise self.fail(f"uses {c!r}, which is not supported — supported: {_SUPPORTED}")

    def group(self) -> Node:
        self.i += 1
        found = self.items(stops=frozenset("}"), until=None, relation=False)
        if self.peek() != "}":
            raise self.fail("opens a '{' it never closes")
        self.i += 1
        return _seq(found)

    def argument(self) -> Node | None:
        c = self.peek()
        if c == "" or c in "}]^_":
            return None
        return self.atom()

    def scripts(self, base: Node, start: int) -> Node:
        written = self.s[start : self.i].strip()
        found: dict[str, tuple[Node, str]] = {}
        while (mark := self.peek()) in ("^", "_") and mark:
            self.i += 1
            self.peek()
            at = self.i
            arg = self.argument()
            if arg is None:
                raise self.fail(f"has {mark!r} with nothing after it to {_verb(mark)}")
            source = self.s[at : self.i].strip()
            if mark in found:
                first = found[mark][1]
                raise self.fail(
                    f"{'raises' if mark == '^' else 'lowers'} {written} twice — group it: "
                    f"{written}{mark}{{{first}{mark}{source}}}"
                )
            found[mark] = (arg, source)
        sup = found["^"][0] if "^" in found else None
        sub = found["_"][0] if "_" in found else None
        if isinstance(base, Big):
            return replace(base, lower=sub, upper=sup)
        if sup is not None and sub is not None:
            return SubSup(base, sub, sup)
        if sup is not None:
            return Sup(base, sup)
        if sub is not None:
            return Sub(base, sub)
        return base

    def control(self) -> Node:
        name = self.command()
        if name in GREEK:
            return Sym(GREEK[name])
        if name in OPERATORS:
            return Sym(OPERATORS[name])
        if name in ("{", "}"):
            return Sym(name)
        if name in BIG:
            return Big(BIG[name], None, None)
        if name == "frac":
            num, den = self.argument(), self.argument()
            if num is None or den is None:
                count = "no arguments" if num is None else "one argument"
                raise self.fail(rf"gives \frac {count}; it takes two, {{numerator}}{{denominator}}")
            return Frac(num, den)
        if name == "sqrt":
            return self.root()
        if name == "left":
            return self.fenced()
        if name == "right":
            shown, _ = self.delimiter("right")
            raise self.fail(rf"closes \right{shown} with no \left to open it")
        if name == "text":
            return self.text()
        raise self.fail(rf"uses \{name}, which is not supported — supported: {_SUPPORTED}")

    def root(self) -> Node:
        degree: Node | None = None
        if self.peek() == "[":
            self.i += 1
            found = self.items(stops=frozenset("]"), until=None, relation=False)
            if self.peek() != "]":
                raise self.fail(r"opens a '[' for \sqrt's degree it never closes")
            self.i += 1
            degree = _seq(found)
        body = self.argument()
        if body is None:
            raise self.fail(r"gives \sqrt nothing to take the root of")
        return Root(body, degree)

    def fenced(self) -> Node:
        shown, opening = self.delimiter("left")
        found = self.items(stops=frozenset(), until="right", relation=False)
        if not (self.peek() == "\\" and self.name() == "right"):
            raise self.fail(rf"opens \left{shown} with no \right to close it")
        self.command()
        _, closing = self.delimiter("right")
        return Fenced(opening, _seq(found), closing)

    def delimiter(self, which: str) -> tuple[str, str]:
        """The delimiter after ``\\left`` or ``\\right``: as written, and as drawn."""
        c = self.peek()
        if c == "\\" and self.name() in ("{", "}"):
            self.i += 2
            return f"\\{self.s[self.i - 1]}", self.s[self.i - 1]
        if c and c in _DELIMITERS:
            self.i += 1
            return c, "" if c == "." else c
        shown = f"\\{self.name()}" if c == "\\" else c
        raise self.fail(rf"uses \{which}{shown} — \left and \right take ( ) [ ] \{{ \}} | or .")

    def text(self) -> Node:
        if self.peek() != "{":
            raise self.fail(r"gives \text no {words} to set")
        depth, start = 0, self.i + 1
        for j in range(self.i, len(self.s)):
            depth += {"{": 1, "}": -1}.get(self.s[j], 0)
            if depth == 0:
                self.i = j + 1
                return Text(self.s[start:j])
        raise self.fail("opens a '{' it never closes")


def _verb(mark: str) -> str:
    return "raise" if mark == "^" else "lower"
