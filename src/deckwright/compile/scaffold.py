"""Start a deck from something that already runs — six annotated slides, not a stub."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import yaml
from pf_core.log import get_logger
from pf_core.utils.io import atomic_write_text

from deckwright.compile.build import BuildResult, build_deck
from deckwright.errors import SpecError
from deckwright.utils.naming import NO_FOLD, deck_filename, slug_and_title

logger = get_logger(__name__)

AUTHORING_DEFAULT = Path("authoring")

SCAFFOLD_WORDS = (
    "A KICKER",
    "Three lines and a chrome block make a cover",
    "Three things are broken",
    "questions@example.com",
)


@dataclass(frozen=True)
class Scaffold:
    """Where the new deck's source went, and what building it produced."""

    spec: Path
    built: BuildResult | None = None


def _scalar(text: str) -> str:
    """``text`` as a YAML scalar: a title holding a colon or a hash comes back quoted."""
    return yaml.safe_dump(text, width=NO_FOLD).removesuffix("...\n").strip()


def _spec_text(slug: str, title: str, theme: str) -> str:
    """A deck that builds, annotated with what to change in it."""
    deck = f"{deck_filename(title)} v1.pptx"
    name = _scalar(title)
    return f"""\
# {title} — a deck that already builds. Change the words; the shapes work.
#
#   deckwright build authoring/{slug}/{slug}.deck.yaml
#   deckwright render "out/{slug}/{deck}" --contact-sheet
#
# Every field: docs/authoring.md. Every component: docs/components.md.
# Everything this library can draw, in one deck: deckwright demo
theme: {theme}
title: {name}
sections: [Problem, Solution]
out: {_scalar(f"../../out/{slug}/{deck}")}
---
# A cover: display type low on the canvas, the subtitle on its own baseline near
# the foot. Without the `chrome:` block the three lines stack at the top margin
# and four-fifths of the slide sits empty. The title box holds three display
# lines, so a long title grows down into its own space instead of over the
# subtitle — shrink it once you know how your title wraps.
background: inverse
kicker: A KICKER
title: {name}
subtitle: Three lines and a chrome block make a cover
chrome:
  kicker: {{at: {{box: {{x: 5.5%, y: 40%, w: 50%, h: 5%}}}}, anchor: bottom}}
  title: {{at: {{box: {{x: 5.5%, y: 46%, w: 85%, h: 32%}}}}, rung: display, anchor: top}}
  subtitle: {{at: {{box: {{x: 5.5%, y: 80%, w: 60%, h: 6%}}}}, anchor: top}}

---
# A section divider. Every slide's `section:` must be one of the names above.
background: inverse
section: Problem
kicker: PART 1 OF 2
title: Problem
subtitle: What is going wrong

---
# Bullets across the whole content width. Drop `animate:` for no click build.
section: Problem
kicker: PROBLEM
title: Three things are broken
animate: one_at_a_time
place:
- at: {{cols: full}}
  bullets:
    items:
    - The first thing
    - The second thing
    - The third thing

---
# A row of cards. `split:` divides the band — add a fourth and nothing else moves.
section: Solution
kicker: SOLUTION
title: Three moves
place:
- at: {{rows: {{from: 0, to: 6}}}}
  split:
  - card: {{heading: Discover, body: What we learned.}}
  - card: {{heading: Design, body: What we chose.}}
  - card: {{heading: Ship, body: What we did.}}

---
# A real PowerPoint chart — editable in the deck, not a picture of numbers.
section: Solution
kicker: SOLUTION
title: Adoption climbs every quarter
place:
- at: {{cols: full, rows: top-two-thirds}}
  chart:
    kind: column
    data:
    - {{category: Q1, value: 12}}
    - {{category: Q2, value: 34}}
    - {{category: Q3, value: 58}}
    - {{category: Q4, value: 91, highlight: true}}

---
background: inverse
title: Thank you
subtitle: questions@example.com
chrome:
  title: {{at: {{box: {{x: 5.5%, y: 46%, w: 85%, h: 32%}}}}, rung: display, anchor: top}}
  subtitle: {{at: {{box: {{x: 5.5%, y: 80%, w: 60%, h: 6%}}}}, anchor: top}}
"""


def new_deck(
    name: str, *, root: str | Path = AUTHORING_DEFAULT, theme: str = "base", build: bool = True
) -> Scaffold:
    """Write a working deck for ``name`` and, unless told not to, build it.

    Raises:
        SpecError: the name is empty, or a deck of that name is already there.
    """
    slug, title = slug_and_title(name)
    spec = Path(root) / slug / f"{slug}.deck.yaml"
    if spec.exists():
        raise SpecError(
            f"{spec} already exists — a scaffold never overwrites a deck you have "
            f"written. Pick another name, or edit that one."
        )
    made_dir = not spec.parent.exists()
    spec.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(spec, _spec_text(slug, title, theme))
    logger.info("deck_scaffolded", deck=slug, spec=str(spec), theme=theme)
    if not build:
        return Scaffold(spec=spec)
    try:
        return Scaffold(spec=spec, built=build_deck(spec))
    except Exception:
        _discard(spec, made_dir=made_dir)
        raise


def _discard(spec: Path, *, made_dir: bool) -> None:
    """Undo the write, so the name is free and the command can be run again."""
    with suppress(OSError):
        spec.unlink(missing_ok=True)
    if made_dir:
        with suppress(OSError):
            spec.parent.rmdir()
