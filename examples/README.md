# deckwright's own decks

Demonstration specs that exercise the library. They are **committed**, because they are
part of it: each one is a worked reference for a capability, and a change gets rebuilt
against them before anyone believes it.

A deck you are writing for an audience does **not** go here — that is
[`authoring/`](../authoring/README.md), which is gitignored. The line is ownership: if
deleting it would cost the library something, it belongs here.

**These specs carry no version in their `out:`.** A version series — `My Deck v1.pptx`,
`v2`, `v3` — records which build you handed over, and nothing here is handed to anyone:
each one is regenerated whenever the library changes, and only the newest is of any
interest. The version series belongs to [`authoring/`](../authoring/README.md) decks,
and the rule for it is
[`docs/pptx-deck-building.md`](../docs/pptx-deck-building.md#versioned-output--sharing).

| Spec | Shows |
|---|---|
| `smoke.deck.yaml` | The smallest deck that builds. Start here when something is broken and you need a control. |
| `feature-tour.deck.yaml` | Most components in one pass, on the base theme. |
| `chart-catalogue.deck.yaml` | Every chart kind that builds, one per slide. |
| `shape-primitives.deck.yaml` | `card`, `panel`, `ellipse`, `connector`, `rule`. |
| `title-treatments.deck.yaml` | Six chrome treatments from the same three lines of text. |
| `tables.deck.yaml` | The `table` component: `rules:`, `down:`, `density:`, `valign:`. |

**Every spec here builds with the CLI alone.** None uses `extends:` — the escape hatch
is real, and documented in [`docs/extending.md`](../docs/extending.md), but a deck that
demonstrates the library must not need code the library does not ship.

**To see everything the library does, do not look here** — run `bin/run demo`. Every
capability is generated from the exercise registry against any theme you name, so it
cannot fall behind the library the way a written deck does. These specs are worked
references for a *reader*; the demo is the catalogue.

## Building them

Each spec's `out:` already points into `out/`, one directory per deck:

```bash
bin/run build examples/feature-tour.deck.yaml
```

Stand-in photographs are generated into `out/`, not committed, for the same reason
`conform` generates its own — no binaries in the repo.

## Adding one

Only if it demonstrates something no existing spec does. A new capability's real home is
an exercise in `src/deckwright/conform/exercise.py`, which runs against whatever brand
templates are in `templates/` — none, unless you add your own, so the module will skip
for you; see [`docs/testing.md`](../docs/testing.md). An example here is for
a *reader*, not for coverage.
