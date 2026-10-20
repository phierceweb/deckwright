"""Cards and pictures in a deck deckwright did not build, recognised from their shapes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

from deckwright.spec._tree import shape_type, slide_box
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
    under = [p for p in plates if _contains(p, source) and _card_sized(p, canvas)]
    if len(under) != 1:
        return None
    return _card_body(lines, source), under[0]


def cards_of(
    bodies: list[Any], plates: dict[Any, tuple[Any, str]], *, canvas: tuple[int, int]
) -> tuple[list[dict], list[Any], list[str]]:
    """Which of ``bodies`` are cards and which stay words, both in reading order, and the
    dropped-shape names of the plates the cards claimed. ``plates`` maps a plate's element
    to the plate and that name."""
    under = [p for p, _ in plates.values()]
    shared: dict[Any, list[Any]] = {}
    for body in bodies:
        if (lying := lone_plate(body.source, under, canvas=canvas)) is not None:
            shared.setdefault(lying._element, []).append(body)
    merged = {
        plate_: split_card([(b.lines, b.source) for b in group])
        for plate_, group in shared.items()
        if len(group) > 1
    }
    on = {id(body): plate_ for plate_ in merged for body in shared[plate_]}
    cards: list[dict] = []
    words: list[Any] = []
    claimed: list[str] = []
    claimed_plates: set[Any] = set()
    for body in bodies:
        if id(body) in on:
            plate_ = on[id(body)]
            split = merged[plate_]
            if split is None:
                words.append(body)  # the boxes on it hold more than a card does
            elif plate_ not in claimed_plates:
                cards.append(split)
                claimed.append(plates[plate_][1])
                claimed_plates.add(plate_)
            continue
        found = card(body.lines, body.source, under, canvas=canvas)
        if found is None:
            words.append(body)
            continue
        cards.append(found[0])
        if found[1] is not None:
            claimed.append(plates[found[1]._element][1])
    return cards, words, claimed


def lone_plate(source: Any, plates: list[Any], *, canvas: tuple[int, int]) -> Any | None:
    """The one card-sized plate the text box ``source`` lies on, or ``None``."""
    if source is None or shape_type(source) is not MSO_SHAPE_TYPE.TEXT_BOX:
        return None
    under = [p for p in plates if _contains(p, source) and _card_sized(p, canvas)]
    return under[0] if len(under) == 1 else None


def split_card(boxes: list[tuple[tuple[str, ...], Any]]) -> dict | None:
    """Text boxes sharing one plate, given in reading order, as one card when together they
    hold a heading and a line or less; ``None`` when they hold more, and stay words."""
    lines = tuple(line for box_lines, _ in boxes for line in box_lines)
    if len(lines) > _MOST_LINES:
        return None
    return _card_body(lines, boxes[0][1])


def _card_body(lines: tuple[str, ...], source: Any) -> dict:
    if len(lines) == _MOST_LINES:
        return {"heading": lines[0], "body": lines[1]}
    runs = source.text_frame.paragraphs[0].runs
    return {"heading" if runs and runs[0].font.bold else "body": lines[0]}


def _card_sized(shape: Any, canvas: tuple[int, int]) -> bool:
    box = slide_box(shape)
    return box is not None and box[2] * box[3] < _MOST_OF_SLIDE * canvas[0] * canvas[1]


def _contains(outer: Any, inner: Any) -> bool:
    """Whether ``inner`` lies on ``outer`` where the slide draws them, groups and all."""
    a, b = slide_box(outer), slide_box(inner)
    if a is None or b is None:
        return False
    return (
        a[0] <= b[0] and a[1] <= b[1] and b[0] + b[2] <= a[0] + a[2] and b[1] + b[3] <= a[1] + a[3]
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
