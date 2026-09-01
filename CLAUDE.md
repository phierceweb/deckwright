# deckwright — AI assistant context

A pf-core consumer: a library/tool in the **src-layout** (no web/DB layers),
built on the pf-core framework.

## Changing the package itself

Most readers want the deck-authoring routes below; what follows only applies to
changing deckwright's own code.

`bin/lint` is the gate: ruff lint, `ruff format --check`, mypy, the structural
file-size check, import direction and framework-first, each naming the rule it applies
when it fails. Layout and types are enforced, not advisory — run `bin/py -m ruff format
src tests` before committing. Two rules are worth stating here because they shape where
code goes.

**Check pf-core before writing any helper** — logging, a config knob, an error
class, retries, caching, parallelism, an atomic file write. It probably has it.
`bin/check-framework` runs in pre-commit and CI and names the replacement in every
failure.

**New capability belongs in `src/deckwright/conform/exercise.py`**, which
`tests/test_templates.py` drives against every real brand template — not in a new unit
test file. [`docs/testing.md`](docs/testing.md) is the evidence behind that, and
`bin/lint` runs the rest of the gates.

## Building a deck

Deck authoring is *conditional*, not a package rule — load the doc you need,
don't carry them all. **Route by what the author actually has**, not by reading
everything:

| They arrive with | Read first |
|---|---|
| A story and **some data**, no treatment in mind | [`docs/choosing.md`](docs/choosing.md) — data shape and claim → chart, table, or no chart at all |
| A story and **no data** — a rule, a consequence, an artefact, an opposition | [`docs/treatments.md`](docs/treatments.md) — which shape it earns, what it costs, and whether the deck already looks like it |
| A deck that is turning into one rectangle repeated | [`docs/treatments.md`](docs/treatments.md) — the run test and the levers, cheapest first |
| A process, steps, branches, anything with arrows | [`docs/flows.md`](docs/flows.md) — and when a flow is a bulleted list wearing a costume |
| A shape in mind, needing the wire format | [`docs/authoring.md`](docs/authoring.md) |
| A component to place | [`docs/components.md`](docs/components.md) |
| An error the compiler printed | [`docs/errors.md`](docs/errors.md) |
| A brand template nobody has onboarded | [`docs/conform.md`](docs/conform.md) |
| An icon to pick | [`docs/glyphs.md`](docs/glyphs.md) |
| A question about what this library can even do | `bin/run demo` — every capability in one deck, generated, against any theme |

Their spec goes in `authoring/<name>/`; the build lands in `out/<name>/`. **`bin/run new "<Name>"` writes a deck that already builds and builds it** — start from that rather than an empty file.

**Asked to use a brand template that is not onboarded** — a `theme:` that does not
resolve, or "use the <brand> template": follow the three-step flow at the end of
[`templates/README.md`](templates/README.md). Short form: have them drag the `.pptx`
(and its `<name>.theme.yaml` sidecar, if they kept one) into `templates/`, run
`bin/run conform templates/<file>.pptx --adopt <name>`, and build with
`theme: <name>` from that point on. Never ask them to paste colours or re-tune by
hand — the sidecar exists so tuning survives.

- **[`docs/authoring.md`](docs/authoring.md)** — **start here, always.** The
  `.deck.yaml` wire format: glossary, the two-document structure, every slide
  field, `place:`, the chart block and all 29 chart kinds, `animate:`, what
  lives in the theme instead — and the component index that routes to the two
  docs below. Read it before authoring or editing any deck spec.
- **[`docs/components.md`](docs/components.md)** — the components'
  fields, defaults and worked examples. Load the sections you are writing, not
  the whole file.
- **[`docs/errors.md`](docs/errors.md)** — every build error beside its fix.
  Open it when a build failed, with the message in hand.
- **[`docs/glyphs.md`](docs/glyphs.md)** — which `icon:` name to reach for,
  grouped by what the slide is about.
- **[`docs/pptx-deck-building.md`](docs/pptx-deck-building.md)** — the general
  mechanics + non-negotiables (animation injection, the render/QA loop, versioned
  output, the "don't rebuild after a hand-edit" workflow).
