# Flows — process and relationship shapes

Which diagram shape a piece of information earns, which of them deckwright draws for you,
which you assemble from primitives, and how to tell a real process from a bulleted list
with arrows on it.

**`flow` the component is not "flow" the chart family.** In the Financial Times' Visual
Vocabulary, *flow* names quantitative movement between states — Sankey diagrams,
waterfalls, chord diagrams. deckwright builds none of those (see
[What deckwright cannot draw](#what-deckwright-cannot-draw)). `flow` here is a **process
diagram**: a run of labelled steps joined in order, carrying no quantity at all.

**To write a `flow:` or `connector:` block, read [`components.md`](components.md)
instead** — it owns their fields and defaults, and [`errors.md`](errors.md) owns the
message when one fails. Nothing about the spec's shape is duplicated here. For choosing
between a chart, a table and a diagram in the first place, read
[`choosing.md`](choosing.md).

For AI assistants: [`pptx-deck-building.md`](pptx-deck-building.md) covers the build/render loop;
this doc is the reference for deciding what shape to draw.

---

## Table of Contents

- [The arrow test](#the-arrow-test)
- [The six shapes](#the-six-shapes)
- [Linear process](#linear-process)
- [Timeline](#timeline)
- [Split and branch](#split-and-branch)
- [Cycle](#cycle)
- [Before-and-after](#before-and-after)
- [Hierarchy](#hierarchy)
- [What `flow` decides for you](#what-flow-decides-for-you)
- [When a flow is a bulleted list in a costume](#when-a-flow-is-a-bulleted-list-in-a-costume)
- [Assembling a shape by hand](#assembling-a-shape-by-hand)
- [What deckwright cannot draw](#what-deckwright-cannot-draw)
- [Adding a shape this catalogue does not name](#adding-a-shape-this-catalogue-does-not-name)

## The arrow test

An arrow makes one of exactly two claims: **sequence** (this happens after that) or
**causation** (this produces that). Before drawing any diagram, name which one your
arrows are making. If you cannot, the arrows are decoration and the content is a list.

Three cases that fail the test, and what to write instead:

| What you have | Why the arrows lie | Write |
|---|---|---|
| Four capabilities the product has | They co-exist; none follows another | `callouts`, or four `card`s in a grid with no joins |
| Five priorities, biggest first | That is rank, not sequence | `bar` chart, or a `table` |
| Three themes from the research | Membership, not order | `bullets` |

A diagram that fails the arrow test costs a slide's whole content band to say what three
lines of `bullets` say in a third of the depth. Delete the arrows first; if the slide
still works, you never needed the diagram.

## The six shapes

| Shape | The information that earns it | Build it with |
|---|---|---|
| [Linear process](#linear-process) | 2–6 steps, each strictly after the last | `flow` |
| [Timeline](#timeline) | The same, where the step labels are dates | `flow`, `head:` = the date |
| [Split / branch](#split-and-branch) | One input, 2–3 mutually exclusive outcomes | `card` + `connector` |
| [Cycle](#cycle) | The last step feeds the first, and the return matters | `card` + `connector` |
| [Before-and-after](#before-and-after) | One subject in two qualitative states | two `card`s + `connector`, or a 2-column `table` |
| [Hierarchy](#hierarchy) | Containment or reporting — not sequence at all | `card` + `connector`, or a `table` with `down:` |

**deckwright expresses two of these directly.** `flow` is a *linear run*: it joins
consecutive steps in order and stops. Branches, cycles and trees have no component —
you place `card`s and join them with `connector`s yourself.

## Linear process

Reach for `flow` when you have 2–6 ordered steps, each with a heading and at most one
line of copy.

**`numbered:`** — set it `true` only when the audience will refer to a step by its
number ("we're stuck on three"). Otherwise leave it off: the disc rail costs real depth
above every plate, and a number nobody cites is decoration. Numbering also changes the
drawing — the joins attach to the **discs** when numbered and to the **plates** when
not, so a numbered flow reads as a rail with plates hanging beneath it.

**`direction:`** — `horizontal` up to about four steps. Turn to `vertical` when any of
these is true:

- Four or more steps carry real copy under each heading.
- The audience will read the steps as a list rather than watch a pipeline.
- The slide already spends its width on something else.

**`current:`** — set it when the slide's claim is *"we are here"*: a status or roadmap
slide the deck returns to. Leave it off when the claim is *"this is the process"*. An
accented step with no status story invites the question "why that one?", and there is no
answer.

**`arrow:`** — `end` is the default and the right answer for a process. Use `both` only
for a genuine two-way relationship (a negotiation, a sync); it destroys the reading of
sequence, which is why the corpus slide that demonstrates it is titled as an exchange.
Use `none` when the steps are ordered but nothing is handed between them — a maturity
ladder, where stage 3 does not *produce* stage 4.

## Timeline

A timeline is a linear process whose step labels are dates. Use `flow` horizontally with
`head:` set to the date and `body:` to what happened, and leave `numbered:` off — the
dates are already the numbering, and a disc reading "1" beside "March 2024" competes
with it.

**`flow` spaces its steps evenly regardless of the intervals between them.** If the gaps
are uneven and that unevenness is the point — eighteen months of nothing, then three
releases in a quarter — `flow` draws a lie. deckwright has no proportional timeline: the
`xy-scatter` kinds place points at real x positions but carry no data labels at all
(see [`authoring.md`](authoring.md)), so the dates cannot print. Use a `table`
with a date column and accept that the reader looks the intervals up, or use `flow` and
say the intervals in the title.

## Split and branch

No component draws this. Place the source and each outcome as `card`s, and join them
with one `connector` per branch.

```yaml
place:
  - at: {cols: {from: 0, to: 3}}
    id: intake
    card: {heading: Request arrives, body: "One queue, no triage yet."}
  - at: {cols: {from: 3, to: 5}, rows: {from: 0, to: 5}}
    connector: {from: intake, to: fast, kind: elbow, arrow: end}
  - at: {cols: {from: 3, to: 5}, rows: {from: 7, to: 12}}
    connector: {from: intake, to: full, kind: elbow, arrow: end}
  - at: {cols: {from: 5, to: 12}, rows: {from: 0, to: 5}}
    id: fast
    card: {heading: Under a day, body: Straight to the owner.}
  - at: {cols: {from: 5, to: 12}, rows: {from: 7, to: 12}}
    id: full
    card: {heading: Anything longer, body: "Scoped, then scheduled."}
```

Two things make this work, and both come from how a connector attaches:

- **A connector joins placements, not shapes, and needs its own rect clear of both
  ends.** The two connector placements above sit in the same column gap but different
  rows, so they do not collide with each other or with the cards.
- **Both branches leave the source at the same point.** The line attaches to the edge
  midpoint nearest the other end's centre, so two connectors from one full-height source
  both start at its right-middle — which is exactly what a fork should look like.

**Use `kind: elbow` for branches.** A straight line from a full-height source to a
half-height outcome is a diagonal, and a diagonal in a box-and-line diagram reads as a
mistake rather than a route.

**Cap it at three branches.** Past that the connectors crowd one edge midpoint and the
outcomes are too short to read. A `table` with a condition column and an outcome column
carries five branches in less space and stays editable.

## Cycle

No component draws this either, and `flow` cannot be bent into it — it joins consecutive
steps and stops, with no join from the last back to the first.

**First check the return arrow carries meaning.** If the loop only says "and then you do
it all again", it is a linear process and the loop is decoration: draw the run with
`flow` and put the repetition in the title. Draw a real cycle only when the *return* is
itself a step — feedback that changes the next pass.

Place three or four `card`s around the content band and join them with `connector`s,
including the return. Keep the middle of the slide empty so the return join has a lane
to run down; a connector that must cross a placement declares `bleed: true` and takes a
full-canvas `box:`.

## Before-and-after

**If the change is numeric, this is not a diagram.** "42% → 71%" is a `stats` row of two
tiles, or a `column` chart with two categories. Two cards with an arrow between them
spend the whole content band to show one subtraction the reader does in their head.

Reach for two `card`s and a `connector` only when the change is qualitative — a
structure, a policy, a way of working. When the two states differ along several named
dimensions, a two-column `table` beats both: the reader compares row by row instead of
holding one card in memory while reading the other.

## Hierarchy

deckwright has no tree layout. Every box is a `card` you place by hand and every edge is a
`connector` you declare, which means an org chart costs a coordinate per box.

**Past about seven boxes or three levels, stop and write a `table`.** Use a `down:` cell
for the parent so it spans its children's rows — the merge *is* the containment, it needs
no arrows, and it stays legible at a size a hand-placed tree does not:

```yaml
table:
  rules: grid
  valign: top
  header: [Group, Team, Lead]
  rows:
    - [{text: Platform, down: 2, valign: middle, emphasis: true}, Ingest, Ana]
    - [Storage, Bo]
    - [{text: Product, down: 2, valign: middle, emphasis: true}, Web, Cai]
    - [Mobile, Dev]
```

## What `flow` decides for you

The arithmetic is the component's, not yours. Four consequences worth knowing before you
write the copy:

- **Every plate is drawn as deep as the wordiest step needs**, and they are all the same
  depth — a ragged run would not read as a sequence. One long `body:` therefore deepens
  every plate, leaving a band of white under the short ones. Keep bodies to one line each.
- **Steps divide the placement evenly**, with a lane of two gutters between them. You
  cannot make one step wider than another; a step that needs more room is a different
  slide.
- **The placement bounds the flow, it does not define it.** A horizontal flow sits at the
  top of its rectangle at whatever depth its copy earns, and only fills the rectangle when
  the copy needs all of it.
- **One reveal group per step, and the join into a step belongs to that step** — so
  `animate: one_at_a_time` builds the process a step at a time, arrow and all.

Too many steps for the width is a build error naming the lane arithmetic, not a squeeze;
so is a numbered disc that will not fit its cell. Drop a step or grow the placement.

## When a flow is a bulleted list in a costume

Run all three tests. Any failure means write `bullets` or `callouts` instead.

| Test | How to run it | Fails when |
|---|---|---|
| **Order** | Swap two steps | The slide still makes sense |
| **Handoff** | Name what step 1 hands to step 2 | You cannot name it |
| **Count** | Count the steps | More than six |

The cost of getting this wrong is not neutral. A `flow` spends a disc rail above every
plate, a gutter of inset on all four sides of each plate, and a two-gutter lane between
steps — before a single word is set. `callouts` puts the same headings and copy in a
fraction of the depth, and `bullets` in less again. Choosing the diagram for a list does
not just fail to help; it takes the room the words needed.

## Assembling a shape by hand

Everything except a linear run is `card` + `connector` on the grid. Three rules govern it:

1. **Give every joined placement an `id:`.** A connector's `from`/`to` names an id, and an
   id no placement declares is a build error listing the ids that do exist. Bare `[x, y]`
   canvas fractions are also accepted, but a coordinate is the thing the grid exists to
   avoid — move a card and a coordinate join goes stale where an id join follows it.
2. **Give the connector its own placement, clear of both ends.** It draws *between*
   rectangles, not inside its own rect, but that rect still has to clear the cards it
   joins. The gap between them is its natural home.
3. **Join to the placement, not to the shape inside it.** A disc at `size: 0.5` leaves a
   visible gap between the line and the drawing; give it a placement it fills and the join
   is exact.

## What deckwright cannot draw

Named here so you do not spend a slide discovering it. None of these has a component or a
chart kind, and none can be faked: series colour is the theme's business, so the
invisible-spacer-series trick that fakes a waterfall or a Gantt in Excel has nothing to
set.

| Shape | Nearest thing deckwright builds |
|---|---|
| Sankey, chord, alluvial | A `table` of source → target → volume |
| Waterfall | `column` with signed values; the running total goes in the title |
| Gantt | A `table` with a phase column and a date-range column |
| Org tree with automatic layout | Hand-placed `card` + `connector`, or a `table` with `down:` |
| Venn, matrix quadrants | `ellipse` and `panel` placed by `box:` |
| Proportional timeline | `flow` with even spacing, or a `table` |

## Adding a shape this catalogue does not name

1. Run [the arrow test](#the-arrow-test) first. Most shapes that feel missing are lists.
2. Express it with `card`, `ellipse`, `panel`, `rule` and `connector` on the grid, using
   ids for every join. If it needs a coordinate the grid cannot give, it takes a `box:`.
3. If the same assembly appears on three or more slides, it has earned a component —
   `flow` itself exists because sixteen slides across six of the eleven sample templates
   laid a process out the same way. Follow
   [Adding a component the spec cannot express](authoring.md#adding-a-component-the-spec-cannot-express),
   and add an exercise to `src/deckwright/conform/diagrams.py` rather than a unit test.
