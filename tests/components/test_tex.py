"""The LaTeX subset an `equation:` reads: parsed to a tree, and refused by name outside it."""

from __future__ import annotations

import re

import pytest

from deckwright.components._mathtree import (
    Big,
    Fenced,
    Frac,
    Root,
    Seq,
    Sub,
    SubSup,
    Sup,
    Sym,
    Text,
)
from deckwright.components._tex import parse
from deckwright.errors import LayoutError

WHERE = "slide 1 (component 'equation')"


def _p(tex):
    return parse(tex, where=WHERE)


@pytest.mark.parametrize(
    "tex, tree",
    [
        ("x", Sym("x")),
        ("x^2", Sup(Sym("x"), Sym("2"))),
        ("x_{i+1}", Sub(Sym("x"), Seq((Sym("i"), Sym("+"), Sym("1"))))),
        ("x_i^2", SubSup(Sym("x"), Sym("i"), Sym("2"))),
        ("x^2_i", SubSup(Sym("x"), Sym("i"), Sym("2"))),
        (r"\frac{a}{b}", Frac(Sym("a"), Sym("b"))),
        (r"\frac12", Frac(Sym("1"), Sym("2"))),
        (r"\sqrt{x}", Root(Sym("x"), None)),
        (r"\sqrt[3]{x}", Root(Sym("x"), Sym("3"))),
        (r"\sum_{i=1}^{n} i", Big("∑", Seq((Sym("i"), Sym("="), Sym("1"))), Sym("n"), Sym("i"))),
        (r"\int_0^1 x", Big("∫", Sym("0"), Sym("1"), Sym("x"))),
        (r"\prod x", Big("∏", None, None, Sym("x"))),
        (r"\lim_{x \to 0} f", Big("lim", Seq((Sym("x"), Sym("→"), Sym("0"))), None, Sym("f"))),
        (r"\left( a \right)", Fenced("(", Sym("a"), ")")),
        (r"\left\{ a \right.", Fenced("{", Sym("a"), "")),
        (r"\alpha\beta", Seq((Sym("α"), Sym("β")))),
        (r"a \leq b", Seq((Sym("a"), Sym("≤"), Sym("b")))),
        (r"\text{if } x", Seq((Text("if "), Sym("x")))),
        ("a - b", Seq((Sym("a"), Sym("−"), Sym("b")))),
        ("{x}", Sym("x")),
    ],
)
def test_the_subset_parses_to_its_tree(tex, tree):
    assert _p(tex) == tree


def test_a_big_operators_operand_runs_to_the_next_relation():
    """The summand is everything after the operator up to `=`, so the right side stays out."""
    assert _p(r"\sum_i x^2 + 1 = y") == Seq(
        (
            Big("∑", Sym("i"), None, Seq((Sup(Sym("x"), Sym("2")), Sym("+"), Sym("1")))),
            Sym("="),
            Sym("y"),
        )
    )


def test_the_quadratic_formula_parses():
    tree = _p(r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}")
    assert tree == Seq(
        (
            Sym("x"),
            Sym("="),
            Frac(
                Seq(
                    (
                        Sym("−"),
                        Sym("b"),
                        Sym("±"),
                        Root(
                            Seq(
                                (
                                    Sup(Sym("b"), Sym("2")),
                                    Sym("−"),
                                    Sym("4"),
                                    Sym("a"),
                                    Sym("c"),
                                )
                            ),
                            None,
                        ),
                    )
                ),
                Seq((Sym("2"), Sym("a"))),
            ),
        )
    )