- **`deckwright qa <deck>.pptx`** — automated checks (bounds, reserved regions,
  min font size, WCAG contrast, render-based overflow) against a built deck's
  manifest. Complements, never replaces, the eyeball-the-render loop above —
  see [`docs/qa.md`](docs/qa.md) for what it catches and, just as important,
  what it structurally cannot.
- **[`docs/cli.md`](docs/cli.md)** — every command and flag, the `DECKWRIGHT_*`
  env vars, and which external tools each command needs.

**Engine internals.** One doc per subsystem, each covering behaviour only — the
wire format for all of them is `docs/authoring.md`, never these:
[`placement.md`](docs/placement.md) (`at:` → rect, grid, reserved regions),
[`imagery.md`](docs/imagery.md) (fit/crop, pixel sampling, the scrim solve),
[`charts.md`](docs/charts.md) (per-type options, palette),
[`panels.md`](docs/panels.md) (HTML → picture, cache, canvas ceiling),
[`icons.md`](docs/icons.md) (SVG → DrawingML, glyph search order, even-odd fill),
[`motion.md`](docs/motion.md) (builds, click-to-reveal, transitions, the verification stack).

## Deck compiler

`deckwright build <spec>.deck.yaml` compiles a declarative `.deck.yaml` (a
deck-config document plus one document per slide) against a theme YAML —
e.g. `templates/acme.theme.yaml` — into a branded `.pptx` and a build
manifest. The spec format is documented end-to-end in
[`docs/authoring.md`](docs/authoring.md). The brand template referenced by a
theme is gitignored at `templates/` — never commit it.

The design system a deck gets with no template at all — the semantic colour roles
and contrast-checked pairs, the type rungs, the fractional grid — is documented in
[`docs/theme.md`](docs/theme.md). To point deckwright at a *new* brand template,
`deckwright conform <template>.pptx` derives a theme from it and drives every
capability through it — see [`docs/conform.md`](docs/conform.md).

**[`docs/README.md`](docs/README.md) indexes every doc in the tree.** Add a row
there in the same change that adds a doc.

## Layout

- `src/deckwright/cli.py` — CLI entry (thin; pf-core `create_cli` / `run_cli`).
- `src/deckwright/config.py` — `Config(AppConfig)` subclass; the `cfg` singleton.
- Add one package per domain under `src/deckwright/`. Grow a layer dir
  (`<domain>/services/`, `orchestrators/`, `utils/`) only when it has ≥2 files.

## Where deck work goes

Split by lifetime, not by topic. Full table in
[`docs/pptx-deck-building.md`](docs/pptx-deck-building.md#where-everything-goes).

- **`authoring/`** — decks *you* write, gitignored. Your content, not the library's. Named for the activity because a *deck* is the built `.pptx`.
- **`examples/`** — deckwright's own demonstration specs, committed. The feature tour, the
  chart catalogue, the table and shape tours: they exercise the library, so they are
  part of it. A deck written for an audience does not go here.
- **`templates/`** — brand `.pptx` files **and** the themes derived from them, side by
  side, gitignored except the README. One directory, one copy of each binary: a template
  is adopted where it lives and `--adopt` writes `<name>.theme.yaml` beside it. Both are
  yours and stay local — the artwork is licensed and the theme carries a client's
  palette. The built-in `base` theme ships inside the package, not here.
- **`out/`** — everything a command writes, gitignored and disposable. Deleting the
  whole directory must lose nothing but time.
- **`out/<deck>/.build/`** — generated inputs and intermediates, hidden so a deck's
  directory shows the deck, its manifest and `render/` and nothing else. A `.pptx`
  embeds its pictures, so what went into building it is scratch. The name is
  `deckwright.paths.SCRATCH`; use `scratch(outdir)` rather than writing it out.

**Scratch belongs outside the repo.** Probes and one-off experiments go in a temp
directory; ones that land in `out/` outlive their session and become indistinguishable
from output that matters.

## Commands

`bin/setup`, `bin/run <cmd>`, `bin/test`, `bin/lint`.

## pf-core

Declared in `pyproject.toml` as `pf-core[cli]`; import from `pf_core.*`. The rule and
the module reference are in [`CONTRIBUTING.md`](CONTRIBUTING.md).
