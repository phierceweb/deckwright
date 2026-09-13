# QA — automated checks for built decks

The `deckwright qa` command checks a *built* deck (a `.pptx` plus the build manifest
`bin/run build` writes alongside it) against the automated checks below and writes a
findings report. This is a distinct layer from the "render and eyeball it" QA
described in `docs/pptx-deck-building.md` — that loop is a human looking at
`contact_sheet.png`; this one is a machine reading the manifest and, optionally,
the rendered PDF text. Run both. Neither replaces the other — see "What this
layer cannot catch" below for exactly why.

For AI assistants: [`pptx-deck-building.md`](pptx-deck-building.md) covers the render/QA loop end
to end; this doc is the full reference for the automated `qa` command
specifically.

---

## Table of Contents

- [Running it](#running-it)
- [The checks](#the-checks)
- [What the manifest records](#what-the-manifest-records)
- [Severity and `--fail-on`](#severity-and---fail-on)
- [Reading `qa.md` and `qa.json`](#reading-qamd-and-qajson)
- [Env knobs](#env-knobs)
- [What this layer cannot catch](#what-this-layer-cannot-catch)
- [Adding a new check](#adding-a-new-check)

## Running it

```bash
bin/run build examples/feature-tour.deck.yaml
bin/run qa "out/feature-tour/deckwright Feature Tour v15.pptx"
```

`qa` takes the path to a built `.pptx`. It looks for `<deck>.manifest.json`
next to it unless `--manifest` names a different file, and reads the theme
path the manifest itself recorded unless `--theme` overrides it. If the
manifest is missing, `qa` fails with a message telling you to build the deck
first — it never guesses or synthesizes one. A deck built by hand outside the
compiler (no manifest) cannot be QA'd; build it with `deckwright build` or accept
that this layer has nothing to check. The package checks are the exception —
they read the `.pptx` itself, so they stay honest even when the manifest is
stale from a hand-edit.

Every check but two runs off the manifest or the saved file alone and is
effectively instant. `overflow` renders the deck with LibreOffice and extracts text with
Poppler's `pdftotext`; `render-contrast` reads the pixels of that same render. Both cost
it, and `--no-render` skips both when you only want the fast geometry/contrast pass
(e.g. a pre-commit hook).

`--outdir` controls where `qa.md` / `qa.json` land (default `<deck-dir>/render/<deck>`).

## The checks

| Check | Reads | Catches |
|---|---|---|
| `bounds` | manifest only | A shape's declared box extends past the slide edges. |
| `placement-fit` | manifest only | A shape's declared box escapes the rect its own placement was given — an overrun onto the neighbouring placement, which `bounds` passes because the shape is still on the slide. |
| `reserved` | manifest only | A shape's declared box intrudes on one of the theme's `reserve:` regions (e.g. the logo wedge). |
| `min-font` | manifest only | A shape's declared font size is below the theme's minimum. A chart's data labels, axis text and legend are recorded as parts of its frame, so they are held to it too. |
| `contrast` | manifest only | A shape's declared foreground/background pair fails WCAG AA (4.5:1 normal text, 3.0:1 at 18pt+). **Severity follows certainty**: a shortfall above 3:1 warns, because the manifest records the pair a component asked for and the real backdrop may be better; below 3:1 nothing behind the text saves it, so it is an error. The build itself never refuses on contrast — it logs `theme_pair_below_aa` and carries on, so a brand's own palette is never unbuildable over a check this layer runs better. Chart text is checked as written into the chart part: each label's ink against the worst stop of the fill it sits on, or against the paper behind the chart when it sits beside its shape. |
| `text-fit` | manifest only | A shape whose own recorded text needs more height than the box it declared — text running past its own frame, which `bounds` structurally cannot see. Each line is measured at its own recorded size. |
| `fill-ground` | manifest only | A shape filled to stand off what is behind it — an inverse or accent `panel`, `card` or `ellipse`, a `versus` plate, a `diverge` bar, a callout's dot, a `fanout` source — that neither luminance (under 3:1) nor colour (under 35 ΔE) separates from the ground it was laid on, so it all but vanishes: an `inverse` bound to the page's own colour, an accent the page already is. A `surface` fill is a recess by design and records no fill to judge. WARN. |
| `placeholder` | manifest only | Recorded text that reads like copy nobody meant to ship — four phrases `deckwright new` seeds, plus `lorem`, `ipsum`, `TODO`, `FIXME`, `[insert`, and a run of three or more `x` in either case. Bare capitalised `TODO` fires unless whitespace and two more capitals follow it — the one exception, and what spares the Spanish *TODO EL MUNDO*; *TODO el mundo* and *TODO, EL MUNDO* are both reported, the second because a comma is not whitespace. `TODO:` fires unconditionally. Lowercase `todo` fires only as `todo:` opening a line, or as `@todo` anywhere. Every recorded row is read — its `lines`, or its `text` where it records none — and so are the slide's speaker notes. `TBD` is deliberately not matched: a deck may legitimately say it. WARN. |
| `overflow` | manifest + render | A line of text the manifest says a shape contains is missing from the rendered PDF's extracted text for that slide. A line the whole page does not hold is asked for again inside the shape's own box, because pdftotext merges side-by-side placements row by row and splices one column's line into the other's. |
| `render-contrast` | **the render's pixels** | Text on a slide showing a picture — one this deck placed, or one the template paints behind every slide — whose *rendered* surroundings fall below WCAG AA. Measured in three horizontal bands per shape, so a gradient scrim is judged where it is weakest. |
| `font-substituted` | **this machine**, not the deck | A face the theme names is not installed here, so the render is set in something else and every finding drawn from it — `overflow`, `render-contrast` — judged type the deck does not carry. One finding per absent face, on slide `0`. It runs only when `qa` renders, and is silent when fontconfig cannot be asked. WARN. |
| `chart-negative` | **the .pptx itself** | A bar or column chart carrying a negative value — not a fault in the file, but one the render cannot verify, because LibreOffice plots it as positive. Line and scatter series are unaffected and are not flagged. See [`charts.md`](charts.md#negative-values-and-why-the-render-cannot-check-them). |
| `chart-datapoints` | **the .pptx itself** | A bar or column chart plotting fewer than four values across all its series — the treatment `choosing.md` says is usually a `stats` row in disguise. The finding quotes that rule. WARN, never an error: the judgement is contextual, and a build that refused it would be wrong more often than the author. Only the six bar and column kinds; a line reads as a direction between ordered points, a pie's slices are the composition itself, and an XY or bubble mark already carries two or three numbers. |
| `beats` | manifest only | Reports each animated slide's rhythm — how many clicks the build spends and how many shapes each beat reveals — in the vocabulary the author wrote (`animate: together`, `animate: one_at_a_time`, `reveals:`, a chart's own build). INFO, so it never fails a run on its own; it is the only place a deck's reveal order surfaces beside `<deck>.beats.md`. |
| `beat-size` | manifest only | One beat of a *staged* build revealing more shapes than `DECKWRIGHT_MAX_BEAT_SHAPES` (default 6) — a slide that asked to be revealed a piece at a time and delivers most of it on one click. `animate: together`, a chart build and a `reveals:` trigger are exempt: one click is what they declare. WARN. |
| `dead-trigger` | **the .pptx itself** | An interactive reveal that cannot do its job: a hidden shape whose every trigger is itself hidden, so nothing can ever be clicked to show it (ERROR), or a target the slide's main build also reveals, so it is already on screen when the trigger is clicked (WARN). The compiler refuses every spec-level case, so this catches a hand-edit or a regression. |
| `shape-id` | **the .pptx itself** | Two shapes on a slide sharing an id, or an id outside 1..2147483647. |
| `theme-substituted` | manifest + the resolved theme | The recorded `theme_path` was not there, so the theme was resolved by *name* — and the file that answered hashes differently from the one the deck was built against. Every other finding is measured against that other theme's palette, grid and rungs. Pass `--theme` to name the right one. WARN. |
| `stale-manifest` | both | The deck's bytes no longer hash to what the manifest recorded — it was edited after the build, so every other finding describes the file that was built rather than the one on disk. WARN. |
| `shape-name` | **the .pptx itself** | Two shapes on a slide sharing a name. Legal OOXML and invisible in a render, but it costs the deck the mapping back to its spec — see [Shape names](#shape-names). WARN. |
| `animation-target` | **the .pptx itself** | An animation naming a shape id the slide does not contain. |
| `relationship` | **the .pptx itself** | An `r:embed`/`r:id` nothing declares, or one pointing at a part the package does not hold. |
| `package` | **the .pptx itself** | The file is not a readable `.pptx`, or a slide part is not well-formed XML. |

The first five read the *manifest*, not the `.pptx` file's actual XML — the manifest
is the compiler's own record of what it meant to place.

**`render-contrast` reads neither.** On a slide whose text sits on a photograph there
is no recorded pair to read — what is behind a title is whatever that picture happens
to be there, blended with whatever scrim went over it — so this one opens the render
and measures the colour actually surrounding each line. It is the only check that can
catch a scrim the build thought was enough and a renderer composited differently, and
it runs only on slides showing a picture — one this deck placed, or the backdrop the
template itself paints, which the manifest records on the slide rather than on any
shape.

**The last four read the saved package**, and they answer a different question: not
"is this slide well designed" but "will PowerPoint open this file at all". PowerPoint
validates the package before it draws anything, and a duplicate shape id, a dangling
relationship or an animation targeting a shape that was never drawn all produce the
same outcome — a repair prompt, and silently discarded content if you accept it.
LibreOffice is far more forgiving, so a render that looks perfect proves nothing here.
Timing is the one tree deckwright writes as raw XML, which is why its targets are checked
against the shapes actually present.

A shape from a placement the author declared `bleed: true` is exempt from `bounds`:
leaving the canvas is the instruction, and reporting it as an error would mean a
bleed-heavy deck could never produce a clean run. The exemption follows the
*declaration*, recorded in the manifest, not the geometry — a shape that escapes
without saying so is still an error. A full-bleed shape (at the origin and at least
slide-sized) is likewise exempt from `bounds` and `reserved` by design — that is
chrome, not a placement bug — and shapes recorded
with `rendered: "image"` are skipped by `contrast` and `overflow`, because a
rasterized panel is not text the manifest can vouch for.

`bounds` and `reserved` are checked once per distinct shape+box — a
multi-paragraph textbox is one geometry no matter how many paragraphs it
holds, so it is not reported once per line. `min-font` and `contrast` are
checked once per *manifest row* — and a row is not always a paragraph.

The composer records one row per chrome paragraph it draws, so a defect on any
line of a title/subtitle stack is caught. The body components do not: each
records one row per shape naming a deliberately **dominant** size and colour.
`callouts` records the head's 18pt and `title` colour for a row that also
holds 13.5pt body copy; `stats` records the value's size and `accent`
against the tile fill for a row that also holds the label. What a row does
not name is not checked — that body copy is never contrast-checked, and that
label's size is never compared to the theme minimum.

`table` is the exception: it records one row per **cell**, each with that cell's
own box, so every cell is contrast- and size-checked and `bounds`/`reserved`
measure the column rather than the table. A finding names the cell —
`'s3.p2.table.r2c4'` — not the table. A cell that reaches with `across:` or `down:`
records the box it really covers, so the check measures the span and not the
first square of it; the cells it swallowed record nothing, because they are not
there to measure.

Two skips remove rows from these checks entirely, silently: `contrast` skips
any record missing a foreground or background colour, and `min-font` skips
any record whose `font_pt` is `null`. Both are common — the 29-slide feature-tour
deck's manifest carries 129 native text rows, of which 16 have no recorded
size and 13 have no colour pair. **A clean `min-font`/`contrast` run does not
mean every line was measured; it means every line that named a size and a
colour pair was.**

## What the manifest records

### Provenance

The manifest opens with what produced it, before the records it describes:

| Key | What it is |
|---|---|
| `build_id` | Identity of the build: the spec, the theme and the deckwright version. The same inputs give the same id. |
| `deckwright` | The version that wrote the file, so an old manifest is recognisable as old. |
| `spec` | The `.deck.yaml` this deck was compiled from. |
| `spec_hash` | That file's contents when it was read. |
| `deck` / `deck_hash` | The `.pptx` written, and its contents. |
| `theme` / `theme_hash` / `theme_path` | The theme, unchanged from before. |
| `canvas` | `{"w", "h", "unit": "in"}` — the slide size, rounded like every other inch. |

Paths are written **relative to the manifest** wherever the two share a directory
tree, so a manifest handed over beside its deck carries no absolute home directory,
and the pair survives being moved. `qa` resolves `theme_path` back against the
manifest's own location, and falls back to the recorded `theme` *name* when that
file is not there — which is what lets a deck on `theme: base` be checked by someone
who has the package but not your directory layout. A name resolves against the
reader's own theme directory first, so a deck naming a brand can pick up a different
theme of that name; the recorded `theme_hash` is compared and a mismatch is reported
as `theme-substituted`.

**The three paths are written relative to the manifest**, so a manifest handed over
beside its deck carries no build-machine path, and a deck directory survives being
moved. `qa` resolves `theme_path` against the manifest's own location; an absolute one
— an older manifest, or a build whose theme shared no ancestor with its output — is
used as written, and a path that is no longer there falls back to the recorded name.

`deck_hash` is the one that catches a **hand-edited deck**. Every check below describes
what the build *intended*; open the `.pptx` in PowerPoint, move a box and save, and the
records here still describe the deck as built. `qa` compares the hash on every run and
reports [`stale-manifest`](#the-checks) when they differ — a warning rather than an
error, because hand-editing is the sanctioned way to finish a deck. Once it fires, read
every other finding as history.

### Placements, and the rect a shape belongs inside

Each slide records the placements it drew, before its shapes:

```json
"placements": [
  {"origin": "s1.hero.bullets", "component": "bullets",
   "box": {"x": 0.8, "y": 2.1, "w": 5.767, "h": 4.95}}
]
```

`origin` is the prefix every shape that placement drew carries in its `name`, which is
the only link from a shape back to the rect it was constrained to — `placement-fit`
walks it. `component` is what the placement declared, and the check reads it to exempt
`connector`, which draws *between* two other placements rather than inside its own.

A shape drawn on no placement — chrome, the background — matches no origin and is
simply not measured, so nothing has to list it. A slide that drew no placements at all
records no `placements` key.

`plate` on a shape marks a surface the compiler painted so something else could be read
on it. It is deliberately larger than the text it sits behind, so `placement-fit` skips
it; it is the one overhang the compiler chooses rather than the author.

### Sizes, when a shape sets more than one

`font_pt` is the shape's *dominant* size — the one `min-font` and `contrast` judge it by.
A shape whose paragraphs sit at different rungs also records `line_pt`, one size per
entry in `lines`:

```json
"lines": ["Precedent is not permission", "Existing code tells you what someone did once"],
"font_pt": 18.0,
"line_pt": [18.0, 13.5]
```

Without it a reader has no way to tell a 13.5pt body line from its 18pt heading, and
measuring both at 18 over-reports the shape's height by half. `record()` refuses a
`line_pt` whose length does not match `lines`, so the two cannot drift apart.

### Shape names

Every shape is named for the spec node that drew it, in the manifest **and in the
`.pptx` itself**:

```
s7.p2.card#1          slide 7, second placement, a card — its first shape
s7.hero.card#1        the same placement, where the author gave it `id: hero`
s7.chrome.title       a chrome line with its own `at:` — its own textbox
s7.chrome             the stacked chrome; its lines are paragraphs in one frame,
                      so the manifest holds `s7.chrome.title` and the package cannot
s7.p4.table.r2c3      a table cell, which is not a shape and so is named only here
s7.bg#1               the slide's background
```

**`#N` counts shapes in the order they were drawn, not the order you would name
them.** Where no colour reads behind a mark, the compiler paints a plate of the slide's
paper *first* and the component draws on top — so `#1` is the plate and the component's
own first shape is `#2`. A geometry finding against `#1` is about the plate, so read it
against the shape it sits behind rather than against the component you named.

PowerPoint preserves shape names through an edit, so the name is what maps a
shape in a hand-edited deck back to the spec that made it — and what the
Selection Pane shows while you are editing.

A placement's number moves when another is inserted above it. Giving it an
[`id:`](authoring.md#placing-components-with-place) fixes its name instead.

### Boxes, rounding, and what is left out

A shape's rectangle is keyed and in inches from the top-left of the slide:

```json
"box": {"x": 0.8, "y": 0.375, "w": 11.733, "h": 1.05}
```

**Inches are rounded to three decimals and point sizes to two.** PowerPoint stores
geometry in EMUs — 914400 to the inch — so dividing back out leaves sixteen digits
of binary residue, and a 13pt line records as `12.99975`. The rounding is an order
of magnitude inside the checks' own tolerances (0.01in at an edge, 0.02in for a
full bleed), so no check can change verdict, and a one-EMU shift no longer rewrites
fourteen digits in a diff.

**A key still at its default is not written.** No `"text": null`, no `"lines": []`,
no `"bleed": false` — about a third of the keys in a deck's manifest. A reader that
wants one falls back to the default on `ShapeRecord`: `rendered` is `"native"`,
`bleed` and `backdrop` are `false`, everything else is `null` or empty.

Read a box with `deckwright.compile.record.box_of(shape)`, which returns
`(left, top, width, height)` or `None`, and the slide size with `canvas_of(manifest)`.
A manifest written before boxes were keyed raises a `SpecError` naming the rebuild.

### Animation steps

A slide's `animations` are one entry per build, each a list of **steps** — one click
each, in order — naming the shapes that arrive:

```json
{"kind": "click_sequence",
 "steps": [["s3.p1.callouts#1", "s3.p1.callouts#2"],
           ["s3.p1.callouts#3", "s3.p1.callouts#4"]]}
```

Names rather than shape ids: an id says nothing to a reader, and is not unique on a
slide — every cell of a table reports its frame's. A shape animated but never
recorded keeps its id as `shape 4`, which at least says which. The motion *role* a
component reported is not recorded; it had already chosen an OOXML preset before the
manifest was written.

### The deck's words

The manifest describes a thousand shapes to say what a few hundred lines of text are —
by line it is about 3.6% content. `deckwright build` therefore writes
**`<deck>.content.md`** beside it: the same build rendered for a reader, slide by
slide, with the chrome as headings, tables as tables, bullets as bullets, and speaker
notes as quotes. Each block is labelled with the origin that drew it, so a line you
want to change points at the placement to change it in.

It is derived from the manifest and carries the same `build_id` — one writer, two
renderings, so they cannot disagree. Regenerate it; never edit it.

## Severity and `--fail-on`

`bounds`, `placement-fit`, `reserved`, and `overflow` (plus the `page-count`
fallback overflow emits when the manifest's slide count doesn't match the render's
page count) are `error`, and so is every package check — `shape-id`, `animation-target`,
`relationship` and `package` — since a file PowerPoint will not open is not a
matter of degree. `min-font`, `render-contrast`, `placeholder`, `font-substituted`,
`fill-ground` and `canvas-size` are `warn`; `contrast` is `warn` above a 3:1 ratio and `error` below it,
as its row above says. `dead-trigger` is `error` for a reveal that can never fire and
`warn` for one that reveals what is already on screen.

`beats` is the only `info` finding, and it is emitted for every animated slide rather
than only when something is wrong — it is a report of the reveal order, not a fault.
**So `--fail-on info` exits non-zero on any deck that animates.** That is what
`--fail-on info` asks for; `--fail-on warn` is the threshold that treats findings as
faults. Findings are data, not exceptions — a
deck with findings still builds and `qa` still exits 0 unless you pass `--fail-on`:

```bash
bin/run qa "out/feature-tour/deckwright Feature Tour v15.pptx" --fail-on error
```

exits non-zero only if the worst finding meets or exceeds the named severity
(`error` / `warn` / `info`). Without `--fail-on`, `qa` always exits 0 regardless
of what it found — it is a report, not a gate, until you opt into one.

A manifest with no `slides` — an empty list, or the key missing entirely —
adds one more finding: `empty-manifest`, `warn` severity, slide `0`. Without
it, a manifest with nothing to check would silently report zero findings, the
same as a deck that was checked and found clean; this finding is what tells
those two apart.

A manifest whose recorded canvas is not a positive width and height adds
`canvas-size`, `warn`, slide `0`, for the same reason: a render's pixels can
only be mapped to slide coordinates through that canvas, so `render-contrast`
measures nothing at all — and a check that measured nothing must not read the
same as a check that found nothing.

## Reading `qa.md` and `qa.json`

`qa.md` opens with a one-line severity tally, then one `## Slide N` section per
slide that has findings, each finding one bullet with a severity icon
(`✗` error, `!` warn, `·` info), the check name, and its detail string. Slides
with no findings are omitted entirely — an empty section would just be noise.
Findings are sorted slide-ascending, worst-severity-first within a slide.

`qa.json` carries the same findings as a flat list — `slide`, `check`,
`severity`, `detail`, `box` (the shape's declared rectangle as
`{"x", "y", "w", "h"}` in inches, or `null`), `shape` (the shape's name, or
`null`) — plus a `counts` object, for a script to gate on without re-parsing
markdown.

## Env knobs

Read at call time, so a long-lived process
picks up `.env` changes between calls:

| Var | Default | Controls |
|---|---|---|
| `DECKWRIGHT_PDFTOTEXT` | `pdftotext` | The Poppler binary the `overflow` check shells out to. |
| `DECKWRIGHT_PDFTOTEXT_TIMEOUT_S` | `60` | Seconds before that call is killed. |
| `DECKWRIGHT_SOFFICE` | `soffice` | The LibreOffice binary `qa` uses to render (unless `--no-render`). |
| `DECKWRIGHT_PDFTOPPM` | `pdftoppm` | The Poppler binary that rasterizes that render's PDF. |
| `DECKWRIGHT_RENDER_DPI` | `110` | Rasterization DPI for that render. |
| `DECKWRIGHT_FC_LIST` | `fc-list` | The fontconfig binary `font-substituted` asks for the installed families. |
| `DECKWRIGHT_FC_LIST_TIMEOUT_S` | `20` | Seconds before that call is killed. |

## What this layer cannot catch

Read this section before trusting a clean `qa` run. A reader who over-trusts
this layer is worse off than one who knows its edges — treat every check here
as a strong signal on a narrow slice of "is this deck okay," not a guarantee.

- **Nothing here watches an animation play.** LibreOffice draws a slide's *final* state, so
  a build mid-reveal is invisible to the render and a transition produces byte-identical
  images with and without one. `beats`, `beat-size` and `dead-trigger` read the timing
  *structurally* — how many clicks, how many shapes per beat, whether a trigger can fire.
  Whether the order teaches the room anything is a judgement, and `<deck>.beats.md` exists
  so you can read the reveal order in words and make it. Whether five consecutive slides
  share one rhythm is the run test applied to motion; `treatments.md` carries it as prose,
  because the tell is a click that stops changing what the room learns.
- **A trigger that emphasises rather than reveals is not judged.** `dead-trigger` looks for
  entrance effects. An interactive trigger that animates a shape already on screen is
  legitimate hand-authored PowerPoint, and this layer cannot tell it from a reveal someone
  broke.
- **A shape's declared box is not its rendered text extent.** `bounds` checks
  the box the manifest recorded for a shape — it has no way to know whether
  the text *inside* that box overflows the box's own edges. This is exactly
  how a real bug shipped earlier in this project: a bulleted list rendered a
  foot off the bottom of the slide while every geometry check reported clean,
  because the shape's declared frame was on-slide even though its rendered
  text was not. If a component can grow taller than its declared box (long
  bullet lists, unbounded user content), that risk lives entirely outside what
  `bounds` can see.
- **A shape can still overlap a neighbour without leaving its own rect.**
  `placement-fit` closes the case where a component draws past the rectangle it
  was handed. It does not close the case where the box is legal and the ink is
  not. A `box:` placement is exact geometry and is never narrowed, so two boxes
  the author wrote may legitimately overlap, and a `plate` is exempt by
  declaration. Rotation and effects are absent from the manifest by construction —
  `Box.from_emu` reads the shape's transform and nothing else — so shadows, a
  centred outline straddling its own edge, `fanout`'s rotated arrowhead and
  PowerPoint's own table auto-grow are rendered ink that no box check can see.
  The render remains the only thing that catches those, by eye.
- **Text inside a rasterized panel is invisible to `pdftotext`.** Anything
  recorded as `rendered: "image"` (HTML-card screenshots, doc/code panels) is
  skipped by `contrast` and `overflow` on purpose — checking it would report
  false losses for text a PDF extractor structurally cannot read. That also
  means those panels get *zero* automated coverage: overflow, illegible type,
  and low contrast inside a screenshotted card are only caught by eye. See
  `docs/panels.md` for the full panel pipeline and what choosing a panel over a
  native shape costs.
- **`placeholder` reads the manifest's words, so a panel hides its copy too.**
  Scaffold or `TODO` text inside an HTML card or a doc/code panel is a picture by
  the time the deck is written, and never reaches the manifest as text — the same
  blind spot `contrast` and `overflow` have there. Nor does the check read intent:
  it matches literal phrases, so a real sentence that happens to contain one is
  reported, and copy that is placeholder in every sense but its wording is not.
- **`placeholder` names four scaffold phrases.**
  Only copy no ordinary deck would write is on the list: `A KICKER`, `Three lines and
  a chrome block make a cover`, `Three things are broken` and `questions@example.com`.
  An unedited scaffold therefore draws four findings, on three of its six slides, and
  its other seeded lines — *Three moves*, *The first thing*, *What we chose.*,
  *Adoption climbs every quarter* — pass, as the same words would in a deck someone
  wrote.
- **The x-run is matched in either case, and asks nothing about what it stands for.**
  A masked identifier (*Card ending XXXX 4242*), a Roman numeral (*Section XXX*) and a
  front-matter page reference all report alongside a real `xxx` placeholder. Three or
  more `x` standing as a word of their own is the whole test — a run inside a word or
  between digits (*maxxxx*, *1xxx2*) is not one.
- **`text-fit` sees only what a component records.** A shape whose paragraphs sit at
  different rungs records a `line_pt` — one size per line — and each is measured at its
  own. A multi-line record *without* those sizes is skipped rather than guessed at,
  because measuring a body paragraph at its heading's size over-reports by a wide margin
  and would fill a sound deck with invented findings. So a component that records a
  heading and its copy under one `font_pt` is invisible to this check until it records
  the sizes too.
- **Every width this layer measures is only as good as the face's metrics.**
  `text-fit`, and the height arithmetic every component uses to size its own
  boxes, are computed from per-character advances — and deckwright ships those for
  two families only, Calibri/Carlito and Arial/Helvetica/Liberation. A theme
  naming anything else is laid out against a deliberately loose ceiling, so a
  clean `text-fit` on such a deck means "nothing overflowed the widest estimate
  available," not "the text fits." The build says so at the time:
  `warning theme_face_unmeasured` names the face and the role. Read that warning
  before trusting this section. It compounds when the face is also **not
  installed** where the deck is opened — the build reserves ceiling width, the
  renderer substitutes something narrower, and a slide that overlaps for your
  audience reports clean for you. See
  [`theme.md`](theme.md#the-face-and-whether-deckwright-can-measure-it) for the
  table of measured families and what to do about it.
- **`font-substituted` needs fontconfig, and answers only for this machine.** It
  asks `fc-list` which families are installed, and where that binary is absent —
  macOS does not ship it; `brew install fontconfig` supplies it — the check returns
  nothing rather than a verdict. A run with no `font-substituted` finding therefore
  means either every face is installed or nobody looked, and `--no-render` makes it
  the latter by design. What it does answer for is the box that rendered, which is
  the one whose pixels `overflow` and `render-contrast` read. The laptop the deck is
  finally opened on is unobservable from here: a face present on your machine and
  missing on the presenter's substitutes there, and nothing in this layer sees it.
- **`min-font` and `contrast` see rows, not lines.** A manifest row can stand
  for a whole multi-paragraph shape under one dominant size and colour, and a
  row that names no size (or no colour pair) is skipped without a finding —
  see "The checks" above for which components record which. Text can
  therefore be too small, or below AA, on a deck these two report clean.
- **`contrast` trusts the manifest's recorded colours, not a sampled pixel.**
  If a component records the wrong foreground or background role — e.g. the
  page background role instead of the dark image actually behind a shape —
  the check computes a ratio for colours that were never really adjacent on
  the slide. It is exactly as accurate as the compiler's own bookkeeping.
  `render-contrast` is the answer to that on a slide carrying a picture, and
  only there — everywhere else the manifest's colours are all anything reads,
  and `--no-render` removes even that.
- **The render is LibreOffice, not PowerPoint.** Font substitution and text
  metrics differ between the two, so `overflow`'s judgment of what did or
  didn't survive rendering is a strong signal, not a guarantee — a line that
  fits in LibreOffice's font substitute could still clip in real PowerPoint,
  and vice versa. Animation states are also irrelevant here: LibreOffice
  renders the final built state, so a `qa` render cannot see a click-reveal
  that never gets to that state. A **slide transition** is invisible to this
  layer twice over: it produces identical renders, and it touches nothing in the
  manifest, so no check reads it at all. Schema validity and child order for both
  are covered by `tests/test_ooxml_schema.py`, not by `qa` — see
  [`motion.md`](motion.md#verification). It cuts the other way too: LibreOffice's
  importer has its own faults, so a render finding can mean the deck is fine
  and the renderer is not. A `table` row that is entirely a vertical merge is
  legal OOXML which LibreOffice mis-imports, dropping the table's last row and
  moving the whole table — `inspect` and the manifest both read correct.
  Isolate before believing either side: build the shape with one variable
  changed and render both.
- **A structural readback is not a render.** `tests/test_templates.py` builds every
  exercise against every real template and reads the result back out of the
  file, which is a strong check on what the compiler *wrote* and no check at
  all on what a renderer *does with it*. The vertical-merge fault above passed
  the corpus against all eleven templates and was caught only by rendering a
  built deck. A capability is not proven until something has looked at it.
- **`overflow` is a normalized substring search, not a layout check.** It
  proves a line of text landed *somewhere* on the rendered page — not that it
  landed inside its own shape, not that it isn't overlapping another shape,
  and not that it wasn't shrunk to the edge of legibility to fit. Matching
  ignores case, spacing, and hyphens — `pdftotext` rebuilds a line the
  renderer wrapped at a hyphen as either `nontext` (reading order deletes the
  hyphen) or `non- text` (`-layout` keeps it at the row break), and neither
  is loss — but that same leniency means a garbled or reordered rendering of
  the right characters would not be flagged either.
- **A line whose own box crop also fails still reports a false `overflow`.** Both
  whole-page extractions read a page row by row, so where two columns sit side by
  side the neighbouring column's text lands *between* the halves of a line the
  renderer wrapped. The check answers that by asking again inside the shape's own
  box, which resolves the ordinary two-column case — but only when `qa` renders,
  and a crop that errors is logged and treated as a miss, so the finding comes
  back. On a single `[error] overflow` it is still worth a look at the render.
- **None of these checks are a design review.** Visual hierarchy,
  alignment, spacing balance, and "does this look intentional" are out of
  scope entirely — the vision-model design review carried into Plan C2 is
  aimed at that gap, not this one.

## Adding a new check

A manifest-only check is a function `(manifest: dict, theme: Theme) -> list[Finding]`
in `src/deckwright/qa/geometry.py`. That `dict` is the serialised form of `ShapeRecord`,
`PlacementRecord` and `SlideRecord` in `src/deckwright/compile/record.py` — read those
dataclasses for the keys and their units rather than inferring them from a built deck's
JSON. `manifest.py` only writes them. One that
needs the render goes in
`src/deckwright/qa/textflow.py` (extracted text) or `src/deckwright/qa/imagery.py`
(pixels, taking the rendered images rather than the theme); one that reads the saved
package goes in `src/deckwright/qa/package.py`, taking the deck path alone — unless it asks
something other than "will PowerPoint open this file": what the chart parts say about the
charts is `src/deckwright/qa/charts.py`, and what the timing says is
`src/deckwright/qa/motion.py`, which reads the manifest for the rhythm and the package for a
reveal that cannot fire. Wire it into
`run_qa` (`src/deckwright/qa/runner.py`) — inside the `if render:` block if it needs one —
and give every `Finding` a `severity` that matches the table above: `error` for a
placement/content defect the audience will notice, `warn` for a quality issue worth a
human decision. Add its row to "The checks" table and, if it has a blind spot, a
bullet in "What this layer cannot catch."
