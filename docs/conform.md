# Conform — onboarding a brand template

How `deckwright conform` reads a brand `.pptx`, writes a theme for it, and drives every
capability through it to report what that template can and cannot carry. This is the
path for **getting a new template into deckwright**, and the answer to "will my deck build
against this?".

Distinguish it from two neighbours: [`docs/theme.md`](theme.md) describes the design
system a theme *expresses*; [`docs/testing.md`](testing.md) describes how the same
exercise set is reused as the project's end-to-end test. This doc is about the command.

---

## Table of Contents

- [What the command does](#what-the-command-does)
- [Onboarding a template, end to end](#onboarding-a-template-end-to-end)
- [Running it](#running-it)
- [Reading the report](#reading-the-report)
- [The derived theme is a starting point, never a build-time path](#the-derived-theme-is-a-starting-point-never-a-build-time-path)
- [Keeping the theme: `--adopt`](#keeping-the-theme---adopt)
- [What is measured, and what is refused](#what-is-measured-and-what-is-refused)
- [The exercises](#the-exercises)
- [Stand-in assets](#stand-in-assets)
- [When a template fails](#when-a-template-fails)
- [Adding an exercise](#adding-an-exercise)

## What the command does

Three things, in order:

1. **Derives a theme** from the template — its canvas, the colours it declares, the
   faces and sizes its own slides are set in — and writes it as YAML.
2. **Builds every exercise against it**, one slide at a time, each as its own single-slide
   deck. A component that fails names itself instead of taking the run down.
3. **Builds one combined deck** from every exercise that passed, so the result can be
   opened and looked at.

Step 2 is the point. Unit tests on the library's own arithmetic cannot answer whether a
*particular* template is usable; only building against it can.

The exercises are also the library's **capability catalogue**, and `deckwright demo` builds
the same set against a theme named rather than derived — see
[`docs/cli.md`](cli.md#demo--every-capability-in-one-deck). One registry, two readers:
add a capability there and it is both conformed and demonstrated.

## Try it without a brand template

`bin/setup` writes a small template deckwright owns, so the whole flow runs on a fresh
clone with nothing to hunt for:

```bash
bin/run conform templates/sample.pptx --adopt sample
```

That is a real derivation — six accents bound off its colour scheme, a hued `inverse`,
a face read from its slides — and every capability builds against it. What it is *not*
is evidence that deckwright copes with an unfamiliar template: it is shaped like what the
compiler already handles. Only real brand templates answer that, which is why the
generated one is stamped and [the corpus guard](testing.md) refuses it. See
[`sample`](cli.md#sample--a-template-to-onboard-against).

## Onboarding a template, end to end

The spine. Every step has a section of its own below.

1. **Drop the `.pptx` in `templates/`.** That directory is gitignored except for its
   README, because a brand template is licensed artwork that must never enter the repo.

   ```bash
   cp ~/Downloads/Brand.pptx templates/
   ```

2. **Conform it, and keep the theme.**

   ```bash
   bin/run conform templates/Brand.pptx --adopt brand
   ```

   The report ends with the three paths the run produced:

   ```
   theme -> out/conform/Brand/Brand.theme.yaml
   deck  -> out/conform/Brand/Brand.pptx
   adopted -> templates/brand.theme.yaml  (edit this one; out/ is disposable)
   ```

3. **Open the combined deck** at the `deck ->` path and look at it. The report says what
   built; only your eyes say whether it looks like the brand.

4. **Read and edit `templates/<name>.theme.yaml`.** The derivation is conservative and
   deliberately incomplete — [`docs/theme.md`](theme.md) has every key it could carry,
   and [What is measured, and what is refused](#what-is-measured-and-what-is-refused)
   has what it would not guess.

5. **Build against it.** `theme: brand` in a deck's config document, or
   `--theme templates/brand.theme.yaml`.

6. **Throw `out/` away** whenever you like. The theme and its template are in
   `templates/`; nothing under `out/` is needed again.

Re-running `conform` on the same template is safe: it rewrites `out/` and leaves
`templates/<name>.theme.yaml` alone unless you pass `--force`.

## Running it

```bash
bin/run conform templates/brand.pptx
```

Any path works; `templates/` is just the documented place to put one, and the only one
that cannot be committed by accident.

Output lands in `out/conform/<template-stem>/` by default (`--out` to change it;
the stem is truncated to 40 characters, so a long template name is shortened):
the derived `<stem>.theme.yaml`, whose `template:` points back at the file you ran
against, and the combined `<stem>.pptx` plus its manifest and the spec it was built
from. The template itself is never copied — there is only ever one of it.

Everything else the run generates — the stand-in photographs, the markdown the
`document` exercise reads, and the one-slide deck each exercise is built as — lives in
a hidden `.build/` beside them. An exercise that **passed** cleans up after itself; one
that **failed** is left there on purpose, because `_<name>.deck.yaml` is exactly what
you want when you go to work out why. Nothing in `.build/` is worth keeping between
runs; deleting the whole conform directory costs only the time to re-run it.

Exit status is non-zero if any exercise failed, so it works as a gate.

## Reading the report

```
brand.pptx
  · canvas 13.33 x 7.50in
  · composes on 'Blank' across 2 master(s)
  · page lt1=FFFFFF, ink dk2=1A1A2E (16.9:1)
  · ignored 3 unedited stock accent(s): accent4, accent5, accent6
  ok    cover
  FAIL  panel: <the error, first line, truncated>
  <passed>/98 exercises
```

The `·` notes are what a reader of the derived theme needs to know about this template —
its canvas, which layout generated slides compose on, the page/ink pair with its measured
contrast, and any judgement call worth surfacing (a stock accent ignored, an ink that did
not come from `dk1`).

Then one line per exercise, and a count. A `FAIL` line carries the build error, so most
are diagnosable without re-running.

## The derived theme is a starting point, never a build-time path

**Nothing is inferred at build time.** The library specializes into a template it is
*told* about, via a theme file a human has read. `conform` writes a first draft of that
file; it does not install it or make it authoritative.

```yaml
name: brand
template: Brand.pptx
drop_template_slides: true
bind:
  page: lt1
  ink: dk1
  accent-1: accent1
  accent-2: accent2
  inverse: dk2
type:
  face: Poppins
  heading_face: Poppins
  ramp:
    body: {pt: 16}
    ...
```

Edit it. The derivation is deliberately conservative and only writes what the template
can actually answer for; everything absent falls back to the built-in design system in
[`docs/theme.md`](theme.md).

## Keeping the theme: `--adopt`

Everything above lands in `out/`, which is disposable by design — deleting it whole must
lose nothing. That is right for the report, the combined deck and the scratch, and wrong
for the theme, the one artefact of onboarding worth keeping.

```bash
bin/run conform templates/brand.pptx --adopt brand
```

After a run that built something, that writes `templates/<name>.theme.yaml` beside the
template it binds, so the theme's relative `template:` resolves from where both of them
live. A deck then names it as `theme: brand`.

**A template is adopted where it lives.** Nothing is copied, so there is only ever one
copy of the binary; a `.pptx` somewhere else is refused, naming the `mv` that fixes it.

**A sidecar theme beside the binary is installed instead of the derivation.** When
`--adopt brand` finds `brand.theme.yaml` next to the `.pptx`, the exercises run against
the sidecar — what gets validated is what gets installed — and it is installed verbatim.
This is how a tuned theme survives leaving the repo: keep it beside the binary, and
re-onboarding costs one command. The report
carries `· theme from sidecar …` so a derived run and a re-onboard are never confused.

**Adoption does not make the derivation authoritative.** It changes *which file you
edit*. Without it the only copy sits in a directory built to be wiped, so editing it is
work waiting to be thrown away. Adopting moves the editing surface; it does not close it.

### What it refuses

Every check runs **before** the first exercise builds, so a mistake costs a second rather
than the whole run:

| Refusal | Why |
|---|---|
| `theme 'brand' already exists … and binds …` | That name is live on another template that is also here, and repointing it hijacks the theme; the existing file may be hand-edited, and nothing would recover it. Adopt under another name, or pass `--force`. |
| `a template is adopted where it lives` | The theme binds its template by a bare filename resolved beside it, so the `.pptx` has to be in the theme directory already. The message names the `mv`. |
| `--adopt takes a bare theme name` | The name becomes a filename and a deck's `theme:` line. Letters, digits, `-` and `_`. |
| `template not found` | Named before anything is written. |

### When exercises fail

A `FAIL` line is one capability this template cannot carry. **Adoption still happens**,
and the command still exits non-zero. That is deliberate: the fix for a `FAIL` is usually
to edit the theme (`chrome:`, a `bind:`) and re-run, which needs the theme somewhere that
survives — refusing to adopt would send the fix back into the disposable directory this
flag exists to get out of.

The exception is a run where **nothing** built. Per
[When a template fails](#when-a-template-fails), that means the theme does not describe
the template at all, so there is nothing worth installing under a project name. The
report says so and names the derived file to read:

```
  0/98 exercises
  not adopted: no exercise built, so the derived theme does not describe brand.pptx —
  read out/conform/brand/brand.theme.yaml and fix its bind: before adopting
```

## What is measured, and what is refused

The interesting part of `conform/derive.py` is what it refuses to trust:

| Source | Treatment |
|---|---|
| The `fontScheme` | **Not read as a declaration.** Across the eleven-template corpus it was honoured by no run at all — one template declares Calibri while every slide in it is Aptos. The face is counted from the runs on the template's own slides, weighted by how much text is set in it. The scheme is consulted for one thing: a run whose typeface reads `+mj-lt` or `+mn-lt` (or the `-ea`/`-cs` script variants) is not set in a face at all — that is OOXML's *reference* to the theme's major or minor font, and it is resolved through the master's own `fontScheme` before it counts. A reference no scheme can resolve is skipped rather than counted, since the built-in default is at least a real typeface. |
| `lt1`/`dk1` by position | **Ignored.** `page` and `ink` bind to the lightest and darkest slots by measured luminance. Three corpus templates carry a mid-grey in `dk1` and their real dark in `dk2`. |
| Unedited accent slots | **Dropped.** An accent still holding Microsoft's shipped value says nothing about the brand, so it is not bound and the report says how many were skipped. |
| The master's own paint | **Outranks the scheme.** What a slide will really show is the master's paint, so when it differs meaningfully from the page slot, every surface role is re-derived against it — a `clrScheme` has no slot for "secondary text on this template's photograph". |
| A background picture | **Sampled, not guessed.** The colour taken is the spot that reads *worst* against whatever ink will land on it, because a title crosses the whole frame and the palette's stated contrast should be the real floor. |
| Type sizes | **Only when they nearly match a built-in rung.** A measured rung further than the tolerance from any built-in is noise, not a decision, and is left out. |
| `inverse` | **The darkest slot carrying hue**, not the darkest slot. Pure black is every brand's black; a dark with hue in it is *this* brand's dark. |

One derived block is not a colour at all: when the template's background art leaves a
wide enough uniform horizontal run in the chrome band, `chrome:` is written with a
`cols:` range aiming the title stack at it. Templates put artwork in a corner and expect
the title beside it.

## The exercises

`src/deckwright/conform` holds one slide per capability, written the way a real deck would
use it, and ordered by how often that shape appears across the sample corpus — so a
template that fails early fails on something that matters. `exercise.py` assembles the
families in that order; each family is its own module beside it.

Every exercise is plain content with no brand words in it. The point is what the
*template* can carry, not what any particular deck says.

The same set is the project's end-to-end test: `tests/test_templates.py` builds all of them
against every real template and checks bounds, reserved regions, contrast, readback and
package structure.
Adding an exercise buys all of that — see [`testing.md`](testing.md).

## Stand-in assets

The exercises that need a photograph name `{photo}` and `{portrait}`, which the runner
fills in with absolute paths. The images are **generated per run, not shipped**: four of
the eleven corpus templates carry no picture at all and the rest name their media
differently, so an exercise that must build everywhere brings its own.

They are deliberately dark at one end and blown out at the other. A flat source would
clear any scrim opacity and prove nothing about the solve — see
[`docs/imagery.md`](imagery.md#the-scrim-solve).

`{notes}` is a small markdown file written the same way, for the `document` component.

## When a template fails

Read the `FAIL` line first — most are a `ThemeError` or `LayoutError` whose message names
the fix. Common shapes:

- **Every exercise fails.** The theme itself is wrong. Check the `·` notes: a canvas that
  is not the size you expect, or a page/ink pair with poor contrast, means the derivation
  picked slots that do not describe this brand. Edit `bind:` and re-run against the edited
  theme. (`--adopt` refuses this case; the derived theme is still at the printed path.)
- **One component fails.** That capability does not fit this template — usually the chrome
  band colliding with the template's own artwork. Adjust `chrome:` in the theme.
- **The command raises before any exercise runs.** The template defines no usable layout,
  carries no theme part, or is not a readable `.pptx` at all — corrupt, truncated, or
  another Office app's file under a renamed extension, which is refused with a message
  naming the path. Nothing can be built from it.

Re-run against an edited theme by building the exercises through the normal `build`
command, or call `deckwright.conform.run.conform()` with an `exercises=` subset to iterate on
one slide.

## Adding an exercise

1. Add an entry to the family module that owns the shape. `exercise.py` holds no
   exercises of its own — it calls each family in deck order and `EXERCISE` is what
   they assemble to:

   | Module | Family |
   |---|---|
   | `titles.py` | covers, headings, and where a title sits |
   | `text.py` | bullets, columns, cards, stat tiles |
   | `charts.py` | the chart catalogue, plus the four a template meets first |
   | `diagrams.py` | badges, connectors, flows, rules, rendered panels |
   | `blocks.py` | swatch wall, grid, set prose, code listing |
   | `motion.py` | entrances, and the builds that spend a click |
   | `layout.py` | a row split into shares, and a placed document |
   | `tables.py` | every shape a table takes |
   | `marks.py` | icons, and every component carrying one |
   | `figures.py` | `diverge`, `fanout`, `versus`, `nav` |
   | `photos.py` | imagery, fit and crop |

   Key it by a short slug that will appear in the report, and position it within its
   family by how common the shape is, not by when you added it. A new family is a new
   module plus one line in `exercise.py`, which is where deck order is decided.
2. Write it as a real deck would — no brand words, no template-specific assumptions. Name
   run-time assets with the `{photo}` / `{portrait}` / `{notes}` placeholders.
3. Run `bin/run conform` against at least one real template and confirm it passes, then
   run `bin/test` with the corpus present so it is exercised against all of them.

Do not add a unit test alongside it. The exercise **is** the test.