@pytest.mark.parametrize(
    "tex, message",
    [
        (
            r"\begin{matrix} a \end{matrix}",
            r"'tex' uses \\begin, which is not supported — supported: \^ _ \\frac \\sqrt",
        ),
        ("a & b", r"'tex' uses '&', which is not supported — supported: \^ _ \\frac"),
        ("{x", r"'tex' opens a '\{' it never closes"),
        ("x}", r"'tex' closes a '\}' it never opened"),
        ("x^", r"'tex' has '\^' with nothing after it to raise"),
        ("x_", r"'tex' has '_' with nothing after it to lower"),
        ("x^2^3", r"'tex' raises x twice — group it: x\^\{2\^3\}"),
        (
            r"\frac{a}",
            r"'tex' gives \\frac one argument; it takes two, \{numerator\}\{denominator\}",
        ),
        (r"\left( a", r"'tex' opens \\left\( with no \\right to close it"),
        (r"a \right)", r"'tex' closes \\right\) with no \\left to open it"),
        (
            r"\left< a \right>",
            r"'tex' uses \\left< — \\left and \\right take \( \) \[ \] \\\{ \\\} \| or \.",
        ),
        ("\x0crac{a}{b}", r"'tex' contains the control character '\\x0c'.* single-quote"),
    ],
)
def test_what_the_subset_does_not_cover_is_refused_by_name(tex, message):
    with pytest.raises(LayoutError, match=rf"^{re.escape(WHERE)}: {message}"):
        _p(tex)


@pytest.mark.parametrize("style", [">", "|", ">+", "|-"])
def test_the_block_scalars_the_refusal_recommends_read(style):
    """The control-character refusal tells the author to write a folded scalar, which YAML
    ends with a line break."""
    import yaml

    from deckwright.spec._scalars import SpecLoader

    tex = yaml.load(f"tex: {style}\n  \\frac{{a}}{{b}}\n\n", Loader=SpecLoader)["tex"]
    assert _p(tex) == Frac(Sym("a"), Sym("b"))


def test_a_line_break_inside_the_equation_is_still_refused():
    with pytest.raises(LayoutError, match=r"control character '\\n'.* folded \(>\) scalar"):
        _p("\\frac{a}\n{b}")


@pytest.mark.parametrize(
    "tex, line",
    [
        (r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}", "x = (−b ± √(b² − 4ac))/(2a)"),
        (r"\frac{a}{b}", "a/b"),
        (r"\frac{10}{3}", "10/3"),
        (r"\frac{\frac{a}{b}}{c}", "(a/b)/c"),
        ("x^{10}", "x¹⁰"),
        ("x^{-1}", "x⁻¹"),
        ("x^{n+1}", "x^(n+1)"),
        (r"x^{\alpha}", "x^α"),
        ("x_1", "x₁"),
        ("x_{i+1}", "x_(i+1)"),
        ("x_i^2", "x_i²"),
        (r"\sqrt{x}", "√x"),
        (r"\sqrt[3]{x}", "∛x"),
        (r"\sqrt[4]{x}", "∜x"),
        (r"\sqrt[5]{x}", "√(5&x)"),
        (r"\sum_{i=1}^{n} i", "∑_(i=1)^n i"),
        (r"\int_0^1 x^2", "∫_0^1 x²"),
        (r"\lim_{x \to 0} f", "lim_(x→0) f"),
        (r"\left( \frac{a}{b} \right)", "(a/b)"),
        (r"\left\{ x \right.", "{x"),
        (r"\text{if } x > 0", "if x > 0"),
        (r"a \cdot b \leq c", "a ⋅ b ≤ c"),
        ("-x = y - 1", "−x = y − 1"),
        ("a = -b", "a = −b"),
        ("f(-x)", "f(−x)"),
        ("f(x, y)", "f(x, y)"),
        (r"2\frac{1}{2}", "2 1/2"),
        (r"\frac{1}{N}\sum_i x", "1/N ∑_i x"),
        (r"\frac{a}{b}c", "a/b c"),
        (r"x \frac{a}{b}", "x a/b"),
        (r"(\frac{a}{b})", "(a/b)"),
    ],
)
def test_the_fallback_is_one_readable_line(tex, line):
    """What LibreOffice, Keynote and every check see in place of the maths."""
    from deckwright.components._unicodemath import linear

    assert linear(_p(tex)) == line
