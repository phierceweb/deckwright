"""The shapes a slide holds once Markup Compatibility is resolved (ISO/IEC 29500-3 §7.5).

python-pptx skips an ``mc:AlternateContent`` in a shape tree, so an equation, a 3D model or
any newer-namespace shape is missing from ``slide.shapes``. deckwright understands none of
the extension namespaces a ``mc:Choice`` requires, so it reads what every such consumer
must: the ``mc:Fallback``, or the first Choice where a file carries no Fallback.
"""

from __future__ import annotations

from typing import Any, Iterator

from lxml import etree

_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
ALTERNATE = f"{{{_MC}}}AlternateContent"
_CHOICE = f"{{{_MC}}}Choice"
_FALLBACK = f"{{{_MC}}}Fallback"


def branch(alternate: Any) -> Any | None:
    """The branch of ``alternate`` a reader that understands no extension takes."""
    fallback = alternate.find(_FALLBACK)
    return fallback if fallback is not None else alternate.find(_CHOICE)


def resolved_children(tree: Any) -> Iterator[Any]:
    """Each child of ``tree`` in document order, with every ``mc:AlternateContent``
    replaced by the children of its chosen branch."""
    for element in tree.iterchildren():
        if element.tag != ALTERNATE:
            yield element
        elif (chosen := branch(element)) is not None:
            yield from resolved_children(chosen)


def resolved_shapes(shapes: Any) -> list[Any]:
    """``shapes`` as python-pptx proxies, including those inside an ``mc:AlternateContent``."""
    tree = shapes._spTree
    members = frozenset(tree._shape_tags)
    return [shapes._shape_factory(e) for e in resolved_children(tree) if e.tag in members]


def in_fallback(element: Any) -> bool:
    """Whether ``element`` sits in an ``mc:Fallback``, which a reader taking the Choice
    never sees."""
    return next(element.iterancestors(_FALLBACK), None) is not None


def unread(element: Any) -> bool:
    """Whether ``element`` sits in a branch a reader of no extension namespace passes over:
    a Choice where its wrapper has a Fallback, or any Choice but the first."""
    return any(
        branch(chosen.getparent()) is not chosen
        for chosen in element.iterancestors(_CHOICE, _FALLBACK)
    )


def apart(first: Any, second: Any) -> bool:
    """Whether no reader sees both elements: some ``mc:AlternateContent`` holds them in
    different branches."""
    theirs = _branches(second)
    return any(
        theirs.get(alternate, mine) is not mine for alternate, mine in _branches(first).items()
    )


def _branches(element: Any) -> dict[Any, Any]:
    """``{alternate: branch}`` for every ``mc:AlternateContent`` enclosing ``element``."""
    return {b.getparent(): b for b in element.iterancestors(_CHOICE, _FALLBACK)}


def alternate(fallback: Any, choice: Any, *, requires: str, namespace: str) -> Any:
    """Put ``choice`` and ``fallback`` where ``fallback`` stood, as the branches of one
    ``mc:AlternateContent``; ``requires`` is the prefix the Choice binds to ``namespace``."""
    wrapper = etree.Element(ALTERNATE, nsmap={"mc": _MC})
    fallback.addprevious(wrapper)
    chosen = etree.SubElement(wrapper, _CHOICE, nsmap={requires: namespace}, Requires=requires)
    chosen.append(choice)
    etree.SubElement(wrapper, _FALLBACK).append(fallback)
    return wrapper
