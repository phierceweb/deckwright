# deckwright docs

Index of everything in this directory. Every doc in the tree is listed here — if you add
one, add its row.

---

## Start here

| I want to… | Read |
|---|---|
| Write or edit a `.deck.yaml` | [`authoring.md`](authoring.md) — the wire format, and the index to the rest |
| Fill in one component | [`components.md`](components.md) — its fields and a worked example |
| Fix a build that failed | [`errors.md`](errors.md) — every message, beside its fix |
| Build, look at, and fix a deck | [`pptx-deck-building.md`](pptx-deck-building.md) — the workflow |
| Run a command | [`cli.md`](cli.md) — every command and env var |
| Use my own brand template | [`conform.md`](conform.md) — derive a theme, check what it carries |
| Know what a deck gets with no template | [`theme.md`](theme.md) — the built-in design system |

## Authoring

Three docs, loaded in that order: the format, then the one component you are writing,
then the message if it failed.

| Doc | Owns |
|---|---|
| [`authoring.md`](authoring.md) | **The `.deck.yaml` wire format.** Glossary, the two-document structure, every slide field, `place:`, the chart block and all 29 chart kinds, `animate:`, what lives in the theme instead — and the component index that routes to the doc below. Read this before writing or editing any deck spec. |
| [`extending.md`](extending.md) | Writing a component: the five mistakes that bite, and the checklist for promoting a deck-local one into the library. |
| [`components.md`](components.md) | Every component: every field, every default, a worked example each. Pulled in per component, not read whole. |
| [`errors.md`](errors.md) | Every build error the compiler emits, beside its fix. A lookup doc — arrive with the message in hand. |
| [`glyphs.md`](glyphs.md) | Which `icon:` name to reach for, grouped by what the slide is about. A shortlist into the 4,001 glyphs that ship. |
| [`choosing.md`](choosing.md) | From a claim and some numbers to a treatment: which chart kind, or a `table`, or `stats`, or no graphic at all. Decides *what* to draw. |
| [`treatments.md`](treatments.md) | Which shape a slide earns when it is neither a dataset nor a sequence, what each treatment costs in depth, and how to keep a deck from becoming one rectangle repeated. |
| [`flows.md`](flows.md) | Which process or relationship shape a piece of information earns, which deckwright draws, and which you assemble from primitives. |
| [`pptx-deck-building.md`](pptx-deck-building.md) | The build → render → QA loop, animation injection, versioned output, and the rule against rebuilding after a hand-edit. |
| [`cli.md`](cli.md) | Every command, its flags, the `DECKWRIGHT_*` environment variables, and the external tools each needs. |
| [`compile.md`](compile.md) | Calling the compiler from Python — `deckwright.build_deck` — and the pipeline behind it. |

## The design system

| Doc | Owns |
|---|---|
| [`theme.md`](theme.md) | What a deck gets with **no template at all**: semantic colour roles, contrast-checked pairs, type rungs, the fractional grid, chrome treatment. |
| [`conform.md`](conform.md) | Onboarding a brand template: what `deckwright conform` derives, what it refuses to trust, and how to read its report. |

## Engine internals

Each of these documents a subsystem's behaviour, not its wire format. The wire format is
always [`authoring.md`](authoring.md).

| Doc | Owns |
|---|---|
| [`compile.md`](compile.md) | The build pipeline: the order `build_deck` forces, template slide dropping, what a manifest is as records, how shapes are named, portable paths, and the two derived views. |
| [`placement.md`](placement.md) | `at:` → rect: the three forms, the column/row grid, reserved regions, chrome bands. |
| [`imagery.md`](imagery.md) | Photographs: fit and crop arithmetic, pixel sampling, the scrim auto-opacity solve, and what text on a picture records. |
| [`charts.md`](charts.md) | The native chart renderer: per-type option sets, the categorical palette, chart build animation. |
| [`panels.md`](panels.md) | HTML rendered to a picture: the theme-as-CSS-variables contract, the cache key, the canvas ceiling. |
| [`icons.md`](icons.md) | SVG → DrawingML: the search order, what an SVG must contain, even-odd filling, and how a glyph is coloured. The names themselves are [`glyphs.md`](glyphs.md). |
| [`motion.md`](motion.md) | Builds, interactive reveals and slide transitions: motion roles, what a click covers, the build-list rules, and the four-layer verification stack. |
| [`services.md`](services.md) | The four external-tool boundaries: what LibreOffice, Poppler, Chrome and Pillow are each asked for, which command needs which binary, and every way they fail. |
| [`utils.md`](utils.md) | The shared primitives: WCAG colour maths, the baked font-advance tables behind every wrap estimate, the fraction vocabulary, reserved-region geometry, the unknown-key wording, the python-pptx drawing floor — and why none of them is a pf-core call. |

## Quality

| Doc | Owns |
|---|---|
| [`qa.md`](qa.md) | The automated checks, severities and `--fail-on` — and, just as important, what the layer structurally cannot catch. |
| [`testing.md`](testing.md) | Which changes need a test and which do not, the measured evidence behind that rule, and the guard that keeps the corpus test honest. |

## pf-core

`docs/pf-core/` is a symlink to the installed framework's own docs — start at
`docs/pf-core/modules.md`. `bin/setup` creates the link (so it exists after setup,
not on GitHub); if it is missing, resolve the target with:

```bash
bin/py -c "import pf_core, pathlib; print(pathlib.Path(pf_core.__file__).parent / 'docs')"
```

Never reach for a third-party library when pf-core already provides it — logging, config,
exceptions, parallelism, LLM clients.

## Conventions

New docs follow the house shape: an H1, a one-line purpose, a disambiguation paragraph
when a confusable system exists, a table of contents, prescriptive voice, and an
"Adding a new X" section for anything extensible. Add the row here in the same change —
a partial index is worse than none, because readers treat it as exhaustive.
