"""How a deck moves: what a click reveals, and how the show arrives at a slide.

python-pptx authors neither, so every module here appends the raw OOXML that
PowerPoint itself would emit.

**Nothing here is visible to the render loop.** LibreOffice draws only a slide's final
state, and silently repairs wrong child order and schema-invalid timing. Only real
PowerPoint confirms an animation is repair-free — see the verification table in
`docs/pptx-deck-building.md`.
"""

from deckwright.motion.builds import add_click_build, add_click_sequence
from deckwright.motion.chartbuild import add_chart_build
from deckwright.motion.interactive import add_click_reveals
from deckwright.motion.transition import add_transition, transition_xml

__all__ = [
    "add_chart_build",
    "add_click_build",
    "add_click_reveals",
    "add_click_sequence",
    "add_transition",
    "transition_xml",
]
