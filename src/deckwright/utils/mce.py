"""The shapes a slide holds once Markup Compatibility is resolved (ISO/IEC 29500-3 §7.5).

python-pptx skips an ``mc:AlternateContent`` in a shape tree, so an equation, a 3D model or
any newer-namespace shape is missing from ``slide.shapes``. deckwright understands none of
the extension namespaces a ``mc:Choice`` requires, so it reads what every such consumer
must: the ``mc:Fallback``, or the first Choice where a file carries no Fallback.
"""

from __future__ import annotations

from typing import Any, Iterator

_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
ALTERNATE = f"{{{_MC}}}AlternateContent"
_CHOICE = f"{{{_MC}}}Choice"
_FALLBACK = f"{{{_MC}}}Fallback"


def branch(alternate: Any) -> Any | None:
    """The branch of ``alternate`` a reader that understands no extension takes."""
    fallback = alternate.find(_FALLBACK)
    return fallback if fallback is not None else alternate.find(_CHOICE)


def shape_elements(tree: Any, member_tags: frozenset[str]) -> Iterator[Any]:
    """Each child of ``tree`` whose tag is in ``member_tags``, in document order, with every
    ``mc:AlternateContent`` replaced by the members of its chosen branch."""
    for element in tree.iterchildren():
        if element.tag == ALTERNATE:
            chosen = branch(element)
            if chosen is not None:
                yield from shape_elements(chosen, member_tags)
        elif element.tag in member_tags:
            yield element


def resolved_shapes(shapes: Any) -> list[Any]:
    """``shapes`` as python-pptx proxies, including those inside an ``mc:AlternateContent``."""
    tree = shapes._spTree
    return [shapes._shape_factory(e) for e in shape_elements(tree, frozenset(tree._shape_tags))]
