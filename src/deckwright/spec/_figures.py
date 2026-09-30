"""Cards and pictures in a deck deckwright did not build, recognised from their shapes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

from deckwright.spec._tree import shape_type
from deckwright.utils.a11y import described, is_file_name

_FILLS = tuple(qn(f"a:{tag}") for tag in ("solidFill", "gradFill", "pattFill", "blipFill"))
_MOST_LINES = 2  # a heading and a line of copy; more than that is a list
# A plate this much of the slide or more is a panel the slide's own words sit on.
_MOST_OF_SLIDE = 0.4


@dataclass(frozen=True)
class Picture:
    """A picture's own file, and the text a screen reader says for it."""

    name: str  # the file name the draft gives it in its media folder
    blob: bytes
    alt: str | None = None
    decorative: bool = False

    def image(self) -> dict[str, Any]:
        """The ``image:`` mapping that places this picture."""
        body: dict[str, Any] = {"src": self.name}
        if self.alt:
            body["alt"] = self.alt
        elif self.decorative:
            body["decorative"] = True
        return body


def filled(shape) -> bool:
    """Whether the shape paints a fill of its own or its style's, rather than nothing."""
    props = shape._element.find(qn("p:spPr"))
    if props is None or props.find(qn("a:noFill")) is not None:
        return False
    if any(props.find(tag) is not None for tag in _FILLS):
        return True
    ref = shape._element.find(f"{qn('p:style')}/{qn('a:fillRef')}")
    return ref is not None and ref.get("idx", "0") != "0"


def plate(shape) -> bool:
    """A filled drawn shape with no words: the plate a card's text may sit on."""
    return shape_type(shape) is MSO_SHAPE_TYPE.AUTO_SHAPE and filled(shape)


def card(
    lines: tuple[str, ...], source: Any, plates: list[Any], *, canvas: tuple[int, int]
) -> tuple[dict, Any] | None:
    """``lines`` as a ``card:`` mapping, and the plate it claims, when ``source`` is a card.

    A filled shape holding one or two paragraphs is one; so is a text box holding them that
    lies on exactly one plate.
    """
    if source is None or len(lines) > _MOST_LINES:
        return None
    if plate(source):
        return (_card_body(lines, source), None) if _card_sized(source, canvas) else None
    if shape_type(source) is not MSO_SHAPE_TYPE.TEXT_BOX:
        return None
    under = [
        p
        for p in plates
        if _same_space(p, source) and _contains(p, source) and _card_sized(p, canvas)
    ]
    if len(under) != 1:
        return None
    return _card_body(lines, source), under[0]


def _card_body(lines: tuple[str, ...], source: Any) -> dict:
    if len(lines) == _MOST_LINES:
        return {"heading": lines[0], "body": lines[1]}
    runs = source.text_frame.paragraphs[0].runs
    return {"heading" if runs and runs[0].font.bold else "body": lines[0]}


def _card_sized(shape: Any, canvas: tuple[int, int]) -> bool:
    return shape.width * shape.height < _MOST_OF_SLIDE * canvas[0] * canvas[1]


def _same_space(first: Any, second: Any) -> bool:
    """Two shapes in one group, or both on the slide, measure in one coordinate space."""
    return first._element.getparent() is second._element.getparent()


def _contains(outer: Any, inner: Any) -> bool:
    return (
        outer.left <= inner.left
        and outer.top <= inner.top
        and inner.left + inner.width <= outer.left + outer.width
        and inner.top + inner.height <= outer.top + outer.height
    )


def picture(shape, *, name: str) -> Picture | str:
    """The picture's own file as ``name`` with its extension, or why it cannot be read."""
    try:
        image = shape.image
    except (KeyError, ValueError, AttributeError):
        return "a linked picture, whose file is not in the deck"
    text, decorative = described(shape)
    alt = " ".join((text or "").split()) or None
    if alt is not None and is_file_name(alt):
        alt = None
    return Picture(name=f"{name}.{image.ext}", blob=image.blob, alt=alt, decorative=decorative)
