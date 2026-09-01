# deckwright

Tell an AI agent your story; get a branded PowerPoint deck.

## Why deckwright?

When generating a slide deck, deciding on the information and how to present it should be
the challenge, not the details and nuances of slide applications. **deckwright** solves this by
making decks build nearly instantly via configuration files that can be easily edited and
iterated.

The product is meant to be used by AI agents. Tell Claude Code the story you want to tell
and you have a deck in minutes: a built `.pptx` in your brand, charts drawn, type set,
with correct spacing and design.

Iterate on the part worth iterating on. Add a slide, cut two, reorder the middle, turn that
list into a column chart, make Q4 the highlight instead of Q3. Each of those is one sentence
to an assistant that has the spec open, and the deck rebuilds in seconds.

What lets that work is that a deck is a `.deck.yaml` — one document per slide — and
**a spec never names a font, a hex value or an inch.** Type, colour, spacing, the grid,
how a title is set: all of it lives in the theme, decided once and applied to every slide.
It's design you never have to think about. Point a deck at a brand template and the same
spec re-solves into that brand.

## Built for AI agents

deckwright ships three reference docs the agent reads while it builds your deck. They cover the
design decisions it would otherwise guess at, so you get a deck that makes sensible choices
without you having to specify them:

- **[What chart should this be?](https://github.com/phierceweb/deckwright/blob/main/docs/choosing.md)**
  — you have numbers and a point to make. `choosing.md` says which chart to use, or whether
  a plain table would be clearer, or whether one big number beats a chart, or whether the
  slide is better with no graphic at all. Its answers come from
  [published research into how accurately people read values off a chart](https://github.com/phierceweb/deckwright/blob/main/docs/choosing.md#sources),
  so they aren't a matter of taste.
- **[How do I keep the deck from looking boring?](https://github.com/phierceweb/deckwright/blob/main/docs/treatments.md)**
  — this is the one that makes a deck look good. For the slides that aren't charts — a
  claim, a consequence, a comparison, a quote — `treatments.md` says what shape the slide
  should take, then asks whether the last few slides already looked like that. A deck where
  every slide is individually fine and all of them are the same rectangle is a deck people
  stop watching, and it gives you the cheapest ways to break the pattern.
- **[Do these arrows mean anything?](https://github.com/phierceweb/deckwright/blob/main/docs/flows.md)**
  — steps, branches, cycles, timelines. `flows.md` says which diagram fits, and it starts by
  asking whether the arrows are making a claim at all. If they aren't, the content is a list
  and should look like one.

Whatever the agent still gets wrong, the compiler catches before it writes the file.

## The build tells you what's wrong before it writes a file

The compiler measures text against the space it was given. If it doesn't fit, the build
stops instead of writing the slide, and tells you what is wrong in plain terms.

```
slide 1 (component 'bullets'): 30 bullets in the longest column need 10.08in but only 5.30in is available — split the slide, add a column, or shorten the list
```

Thirty bullets, room for far fewer, and three specific things to do about it. An agent reads
that and fixes it on its own, before you ever open the deck. Every message the compiler emits
is listed beside its fix in [docs/errors.md](https://github.com/phierceweb/deckwright/blob/main/docs/errors.md).

After the build, `deckwright qa` checks the finished file: text sitting outside its box, text
too faint against whatever colour actually ended up behind it, and copy that overflows once
the slide is really rendered. The same doc lists what these checks cannot see; none of it
replaces looking at the slides.

## Bring your own brand

`deckwright conform templates/brand.pptx --adopt acme` reads a real PowerPoint template — its
colour scheme, the fonts its slides actually use, the corner it keeps clear for a logo —
builds a theme from it, then runs every capability in the library through that theme and
reports anything it couldn't carry across. Decks then say `theme: acme`, and every component
re-solves itself into the brand. No colours to paste, nothing to re-tune by hand, and the
same decks work under a different brand tomorrow.

A template is adopted where it lives, so put it in `templates/` and the theme lands beside
it; `DECKWRIGHT_THEME_DIR` moves both. With no template at all, the built-in `base` theme is a
complete design system in its own right — colour roles, contrast-checked pairings, type
sizes, a proportional grid — described in
[docs/theme.md](https://github.com/phierceweb/deckwright/blob/main/docs/theme.md).

## Two more things that help past the first draft

`deckwright demo` builds every capability the library has into a single deck, in whatever theme
you're using. When a slide isn't landing and you don't know what else it could be, the answer
is a deck you can look at.

And edits don't have to start in the spec. When someone opens the delivered `.pptx` and
changes a line in PowerPoint, `deckwright diff` compares the file against its build record and
tells you exactly what moved — so the change goes back into the spec and survives the next
build.

## Scope — where deckwright fits

deckwright turns a spec into a deck. It doesn't write your content: there is no model inside
it, no "generate a deck about X", and no opinion about your argument. The story is yours, or
your agent's; deckwright is what makes it build, rebuild and stay on brand.

Two limits worth knowing going in:

- **A build that passes is not a finished deck.** The checks confirm a slide is inside its
  bounds, legible, and contrast-safe. A slide can pass all of them and still be one nobody
  would show. Render it and look at it. The three docs above are the closest thing here to a
  designer; the automated checks only keep a slide legal.
- **It builds `.pptx`, and only that.** Rendering runs through LibreOffice to produce slide
  images for review. There is no HTML export, no Google Slides target, and no
  live-presentation mode. Chart families PowerPoint doesn't draw natively — Sankeys,
  waterfalls, chord diagrams — aren't available, and the docs name them so you know to reach
  for something else.

Pre-1.0: pin to a tagged release, and expect the spec format to move.

## How it relates to other tools

| Tool | What it is | How deckwright relates |
|---|---|---|
| [python-pptx](https://pypi.org/project/python-pptx/) | The Python library for reading and writing `.pptx` | deckwright is built on it. python-pptx places shapes at coordinates you work out yourself; deckwright places components on the theme's grid, solves their colour against whatever is behind them, and checks the result |
| [Marp](https://marp.app/), [Slidev](https://sli.dev/), reveal.js | Markdown/HTML decks, presented in a browser | Same "deck in version control" idea, different output. They present in a browser and export to PDF, and where a `.pptx` export exists a slide usually arrives as a picture. deckwright produces a native deck of editable shapes and real PowerPoint charts, built from a brand template someone else can open and edit |
| [Quarto](https://quarto.org/), Pandoc, [md2pptx](https://github.com/MartinPacker/md2pptx) | Markdown → `.pptx` by filling in a reference template's layouts | Filling placeholders limits you to what the template's layouts already express. deckwright derives a theme from the template and composes on a grid, so the component set is the library's, not the template's |
| Google Slides API, Office.js | Programmatic editing of a hosted document | Calls against live state, with no text source of truth to diff or regenerate from. In deckwright the spec is the source and the deck is disposable output |
| Gamma, Tome, Beautiful.ai | AI deck generators — they write the content and choose the design | Different job. deckwright writes no content and picks no story. It takes the spec you or your agent wrote and enforces the brand and the geometry around it |

## Install

```bash
git clone https://github.com/phierceweb/deckwright
cd deckwright
bin/setup                      # venv (3.12+), editable install, then builds a deck
bin/run new "Q4 Review"        # scaffold a working deck and build it
```

deckwright is used from a checkout: the agent reads this repo's reference docs while it builds
your deck, so the docs and the compiler travel together. Python 3.12–3.14. The built-in
`base` theme is part of the package, so a fresh clone builds decks with no further setup.

Some system tools unlock the rendering commands: LibreOffice (`soffice`) and Poppler
(`pdftoppm`, `pdftotext`) for `render` and the render-based checks,
and a local Chrome/Chromium for `shot` and the `document:` component — see
[External tools](https://github.com/phierceweb/deckwright/blob/main/docs/cli.md#external-tools).
fontconfig (`fc-list`) answers which faces this machine has, for `doctor`'s fonts row and
QA's `font-substituted` check; without it those two go quiet.
`deckwright doctor` reports which of them this install can reach, and names the install command
for anything missing.

Releases are tagged; `main` is the development line. Release notes:
[CHANGELOG.md](https://github.com/phierceweb/deckwright/blob/main/CHANGELOG.md).

## Commands

```bash
deckwright new "Q4 Review"              # scaffold a deck that already builds, and build it
deckwright extract <deck>.pptx          # draft a .deck.yaml from a deck deckwright did not build
deckwright build <spec>.deck.yaml       # compile a .deck.yaml into a themed .pptx + manifest
deckwright demo                         # every capability in one deck, against any theme
deckwright render <deck>.pptx           # rasterize each slide to an image
deckwright qa <deck>.pptx               # geometry, contrast and overflow checks
deckwright inspect <deck>.pptx          # every shape with its id and box
deckwright diff <deck>.pptx             # what a hand-edit changed, to carry back into the spec
deckwright conform <brand>.pptx --adopt <name>   # derive a theme from a brand template
deckwright sample                       # write a template to try conform against
deckwright doctor                       # glyphs, themes and external tools, attested
```

Every command and flag, and the `DECKWRIGHT_*` environment variables:
[docs/cli.md](https://github.com/phierceweb/deckwright/blob/main/docs/cli.md).

## Use it from Python

The CLI is the main surface; the same compiler is one call for a caller that generates specs
rather than writing them:

```python
import deckwright

result = deckwright.build_deck("review.deck.yaml")
print(result.deck, result.slides)      # the .pptx, and how many slides it holds
```

A spec is data, so the usual shape is to build a mapping, dump it as YAML, and compile that.
`deckwright.load_theme` reads a theme if you want its palette or grid before generating against
it, and the exceptions (`SpecError`, `ThemeError`, `LayoutError`, `RenderError`) are exported
for catching. Details:
[docs/compile.md](https://github.com/phierceweb/deckwright/blob/main/docs/compile.md).

## What ships

Twenty-two slide components, 29 native chart kinds, ~4,000 Material Symbols glyphs, imagery
with fit/crop and automatic scrims, HTML panels rendered through headless Chrome, and
animation — builds, click-to-reveal and slide transitions. 98 capability exercises cover
them, and the test suite drives all of them against every brand template present, so "it
works under your brand" is something the suite checks. `conform` reuses the same set to
report on a template it has just met.

## Working from a checkout

```bash
bin/setup        # venv (3.12+), editable install, .env — then verifies and builds a deck
bin/run doctor   # what this install can do; names anything missing
bin/run --help   # the deckwright CLI
```

`bin/setup` finishes by checking the glyph bundle, writing `templates/sample.pptx` to onboard
`conform` against, compiling `examples/smoke.deck.yaml` end to end, and printing the `doctor`
table. `bin/run <command>` runs the CLI through the project venv; `bin/test` and `bin/lint`
run the suite and the gates.

## Where everything is

Split by lifetime: what you write is safe, what a command writes is disposable. The
gitignored ones each carry a README saying what belongs in them.

```
authoring/    decks you are writing                          gitignored  ← start here
out/          everything a command writes; delete it freely  gitignored
templates/    brand .pptx files and the themes derived from  gitignored
              them — one directory, no copies
examples/     deckwright's own demo specs — part of the library
docs/         the reference; docs/README.md indexes it
src/deckwright/  the package        bin/  scripts        tests/  the suite
```

`authoring/` and `examples/` both hold `.deck.yaml` sources, and the difference is ownership:
a deck written for an audience is yours and is never committed; a spec that exercises the
compiler belongs to the library and is.

## Docs

Every document in the tree, so an assistant reading this repo can go straight to the right
one. [docs/README.md](https://github.com/phierceweb/deckwright/blob/main/docs/README.md) is the
same index, maintained in the docs directory itself.

**Writing a deck**

- [authoring.md](https://github.com/phierceweb/deckwright/blob/main/docs/authoring.md) — the `.deck.yaml` format end to end: the two-document structure, every slide field, `place:`, the chart block and every chart kind, `animate:`. Read this before writing or editing any spec
- [components.md](https://github.com/phierceweb/deckwright/blob/main/docs/components.md) — every component, its fields and defaults, with a worked example each. Load the one you're writing, not the whole file
- [choosing.md](https://github.com/phierceweb/deckwright/blob/main/docs/choosing.md) — you have data and a claim: which chart kind, or a table, or a single stat, or no graphic at all
- [treatments.md](https://github.com/phierceweb/deckwright/blob/main/docs/treatments.md) — you have no data: what shape the slide earns, what it costs, and whether the deck already looks like that
- [flows.md](https://github.com/phierceweb/deckwright/blob/main/docs/flows.md) — processes, steps, branches, anything with arrows — and when a flow is a bulleted list in a costume
- [glyphs.md](https://github.com/phierceweb/deckwright/blob/main/docs/glyphs.md) — which `icon:` name to reach for, grouped by what the slide is about
- [errors.md](https://github.com/phierceweb/deckwright/blob/main/docs/errors.md) — every build error beside its fix. Arrive with the message in hand
- [extending.md](https://github.com/phierceweb/deckwright/blob/main/docs/extending.md) — writing your own component, and when a deck-local one should move into the library

**Brand and design**

- [theme.md](https://github.com/phierceweb/deckwright/blob/main/docs/theme.md) — what a deck gets with no template at all: colour roles, contrast-checked pairs, type sizes, the grid
- [conform.md](https://github.com/phierceweb/deckwright/blob/main/docs/conform.md) — onboarding a brand template: what `conform` derives, what it refuses to trust, how to read its report

**Commands and workflow**

- [cli.md](https://github.com/phierceweb/deckwright/blob/main/docs/cli.md) — every command, flag and `DECKWRIGHT_*` variable, and which external tool each needs
- [pptx-deck-building.md](https://github.com/phierceweb/deckwright/blob/main/docs/pptx-deck-building.md) — the build → render → QA loop, animation injection, versioned output, and the rule against rebuilding after a hand-edit
- [qa.md](https://github.com/phierceweb/deckwright/blob/main/docs/qa.md) — the automated checks and severities, and what this layer structurally cannot catch
- [compile.md](https://github.com/phierceweb/deckwright/blob/main/docs/compile.md) — calling the compiler from Python, the order the build runs in, and what the manifest records

**Engine internals** — behaviour, not wire format; the format is always `authoring.md`

- [placement.md](https://github.com/phierceweb/deckwright/blob/main/docs/placement.md) — `at:` to a rectangle: the grid, reserved regions, chrome bands
- [imagery.md](https://github.com/phierceweb/deckwright/blob/main/docs/imagery.md) — photographs: fit and crop, pixel sampling, and the scrim that keeps text readable over them
- [charts.md](https://github.com/phierceweb/deckwright/blob/main/docs/charts.md) — the chart renderer: per-type options, the categorical palette, chart build animation
- [panels.md](https://github.com/phierceweb/deckwright/blob/main/docs/panels.md) — HTML rendered to a picture: the theme-as-CSS-variables contract, the cache, the canvas ceiling
- [icons.md](https://github.com/phierceweb/deckwright/blob/main/docs/icons.md) — SVG to DrawingML: the glyph search order, what an SVG must contain, how a glyph is coloured
- [motion.md](https://github.com/phierceweb/deckwright/blob/main/docs/motion.md) — builds, click-to-reveal and transitions, and the four-layer verification behind them
- [services.md](https://github.com/phierceweb/deckwright/blob/main/docs/services.md) — the external-tool boundaries: what LibreOffice, Poppler, Chrome and Pillow are each asked for, and every way they fail
- [utils.md](https://github.com/phierceweb/deckwright/blob/main/docs/utils.md) — the shared primitives: WCAG colour maths, the font-advance tables behind every wrap estimate, reserved-region geometry

**Contributing**

- [testing.md](https://github.com/phierceweb/deckwright/blob/main/docs/testing.md) — which changes need a test and which don't, and the evidence behind that rule

## Built on pf-core

deckwright is built on [pf-core](https://github.com/phierceweb/pf-core)
([PyPI](https://pypi.org/project/pf-core/)), an open-source Python foundation for LLM-facing
applications. deckwright uses its structured logging, exception hierarchy, config-from-env, CLI
subcommand factories and atomic-write utilities; projects that make model calls also get
prompt versioning, cost tracking and an eval harness. pf-core is also where the conventions
that keep a codebase legible to an AI agent are enforced instead of merely written down: a
build gate fails when a file outgrows its line budget, and a companion checker refuses a
hand-rolled utility the framework already provides.

For other phierceweb projects, see: [github.com/phierceweb](https://github.com/phierceweb).

## Contributing

[CONTRIBUTING.md](https://github.com/phierceweb/deckwright/blob/main/CONTRIBUTING.md) — what
belongs in the library, the gates to run before a PR, and the conventions. The short version:
a new capability is a slide the compiler can build, it lands as an exercise that drives it
against every brand template, and design decisions belong in the theme, never in a component.

## Security

[SECURITY.md](https://github.com/phierceweb/deckwright/blob/main/SECURITY.md) covers
vulnerability reporting and what a spec, a theme and a `.pptx` you were sent can each
actually do — building someone else's `.deck.yaml` can run their code, and every XML part of
a `.pptx` is parsed with entity expansion and network access refused.

## License

MIT — see [LICENSE](https://github.com/phierceweb/deckwright/blob/main/LICENSE). Bundled
[Material Symbols](https://github.com/google/material-design-icons) glyphs are Copyright
Google, Apache License 2.0 — their licence ships beside them at
`src/deckwright/icons/glyphs/material/LICENSE`, which is why the distributed artifact is
`MIT AND Apache-2.0` rather than MIT alone. The test suite carries ECMA-376 (ISO/IEC 29500)
schema files under `tests/schemas/ooxml/`; provenance in that directory's `SOURCE.md`.
