"""Start a deck from something that already runs — eight annotated slides, not a stub."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import yaml
from pw_foundation.log import get_logger
from pw_foundation.utils.io import atomic_write_text

from deckwright.compile.build import BuildResult, build_deck
from deckwright.errors import SpecError
from deckwright.utils.naming import NO_FOLD, deck_filename, slug_and_title

logger = get_logger(__name__)

AUTHORING_DEFAULT = Path("authoring")

SCAFFOLD_WORDS = (
    "A KICKER",
    "Three lines and a chrome block make a cover",
    "The one line the room should keep",
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


def _grounds(theme: str) -> str:
    """Comment lines naming the theme's grounds, so a slide's `background:` is chosen
    knowing what each one looks like; nothing for a theme that will not load."""
    from deckwright.errors import ThemeError
    from deckwright.theme.load import load_theme
    from deckwright.utils.color import delta_e, relative_luminance

    try:
        loaded = load_theme(theme)
    except ThemeError:
        return ""
    palette, scale = loaded.palette, loaded.scale

    def ground(name: str) -> str:
        colour = palette.pair(name).bg
        return f"{name} {colour} ({'light' if relative_luminance(colour) > 0.4 else 'dark'})"

    accents = ", ".join(f"{n} {palette.role(n)}" for n in palette.accents)
    lines = [
        f"# Grounds on {theme}: {ground('page')}, {ground('inverse')}; {accents}.",
        f"# The canvas is {round(scale.slide_w, 3):g} x {round(scale.slide_h, 3):g}in; "
        f"a box's percents are of it.",
    ]
    surface, page = palette.pair("surface").bg, palette.pair("page").bg
    # The difference past which a plate reads as a shape rather than a recess.
    if delta_e(surface, page) >= 10:
        lines.append(
            f"# card, flow, code and a table's header paint one {surface} plate here, so "
            f"slides of them read as one treatment."
        )
    return "\n".join(lines) + "\n"


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
# Every slide below is a different composition. Pick by what each slide does in the
# talk — docs/treatments.md#compositions — and what a click is for: docs/lessons.md.
# Every field: docs/authoring.md. Everything this library can draw: deckwright demo
{_grounds(theme)}theme: {theme}
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
  subtitle: {{at: {{box: {{x: 5.5%, y: 80%, w: 60%, h: auto}}}}}}

---
# A section divider. Every slide's `section:` must be one of the names above. It sits
# on `inverse` because every theme has one that reads; once you have seen your theme,
# an accent is usually the better ground (docs/authoring.md#background).
background: inverse
section: Problem
kicker: PART 1 OF 2
title: Problem
subtitle: What is going wrong

---
# A statement: the title is the slide. For the one rule or result the room should
# keep — once or twice a deck, not every third slide.
section: Problem
title: The one line the room should keep
subtitle: Said once, with nothing beside it
chrome: statement

---
# A side title: the chrome takes the left third and the body the rest. No `animate:` —
# a list whose order is not the lesson needs no click; say the items aloud.
section: Problem
kicker: PROBLEM
title: Three things are broken
chrome: side
place:
- at: {{cols: full}}
  callouts:
    items:
    - {{head: The first thing, body: Why it matters.}}
    - {{head: The second thing, body: Why it matters.}}
    - {{head: The third thing, body: Why it matters.}}

---
# A row of cards, one per click: here the order *is* the lesson. `split:` divides the
# band — add a fourth and nothing else moves.
section: Solution
kicker: SOLUTION
title: Three moves, in order
animate: one_at_a_time
place:
- at: {{rows: {{from: 0, to: 6}}}}
  split:
  - card: {{heading: Discover, body: What we learned.}}
  - card: {{heading: Design, body: What we chose.}}
  - card: {{heading: Ship, body: What we did.}}

---
# Evidence first: the title asks, the chart answers, and the next slide says it. A
# real PowerPoint chart — editable in the deck, not a picture of numbers.
section: Solution
title: Did adoption climb?
place:
- at: {{cols: full}}
  chart:
    kind: column
    alt: Adoption by quarter, rising from 12 to 91
    data:
    - {{category: Q1, value: 12}}
    - {{category: Q2, value: 34}}
    - {{category: Q3, value: 58}}
    - {{category: Q4, value: 91, highlight: true}}

---
# The claim lands as this slide's title, over the same chart — a chart takes no
# `morph:`, so it is repeated — with what it means beside it rather than under it.
section: Solution
title: Adoption climbs every quarter
place:
- at: {{cols: left-two-thirds}}
  chart:
    kind: column
    alt: Adoption by quarter, rising from 12 to 91
    data:
    - {{category: Q1, value: 12}}
    - {{category: Q2, value: 34}}
    - {{category: Q3, value: 58}}
    - {{category: Q4, value: 91, highlight: true}}
- at: {{cols: right-third}}
  callouts:
    items:
    - {{head: Seven times Q1, body: "In a year, with no paid push."}}

---
background: inverse
title: Thank you
subtitle: questions@example.com
chrome:
  title: {{at: {{box: {{x: 5.5%, y: 46%, w: 85%, h: 32%}}}}, rung: display, anchor: top}}
  subtitle: {{at: {{box: {{x: 5.5%, y: 80%, w: 60%, h: auto}}}}}}
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
