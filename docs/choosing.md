# Choosing — from a claim and some numbers to a treatment

You arrive with a story you want to tell and some data to tell it with. This doc gets you
to a treatment: which of the 29 chart kinds, or a `table`, or `stats`, or no graphic at
all. It commits to an answer for each case and says what would change it.

**This doc decides *what* to draw; three others say *how* to write it.**
[`authoring.md`](authoring.md) owns the `chart:` block and all 29 kinds,
[`components.md`](components.md) the `table:` and `stats:` fields, and
[`errors.md`](errors.md) the message when a build fails. [`charts.md`](charts.md) is the
renderer's internals and answers none of it. For process and relationship diagrams —
arrows, steps, branches — read [`flows.md`](flows.md).

For AI assistants: [`pptx-deck-building.md`](pptx-deck-building.md) covers the build/render loop;
this doc is the reference for deciding what a slide should show.

---

## Table of Contents

- [Write the claim first](#write-the-claim-first)
- [The intent table](#the-intent-table)
- [When the answer is no chart](#when-the-answer-is-no-chart)
- [When a table beats a chart](#when-a-table-beats-a-chart)
- [Comparison and ranking](#comparison-and-ranking)
- [Part-to-whole](#part-to-whole)
- [Change over time](#change-over-time)
- [Correlation](#correlation)
- [Deviation](#deviation)
- [Distribution](#distribution)
- [Profile across dimensions](#profile-across-dimensions)
- [The traps](#the-traps)
- [What deckwright cannot draw](#what-deckwright-cannot-draw)
- [When a new chart kind lands](#when-a-new-chart-kind-lands)
- [Sources](#sources)

## Write the claim first

**Write the slide's `title:` as a sentence before you choose anything.** "Revenue" is a
label and tells you nothing; "Enterprise overtook self-serve in Q3" is a claim, and the
claim names its own treatment — two series, over time, with a crossing. The chart's only
job is to make that sentence visible.

This is also the test for whether the chart is working: if a reader can see your title is
true without reading the axis labels, it is. If they have to hunt, you picked the wrong
encoding or too much data.

**One perceptual fact does most of the work.** Cleveland and McGill ranked how accurately
people read quantities off a graphic, in six ranks: position along a common scale, then
position along non-aligned scales, then length/direction/angle (tied — the paper says
there is not enough evidence to separate them), then area, then volume and curvature, then
shading and colour saturation. Their design rule follows: use the highest encoding you
can. In their own experiment, position judgements came out about twice as accurate as
angle judgements, and they concluded a pie can always be replaced by a bar — swapping an
angle judgement for a position one.

Every recommendation below falls out of that. **A bar or column chart wins by default
because it uses the best encoding there is.** Note what the ranking does *not* say: length
and angle are tied, so "a bar beats a pie because length beats angle" is not the argument.
The argument is that a bar puts every value on a *common baseline*, which nothing in the
pie family does.

## The intent table

Find the sentence closest to yours. The chart column is the commitment; reach for the
alternative only for the reason given.

| Your claim sounds like | Reach for | Instead of, unless |
|---|---|---|
| "A is bigger than B" — up to ~8 items | `column` | `bar` when the category names are long |
| "A leads, then B, then C" | `bar`, rows sorted **ascending** | `column` — a ranking is read down a list |
| "It grew every quarter" — 2+ points, ordered | `line` | `line-markers` at ≤12 points, where each value matters |
| "A is 60% of the whole" — one whole, ≤5 parts | `pie` or `doughnut` | `bar` at 6+ parts |
| "The mix shifted from A to B" | `area-stacked-100` | `column-stacked` when absolute totals matter too |
| "These two move together" | `xy-scatter` | `bubble` when you must label or highlight a point |
| "Big on this axis, small on that, and heavy" | `bubble` | — |
| "We beat target in 3 of 5 regions" | `column` of signed variances, or [`diverge`](components.md#diverge--signed-bars-either-side-of-a-centre-rule) | `column-stacked` — never; deviation needs a zero line |
| "Strong here, weak there" — one entity, 3+ dimensions | `radar` | `bar` for two or more entities |
| "Here are the numbers" | `table` | — |
| "This one number is the story" | `stats` | — |
| "Three things are true" | `bullets` or `callouts` | — |

**Sort a `bar` ascending.** A horizontal bar chart draws its first row at the *bottom*,
so writing the rows biggest-first puts the smallest at the top and the ranking reads
backwards. Write them smallest-first and the longest bar lands on top, where a reader
looks. A `column` has no such twist — it draws left to right in the order given.

## When the answer is no chart

Reach for a graphic only when the shape of the data is the argument. Three cases where it
is not:

- **One number.** A single figure is a `stats` tile, set at the `stat` rung and readable
  from the back of a room. A one-bar chart spends the content band drawing an axis for a
  value the reader could have read in full.
- **Two or three numbers with no relationship between them.** 4 offices, 200 staff, 12
  years — that is a `stats` row (four tiles to a row; more items wrap onto further
  rows until the body band runs out), not a chart. There is no comparison to make;
  the numbers just are.
- **Three claims.** `bullets` for bare lines, `callouts` when each claim needs a heading
  and a line of support. Keep `callouts` to about six rows; past that the rows are thinner
  than the type needs and the build fails saying so.

A chart with fewer than four datapoints is almost always one of these three in disguise.

**Read your title aloud before you draw it.** If the sentence already contains every number the chart would show, the chart is decoration. `qa` reports this as `chart-datapoints`, quoting the line above — a warning, because the judgement is yours.

## When a table beats a chart

Knaflic's framing is the useful one: a graph talks to the visual system, which is fast; a
table talks to the verbal system, and the reader *reads* it. Choose a table when reading
is what you want.

Reach for `table` when any of these is true:

| Condition | Why a chart fails |
|---|---|
| The exact values are the point | An axis makes the reader estimate what you could have printed |
| Mixed units in one view | %, $ and days share no axis |
| More than two dimensions per row | Owner, effort, status and date have no encoding left |
| The audience will look up *their* row | Each reader wants one row, not the shape |
| Fewer than ~4 rows and a chart would be mostly axis | Nothing to see |

Use the table's own controls to keep it from reading as a wall of grey. `align: [left,
right, right]` so figures line up on their digits; `total:` for the summary line, which is
ruled above itself at twice the weight; `rules: header` for the editorial look where
spacing parts the rows; `density: 0.7` to tighten a long table; and a per-cell `pair:` to
paint the one row that is the recommendation. `valign: top` when one column carries prose
and the rest carry labels.

**A table is also the honest answer for more than two dimensions.** Three columns of
numbers plus a status plus an owner is not a chart that exists — it is a table, and
trying to encode the fourth dimension as colour or size loses the reader.

**In a live talk, put the table on the slide only if you will walk the audience through
it.** Otherwise pull the one row that matters into a `stats` tile or a `column` chart and
send the table to an appendix slide.

**A total row is a conclusion, not a heading.** When you are walking the room through the
table, consider giving the total its own beat: they read the split, then the sum arrives. Put
the body rows in one placement and the summary row in a second `table` beneath it — the same
`widths:` and `align:`, one row, `emphasis: true` on each cell — and let `animate: one_at_a_time`
hold it back. That trades the double-weight rule a `total:` draws above itself for the beat.
This is editorial guidance, not a finding: a table that will be read rather than presented
wants everything at once.

## Comparison and ranking

**Default to `column`.** Every column stands on the same baseline, so the reader is
comparing positions along a common scale — the most accurate judgement available.

**Switch to `bar` for long category names, or for many categories.** Label length is the
main reason and a decisive one: a horizontal bar gives its label a full line of width,
where a column has only its own width and the renderer must rotate or shrink the text.
"Enterprise self-serve migration" under a column is unreadable at any type size; beside a
bar it is fine. deckwright also reserves the label column explicitly in the file for the bar
family, so long labels do not run off the slide in Keynote.

**Sort the rows** unless the categories have a natural order (quarters, sizes, ages). A
ranking that is not sorted is a ranking the reader has to do themselves. deckwright draws
rows in the order you write them, so sorting is your job in the `data:` list.

**Two to four series: `column` with a legend**, which appears automatically past one
series. Past four series a clustered column becomes a picket fence — split it into two
charts on the grid, or drop to the two series your claim actually needs.

**To draw the eye to one bar, set `highlight: true` on that row.** It recolours that one
point. At most one row per chart may set it.

## Part-to-whole

**`pie` or `doughnut` for one whole with five parts or fewer.** Readers do fine on a pie
around the quarter/half/three-quarter landmarks, which is what it is genuinely good at:
showing that one part is about half.

**Five is editorial guidance, not a finding — no research fixes a slice count.**
Datawrapper says five; their own Academy page says four; other practitioners reject a
number at all. Use five as a working limit and let the data decide: if two adjacent
wedges are close enough that you would have to label them to tell them apart, the pie has
already failed.

**Treat `doughnut` as interchangeable with `pie`, not as a compromise.** Removing the
centre removes the central angle entirely, and donuts test as accurate as pies — readers
were never reading the angle. They read arc length and area (Skau and Kosara), which is
also why the naive "pies fail because angle is a poor encoding" story is wrong. Pies fail
because no slice sits on a common baseline.

**At six or more parts, use `bar`.** Group the tail into "Other" if the small parts do not
each carry a claim.

**Do not use a pie to compare shares that are close.** Two wedges at 24% and 27% are
indistinguishable; the same two values as bars are obviously different. If the claim is
"A is bigger than B", it was never a part-to-whole story — it is a comparison.

**`pie-exploded` and `doughnut-exploded` pull *every* wedge apart**, which emphasises
nothing — and breaking the continuous arc removes the very cue the reader was using. Use
`pie` with `highlight: true` on the one wedge that matters instead.

**Stacked or 100%?** Ask what the reader must compare:

| The claim | Kind |
|---|---|
| "The total grew, and here is what it is made of" | `column-stacked` |
| "The mix changed" — totals differ or do not matter | `column-stacked-100` |
| "The mix changed over a continuous timeline" | `area-stacked-100` |

**A stacked chart gives you one honestly comparable series, and a 100% stacked chart gives
you two.** Only the bottom segment sits on a shared baseline; everything above it floats,
so the reader is comparing lengths on non-aligned scales. Stacking to 100% adds a second
shared baseline at the *top* of the plot, where the topmost series becomes readable again.

So: **put the series your claim is about at the bottom** — it is the one written first in
each row's `values:` mapping — and on a `*-stacked-100` kind, put the second most important
series last. Every series in the middle is decoration; if three of them matter, this is
two charts, not one.

## Change over time

**`line` for a trend, `line-markers` when there are twelve or fewer points and each value
is worth reading.** Markers past that turn the line into beads.

**The rule is about ordering, not time.** A line is right whenever one variable imposes an
order on the data (Wilke's formulation); time is just the commonest such variable. It is
wrong the moment the x axis is a set of unordered categories, because the segment between
two points asserts values you never measured.

**Distinguish levels from flows.** A line suits a continuous *level* that exists at every
instant — headcount, ARR, price. A `column` suits a per-period *flow* that fills up from
zero and resets — bookings in Q1, hires in Q1. Drawing a flow as a line implies the
quantity was accumulating smoothly between your measurements, which it was not.

**Use `column` over `line` when the periods are few and discrete** — four quarters, three
years — and the claim is about the individual values rather than the trajectory.

**Up to four lines.** Past that, colour stops distinguishing them and the legend does all
the work. Split the chart, or plot the two lines the claim needs and put the rest in a
table.

**You cannot highlight a point on a line, area, radar or scatter chart.** A point on those
is a stroke or a band with no fill of its own, so deckwright refuses `highlight:` outright
with a `LayoutError` naming the kinds that can. To draw attention on a line chart, use the
slide title, `animate: by_series`, or pin the axis with `y_min`.

**Set `y_min: 0` on a column chart** unless you have a reason not to. Left unset the axis
auto-scales to the data's own range, which can make a 12-point move look like a 90-point
one. A line chart showing a trend is the standard exception: a zero baseline can flatten a
real movement into nothing.

## Correlation

**`xy-scatter` for two numeric variables.** Points only — no line, because a line through
points chosen to have none draws a relationship you did not measure.

**Use `bubble` instead when you need to call out a single point.** The scatter kinds carry
no data labels at all — the numbers do not print beside the points — and they refuse
`highlight:`. `bubble` supports both. Give every row the same `size:` and you have a
labelled, highlightable scatter plot.

**`xy-scatter-lines` and `xy-scatter-smooth` are not correlation charts.** They join the
points in row order, so they are for a path through a space — a curve traced over time, a
trade-off frontier. Reach for them only when the order of the rows is itself meaningful.

**`bubble` for three variables**, where the third is a magnitude. Size is read as area,
near the bottom of the perceptual ranking, so treat it as "roughly bigger" rather than a
value the reader can measure. Never encode a fourth variable.

## Deviation

**`column` with signed values.** Negatives fall below the axis and the zero line does the
work; this is the whole treatment. Set `y_min` and `y_max` symmetrically when you want
over- and under-performance to read at the same weight.

Sort by the variance, not alphabetically — a deviation chart's shape is the argument.

**Use `column`, not `bar`, and check the render.** LibreOffice — which both `render` and
`qa` go through — plots a negative *bar or column* value as positive and drops the sign from
its data label, on a chart whose OOXML and embedded worksheet both hold the correct negative
number. `qa` reports it as `chart-negative` rather than letting it pass, because the
verification loop cannot see the one thing a deviation slide is about. The
[`diverge`](components.md#diverge--signed-bars-either-side-of-a-centre-rule) component draws
signed rows as real geometry and is unaffected; reach for it when the sign is the message and
the audience does not need an axis or editable data.

## Distribution

**deckwright has no histogram and no box plot.** A `column` chart with bins as categories is
the closest thing, and it is genuinely readable, but the bars will carry the theme's gap
between them: `gap_width` is a theme knob (`theme.chart.gap_width`), not a spec field, so
you cannot close it for one slide. The bars will not touch the way a histogram's do.

If the distribution's shape is the claim and the gap bothers you, either set the theme's
`gap_width` to `0` for a deck that is mostly histograms, or state the shape in words and
show the summary statistics as a `stats` row.

## Profile across dimensions

**`radar` for one entity across three or more dimensions** — a capability profile, a
scorecard. `radar-filled` for a single series; `radar-markers` when each vertex value
matters.

**Two entities at most, and prefer bars for two.** Filled radars overlap into mud, and
outlines cross so often the reader cannot follow either. A grouped `bar` chart compares
the same two profiles on a common scale and reads better in every case — reach for radar
when the *shape* of one profile is the point, not the individual values.

Radar refuses two things other kinds allow. `highlight:` is rejected outright, and so is
`animate: by_category` — the categories are vertices of one closed outline, so a
per-category build would emit a click per category with nothing moving.

## The traps

| Trap | Why it fails | Do this |
|---|---|---|
| Pie with 8 slices | No slice sits on a common baseline, and adjacent small wedges become indistinguishable | `bar`, or group the tail into "Other" |
| Exploded pie | Emphasises every wedge, therefore none, and breaks the continuous arc the reader reads | `pie` + `highlight: true` on one wedge |
| Line over unordered categories | A line asserts you can interpolate between the points; between "Retail" and "Legal" there is nothing | `column` |
| Second y-axis | The two scales are arbitrary, so the crossover point is an artefact of scaling, not a finding | Two charts side by side on the grid, or index both series to a common baseline before writing the spec |
| Stacked chart to compare inner segments | Only the bottom segment shares a baseline | Put the claim's series at the bottom, or split into separate charts |
| Six clustered series | Colour stops distinguishing them past the theme's accent count, and the cycle repeats | Cut to the series the claim needs |
| Auto-scaled axis on a comparison | A small move fills the plot and reads as a large one | `y_min: 0` |
| Long labels under columns | They wrap, shrink or run off in Keynote | `bar` |
| `highlight:` on a line/area/radar/scatter chart | Refused with a `LayoutError` — those points have no fill | Use the title, `animate:`, or switch to `bubble` |
| A table nobody will read aloud | The audience reads instead of listening | Pull the one row into `stats`; table to an appendix |

**deckwright cannot build a second y-axis at all**, so that row is a trap you cannot fall
into here — but it is also why "just put it on a secondary axis" is never an available
fix. Two chart placements on the grid is the answer.

## What deckwright cannot draw

**First, two the literature recommends that you *can* build today** — both are often the
better answer than the chart people reach for first, and neither is obvious from the list
of kinds:

- **Slope chart** — `line` with exactly two categories. The best treatment there is for
  "these ranks changed between two points in time", and far clearer than a paired column.
- **Small multiples** — several `chart` placements on the grid, one per category, same
  kind and same `y_min`/`y_max`. This is the honest replacement for a six-series line
  chart and for a dual axis.

**The rest have no kind, and none can be faked.** Series colour is the theme's business,
so the invisible-spacer-series trick that builds a waterfall or a Gantt in Excel has
nothing to set:

| Treatment | Nearest thing deckwright builds |
|---|---|
| Waterfall | `column` with signed values; put the running total in the title |
| Histogram (bars touching) | `column` with bins as categories, carrying the theme's gap |
| Box plot, violin, beeswarm | Summary statistics as a `stats` row or a `table` |
| Dot plot / lollipop, categorical | `bar` |
| Bullet chart (actual vs target) | `bar` of actuals with the target in the title, or a two-series `column` |
| Treemap, marimekko, sankey | `table`, or `column-stacked-100` for the share |
| Map | Not at all; use a `table` or an `image` |

## When a new chart kind lands

Adding a kind to the renderer is [`charts.md`'s procedure](charts.md#adding-a-new-chart-type).
Adding it *here* is a separate step and is not optional:

1. Add a row to [the intent table](#the-intent-table) naming the claim it serves — not its
   data shape. A kind nobody can map to a sentence will not get chosen.
2. Name what it replaces. A new kind that is the better answer for a case already in this
   doc must change that case's recommendation, or the doc now gives two answers.
3. If it fixes something in [What deckwright cannot draw](#what-deckwright-cannot-draw), delete
   that row.

## Sources

**Perception.** Cleveland, W. S. & McGill, R. (1984), *Graphical Perception: Theory,
Experimentation, and Application to the Development of Graphical Methods*, JASA 79(387)
pp. 531–554, doi:[10.1080/01621459.1984.10478080](https://doi.org/10.1080/01621459.1984.10478080)
— the six-rank ordering, the ~2× position-over-angle accuracy result, and the
replace-a-pie-with-a-bar prescription. Replicated by Heer & Bostock,
[*Crowdsourcing Graphical Perception*](http://idl.cs.washington.edu/files/2010-MTurk-CHI.pdf)
(CHI 2010), which confirms position over length and area but finds **no** support for
angle being worse than length — hence this doc never orders those two. Skau & Kosara,
[*Arcs, Angles, or Areas*](https://media.eagereyes.org/papers/2016/Skau-EuroVis-2016.pdf)
(EuroVis 2016) — pies are read by arc length and area, not angle, and donuts are as
accurate as pies.

**Taxonomies.** The
[FT Visual Vocabulary](https://github.com/Financial-Times/chart-doctor/blob/main/visual-vocabulary/Visual-vocabulary-en.pdf)
— nine families (deviation, correlation, ranking, distribution, change over time,
magnitude, part-to-whole, spatial, flow); this doc's sections follow it, minus spatial and
flow, which deckwright cannot draw. Its bar caption is the source for the long-labels rule.
[Abela's Chart Chooser](https://extremepresentation.com/wp-content/uploads/chart-chooser-2020.pdf)
(2020) — the comparison / relationship / distribution / composition tree, and the
static-vs-over-time split this doc borrows for part-to-whole.

**Practice.** Datawrapper, all by Lisa Charlotte Muth:
[pie charts](https://www.datawrapper.de/blog/pie-charts/) (five slices max — note their
Academy page says four, which is why this doc treats the number as editorial);
[stacked column charts](https://www.datawrapper.de/blog/stacked-column-charts/) (the
baseline trap, and the second baseline a 100% stack buys you);
[line charts](https://www.datawrapper.de/blog/line-charts) (levels vs per-period flows);
[choosing a chart type](https://www.datawrapper.de/blog/chart-types-guide) (a 3% gap is
obvious in bars and invisible in a pie).
Claus Wilke, [*Fundamentals of Data Visualization*](https://clauswilke.com/dataviz/) —
swap the axes for long labels, order unordered categories by value, and lines are for
whenever a variable imposes an ordering.

**Tables and text.** Cole Nussbaumer Knaflic,
[table vs graph](https://www.storytellingwithdata.com/blog/2011/11/visual-battle-table-vs-graph)
— tables engage the verbal system and are read; graphs engage the visual system and are
seen; plus the three table conditions this doc uses. Alex Velez,
[what is a table?](https://www.storytellingwithdata.com/blog/2020/9/24/what-is-a-table)
— mixed units, and the warning that an audience reading your table has stopped listening.
Knaflic, [the power of simple text](https://www.storytellingwithdata.com/blog/2012/06/power-of-simple-text)
— one or two numbers beat a chart of them.

**Dual axes.** Stephen Few,
[*Dual-Scaled Axes in Graphs*](https://www.perceptualedge.com/articles/visual_business_intelligence/dual-scaled_axes.pdf)
(2008) — the rigorous case: comparing magnitudes across two scales is meaningless, and
whether and where the lines cross is arbitrary. Muth,
[why not to use two axes](https://www.datawrapper.de/blog/dualaxis) — the same argument
with a worked rescaling, plus the alternatives this doc recommends (two charts, or index
both series to a common baseline).
