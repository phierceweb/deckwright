# Treatments — what a slide should look like, and whether the deck already looks like it

You have a slide's worth of content that is neither a dataset nor a sequence. This doc
gets you to a treatment, and then asks the question no single-slide decision can: does the
deck around it already look like that?

**This doc decides which shape, and how often.** Numbers and a claim to make about them are
[`choosing.md`](choosing.md); anything with arrows is [`flows.md`](flows.md); the fields and
a worked example for the shape you land on are [`components.md`](components.md); the wire
format around them is [`authoring.md`](authoring.md).

For AI assistants: [`pptx-deck-building.md`](pptx-deck-building.md) covers the build/render loop;
this doc is the reference for deciding what a slide should show and how much the slide
before it already showed.

---

## Table of Contents

- [Chosen twice](#chosen-twice)
- [The intent table](#the-intent-table)
- [What a treatment costs](#what-a-treatment-costs)
- [When the treatment is more than the content earns](#when-the-treatment-is-more-than-the-content-earns)
- [The run test](#the-run-test)
- [Breaking a run, cheapest lever first](#breaking-a-run-cheapest-lever-first)
- [Varying inside a run you cannot break](#varying-inside-a-run-you-cannot-break)
- [Section openers](#section-openers)
- [Looking at it](#looking-at-it)
- [When none of these is the shape](#when-none-of-these-is-the-shape)

## Chosen twice

Start where [`choosing.md`](choosing.md#write-the-claim-first) starts: write the slide's
`title:` as a sentence before choosing anything — the same step for a `versus` as for a
`column` chart.

**A slide is chosen twice: once against its own content, and once against the slide before
it.** Only the first choice has a doc. A deck where every slide is individually correct and
all of them are the same rectangle is a deck nobody watches, and no per-slide test will ever
say so.

**Let the claim land before the evidence.** [`choosing.md`](choosing.md) says the chart's only
job is to make the title visible, and it follows that the two should not arrive together — a
chart that appears with its own headline competes with it. A slide's chrome is never part of a
build, so `animate: together` leaves the title and subtitle on screen and holds the body back a
click. One beat of separation is usually enough, and a deck built to be read rather than
presented has none to spend.

## The intent table

The rows below are the treatments *not* reached by having numbers or arrows. With either of
those, [`choosing.md`](choosing.md) and [`flows.md`](flows.md) are more specific than
anything here.

| Your slide sounds like | Reach for | Instead of, unless |
|---|---|---|
| "Here are three things that are true" | `bullets` | `callouts`, if each one needs a name *and* a sentence |
| "Three things, each with a name and an explanation" | `callouts` | `card`, if they should read as separate objects rather than rows |
| "Four parallel ideas, each its own object" | `card` in a grid | `callouts` — far cheaper vertically, and no plate to fill |
| "One call, and here is everything it sets off" | `fanout` | `flow`, if the consequences happen in order |
| "This, versus that" | `versus` | `stats`, if the two numbers are independent facts and not opposed |
| "Some of these got better and some got worse" | `diverge` | `chart`, if every value has the same sign |
| "Two paragraphs of argument" | `prose` | `bullets`, only if the lines are truly parallel items — prose in a bullet costume wraps ragged against its own dots |
| "Someone said this, and who matters" | `prose` with `cite:` | `callouts`, if it is three short quotes rather than one voice |
| "Look at the actual file" | `document` | `bullets`, if you are writing the words rather than quoting them |
| "The picture is the point" | `image`, bled to the placement | `background:`, if the type is the point and the picture is only a surface |
| "Where are we in this deck" | `nav` | a divider slide, if the deck is short enough to afford one |
| "These two regions are different" | `rule` between them | `panel`, if the region carries its own content rather than merely ending the one beside it |
| "This block is a second surface" | `panel` + chrome reversed onto it | `card`, the moment the block wants its own heading |
| "This one mark carries the slide" | `icon` | the owning component's own `icon:`, whenever the mark belongs beside text |

**`versus`, `fanout` and `diverge` are the three worth knowing before you need them.** Not
one of them appears in any deck under `examples/` — so the three treatments most able to
break up a wall of charts are the three an author is least likely to have seen. Each exists
because a more obvious component states the same facts without stating the relation between
them; the rationale is written beside the fields in [`components.md`](components.md).

**A component's own `icon:` beats a placed `icon`.** `callouts`, `card`, `stats` and `flow`
each re-derive an indent, a tile height or a plate depth from the glyph; `fanout` and
`versus` take one into a slot they reserve either way. Placing a bare `icon` beside any of
them means maintaining by hand an offset the owning component would have computed.

## What a treatment costs

**A treatment's cost is depth** — the share of the content band the shape spends before a
single word is set. It is why a slide that "has room for one more point" often does not.

| The treatment | Costs | What that means for the slide |
|---|---|---|
| `rule`, `connector`, `icon`, `ellipse`, `nav` | Almost nothing | Marks and furniture. They compose with anything. |
| `swatches`, `grid` | Half a band, or most of one | Both draw the theme rather than content: a palette wraps to as many rows as it has roles, and a grid needs depth to read as one. |
| `bullets`, `callouts`, `card`, `prose` | Half a band | Two fit on one slide, one over the other. `prose` caps its measure, so more copy costs depth, never width. |
| `stats`, `table`, `versus`, `panel`, `chart`, `code` | Most of a band | Pair one with a lighter band rather than another of these. |
| `diverge` | Most of a band, or half of one | The exception to the row above: two blocks stack on one slide, and `peak:` exists to make them share a scale. |
| `flow`, `fanout`, `image`, `document` | The slide | A second component alongside one of these is a footer strip, not a peer. |

**A heavy shape over a short band is the composition to reach for** — the shape carries the
claim and a two- or three-row `callouts` under it says what the shape means. It is what
`rows:` is for: give the shape `rows: {from: 0, to: 9}` and the band `rows: {from: 9, to: 12}`.

## When the treatment is more than the content earns

[`flows.md`](flows.md#when-a-flow-is-a-bulleted-list-in-a-costume) makes this argument for
diagrams, and that section is the canonical version. The same failure has three other common
forms:

| The costume | The tell | Write |
|---|---|---|
| A two-column `table` | Every row is a label and one value; no cell needs reading against another | `callouts`, or `stats` if the values are the point — and [`choosing.md`](choosing.md#when-a-table-beats-a-chart) on when a table does earn it |
| A row of `card`s | The plates carry one line each and nothing sits beside them | `callouts` |
| A `panel` with a heading placed on it | You are maintaining two placements to make one object | `card`, which is that object |

**None of these survives contact with the render, and all of them survive QA.** The plate,
the rail and the axis are legal geometry inside a legal box; nothing in the manifest knows
the words needed the room.

## The run test

**Count the longest run of the same primary treatment.** Read the deck's `place:` blocks in
order and write down the component carrying each slide. Break any run longer than about four
that is not a catalogue.

Measure it because it is invisible while you author. Slides are written one at a time, each
one correct, and the wall assembles itself. The committed decks show every point on the
scale:

- `examples/chart-catalogue.deck.yaml` — 36 slides, every placement `at: {cols: full}`,
  no chrome override, no `animate:`, never two components on a slide. It is a catalogue and
  that is defensible; it is also the shape to recognise.
- `examples/feature-tour.deck.yaml` — an eleven-slide chart wall inside a deck otherwise
  about the compiler, and two pairs within it render one dataset twice, stacked and then
  normalized.
- `examples/tables.deck.yaml` — ten consecutive table slides, three of them the same
  rows with `rules:` changed.

**The run test applies to motion too.** Read the `animate:` values in the same pass. Five
slides that each reveal in three left-to-right beats teach the room the rhythm, and the
reveal stops carrying meaning — the build is pacing the deck instead of the content. No
number attaches to this one; the tell is a click that stops changing what the room learns.

**A long run is sometimes right.** A catalogue, a chart appendix, a reference deck: the
repetition *is* the structure. The test is not "never repeat" — it is know the number and
decide it on purpose.

## Breaking a run, cheapest lever first

You rarely have to change the treatment. Stop at the first lever that fits; each is a
smaller edit than the one below it.

1. **`background:` on one slide.** One field, no layout change. As mid-run relief it costs
   nothing and resets the eye. For a section opener,
   [`authoring.md`](authoring.md#background) is prescriptive about which surface, and says
   why.
2. **A component's own `pair:`.** A `panel`, a `diverge` block or a `card` painted on its own
   ground while its neighbours stay on the page. It is a field on those components, not a key
   beside `at:`. This is the most under-used lever in the repo and it buys more contrast per
   character than anything else in the spec.
3. **Split the band.** Give the treatment `rows: {from: 0, to: 9}` and put a short `callouts` or
   `stats` under it. The slide gains a second voice without gaining a second idea.
4. **Move the chrome.** `examples/title-treatments.deck.yaml` builds six different slides out
   of the `chrome:` block alone, with the body component barely mattering. The mechanics are
   [`authoring.md`](authoring.md#moving-the-chrome).
5. **Go off-grid with `box:` and `bleed:`.** The half-screen split, the colour field running
   off an edge, the plate under a grid placement. A `split:` field does exist for dividing a placement between components; what there is no field for — a split screen
   is a bleeding `box:` plus chrome moved into the other half.
6. **Change the treatment.** The largest edit, and the one to reach for last.

**You never write a colour.** A spec names palette roles and pairs and the theme resolves
them — see [`authoring.md`](authoring.md#what-lives-in-the-theme-not-the-spec). Levers 1 and
2 move a whole region's ground; individual components additionally name a role of their own
through `color:`, `ink:`, `pair:` or a table's `head_pair:`, and each of those is checked for
contrast against what it actually lands on.

## Varying inside a run you cannot break

Sometimes seven slides really are seven rules and the treatment is right for all seven. Two
devices work without changing it.

**Mirror the composition.** Alternate which side the heavy component sits on —
`{cols: {from: 0, to: 7}}` then `{cols: {from: 5, to: 12}}` and back. The reader sees the same treatment; the
page does not look like the previous page.

**Foot two or three of them.** Drop a full-width strip into `rows: {from: 10, to: 12}` on a couple of
slides in the run. It shortens the main component, re-proportions the page, and gives those
slides a beat the others do not have.

**Never repeat the same headings verbatim down a run.** Nine slides whose `callouts` all read
*What it is / Why / Receipt* teach the audience the shape and then give them nothing new to
read. Numbered kickers do it from the other end — `RULE 3 OF 7` tells the room how much is
left, which is the tell that the treatment is pacing the deck instead of the content.

## Section openers

An opener is the cheapest variety in a deck: it carries almost no content, so it can carry
all the contrast.

**Give it a surface of its own** — lever 1, and `authoring.md` says which one.

**Place little or nothing.** A `rule` under a moved title is enough; chrome-only openers are
the norm in every committed deck.

**Use them to cap runs, not only to start chapters.** Dropping one into the middle of a long
stretch is what keeps a chart appendix watchable.

## Looking at it

None of this is checkable by machine, and `qa` says so itself:
[`qa.md`](qa.md#what-this-layer-cannot-catch) closes by putting visual hierarchy, balance and
"does this look intentional" explicitly out of scope. Nothing in the manifest records that
six slides in a row were the same rectangle.

**The contact sheet is the instrument.** Render the deck and look at every slide at once
rather than one at a time — the run you cannot see while authoring is obvious in a grid of
thumbnails. The loop is
[`pptx-deck-building.md`](pptx-deck-building.md#the-build--render--qa-loop).

## When none of these is the shape

**Most "I need a new component" is a composition of two existing ones plus a `box:`.** Before
writing one:

1. Check the two catalogues that route by information shape rather than by name —
   [`choosing.md`](choosing.md#the-intent-table) and [`flows.md`](flows.md#the-six-shapes).
   Both also name what deckwright cannot draw, and what to build instead.
2. Try the composition. Levers 3 and 5 above cover most of what looks like a missing
   component.
3. If it is genuinely new, the API is
   [`authoring.md`](authoring.md#adding-a-component-the-spec-cannot-express) and the traps and
   promotion checklist are [`extending.md`](extending.md). An exercise in
   `src/deckwright/conform/` is how it gets tested, and a row in the cost table above
   is how anyone else finds it.
