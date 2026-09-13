# Authoring a deck

How to write a `.deck.yaml` that `deckwright build` compiles into a branded PowerPoint file. This is the wire format — the structure of the file, every slide field, how a component is placed, and the chart block — plus the index that says which component you want.

Three companions carry the bulk, and you pull each in only when you need it:

| Read | When |
|---|---|
| [`docs/components.md`](components.md) | You have picked a component from the index below and need its fields, its defaults and a worked example. |
| [`docs/errors.md`](errors.md) | A build failed and you have the message in hand. |
| [`docs/glyphs.md`](glyphs.md) | You are choosing an `icon:` name. |

For AI assistants: these docs are written so you can author a correct deck **without reading the source**. Start here; load the others on demand. [`pptx-deck-building.md`](pptx-deck-building.md) covers the surrounding workflow (render, QA, versioned output, hand-edits).

---

## Glossary

Read this first. Several of these words are jargon kept deliberately in the code and theme, and this table is how you survive meeting them.

| Word | What it means |
|---|---|
| **theme** | The brand: every colour, font, size, margin and chart style, in one YAML file. You name a theme; you never set what's in it. |
| **template** | The `.pptx` file the theme borrows its colour palette, fonts and background images from. Referenced by the theme, never by your spec. |
| **background** | Which backdrop a slide is painted on, and therefore which colour pair its text is allowed to use: any pair the palette declares — `page` (default), `inverse`, an accent — or an image. |
| **section** | A chapter of the deck. You list the chapter names once in the deck document and tag each slide with the one it belongs to. |
| **placement** | One entry under a slide's `place:` — an `at:` saying where, plus exactly one component key saying what. |
| **kicker** | The small label above a slide's title. You write it; nothing derives it for you. |
| **component** | The content of a slide: a list of bullets, a row of stat tiles, a chart. Each one goes in its own placement, and a slide may carry several. |
| **body** | The area a component fills — everything below the chrome. Also the old, deleted `body:` key; if you see it in an old spec, it's gone. |
| **reserved region** | A region of the slide that content must not enter, because the brand puts a logo there. Defined in the theme's `reserve:`; the compiler routes the content band around it, or rejects the placement that hits it. |
| **chrome** | A slide's own text — `kicker`, `title`, `subtitle`. Every field is optional; absent means absent. By default the three stack from the top margin, and a `chrome:` block moves any of them anywhere on the canvas. |
| **panel** | Two unrelated things. The `panel` **component** is a filled colour block. A *rendered panel* is an HTML fragment screenshotted by a headless browser, which is how the `document` component shows a real markdown file. |
| **manifest** | A `.manifest.json` written next to the built deck, recording every shape's text, size, colour and position. The `qa` command checks the deck against it. |

---

## Table of Contents

