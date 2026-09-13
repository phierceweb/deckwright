# Components — the field table and a worked example for each

The reference for every component a placement can carry. **The component's name
is the key** inside a `place:` entry — there is no `body:` wrapper and no `type:` field.

Arrive here from the component index in [`docs/authoring.md`](authoring.md#components),
which owns everything around these: the two-document structure, slide fields, `place:`
and `at:`, and the chart block. Error messages are in [`docs/errors.md`](errors.md).
Registering a component of your own is
[Adding a component the spec cannot express](authoring.md#adding-a-component-the-spec-cannot-express).

**Every field table below is exhaustive.** A component refuses any key it does not
read, naming the ones it does — so a misspelled `colums:` fails the build rather than
rendering one column and saying nothing.

---

## Table of Contents

- [`bullets` — a column of bulleted lines](#bullets--a-column-of-bulleted-lines)
- [`callouts` — a mark beside a heading and a line of copy](#callouts--a-mark-beside-a-heading-and-a-line-of-copy)
- [`stats` — a row of big-number tiles](#stats--a-row-of-big-number-tiles)
- [`table` — a real, editable PowerPoint table](#table--a-real-editable-powerpoint-table)
- [`panel` — a filled block behind other content](#panel--a-filled-block-behind-other-content)
- [`ellipse` — a disc: a badge, a dot, a step number](#ellipse--a-disc-a-badge-a-dot-a-step-number)
- [`card` — a rounded plate with a heading, a line of copy and an icon](#card--a-rounded-plate-with-a-heading-a-line-of-copy-and-an-icon)
- [`flow` — a run of steps, joined in order](#flow--a-run-of-steps-joined-in-order)
- [`connector` — a line joining two placements](#connector--a-line-joining-two-placements)
- [`rule` — a divider](#rule--a-divider)
- [`nav` — the deck's sections, with the one you are in marked](#nav--the-decks-sections-with-the-one-you-are-in-marked)
- [`icon` — a vector mark](#icon--a-vector-mark)
- [`image` — a photograph, and any text reversed out of it](#image--a-photograph-and-any-text-reversed-out-of-it)
- [`document` — a real markdown file, rendered](#document--a-real-markdown-file-rendered)
- [`fanout` — one call and the work it sets off](#fanout--one-call-and-the-work-it-sets-off)
- [`versus` — two magnitudes either side of a glyph](#versus--two-magnitudes-either-side-of-a-glyph)
- [`diverge` — signed bars either side of a centre rule](#diverge--signed-bars-either-side-of-a-centre-rule)
- [`chart` — a real, editable PowerPoint chart](#chart--a-real-editable-powerpoint-chart)

Every field table reads the same way: a field marked **yes** under *Required* has no
default and its absence is an error; everything else may be left out, and the *Default*
column is what you get when you do.

---

### `bullets` — a column of bulleted lines

| Field | Required | Default | What it does |
|---|---|---|---|
| `items` | **yes** | — | The bullet strings. Non-empty list. |
| `columns` | no | `1` | Split the items across this many columns, filling left to right. Capped at the number of items. |
| `heading` | no | — | A small orange heading above the first column. |

```yaml
section: Spec
title: What ships today
subtitle: One vocabulary, every component
animate: one_at_a_time
place:
  - at: {cols: full}
    bullets:
      heading: Components
      columns: 2
      items:
        - Bulleted columns
        - Dot-and-text callouts
        - Big-number stat tiles
        - Rendered markdown documents
        - Native OOXML charts
        - Chrome-only slides
```

One reveal group per bullet when the list is one column, so `one_at_a_time` stages it a line per click; one group per column when it has several. The heading arrives with the first bullet.

### `callouts` — a mark beside a heading and a line of copy

| Field | Required | Default | What it does |
|---|---|---|---|
| `items` | **yes** | — | Non-empty list of mappings. |
| `heading` | no | — | A label above the rows, in the `head` rung — the same band `bullets` reserves, so the two line up in a `split:`. |
| `items[].head` | **yes** | — | The bold heading for that row. |
| `items[].body` | no | — | One line of supporting copy under it. |
| `items[].icon` | no | — | A glyph name, drawn in place of the accent dot. A list may mix marked and unmarked rows; the text indents to clear whichever mark it sits beside. |

```yaml
section: Spec
title: Why the format changed
animate: together
place:
  - at: {cols: full}
    callouts:
      items:
        - {head: One row per datapoint, body: A row carries its own label and its own numbers.}
        - {head: Nothing positional, body: "No index to count, no parallel arrays to zip."}
        - {head: One word for one thing, body: "A chart has a kind; a placement names its component."}
        - {head: Strict by default, body: "An unknown field is an error, never a silent drop."}
```

The mark and its text reveal together, so a click-build never leaves a dot on screen with nothing beside it.

One reveal group per row. Keep to about six rows — past that the rows are thinner than the type needs and the build fails saying so.

### `stats` — a row of big-number tiles

| Field | Required | Default | What it does |
|---|---|---|---|
| `items` | **yes** | — | Non-empty list of mappings. |
| `items[].value` | **yes** | — | The big number. Quote it — `"4"`, not `4`. |
| `items[].label` | no | — | Small caption inside the tile. |
| `items[].icon` | no | — | A glyph name, drawn above the number. Every tile in the row grows to fit it, so the row stays level. |
| `columns` | no | one per item | Tiles per row. **Hard maximum 4**; a larger number is silently reduced. |
| `caption` | no | — | An italic line under the tiles. |

```yaml
section: Spec
title: The shape of it
place:
  - at: {cols: full}
    stats:
      columns: 4
      caption: The spec says what goes where; the library owns every position.
      items:
        - {value: "21", label: components}
        - {value: "29", label: chart kinds}
        - {value: "10", label: type rungs}
        - {value: "0", label: colours in the spec}
```

One reveal group per tile; the caption joins the last tile's group.

### `table` — a real, editable PowerPoint table

A native OOXML table: selectable text, editable in PowerPoint, and every cell recorded
in the manifest so QA's contrast, minimum-size and overflow checks measure the cells
rather than one grey rectangle.

| Field | Required | Default | What it does |
|---|---|---|---|
| `rows` | **yes** | — | Non-empty list of rows; each row a non-empty list of cells. Quote numbers — `"12"`, not `12`. |
| `header` | no | — | A list of column labels, set bold on its own band above the rows. Fixes the column count. |
| `total` | no | — | A final row set bold and ruled *above* itself at twice the weight — the summary line under a column of figures. |
| `align` | no | the placement's `align` | One of `left`/`center`/`right` **per column** — so a price column can be right-aligned while its labels are not. |
| `valign` | no | `middle` | `top`, `middle` or `bottom` for every cell in the table. Reach for `top` when one column carries prose and the rest carry labels. |
| `widths` | no | an even split | Relative column widths. `[3, 2, 2, 1]` and `[0.375, 0.25, 0.25, 0.125]` give the same table. |
| `head_pair` | no | `surface` | The palette pair the header band is painted in; its ink is that pair's foreground. |
| `body_pair` | no | — | A pair for the body cells. Left out, they are unfilled and the slide's own surface shows through — which is what makes one declaration read on `page` and on `inverse`. |
| `banding` | no | `false` | Fill every other body row. The alternate colour is the body's own surface nudged away from its ink, so it works on a light table and a dark one. |
| `rules` | no | `rows` | What the hairlines mark — see the table below. |
| `color` | no | `line` | A palette **role** for the rules. |
| `weight` | no | `1.0` | Rule weight as a multiple of the theme's line weight. A hairline is about `0.3`. |
| `density` | no | `1.0` | Multiplies the padding inside every cell. `0.6` is dense, `1.4` airy. It is a multiplier and not a measurement because nothing else in a spec is one. |

**A cell is a string, or a mapping when a string cannot say enough.** Any cell in
`rows:`, `header:` or `total:` may be written as a mapping instead:

| Cell key | Default | What it does |
|---|---|---|
| `text` | `""` | The words. A cell written as a plain string is exactly this; an omitted or null `text` is an empty cell. |
| `across` | `1` | How many columns the cell covers, itself included. The columns it swallows are merged in the file, and their padding becomes measure — a spanned cell wraps later than its first column would. |
| `down` | `1` | How many rows the cell covers, itself included. The rows beneath it are written with only the columns left to them. |
| `align` | its column's | Overrides `align` for this cell alone, which is how a `Total` label sits left in a right-aligned column. |
| `valign` | the table's | Overrides `valign` for this cell alone — a `down:` label centred against top-set body cells. |
| `emphasis` | `false` | Set in the heading weight. A header or total row is already emphasised. |
| `pair` | the row's | A palette pair painted behind this cell alone — the recommendation in a comparison, the outlier in a column. |

```yaml
table:
  header: [Workstream, {text: Effort, across: 2, align: center}, Owner]
  align:  [left, right, right, left]
  widths: [3, 1, 1, 1.4]
  banding: true
  rows:
    - [Spec and schema, "12", "8", Compiler]
    - [Placement engine, "21", "14", Layout]
  total: [{text: Total, emphasis: true}, "33", "22", ""]
```

**`rules:` names what the lines mark**, in the colour a `rule` would take on this slide —
so the theme's `line` grey gives way to `muted` on a white page rather than disappearing
into it.

| `rules` | Draws |
|---|---|
| `rows` | A hairline under every row but the last. The default, and what a table of figures wants. |
| `header` | One line, under the header band — plus a `total:`'s own rule above itself, which every mode but `none` keeps. The editorial look: the body rows are parted by their spacing. |
| `grid` | The row lines, plus one down the right of every column but the last. |
| `none` | Nothing at all — including above a `total:`, which is still marked by its weight. Pair it with `banding: true`, or the rows have nothing separating them. |

**A cell can reach down as well as across.** A row beneath a `down:` cell is written
with only the columns left to it, because the one above is already spoken for:

```yaml
table:
  rules: grid
  valign: top
  header: [Stage, Step, Owner]
  rows:
    - [{text: Discovery, down: 2, valign: middle, emphasis: true}, Interviews, Ana]
    - [A brief either side can argue with, Ana]
    - [{text: Build, down: 2, valign: middle, emphasis: true}, The first slice, Bo]
    - [Everything the first slice deferred, Bo]
```

A reaching cell is merged in the file, so it is one cell in PowerPoint too. Its rule
falls where its span *ends*, and the row boundaries it crosses stay unruled in its own
column alone — which is what parting a merged label from the rows beside it looks like.

Reaches stack: two columns may reach down past a third that does not, and the row below
is written with the one column left to it.

```yaml
table:
  header: [Phase, Detail, Who]
  rows:
    - [{text: Discovery, down: 2}, {text: "Interviews, then a brief", down: 2}, Ana]
    - [Bea]
```

**A row cannot be covered from above in every column.** Such a row has no cells of its
own, so it is height and nothing else — and the table you meant is the same table with
neither that row nor the `down:` that reached into it. It is refused rather than drawn,
which is also what keeps the deck renderable: a row that is entirely a vertical merge is
legal OOXML that LibreOffice imports wrongly, dropping the table's last row.

**Where banding's colour comes from.** With no `body_pair` it is the `surface` pair,
which exists for this — a plate distinct from the page, contrast-checked when the theme
loaded. With one, it is that pair's own colour shifted slightly toward its ink, keeping
the ink the pair was validated with. It is never derived from what the slide happens to
show: nudging a sampled photograph puts a mid-grey under the type.

```yaml
title: What is on the menu
place:
  - at: {cols: full, rows: {from: 0, to: 7}}
    table:
      header: [Dish, Category, Served, Price]
      align: [left, left, center, right]
      widths: [3, 2, 2, 1]
      density: 0.7
      rows:
        - [Bruschetta al pomodoro, Starter, All day, $8]
        - [Tagliatelle al ragu, Main, From 6pm, $18]
        - [Branzino al forno, Main, From 6pm, $26]
        - [Tiramisu, Dessert, All day, $9]
```

A table is rectangular: every row has to account for every column exactly once — its own
cells, their `across:` spans, and any column a `down:` cell above already covers. The
error names the row by its position in your own `rows:` list. The column count comes from
`header:` when there is one, otherwise from the first body row; neither can inherit a
column, so both are a plain count.

Row heights come from the same wrap estimate every component uses, and the estimate
over-reserves rather than risk clipping — a cell that lands on a wrap boundary can get a
row one line taller than its text renders. The slack lands at the bottom of a top-anchored
cell, where it reads as a stray blank line; `valign: middle` distributes it evenly and the
rhythm evens out.

A row holding an unquoted comma is read by YAML as a nested list, not a cell — the error
says so, because it is the commonest way a table fails to parse.

**A row is as deep as the wrap estimate says**, and the estimate measures the cells in
the face they will render in — real per-character advances for the theme's typeface,
plus a small safety margin, with a conservative ceiling table standing in for a face
the library has no metrics for. A table row grows rather than clips, and the margin
is a few percent of width, so a row very rarely reserves a line the render does not
use.

A `down:` cell is measured against the rows it covers together, and any shortfall is
shared between them rather than charged to the first. That even share is not the
*shallowest* answer when two spans overlap a row — each grows it toward its own need —
so when the even split overruns the placement, a tight packing that satisfies every cell
is used instead. A table that fits is never refused for the sake of an even one; what
you lose in the fallback is the evenness, not the table.

The whole table is one reveal group.

### `code` — a monospace listing

Code, a config fragment, a schema — set in the theme's mono face on a plate of one of
its pairs. The other way to put a listing on a slide is `document:`, which renders
markdown through a headless browser and returns a picture; this draws **real text**, so
it is selectable in PowerPoint, recoloured by the theme, and present in the manifest as
lines `qa` can measure for overflow.

| Field | Required | Default | What it does |
|---|---|---|---|
| `lines` | one of the two | — | A list, one entry per line. Blank entries are blank lines. |
| `text` | one of the two | — | The same thing as a block scalar, for pasting a listing in whole. |
| `heading` | no | — | A label above the plate, set in the `head` rung, like `bullets`. |
| `pair` | no | `surface` | Any declared palette pair. The plate takes that pair's background, and the text the ink that reads on it. |
| `accent` | no | — | Line prefixes to emphasise. A line starting with one is drawn bold in the accent that reads on the plate. |
| `wrap` | no | `false` | Whether a long line wraps. Off by default — a wrapped listing lies about its own indentation. |
| `size` | no | the `caption` rung | Point size. Refused below the theme's minimum. |

```yaml
title: The spec, shown as itself
place:
  - at: {cols: {from: 0, to: 7}}
    code:
      heading: deck.yaml
      accent: ["theme:", "place:"]
      lines:
        - "theme: brand"
        - "---"
        - "place:"
        - "  - at: {cols: full}"
        - "    bullets: {items: [...]}"
```

### `swatches` — the theme's own palette

A chip per palette role, labelled with the role's name and the hex it resolved to. The
values are read from the live theme at build time, so a slide showing what
`deckwright conform` derived from a brand template cannot drift from the theme the deck
was actually built against.

A chip whose colour is close to the slide's own paper — `page`, `surface`, an
`inverse-ink` — is given the theme's rule colour as an edge, because a white chip on a
white page is not a chip.

| Field | Required | Default | What it does |
|---|---|---|---|
| `roles` | no | every role the theme declares | Which roles to show, in order. |
| `caption` | no | — | A note beneath the chips. |
| `columns` | no | as many as fit, to 8 | How many chips per row. |

```yaml
title: Every role, and the hex it resolved to
place:
  - at: {cols: full}
    swatches:
      roles: [ink, accent-1, accent-2, muted, line]
      caption: Read from the live theme at build time.
```

### `grid` — the theme's own geometry

The columns every `at:` resolves against, drawn as bars, with any region a placement
must stay out of laid over them. Both come from the live theme: the grid a deck is
measured on, and the polygons `conform` derives from a brand template's artwork.

A reserved region is drawn as its **real polygon**, not its bounding box — a corner
wedge is a triangle, and the usable space above its diagonal is exactly what a box
would wrongly appear to forbid.

| Field | Required | Default | What it does |
|---|---|---|---|
| `show` | no | `columns` | `columns`, `rows`, or `both`. |
| `reserve` | no | `true` | Whether to overlay the theme's reserved regions. |
| `caption` | no | the theme's own measurements | A note beneath. The default states the column count, width and gutter the theme actually holds. |

```yaml
title: A grid, and a polygon it has to respect
place:
  - at: {cols: full}
    grid: {}
```

### `panel` — a filled block behind other content

A colour field: a half-canvas band, an edge strip, or the plate a title is reversed
out of. It carries no text — a chrome line naming the same `pair:` supplies that,
and reads on it because the palette checked the two colours against each other when
the theme loaded.

| Field | Required | Default | What it does |
|---|---|---|---|
| `pair` | no | `surface` | Any declared palette pair. The block is painted in that pair's **background**. |
| `radius` | no | `0` | Corner rounding as a fraction of the block's short side. `0.5` is a stadium. |

```yaml
title: Reversed out of a panel
chrome:
  title: {at: {box: {x: 9%, y: 36%, w: 30%, h: 20%}}, pair: accent-3}
place:
  - at: {box: {x: 0%, y: 0%, w: 45%, h: 100%}}
    bleed: true
    panel: {pair: accent-3}
```

A fill too close to the slide's own paper to see — the default `surface` on a white
page — is given the theme's `line` colour as an edge, so the block reads on a light
background as well as a dark one.

### `ellipse` — a disc: a badge, a dot, a step number

The commonest non-text mark in the corpus. The diameter is the **short side of its
placement**, so the same declaration is a bullet dot in a one-column slot and a badge
in a half-canvas box.

| Field | Required | Default | What it does |
|---|---|---|---|
| `pair` | no | `accent-1` | Any declared palette pair. The disc is painted in that pair's **background**, and a label in its **foreground**. |
| `label` | no | — | Text centred in the disc. Refused, never clipped, when the disc cannot hold it. |
| `rung` | no | `caption` | The label's type-ramp role. |
| `size` | no | `1.0` | Diameter as a fraction of the placement's short side. |
| `shadow` | no | `false` | Drop the theme's declared shadow behind it. |

```yaml
place:
- at: {cols: {from: 0, to: 1}, rows: {from: 0, to: 2}}
  ellipse: {label: '1'}
- at: {cols: left-half, rows: mid-third}
  align: center
  anchor: middle
  ellipse: {label: '2', size: 0.5, rung: stat, shadow: true}
```

Unlike every other component, `align`/`anchor` move the **disc** inside its placement
rather than moving type: the shape is the content here, and a label is centred in it by
construction. A disc smaller than its placement therefore sits at the top-left corner
until you say otherwise.

### `card` — a rounded plate with a heading, a line of copy and an icon

132 rounded-rect cards across the corpus, and they are all this object. The plate is a
declared pair, so its type is contrast-checked against the plate's own fill, not
against the slide's — a white card on a dark slide still reads.

| Field | Required | Default | What it does |
|---|---|---|---|
| `heading` | one of the three | — | Set at the `head` rung. |
| `body` | one of the three | — | One or two lines at the `body` rung. |
| `icon` | one of the three | — | A glyph name (`shield`) or an image file (`logo.png`), placed at the top of the plate two heading line-heights square. A bare name is a glyph; anything with a suffix or a path separator is a file, resolved like any deck image. |
| `pair` | no | `surface` | Any declared palette pair. |
| `radius` | no | `0.06` | Corner rounding as a fraction of the plate's short side. `0` squares it, `0.5` is a stadium. |
| `shadow` | no | `false` | Drop the theme's declared shadow behind it. |

```yaml
place:
- at: {cols: left-third, rows: {from: 0, to: 5}}
  card:
    heading: Discover
    body: Read the corpus before naming the vocabulary.
    shadow: true
```

The type is inset from the plate by the theme's gutter on every side, and `align`/
`anchor` set it inside that area. The gutter is measured from the plate's painted
edge, not from its square corner, so a large `radius` insets the sides further: on a
stadium the corner curve has swept a long way in by the height the first line sits
at, and a fixed inset would leave the leading glyph outside the shape. A card with
none of the three content fields is refused, naming `panel` — an empty plate is that
component.

### `flow` — a run of steps, joined in order

Sixteen slides across six of the eleven sample templates lay a process out as a run of
steps. `flow` is that slide in one block: it divides the placement into a cell per step,
draws each as a `card`, puts a numbered `ellipse` on the rail beside it, and joins
consecutive marks with a `connector`. Nothing is hand-placed and no step repeats a
coordinate.

| Field | Required | Default | What it does |
|---|---|---|---|
| `items` | **yes** | — | The steps. At least two — one step is the `card` component. |
| `items[].head` | **yes** | — | The step's heading, at the `head` rung. |
| `items[].icon` | no | — | A glyph name, drawn above the step's heading. The plate grows to fit it. |
| `items[].body` | no | — | One line of supporting copy under it. |
| `direction` | no | `horizontal` | `horizontal` runs the steps across the placement, `vertical` down it. |
| `numbered` | no | `false` | Put a numbered disc on the rail: above each step across, left of it down. |
| `current` | no | — | The 1-based step to highlight. Its plate takes the accent. |
| `pair` | no | `surface` | The palette pair every other plate is painted in. |
| `arrow` | no | `end` | `none`, `end` or `both`, on each join. |

```yaml
place:
  - at: {cols: full, rows: top-two-thirds}
    flow:
      numbered: true
      current: 2
      items:
        - {head: Discover, body: Read the corpus first.}
        - {head: Define, body: Name the vocabulary.}
        - {head: Build, body: One primitive at a time.}
        - {head: Verify, body: Look at the render.}
```

Every plate is drawn as deep as the **wordiest** step needs at that width, never deeper —
a run whose plates each stopped at their own copy would read as a ragged edge rather than
a sequence. So the placement bounds the flow, it does not define it: a horizontal flow
sits at the top of its rectangle at the depth its copy earns, and only fills the whole
rectangle when the copy needs all of it.

The join attaches to the **discs** when the steps are numbered and to the plates when
they are not, so a numbered flow reads as a rail with plates hanging off it. Down the
page each plate floats in the middle of its cell, keeping the disc level with the copy.

`align` passes through to each step's type; `anchor` settles the whole run inside its placement, like any content-sized component. One reveal group per step, and
the join *into* a step belongs to that step — so `animate: one_at_a_time` builds the
process a step at a time, arrow and all.

### `connector` — a line joining two placements

The line attaches to the edge of each end that **faces** the other, so moving either
placement moves the join and nothing in the spec repeats a coordinate.

| Field | Required | Default | What it does |
|---|---|---|---|
| `from` | **yes** | — | A placement `id:`, or `[x, y]` as fractions of the canvas. |
| `to` | **yes** | — | The same. |
| `kind` | no | `straight` | `straight`, `elbow` or `curved`. One native connector either way — PowerPoint routes the bend. |
| `arrow` | no | `none` | `none`, `end` (the `to` end) or `both`. |
| `color` | no | `accent-1` | A palette **role**, not a pair. |
| `weight` | no | `1.0` | Stroke weight as a multiple of the theme's line weight. |

One reveal group, reported under the **`line`** motion role, the same as `rule`.

```yaml
place:
- at: {cols: {from: 0, to: 3}, rows: {from: 2, to: 6}}
  id: discover
  card: {heading: Discover, body: Read the corpus.}
- at: {cols: {from: 3, to: 4}, rows: {from: 2, to: 6}}
  connector: {from: discover, to: design, arrow: end}
- at: {cols: {from: 4, to: 7}, rows: {from: 2, to: 6}}
  id: design
  card: {heading: Design, body: Name the vocabulary.}
```

Two things follow from "it joins **placements**":

- A connector draws *between* rectangles, not inside its own, so its own `at:` still
  has to clear the placements it joins. The gap between two cards is the natural home,
  as above; a line that must cross either end declares `bleed: true` and takes a
  full-canvas `box:`.
- The join lands on the placement's edge, not on the shape drawn inside it. A disc at
  `size: 0.5` leaves a visible gap; give it a placement it fills and the join is exact.

An id no placement on the slide declares is an error listing the ids that exist. A
`from` and `to` that resolve to the same point is an error too — the line has no
direction to draw in.

### `prose` — paragraphs at a readable measure

Dense copy that is neither a list nor a chart: an argument, a letter, a quotation. The
frame is capped near the classic 66-character measure rather than the placement's full
width — a 16:9 band sets a line nobody can track back to its successor. A content-sized
component: give the placement `anchor: middle` to settle it, and `align:` to place the
capped frame inside a wider placement.

| Field | Required | Default | What it does |
|---|---|---|---|
| `paragraphs` | **yes** | — | A list of strings, one per paragraph. |
| `cite` | no | — | An attribution. Its presence sets the paragraphs as a quotation — italic, with `— cite` beneath in the caption style. |

```yaml
title: The case in two paragraphs
place:
  - at: {cols: full}
    anchor: middle
    prose:
      paragraphs:
      - The night network is not a luxury service.
      - Cutting it saves four percent and strands the late shift.
```

### `rule` — a divider

| Field | Required | Default | What it does |
|---|---|---|---|
| `orient` | no | `horizontal` | `horizontal` or `vertical`. |
| `color` | no | `line` | A palette **role**, not a pair. |
| `weight` | no | `1.0` | Stroke weight as a multiple of the theme's line weight. A hairline is about `0.3`. |

One reveal group, reported under the **`line`** motion role — so a rule draws itself
whichever way the theme binds that role (`wiperight` by default). See
[`motion.md`](motion.md#motion-roles).

```yaml
place:
- at: {cols: full, rows: {from: 0, to: 1}}
  rule: {color: accent-1, weight: 1.5}
- at: {cols: {from: 5, to: 6}, rows: {from: 1, to: 10}}
  align: center
  rule: {}
```

A rule spans its placement outright, so the key that would move it *along* that axis is
refused rather than ignored: a horizontal rule reads `anchor` (`top` | `middle` |
`bottom`) and refuses `align`, and a vertical one is the mirror image.

**How a stroke gets its colour.** A line has no pair to be checked against, so `rule`
and `connector` share one rule. A role you name is used as asked, and refused only when
it is invisible against this slide's paper — a brand's own hairline colour at 2.6:1 is a
design choice, not a mistake. The **default** has no author behind it, so it must clear
WCAG's 3:1 non-text minimum or give way to a role that does: the theme's `line` grey is
right on a dark slide and a ghost on a white one, where the rule takes `muted` instead.

### `nav` — the deck's sections, with the one you are in marked

| Field | Required | Default | What it does |
|---|---|---|---|
| `items` | no | the deck's `sections:` | The section names, left to right. Non-empty list. Leave it out and the nav follows the deck, so a rename or a reorder in `sections:` reaches every slide. |
| `active` | no | the slide's own `section:`, when it is one of `items` | Which of them this slide is in. A name given here must be one of `items`; a name that is not is an error, because a renamed section would otherwise read as no section. Labels shorter than the section names mark nothing unless `active:` names one. |
| `color` | no | the guarded accent | A palette **role** for the active label. |

A section eyebrow, for a deck long enough that a reader loses the thread but not long
enough to want a divider slide between every act. Set it in a one-row band as `nav: {}`
and repeat the placement: each slide marks the section it declares.

**No reveal group.** An eyebrow is chrome, and a slide that builds its body should not
spend its first click arriving at its own furniture — so the band is on screen from the
first beat whatever `animate:` says.

```yaml
place:
- at: {cols: full, rows: {from: 0, to: 1}}
  align: right
  nav:
    items: [Problem, Evidence, What shipped, Next]
    active: Evidence
```

**How the active label gets its colour.** The same rule `rule` and `connector` hold for a
stroke, one layer up: a role you name is used as asked and refused only when it cannot be
seen at all against this slide's paper. A brand accent that reads at 2.6:1 is a design
choice, and the active item is a rung larger and bold as well as coloured, so the mark
never rests on colour alone. The **default** has no author behind it, so it goes through
the guarded accent — which at caption size wants 4.5:1 and mostly will not get it, and
gives way to the slide's own ink. Name the role when you want the brand colour; leave it
out when you want the reader to be certain.

Naming a role under AA is honoured, and `qa`'s [`contrast`](qa.md) check will still
report the label — a WARN, not an error. That is the check doing its job: the ratio is
genuinely low, you decided it anyway, and the deck still builds.

### `icon` — a vector mark

The corpus's commonest non-text shape by a wide margin: 4,019 `custGeom` freeform
paths in the size range a glyph occupies, against eight charts and five tables across
128 slides. A card with a mark reads as designed; the same card without one reads as
typeset.

An icon is drawn as **real path geometry**, not as a pasted picture, so it stays sharp
at any size, recolours from the palette, and is editable in PowerPoint like any other
shape.

| Field | Required | Default | What it does |
|---|---|---|---|
| `name` | yes | — | Which glyph: a lowercase slug like `chart-bar`. Any Material Symbols name from the shipped set (`rocket_launch`, or the hyphenated `rocket-launch`), or a curated alias (`deploy`, `team`, `growth`). |
| `size` | no | `1.0` | The glyph's side as a fraction of the placement's short side — literally `min(width, height) * size`, so the drawn square is predictable from the rect the placement was given. `1.0` fills the short side; the long side keeps the leftover as margin. |
| `ink` | no | — | A colour role, painted verbatim. Omit and the mark takes the first brand accent that reads where it lands, falling back to the surface's ink — and, where no colour reads across the box at all, to a plate of the slide's paper behind the glyph (see [icons.md](icons.md#the-colour-a-glyph-is-painted)). That plate is padded around the glyph and clipped to the placement, so it never reaches the placement beside it. |

```yaml
place:
- at: {cols: {from: 0, to: 3}, rows: top-third}
  icon: {name: target}
- at: {cols: {from: 3, to: 6}, rows: top-third}
  icon: {name: chart-bar, ink: accent-2}
```

The placement is squared off before the glyph is drawn, so an icon in a wide slot
keeps its proportions rather than stretching. Where that square sits in the rect is the
placement's `align` and `anchor` — `left`/`top` by default, so add `align: center` to
centre it.

**Which name to reach for** is [`docs/glyphs.md`](glyphs.md), a shortlist grouped by
what the slide is about. 4,001 vendored Material Symbols resolve, plus the curated names
in [`docs/icons.md`](icons.md#the-set-that-ships). Asking for one nobody drew fails the
build with the closest real names.

**Where the glyphs come from**, in order: `$DECKWRIGHT_ICON_DIR`, the theme's own
`icons:` directory, then the shipped set. A brand overriding `target`
with its own drawing needs no change to any deck. Each file is an `.svg` with a
`viewBox` and one or more `<path>` elements — `<circle>`, `<rect>` and strokes are not
read, so flatten a drawing to paths before dropping it in.

**Colour is not decoration.** WCAG puts a meaningful graphic at 3:1 (1.4.11) — the
same floor a large heading takes — so an accent below that against what is behind it
is not a stylistic choice, it is a mark nobody can see. Naming an `ink` skips the
check, on the grounds that an author who names a colour means it.

### `image` — a photograph, and any text reversed out of it

The corpus's commonest slide by a wide margin. Picture and caption are one component,
not two, because the scrim between them is solved against the pixels the caption
actually covers: write `over:` and you get a measured scrim by default.

| Field | Required | Default | What it does |
|---|---|---|---|
| `src` | **yes** | — | The image file. Resolved beside the deck spec, then beside the theme's template, then out of the template's own `ppt/media/`. A relative name may not climb out of those directories with `..`; an absolute path is taken as written. |
| `fit` | no | `cover` | `cover` fills the placement and crops the source; `contain` shrinks the picture to fit whole, letterboxing it. |
| `crop` | no | — | Trim the source to this aspect first, centred — `16:9`, `4/3`, or a bare `1.78`. Applied *before* `fit`. |
| `mask` | no | `none` | `none`, `circle`, or `rounded`. |
| `radius` | no | `0.08` | Corner radius for `mask: rounded`, as a fraction `0`–`0.5` of the picture's short side. |
| `inset` | no | `0.025` | Gap between the picture's edge and its `over:` text, as a fraction of canvas width. |
| `scrim` | no | on when `over:` is present | `false` to suppress it, `true` to solve one, or the mapping below. |
| `over` | no | — | Lines of type reversed out of the picture. Each is a string, or a mapping of `text`, `rung`, `align`. |

```yaml
place:
  - at: {cols: full, rows: top-two-thirds}
    anchor: bottom
    image:
      src: harbour.jpg
      crop: "16:9"
      scrim: {gradient: bottom}
      over:
        - text: The sea took them one by one
        - {text: Book XII, rung: caption}
```

**`mask: circle` squares the placement first.** An ellipse drawn on an oblong box is an
oval, so the box is reduced to the largest square inside it, positioned by the
placement's `align`/`anchor`. For the same reason `mask: circle` refuses `fit: contain`
— that would re-oblong the box to the source's own aspect. Crop to `1:1` instead.

**The `scrim` mapping.**

| Field | Default | What it does |
|---|---|---|
| `pair` | `inverse` | The contrast-checked palette pair the scrim's colour and its ink come from. |
| `opacity` | `auto` | A fraction `0`–`1`, or `auto` to solve the least opacity that clears WCAG AA over these pixels. |
| `gradient` | `none` | `none`, `top`, or `bottom` — which edge the scrim is opaque at, fading to clear at the other. |

An `auto` opacity is solved against the sampled photograph at the band the text
occupies, so a caption in a picture's dark third gets far less scrim than the same
caption across all of it. Under a gradient it is solved at the band's *weakest* point.
A light photograph with white `over:` text will be scrimmed nearly flat — that is the
honest answer, and the fix is a `gradient:`, a darker crop, or a `pair:` whose ink is
dark.

### `document` — a real markdown file, rendered

Renders the file itself into a macOS-style window card and places it as a picture. Showing the real document beats retyping it: it cannot drift from the source.

| Field | Required | Default | What it does |
|---|---|---|---|
| `source` | **yes** | — | Path to a markdown file. Resolved **beside the deck spec** first, then as given — absolute, or relative to the directory you run the command from. |
| `side` | no | `full` | `left`, `right`, or `full`. `left`/`right` render it at half the body width. |
| `max_width` | no | `1000` | Layout width in CSS pixels before the screenshot. Lower it to make the type read larger on the slide. |
| `filename` | no | the file's own name | The text in the card's title bar. |
| `lines` | no | the whole file | `12-40` — one-based and inclusive, the way an editor names them. Cards part of a long file without copying that part into a second file, which is the drift this component exists to prevent. |

```yaml
section: Spec
title: The document itself, not a retyping of it
place:
  - at: {cols: full}
    document:
      source: ../docs/qa.md
      lines: '1-9'
      side: right
      max_width: 760
```

This one needs a Chromium-family browser on the machine; the others do not.

A card taller than the slide is refused rather than shrunk to unreadable. Reach for `lines:` to card the part you mean, or raise `max_width` to set the type smaller — **never** copy an excerpt into a second file. That copy is what this component exists to avoid, and it drifts.

### `fanout` — one call and the work it sets off

The "look what that one line actually does" slide: a plate on the left for the call, a
bus, and one branch per consequence. A [`flow`](#flow--a-run-of-steps-joined-in-order) is
the wrong shape for it — a flow is a *sequence*, each step following the one before, and
this is a *fan*, every branch leaving the same point at once.

| Field | Required | Default | What it does |
|---|---|---|---|
| `source` | **yes** | — | The call the branches leave from, set in the theme's mono face on an accent plate. |
| `items` | **yes** | — | The consequences. At least two — one is the `connector` component. |
| `items[].text` | **yes** | — | What that branch sets off. |
| `items[].icon` | no | — | A glyph on the branch, between the arrow and the text. |
| `weight` | no | `1.0` | Bus stroke as a multiple of the default, `0.5` to `4.0`. |

```yaml
title: Invisible side effects
subtitle: One line of code. None of the right-hand column is visible at the call site.
animate: one_at_a_time
place:
  - at: {cols: full, rows: {from: 0, to: 9}}
    fanout:
      source: publish(post)
      weight: 2.0
      items:
        - {icon: mail, text: Subscriber digest}
        - {icon: password, text: Cognito login synchronisation}
        - {text: A dozen cache invalidations}
```

The plate, the trunk and the spine are the first reveal group, so the shape is
established before anything hangs off it; then one group per branch, its arrow, glyph and
text arriving together.

### `versus` — two magnitudes either side of a glyph

A before and an after, or a this and a that. Two [`stats`](#stats--a-row-of-big-number-tiles)
tiles say the same numbers without saying they are *opposed*: the glyph between these two
is what makes the pair read as one comparison, and `highlight` says which side the slide
is arguing for.

| Field | Required | Default | What it does |
|---|---|---|---|
| `left` | **yes** | — | The first side: a mapping of the keys below. |
| `right` | **yes** | — | The second side, same keys. |
| `…value` | **yes** | — | The magnitude, at the `stat` rung. |
| `…label` | **yes** | — | What it measures. |
| `…note` | no | — | A third line, smaller. |
| `…highlight` | no | `false` | Paint this side in the accent. **One side only** — marking both says nothing. |
| `icon` | no | `schedule` | The glyph between them. A clock for time, a scale for a trade. |

```yaml
title: Default to a unit test
place:
  - at: {cols: full, rows: {from: 0, to: 5}}
    versus:
      icon: schedule
      left: {value: "2 days", label: the unit stage — it runs in parallel}
      right: {value: "1 day", label: collected in person, highlight: true}
```

**The plates are sized in proportion to their values.** A value the component can read a
number out of — `11.2%`, `$1,200`, `1.6x` — sizes its plate, so a side 60% larger is 60%
wider and the shape carries the comparison rather than leaving it to the reader to do the
arithmetic. [`choosing.md`](choosing.md) has the reason: length is a far stronger encoding
than a printed number, and two identical plates state that the magnitudes are equal.

**Both sides have to be written in the same unit.** `2 days` against `4 hours` reads 2
against 4 and would draw the longer span smaller, so a pair whose units differ keeps the
even split instead. The unit is matched whole, so `1 day` against `4 days` splits evenly
too — no string rule separates a plural from a different unit, `hrs`/`hr` and `ms`/`m`
being the same shape, and sizing two units against each other argues the opposite of the
data. Write both sides in the same unit to get the proportional plates. A magnitude suffix
counts as part of it: `$1.2M` and `$480K` do not compare, `$1.2M` and `$0.48M` do.

The smaller plate never drops below the width its longest word needs, so a long label
widens the plate rather than breaking mid-word; a placement too narrow to set both sides
is refused at build, naming the two widths. Whether the stack then *fits the band* is
`qa`'s `text-fit` check — give the placement more rows, or shorten the note.
Values with no number in them — `before` and `after` — keep the even split; there is
nothing to encode.

Each plate is its own surface, so its type is contrast-checked against the plate's fill
rather than the slide's. One reveal group per side; the glyph arrives with the first.

### `diverge` — signed bars either side of a centre rule

The shape a before-and-after wants when some measures improved and others got worse:
right of the rule is movement toward the target, left is away from it. A `chart` cannot
draw this — a bar chart with negative values writes correct OOXML, but the LibreOffice
path `render` and `qa` both go through draws those bars rightward and strips the sign
from the label, so the render loop cannot verify the one thing the slide is about.

| Field | Required | Default | What it does |
|---|---|---|---|
| `items` | **yes** | — | Non-empty list of mappings, one row each. |
| `items[].label` | **yes** | — | The row's name, set flush to the rule. |
| `items[].value` | **yes** | — | The signed number. Positive draws right in the first accent, negative left in the second. |
| `items[].note` | no | — | A quiet aside — the before-and-after counts behind the percentage. It is placed in the half the row's own bar does not use, so it never collides with the bar however long it runs. |
| `unit` | no | — | A suffix on every reading — `%`, `pt`, `x`. The sign is always written, so a bare number reads as a count and a `%` as a change. |
| `peak` | no | the largest magnitude present | The magnitude the longest bar stands for. **Pin it when two blocks share a slide**, or each scales to its own longest bar and two equal values draw unequal. |
| `label_width` | no | `0.3` | The label column as a fraction of the placement's width, `0.1` to `0.6`. |
| `pair` | no | — | A declared pair this block is drawn on. The placement is painted in that pair's background and every label is inked against *it* rather than the slide, which is what lets a light half and a dark half sit on one slide. |

```yaml
title: Refactor roadmap
subtitle: Right is toward the documented architecture; left is away from it
animate: one_at_a_time
place:
  - at: {cols: full, rows: {from: 0, to: 5}}
    diverge:
      peak: 300
      unit: "%"
      items:
        - {label: Sorted by hand, value: 271, note: 7 to 26}
        - {label: Machine passes, value: 92, note: 127 to 244}
  - at: {cols: full, rows: {from: 5, to: 9}}
    diverge:
      peak: 300
      pair: inverse
      items:
        - {label: Misroutes, value: -40, note: 10 to 14}
```

Both blocks name the same `peak`, so a bar in the dark half is comparable with one in
the light half. `align` is refused — the labels are set against the rule, and centring
them would pull every one off the axis it belongs to.

One reveal group per row: the label, the bar, its value and its note arrive together.

### `chart` — a real, editable PowerPoint chart

The chart is a native OOXML chart part with an embedded worksheet: editable in PowerPoint via Edit Data, vector at any zoom, and its labels are real text.

```yaml
section: Spec
title: Two channels, stacked
subtitle: Series names are the keys of each row's values
animate: by_series
place:
  - at: {cols: full}
    chart:
      kind: column-stacked
      data:
        - {category: Q1, values: {Ads: 20, Organic: 15}}
        - {category: Q2, values: {Ads: 28, Organic: 22}}
        - {category: Q3, values: {Ads: 35, Organic: 31}}
        - {category: Q4, values: {Ads: 42, Organic: 41}}
```

The chart block — `kind:`, the three row shapes, `highlight:` and all 29 kinds — is
[`docs/authoring.md`](authoring.md#the-chart-block).