- [Glossary](#glossary)
- [Where a spec comes from](#where-a-spec-comes-from)
- [A complete deck, start to finish](#a-complete-deck-start-to-finish)
- [The two-document structure](#the-two-document-structure)
- [The deck document](#the-deck-document)
- [Slide fields](#slide-fields)
- [Moving the chrome](#moving-the-chrome)
- [Placing components with place:](#placing-components-with-place)
- [Components](#components) — the index; the field tables are [`components.md`](components.md)
- [The chart block](#the-chart-block)
- [All 29 chart kinds](#all-29-chart-kinds)
- [animate](#animate)
- [transition](#transition)
- [reveals](#reveals)
- [What lives in the theme, not the spec](#what-lives-in-the-theme-not-the-spec)
- [Adding a component the spec cannot express](#adding-a-component-the-spec-cannot-express)

Every build error, beside its fix, is [`docs/errors.md`](errors.md).

---

## Where a spec comes from

Three ways a spec starts.

- **`deckwright new "<Name>"`** writes a deck directory under `authoring/` holding a spec
  that already builds, and builds it. Start here for a new deck: editing a working
  file is faster than filling an empty one.
- **`deckwright extract <deck>.pptx`** drafts a spec from a deck that already exists, when
  what you want out of it is its words. Chrome, bullets, tables and speaker notes
  convert, inside grouped shapes as well as on the slide; every shape it cannot turn into
  words becomes a `# not converted:` comment naming what you have to put back by hand.
  `--as md` writes a plain transcript instead of a spec.
- **The example below**, copied and rewritten.

An extracted draft carries the deck's words and none of its design. A deck from elsewhere
comes back as chrome plus bullets, with only its placeholders and its type sizes to say
which line was the title; a deck deckwright built keeps its kicker, title and subtitle,
because the extractor reads the shape names `build` writes. Treat either as source
material, and read [`docs/treatments.md`](treatments.md) before it goes anywhere.
[`docs/cli.md`](cli.md) has what converts and what does not.

---

## A complete deck, start to finish

Copy this, change the words, build it. It is a valid deck.

```yaml
theme: base
sections: [Problem, Solution]
out: ../../out/example/Example v1.pptx
---
background: inverse
kicker: JULY 2026
title: A worked example
subtitle: Everything below is optional
---
background: inverse
section: Problem
kicker: PART 1 OF 2
title: Problem
subtitle: What is going wrong
---
section: Problem
kicker: PROBLEM
title: Three things are broken
animate: one_at_a_time
place:
  - at: {cols: full}
    bullets:
      items:
        - The first thing
        - The second thing
        - The third thing
---
section: Solution
kicker: SOLUTION
title: Adoption climbs every quarter
subtitle: Since the rollout
place:
  - at: {cols: full}
    chart:
      kind: column
      data:
        - {category: Q1, value: 12}
        - {category: Q2, value: 34}
        - {category: Q3, value: 58}
        - {category: Q4, value: 91, highlight: true}
---
background: inverse
title: Thank you
place:
  - at: {cols: full}
    bullets:
      items: [questions@example.com]
```

Build it:

```bash
bin/run build authoring/example/example.deck.yaml
```

That writes the `.pptx` named by `out:` — resolved against the spec's own directory, so a spec in `authoring/example/` and an `out:` of `../../out/example/…` land it in `out/example/` — plus a sibling `.manifest.json`, a `.content.md` of the deck's words and a `.beats.md` of its reveal order. Then look at it — rendering and eyeballing the result is the real check:

```bash
bin/run render "out/example/Example v1.pptx" --contact-sheet
bin/run qa "out/example/Example v1.pptx"
```

---

## The two-document structure

A `.deck.yaml` is a **multi-document YAML file**. Documents are separated by `---` on its own line.

A number keeps the text you wrote it in wherever it prints: `1.10` stays `1.10` in a table
cell or a stat, not the `1.1` YAML reads. It still counts as a number wherever one is
expected. What YAML 1.1 would read in another base — `007`, `0x1F`, `1:30`, `16:9` — is the
text you wrote, never 7, 31, 90 or 969: it prints as typed and `crop: 16:9` is that
aspect. A field that takes any number reads it as a decimal (`007` is 7) or refuses it by
name; a whole-number field such as a column index refuses it.

- **The first document is the deck document.** Theme, section names, output path.
- **Every document after it is one slide,** in order.

```yaml
theme: base          # ─┐
sections: [One, Two]   #  │ document 1 — the deck
out: ../out/d/D.pptx # ─┘
---
background: inverse    # ─┐ document 2 — slide 1
title: Hello           # ─┘
---
section: One           # ─┐ document 3 — slide 2
title: A slide         # ─┘
```

Do not put a `---` before the deck document. A deck needs at least one slide document.

---

## The deck document

| Field | Required | What it does |
|---|---|---|
| `theme` | **yes** | Names the theme file, resolved against the theme directory (`templates` by default) and then the packaged built-ins — so `theme: base` resolves anywhere deckwright is installed. |
| `out` | yes, unless `--out` is passed | Where to write the `.pptx`. Relative paths resolve **against the spec file's own directory**. |
| `sections` | no | The deck's chapter names, in order. Every slide's `section:` must be one of them. |
| `extends` | no | A Python module registering bespoke components. Resolved relative to the spec file. **It is imported and executed**, before any placement is validated — so building someone else's `.deck.yaml` runs their code on your machine. See [Adding a component](#adding-a-component-the-spec-cannot-express). |
| `title` | no | Metadata only. The compiler does not draw it — the opening slide's own `title:` is what appears. |

Those five are the whole list. Any other key in the deck document is an error, and the message suggests the field you probably meant.

```yaml
theme: base
title: Q4 review
sections: [Chrome, Theme, Spec]
extends: my_components.py
out: ../out/deck/Deck v1.pptx
```

**`sections` is the single source of truth for chapter order.** Every slide's `section:` must be a name from this list; a name that is not in it is an error naming both. Omit `sections` entirely and any `section:` value is accepted.

A chapter also has to run **once**. A slide that resumes a section after another has begun is refused, naming both slides — otherwise a reorder that scattered one chapter builds clean, and a theme that draws no section rail shows nothing. A slide carrying no `section:` of its own sits in whichever run it falls in and does not break it.

Nothing is derived from a section any more — no kicker, no part number, no navigation strip. If a slide should say `PART 2 OF 3`, write that in its `kicker:`.

---

## Slide fields

There is no `layout:`. Every field below is optional; an absent field draws nothing.

| Field | What it does |
|---|---|
| `title` | The slide's headline. |
| `kicker` | A small label above the title. |
| `subtitle` | A line under the title, smaller. |
| `background` | Any declared palette pair — `page` (default), `inverse`, `accent-1`, … — or `{image: name.png}`. Selects which contrast-checked colour pair the slide's text uses. |
| `section` | Which chapter this slide belongs to. Must match a name in the deck's `sections`. |
| `notes` | Speaker notes. Spoken, not shown. |
| `animate` | How the slide's components reveal on click. See [animate](#animate). |
| `transition` | Only ever `none` — a deliberate hard cut into this slide, refusing the theme's transition. See [transition](#transition). |
| `place` | A list of placements. See below. |
| `chrome` | Where the title, kicker and subtitle go, overriding the theme. See [Moving the chrome](#moving-the-chrome). |

```yaml
kicker: Q3 RESULTS
title: Revenue up 40%
background: inverse
section: Spec
animate: one_at_a_time
```

Misspell anything and the compiler tells you what you meant:

```
d.deck.yaml: slide 1: unknown field 'subtile'; did you mean 'subtitle'?
```

By default `kicker`, `title` and `subtitle` stack from the top margin, and the
content band starts below them: a title long enough to wrap costs the body a line
of height rather than being drawn over the subtitle. The compiler measures the wrap
from the text, the rung and the rung's own typeface — real per-character font
metrics plus a small safety margin, falling back to a conservative ceiling for a
face it has no metrics for — so a long title shows up as slightly less room for the
body, and the render is where you decide whether the title should simply be shorter.

### Moving the chrome

The theme decides the default treatment. A slide's `chrome:` block overrides it,
one field at a time, one key at a time — anything you leave out keeps whatever the
theme said.

```yaml
title: Centred on the canvas axis
subtitle: The frame spans the canvas and the ink floats in it
chrome:
  title:    {at: {box: {x: 0%, y: 10.5%, w: 100%, h: 10%}}, align: center}
  subtitle: {at: {box: {x: 0%, y: 21.5%, w: 100%, h: 5%}}, align: center}
```

| Key | Values |
|---|---|
| `at` | The same grammar as a placement's `at:` — `cols`, `cols`+`rows`, or `box` — but resolved against the **whole canvas**, since chrome is what decides where the content band starts. A `box` may write `h: auto` for a depth that follows the text: the line takes as many lines as it wraps to, so re-shuffling content cannot leave a hand-measured height behind. Every other value stays a percent. |
| `align` | `left` (default), `center`, `right`. |
| `anchor` | `top` (default), `middle`, `bottom`. Needs an `at:`. |
| `rung` | Any type-ramp role, e.g. `display` for a cover title. Defaults to the field's own name. |
| `pair` | Any declared palette pair, e.g. `accent-3` for a line reversed out of a panel painted in it. Defaults to the slide's own pair. |
| `ink` | A colour **role**, when the ink is all that moves and the surface behind it stays as it is. Defaults to the pair's own foreground. |

Every number is a fraction of the canvas, never an inch. A `box` that leaves the
canvas is an error saying so, which is what catches inches pasted in from a
measured deck.

**Naming a colour is a claim the compiler checks.** A `pair:` or an `ink:` is
measured against what the slide *actually painted* under that band — the panel, the
photograph, the template's own artwork — and a line that does not clear the ratio
its size needs is an error rather than a colour quietly moved:

```
slide 1: chrome 'title' is inked FFFFFF from 'page', which reads at 1.00:1 on the
FFFFFF this slide paints — below 3.0:1. Choose a colour that suits this background,
or place a panel behind the line.
```

Leave both out and the ink is free to move to whatever reads where the line landed.

Two behaviours follow from giving a line an `at:`:

- **It stops pushing the body down.** Only stacked lines set the content band's
  top, so a title in the right-hand columns sits *beside* the body rather than
  above it, and a title on a colour panel sits *over* it.
- **It gets a frame of its own**, which is what lets it carry an `anchor`. Setting
  `anchor` on a field with no `at:` is an error: the stacked lines share one frame,
  so there is nothing of its own to anchor in.

Chrome is drawn last, above every placement — that is what makes a reversed-out
title on a `panel` work:

```yaml
title: Reversed out of a panel
chrome:
  title: {at: {box: {x: 9%, y: 36%, w: 30%, h: 20%}}, pair: accent-3}
place:
  - at: {box: {x: 0%, y: 0%, w: 45%, h: 100%}}
    bleed: true
    panel: {pair: accent-3}
```

`examples/title-treatments.deck.yaml` builds six treatments from these keys —
flush-left rail, canvas-centred, hero cover, offset column, on a panel, and
right-aligned — and is the fastest way to see the geometry.

### `background`

A background names **any pair the theme's palette declares**, or an image.

| Value | What is painted |
|---|---|
| `page` (or omitted) | The template's own surface, kept as it is — its colour, or its background art. Painted only where the template shows something other than what `page` promises. Text takes the `page` pair. |
| `inverse` | The `inverse` pair's background colour, full bleed, with the theme's `marks.inverse` art laid over it if it has any. Text takes the `inverse` pair. |
| `accent-1`, `surface`, … | That pair's background colour, full bleed. Text takes that pair, so an accent nothing readable sits on is rejected rather than drawn. |
| `{image: cover.png}` | The same painted surface, with your image over it. Resolved like any deck image: beside the deck spec first, then beside the theme's template, then out of the template's own `ppt/media/`. A relative name may not climb out of those directories with `..` — that name stays inside none of them — though an absolute path is still taken as written. Text takes the `inverse` pair. |

The background is what decides the slide's colour pair, and a pair is contrast-checked when the theme loads. Ink and surface always come from the same validated pair, so a slide cannot end up with white text on a white surface.

**For a section opener, reach for the brand's accent before `inverse`.** A template's
own colours live in its accents; the darkest slot of a `clrScheme` is pure black on
seven of the eleven sample templates, and not one of them uses black as a surface.

---

## Placing components with `place:`

A placement is a mapping carrying `at:` plus **exactly one** component key. Zero component keys, or two, is an error naming the slide and the placement number.

```yaml
place:
  - at: {cols: left-half}
    chart: {kind: column, data: [...]}
  - at: {cols: right-half}
    bullets: {items: [one, two]}
```

`at:` takes one of:

| Form | Meaning |
|---|---|
| `{cols: <name>}` | A named fraction of the content width: `full`, `left-half`, `right-half`, `left-third`, `mid-third`, `right-third`, `left-two-thirds`, `right-two-thirds`. |
| `{cols: <name>, rows: <name>}` | Also bounded vertically: `band` (the whole band), `top-half`, `bottom-half`, `top-third`, `mid-third`, `bottom-third`, `top-two-thirds`, `bottom-two-thirds`. |
| `{cols: {from: N, to: N}}` | An exact span, where no fraction names it. Half-open indices into the theme's `columns:`; `rows:` takes the same form over its `rows:`. |
| `{box: {x: 0%, y: 10%, w: 100%, h: 20%}}` | The escape hatch: percents of the canvas. May start off the edge. |

### `split:` — a row of equal things

A row of four cards is four placements only because someone wrote four spans. State
the band once and let the compiler divide it:

```yaml
place:
- at: {rows: {from: 1, to: 7}}
  split:
  - card: {heading: ellipse, body: "A disc, sized off its placement."}
  - card: {heading: card, body: A rounded rect with a heading.}
  - card: {heading: connector, body: A line joining two placements.}
  - card: {heading: rule, body: "A divider, weighted off the theme."}
```

Each child is an ordinary placement — any component, plus `id:`, `align:`, `anchor:` —
**without an `at:`**, because the band gives it its rectangle. Add a fifth and nothing
else changes; with hand-written spans you would redo all four.

`at:` is optional and defaults to the whole content width, so a `split:` usually says
only how deep it is. Narrow the band with `cols:` when it should not span everything.

A child may take more than one share with `span:`:

```yaml
- split:
  - span: 2
    card: {heading: Twice as wide}
  - card: {heading: One}
  - card: {heading: One more}
```

Where the shares divide the column grid evenly, they *are* column spans — a four-way
split lands exactly where `{from: 0, to: 3}`, `{from: 3, to: 6}` and the rest would.
Where they do not — five across twelve columns — the band's width is divided evenly
instead, which is the only way to say "five across" at all.

`split:` does not nest, and it divides columns, not a `box:`. A grid of cards is one
`split:` per row.

Quarters have no name on purpose. Every quarter in a real deck is one of N equal
things across a row, and the spans for that are what `{from:, to:}` is for — or
name the thirds and halves you actually mean.

Both divisors are the theme's and visible in it: `scale.columns` and `scale.rows`,
each 12 by default. A name a grid cannot divide evenly — thirds on a 10-column
theme — is an error telling you to state the span outright, rather than rounding
two "thirds" to different widths on the same slide.

Five optional keys sit beside `at:`: `id:` names the rectangle so another placement can refer to it, `reveals:` names another placement's `id:` to stay hidden until that one is clicked (see [reveals](#reveals)), `bleed: true` declares that the placement is meant to run off the slide edge — and a bleeding placement may leave `at:` out entirely, which is what a connector drawn between two other placements does, and `align:` (`left` | `center` | `right`) and `anchor:` (`top` | `middle` | `bottom`) say where the component sits inside the rectangle.

**`id:` also names the shapes.** Every shape the build draws is named for the placement that drew it, in the manifest and in the `.pptx` — `s7.p2.card#1` for the second placement on slide 7, `s7.hero.card#1` where you wrote `id: hero`. PowerPoint keeps those names through a hand-edit, so they are what tie an edited deck back to this file. A number moves when a placement is inserted above it; an `id:` does not. See [what the manifest records](qa.md#what-the-manifest-records).

**Which components fill, and which hug.** `card`, `panel`, `versus` and `chart` stretch
to whatever rectangle the placement gives them; `bullets`, `callouts`, `stats`, `flow`,
`table` and `code` size to their content and leave the rest of the placement empty. The
split decides which lever you reach for: bound a *filling* component with `rows:` or it
swallows the band, and settle a *hugging* one with `anchor:` or its slack piles up below.

`align` moves type inside the frames a component draws. **`anchor` moves the component itself**: a component sized to its content leaves slack in its placement, and `middle` or `bottom` distributes that slack instead of piling it below — the difference between a slide that reads airy and one that reads unfinished. The default `top` moves nothing, so no existing deck shifts. A `bleed: true` placement is never settled: a declared overrun is the author overriding geometry on purpose. A component that already places itself, like `ellipse`, measures as correct and is left alone. A component that sets no text of its own — `chart`, `connector`, `document`, `panel` — refuses them rather than ignoring them; `callouts` refuses `align` because its rows are set flush against the dot rail, and `rule` refuses whichever of the two would move it along the axis it already spans.

`ellipse` is the one exception: its shape *is* its content, so `align`/`anchor` position the disc inside the placement.

A `cols:` span without `rows:` fills the content band top to bottom. The 12 rows divide **that band**, not the canvas: a row never reaches above where the body starts or below the bottom margin.

The compiler rejects a spec whose placements collide. Two placements that share a column, or one that falls outside the content band, is an error naming both — so a slide either lays out cleanly or fails, never overprints. `bleed: true` exempts a placement from those checks; that is how a full-canvas image is expressed. (A declared `bleed:` carries into QA too: it exempts those shapes from the `bounds` check, because leaving the canvas is the instruction. `reserved` still measures them unless the geometry is genuinely full-bleed — at the origin and at least slide-sized. See [`qa.md`](qa.md).)

A theme's `reserve:` regions are handled differently, because a brand logo corner would otherwise make `cols: full` an error on every slide. A `cols:`/`rows:` placement that reaches into a reserved region is **narrowed** to clear it, keeping a gutter's clearance — so a full-height placement gives up the columns the region reaches into, while one bounded by `rows:` above the region keeps the full width. A `box:` is never narrowed; you stated the geometry outright, so hitting a reserved region is an error naming the region.

---

## Components

**The component's name is the key** inside a `place:` entry. There is no `body:` wrapper
and no `type:` field.

Pick one from this table and read its section in
[`docs/components.md`](components.md) — the fields, the defaults and a worked example
are all there. `chart` is the exception: its block is a wire format rather than a field
list, so it stays on this page.

| Component | What it draws |
|---|---|
| [`bullets`](components.md#bullets--a-column-of-bulleted-lines) | A column of bulleted lines, optionally split across columns. |
| [`callouts`](components.md#callouts--a-mark-beside-a-heading-and-a-line-of-copy) | Rows of a heading and a line of copy, each beside a dot or an icon. |
| [`stats`](components.md#stats--a-row-of-big-number-tiles) | A row of big-number tiles, up to four across. |
| [`table`](components.md#table--a-real-editable-powerpoint-table) | A real, editable PowerPoint table: spans, banding, rules, per-column alignment. |
| [`panel`](components.md#panel--a-filled-block-behind-other-content) | A filled colour block. It carries no text; a chrome line supplies that. |
| [`code`](components.md#code--a-monospace-listing) | A listing on a themed plate — real text, no browser. |
| [`prose`](components.md#prose--paragraphs-at-a-readable-measure) | Paragraphs at a capped, readable measure; `cite:` makes them a quotation. |
| [`swatches`](components.md#swatches--the-themes-own-palette) | A chip per palette role, labelled with the hex it resolved to. |
| [`grid`](components.md#grid--the-themes-own-geometry) | The theme's columns, and any region a placement must avoid. |
| [`ellipse`](components.md#ellipse--a-disc-a-badge-a-dot-a-step-number) | A disc — a badge, a dot, a step number — with an optional label in it. |
| [`card`](components.md#card--a-rounded-plate-with-a-heading-a-line-of-copy-and-an-icon) | A rounded plate carrying a heading, a line of copy and an icon. |
| [`flow`](components.md#flow--a-run-of-steps-joined-in-order) | A run of steps as plates on a rail, numbered and joined in order. |
| [`connector`](components.md#connector--a-line-joining-two-placements) | A line between two placements, attached by their `id:`. |
| [`rule`](components.md#rule--a-divider) | A divider, horizontal or vertical. |
| [`nav`](components.md#nav--the-decks-sections-with-the-one-you-are-in-marked) | The deck's sections in a band, with the one you are in marked. |
| [`icon`](components.md#icon--a-vector-mark) | A vector mark, drawn as real geometry rather than a pasted picture. |
| [`image`](components.md#image--a-photograph-and-any-text-reversed-out-of-it) | A photograph, and any text reversed out of it over a measured scrim. |
| [`document`](components.md#document--a-real-markdown-file-rendered) | A real markdown file, rendered into a window card. |
| [`fanout`](components.md#fanout--one-call-and-the-work-it-sets-off) | One call, and one branch per consequence. |
| [`versus`](components.md#versus--two-magnitudes-either-side-of-a-glyph) | Two magnitudes either side of a glyph. |
| [`diverge`](components.md#diverge--signed-bars-either-side-of-a-centre-rule) | Signed bars either side of a centre rule. |
| [`chart`](components.md#chart--a-real-editable-powerpoint-chart) | A native OOXML chart. Its block is [documented below](#the-chart-block). |

A placement carries exactly one of them. When none of them fits, register your
own — [Adding a component the spec cannot express](#adding-a-component-the-spec-cannot-express).
The mistakes that section does not cover, and the checklist for promoting a
deck-local component into the library, are [`docs/extending.md`](extending.md).

---

## The chart block

### The block's own fields

| Field | Required | What it does |
|---|---|---|
| `kind` | **yes** | Which chart to draw. One of the [29 kinds](#all-29-chart-kinds). |
| `data` | **yes** | The datapoints, one row per point. Non-empty list. |
| `unit` | no | A unit on every data label — `%`, `k`, `pt`. A currency sign (`$`, `£`, `€`, `¥`, `₹`) is written *before* the number, everything else after. **Category-shaped kinds only**; an XY or bubble row has no single unit to carry, and one written there is accepted and does nothing. Written into the number format as a literal, so `36` reads `36%` without Excel's `%` code multiplying it by a hundred. The **value axis takes the same format**, so the scale and the values it frames agree. Ignored on the `*-stacked-100` kinds, whose axis is already a percentage. |
| `decimals` | no | How many decimal places the data labels print, 0 to 6. Omit it and the places are read off the data — a series of `11.2, 9.6` labels to one place, whole numbers to none — so this is only for overriding that: `0` rounds a noisy series to whole numbers, a larger number pads to a fixed width. |
| `labels` | no | Which named series print their data labels — a mapping of series name to `true` or `false`. Reach for it when a flat reference series would otherwise stamp the same number over every point: `labels: {Platform average: false}` keeps the line, its colour and its legend entry, and drops only its labels. Every series prints them by default and `true` is that default written out, so this key only ever takes labels away. It needs named series, which means `values:` rows — the `value:` shorthand and the xy/bubble kinds have one unnamed series and refuse it. |
| `y_min` / `y_max` | no | Pin the value axis. Set them to stop auto-scaling from making a 12-point move look like a 90-point one. |

```yaml
chart:
  kind: bar
  unit: "%"          # labels and the value axis read 36%, 64% — not 3600%
  data:
    - {category: Urban, value: 36}
    - {category: Rural, value: 64, highlight: true}
```

A flat reference series repeats one number at every point, which says nothing after the
first. `labels:` drops that series' labels and keeps everything else about it:

```yaml
chart:
  kind: line-markers
  unit: "%"
  labels: {Platform average: false}   # the reference line keeps its line, drops its labels
  data:
    - {category: Jan, values: {Your store: 11.2, Platform average: 7}}
    - {category: Feb, values: {Your store: 9.6, Platform average: 7}}
```

No other field is accepted. There is no `colour`, no `legend`, no `title` inside the chart block — the slide's own `title:` is what names the chart, the legend appears by itself once there are two series, and colour is the theme's business.

### `data:` — one row per datapoint

**Every datapoint is one row.** A row carries its own label, its own numbers, and its own settings. Nothing is positional; nothing needs counting.

Three row shapes exist, chosen by the `kind:`.

#### Category rows — 22 of the 29 kinds

```yaml
chart:
  kind: column
  data:
    - {category: Q1, value: 12}
    - {category: Q2, value: 34}
    - {category: Q3, value: 58}
    - {category: Q4, value: 91, highlight: true}
```

| Row property | Required | What it does |
|---|---|---|
| `category` | **yes** | The x-axis label, or the wedge name on a pie. |
| `value` | one of the two | A single number, for a one-series chart. |
| `values` | one of the two | A mapping of series name to number, for a multi-series chart. |
| `highlight` | no | `true` marks this datapoint. On a **single series** every other point goes muted and the marked one keeps the accent — emphasis by isolation, so a second hue never reads as a second category. On a multi-series or line chart the marked point takes the second accent instead. `true` or `false` only — not a number. |

**`value:` is the single-series shorthand.** Use it when there is only one number per category:

```yaml
data:
  - {category: Q1, value: 12}
  - {category: Q4, value: 91}
```

**`values:` names each series.** The series names, and their order, come from the **first row's** `values` keys. Every row after it must carry exactly that same set — no more, no fewer:

```yaml
data:
  - {category: Q1, values: {Ads: 20, Organic: 15}}   # ← defines the series
  - {category: Q2, values: {Ads: 28, Organic: 22}}
```

Mixing `value:` and `values:` within one chart is an error. Pick one for the whole chart.

A legend appears automatically when there is more than one series, and not before.

#### XY rows — the 5 `xy-scatter*` kinds

No categories. The row carries its own coordinates:

```yaml
chart:
  kind: xy-scatter
  data:
    - {x: 1.2, y: 4.5}
    - {x: 2.4, y: 8.1}
    - {x: 4.8, y: 15.2}
```

| Row property | Required | What it does |
|---|---|---|
| `x` | **yes** | Horizontal position. |
| `y` | **yes** | Vertical position. |
| `highlight` | no | Accepted, but see the note below — it does not show on these kinds. |

`category` on an xy row is an error, and so is `x`/`y` on a category row. The message names both the row and the kind.

#### Bubble rows — the 2 `bubble*` kinds

Same as xy, plus a third number:

```yaml
chart:
  kind: bubble
  data:
    - {x: 1.2, y: 4.5, size: 30}
    - {x: 2.4, y: 8.1, size: 55}
    - {x: 3.9, y: 12.0, size: 18, highlight: true}
```

| Row property | Required | What it does |
|---|---|---|
| `x` | **yes** | Horizontal position. |
| `y` | **yes** | Vertical position. |
| `size` | **yes** | The bubble's area. Must be greater than zero. |
| `highlight` | no | `true` paints this bubble in the theme's **second accent**. |

### `highlight:` — where it shows and where it doesn't

`highlight: true` recolours one datapoint in the theme's **second accent** (the only accent, where a theme declares one). **At most one row per chart may set it**; two is an error naming both rows.

It only shows on kinds whose datapoint is a filled shape:

- **Visible:** the six bar/column kinds, the four pie/doughnut kinds, and both bubble kinds.
- **Refused:** every `line*`, `radar*`, `xy-scatter*` and `area*` kind. On those, a datapoint is drawn as a stroke, a marker, or one continuous band — there is no per-point shape to recolour, so the build fails rather than accepting a setting it cannot honour. The message lists the kinds that can.

To draw attention on a line or area chart, use the slide's title and `animate:` instead.

---

## All 29 chart kinds

Twenty-two take category rows; five take xy rows; two take bubble rows.

### Category rows

| `kind:` | Reach for it when |
|---|---|
| `column` | The default. One value per category, compared side by side. |
| `bar` | Same as `column`, horizontal — use it when the category names are long. |
| `column-stacked` | Parts of a total per category, in absolute numbers. |
| `column-stacked-100` | Parts of a total per category, as percentages of each column. |
| `bar-stacked` | Horizontal parts of a total. |
| `bar-stacked-100` | Horizontal parts of a total, as percentages. |
| `line` | A trend across an ordered axis, where the shape matters more than each point. |
| `line-markers` | The same trend, with a dot on each point so individual values read. |
| `line-stacked` | Cumulative lines. Rarely the clearest choice — prefer `area-stacked`. |
| `line-stacked-100` | Cumulative lines as percentages of each category. |
| `line-markers-stacked` | Cumulative lines with a dot per point. |
| `line-markers-stacked-100` | Cumulative percentage lines with a dot per point. |
| `area` | A trend where the magnitude under the line is part of the point. |
| `area-stacked` | How a total splits between parts, over time. |
| `area-stacked-100` | The same split as a share of 100% at every step. |
| `radar` | Several dimensions of one profile at once, drawn as an outline. |
| `radar-filled` | The same profile filled in. Good for one series, muddy for several. |
| `radar-markers` | The outline with a dot at each dimension. |
| `pie` | Shares of a single whole. Keep to four or five wedges. |
| `doughnut` | The same shares with a hole in the middle; reads a little lighter. |
| `pie-exploded` | Wedges pulled apart from each other. |
| `doughnut-exploded` | The same, with a hole. |

Pie, doughnut and their exploded variants have no axes, and label each wedge with its category name instead of relying on a legend.

### XY rows

| `kind:` | Reach for it when |
|---|---|
| `xy-scatter` | Correlation between two numbers. Points only, no connecting line. |
| `xy-scatter-lines` | The points joined in row order by straight segments. |
| `xy-scatter-lines-no-markers` | The joined path alone, without its points. |
| `xy-scatter-smooth` | The points joined by a curve. |
| `xy-scatter-smooth-no-markers` | The curve alone, without its points. |

Scatter kinds carry no data labels — the numbers do not print beside the points. Use `bubble` if you need labelled points.

### Bubble rows

| `kind:` | Reach for it when |
|---|---|
| `bubble` | Three numbers per point: two positions and a magnitude. |
| `bubble-3d` | The same, drawn as a shaded sphere. |

---

## animate

`animate:` is a slide field, not a component field. It controls how the slide's placements arrive on click.

| Value | What happens |
|---|---|
| `none` | Nothing animates. Same as leaving `animate:` out. |
| `together` | One click reveals the whole component at once. |
| `one_at_a_time` | One click per group: one bullet (or one column, when a list has several), one callout row, one stat tile. |
| `by_category` | **Charts only.** The chart builds one category at a time — Q1, then Q2, then Q3. |
| `by_series` | **Charts only.** The chart builds one series at a time — all of Ads, then all of Organic. |

```yaml
section: Spec
title: Adoption climbs every quarter
animate: by_category
place:
  - at: {cols: full}
    chart:
      kind: column
      data:
        - {category: Q1, value: 12}
        - {category: Q4, value: 91, highlight: true}
```

What counts as a group for `one_at_a_time`:

| Component | One click reveals |
|---|---|
| `bullets` | One bullet in a single-column list, one column in a list with several; the heading rides with the first. |
| `callouts` | One row — its dot and its text together. |
| `stats` | One tile; the caption rides with the last tile. |
| `document` | The whole card — it is a single group. |
| `chart` | The whole chart — it is a single group. |

`by_category` and `by_series` on anything other than a chart is an error. Any value outside these five is an error listing all five. With several placements on a slide, `one_at_a_time` clicks through all of their groups in placement order.

A slide's chrome never animates — the title and subtitle are on screen when the slide arrives, whatever `animate:` says. That is what lets a claim land a beat before its evidence.

A slide carries **one** animation timeline. Two charts on one slide both asked to build is an error naming the collision — give one a slide of its own, or drop it to `together`.

How a beat *looks* is the theme's, not the spec's: `motion.stagger_ms` cascades whatever a single click reveals — the whole slide under `together`, one group's parts under `one_at_a_time`. See [`theme.md`](theme.md#motion).

The old `reveal:` field is gone. `reveal: per-item` is now `animate: one_at_a_time`; `per-category`/`per-series` are `by_category`/`by_series`; `all`/`none` are `together`/`none`.

> LibreOffice renders the *final* state of a slide, so `bin/run render` shows every animated shape as visible. It cannot show a build mid-reveal. Only real PowerPoint confirms an animation opens without a repair prompt.

Every value above is confirmed at playback in real PowerPoint. **Keynote is the exception: it does not play `by_category`/`by_series`** — the chart arrives whole. For a Keynote audience use `together`, or split the categories across slides.

---

## transition

`transition:` is a slide field with exactly one legal value: `none`.

```yaml
title: A new act begins
transition: none      # arrive on a hard cut, refusing the theme's transition
```

**A transition belongs to the slide it arrives at** — it describes how the show moves
*to* this slide from the one before it, not away from it. Reading it the other way puts
every transition in a deck one slide out.

Which transition a deck uses is the theme's (`motion.transition` in
[`theme.md`](theme.md#the-decks-transition)), for the same reason a deck never sets a
colour: every deck on the brand should move the same way. A slide naming any other
value is an error pointing at the theme.

Leave it out and the slide takes whatever the theme says — which, for a theme with no
`motion.transition`, is no transition at all.

> A still render cannot show a transition: `bin/run render` produces identical images
> with and without one, and `deckwright qa` never sees it. Only presentation mode does.

---

## reveals

`reveals:` is a **placement** field. It keeps that placement hidden until the placement
it names is clicked.

```yaml
place:
  - at: {cols: left-half}
    id: question
    card: {heading: What broke?}
  - at: {cols: right-half}
    reveals: question      # hidden until the card above is clicked
    card: {heading: The cache key never invalidated}
```

The trigger needs an `id:`; `reveals:` names it. Unlike `animate:`, this spends **no
slide advance** — you click the trigger itself, in any order, and the slide never moves
on. Every shape that placement drew is a trigger, so a card's icon and its words work as
well as its plate; there is no margin you have to hit. Good for a question you want to
sit with before the answer lands.

A slide carries one animation timeline, so `reveals:` and `animate:` cannot share one —
asking for both is an error naming the collision. Naming an id no placement on the slide
carries, or naming itself, is likewise an error listing the ids that do exist.

> Like every build, this is invisible to `bin/run render` — the shape is drawn in its
> final state. Only presentation mode shows it held back.

---

## What lives in the theme, not the spec

**A deck author never sets a colour.** Not on a slide, not on a chart, not on a tile. There is no field for it, and adding one would be rejected as an unknown field.

Every aesthetic decision lives in the theme file — `templates/<name>.theme.yaml`:

| In the theme | Covers |
|---|---|
| `bind` | Semantic colour roles — `page`, `ink`, `muted`, `line`, `surface`, `inverse`, `accent-1`…`accent-N` — mapped onto slots in the brand template's own palette. Every unbound role keeps the design system's default, so a theme with no `bind:` still renders correctly. An accent bound to a slot that still holds Microsoft's shipped value is ignored. |
| `type` | `face` (body) and `heading_face` (display), the mono face, and the size/bold/italic of every rung of the type ramp — `kicker`, `caption`, `body`, `lead`, `head`, `stat`, `subtitle`, `title`, `display`, `hero`. A rung states a **point size** at the theme's `reference_height` — `pt: 13.5` is 13.5pt on a 7.5in-tall slide and 27pt on a 15in one, so one theme reads correctly at any slide size. A ramp rung may name its own face by role — `face: heading`, `face: body`, `face: mono` — or a literal typeface. Both faces fall back to the template's `fontScheme`, which is often stale — a template routinely declares one face while its slides use another — so a theme states them outright. |
| `scale` | Page margins, the column grid, the gutter, and where the body starts below the title — all as fractions of the canvas. `left`, `right` and `gutter` are fractions of width; `top`, `bottom` and `body_top` fractions of height. The canvas itself comes from the template. |
| `marks` | Art laid over a painted background. A mark's name *is* the background it decorates, so `marks.inverse` is the only one there is — any other name is rejected at load rather than silently ignored. Mark media is resolved beside the brand template or out of it, so `marks:` needs a `template:`. |
| `compose_layout` | Names the template layout generated slides are built on. Optional — the compiler picks the emptiest layout across every master, and this is only needed when two equally empty layouts would compose differently, which it reports rather than guessing. |
| `reserve` | Regions content must avoid, as polygons in fractions of the canvas. The compiler narrows the content band for a region that spans it edge to edge, and rejects any placement that hits the rest. A region applies to every slide — there is no layout to scope one to, so `applies_to:` is rejected at load. Each entry is a mapping with a `name:` and a `poly:` list of `[x, y]` pairs; a malformed entry or point is rejected at load, naming the region and showing the value. |
| `chart` | Gradients, drop shadows, bar gap width, marker size and shape, gridlines, data-label position, thousands separators. |
| `motion` | How a reveal is paced — `stagger_ms` cascades what arrives on a single click. The spec says how many beats an argument has; the theme says what a beat looks like. |

**Why:** the spec says *what the slide is about*; the theme says *what the brand looks like*. Retheming a deck is then one line — change `theme:` — instead of a search-and-replace through every slide. It also means a deck cannot drift off-brand one hardcoded hex at a time.

If a colour or size is wrong, fix the theme, not the deck. The brand template a theme points at is gitignored at `templates/` — never commit it.

---

## Adding a component the spec cannot express

When no built-in component fits, register your own in a Python module and point the deck document at it with `extends:`. The module is imported before the spec's placements are validated, so its `@component` registrations are live by the time a placement names one.

1. Write the module beside your spec:

```python
# my_components.py
from deckwright.layouts.components import component
from deckwright.layouts.registry import SlideCtx
from deckwright.utils.shapes import para, textbox


@component("banner")
def banner(ctx: SlideCtx):
    rect = ctx.body_rect
    text = str(ctx.body["text"])
    style = ctx.style("head")
    tf = textbox(ctx.slide, rect.left, rect.top, rect.width, 1.0)
    para(tf, text, style.size, ctx.fg(), first=True)
    ctx.manifest.record(tf._parent, lines=[text], font_pt=style.size,
                        fg=ctx.pair.fg, bg=ctx.pair.bg)
    return []
```

2. Point the deck document at it, and place it by name:

```yaml
theme: base
extends: my_components.py
out: ../out/deck/Deck v1.pptx
---
title: A bespoke body
place:
  - at: {cols: full}
    banner: {text: Anything the spec cannot say}
```

Rules for a custom component:

- Take exactly one argument, `ctx: SlideCtx`, and draw onto `ctx.slide`.
- Read its own fields from `ctx.body` — the mapping under its key in the placement.
- Read every colour and size from the theme — `ctx.fg()`, `ctx.dim()`, `ctx.style("head")` — never a literal hex or point size. The same rule that applies to a spec applies here.
- For accent *text*, use `ctx.accent(size_pt=...)` (hex, drawable via `ctx.rgb(...)`), not `ctx.color("accent-1")`: it keeps the accent only where it measurably reads at that size and falls back to the ink that does. If your component painted the fill the text sits on — a tile, a badge — measure against that fill with `ctx.accent_on(fill, size_pt=...)` / `ctx.ink_on(fill)`, not against the slide. `ctx.color(role)` is the unguarded read, for fills and strokes.
- Pass `ctx.text_align()` to `para(align=...)` and `ctx.text_anchor()` to `textbox(anchor=...)` so the placement's `align:`/`anchor:` reach the type. A component that draws no type of its own calls `require_default_align(ctx)` instead, so those keys fail loudly rather than being ignored.
- Draw inside `ctx.body_rect` — the rectangle its own placement resolved to, already clear of the theme's reserved regions.
- **Record every shape you draw** with `ctx.manifest.record(shape, lines=..., font_pt=..., fg=..., bg=...)`. Nothing else records it. An unrecorded shape is absent from the build manifest, and `deckwright qa` reads only the manifest — so bounds, reserved regions, minimum font size, contrast and render overflow all measure nothing for it and report clean. This fails silently: the slide looks right and QA agrees, which is the worst combination.
- Return the reveal groups: a list of lists of shape ids, one inner list per revealable unit. Return `[]` for a component that does not animate.

For the wider component API — `BodyResult`, reported heights, panels — see [`docs/pptx-deck-building.md`](pptx-deck-building.md).
