# Charts — a real, native chart part

How `charts/native.py` turns a validated `ChartSpec` into a native OOXML chart —
a real, editable PowerPoint chart with an embedded worksheet, built via
python-pptx's chart API. This doc is about the **renderer's internals**: the
per-type option sets, the palette, and how to add a type.

**To write a chart in a deck spec, read [`docs/authoring.md`](authoring.md)
instead** — it owns the wire format (`kind:`, the row-oriented `data:` list,
`value:` vs `values:`, `highlight:`, the full table of all 29 kinds) and every
error message the chart block can produce. Nothing about the spec's shape is
duplicated here.

For AI assistants: [`pptx-deck-building.md`](pptx-deck-building.md) covers the render/QA loop
end to end; this doc is the full reference for the chart renderer
specifically.

---

## Table of Contents

- [What reaches the renderer](#what-reaches-the-renderer)
- [The native renderer](#the-native-renderer)
- [Chart build animation](#chart-build-animation)
- [Room for the labels a bar chart sets on its left](#room-for-the-labels-a-bar-chart-sets-on-its-left)
- [Negative values, and why the render cannot check them](#negative-values-and-why-the-render-cannot-check-them)
- [Turning one series' labels off](#turning-one-series-labels-off)
- [The unit reaches the axis too](#the-unit-reaches-the-axis-too)
- [Refusing a truncated axis](#refusing-a-truncated-axis)
- [The categorical palette](#the-categorical-palette)
- [Adding a new chart type](#adding-a-new-chart-type)

## What reaches the renderer

`ChartSpec.from_body` parses the spec's `chart:` block and hands the renderer a
frozen `ChartSpec`: a `type`, `categories`, one or more `Series`, an optional
`highlight` index, `decimals`, and `y_min`/`y_max`.

The spec's wire format is **row-oriented** — one `data:` row per datapoint, each
carrying its own category (or `x`/`y`/`size`), its own numbers, and its own
`highlight` flag. `from_body` derives the `categories`/`series` tuples the
renderer consumes, so nothing downstream of the parse sees rows. Series names and
their order come from the first row's `values` mapping.

Two consequences worth knowing when working on the renderer:

- **`highlight` arrives as an index**, resolved from whichever row set
  `highlight: true`. The renderer's per-point colour override is unchanged.
- **`Series.unit` comes from the block, not the row.** `unit:` is a key of the
  `chart:` block, threaded through `_parse_category_rows` onto every `Series`, and
  `_number_format` turns it into the code both the labels and the value axis print
  in, so the scale and the values it frames agree. Only
  the point-shaped parser takes no `unit` argument, so it stays `None` on the
  xy-scatter and bubble kinds: `unit:` is accepted there and does nothing.

## The native renderer

`charts/native.py` builds a real chart part via python-pptx's chart API —
`add_chart`, an embedded `CategoryChartData`/`XyChartData`/`BubbleChartData`
worksheet (shape-dependent), and per-series or per-point fill styled from the
theme. It draws all **29** creatable `ChartSpec` types — every type
python-pptx can build: the 22 category-shaped types (`bar`, `column`,
`column-stacked`, `column-stacked-100`, `bar-stacked`, `bar-stacked-100`,
`line`, `line-markers`, `line-stacked`, `line-stacked-100`,
`line-markers-stacked`, `line-markers-stacked-100`, `area`, `area-stacked`,
`area-stacked-100`, `radar`, `radar-filled`, `radar-markers`, `pie`,
`doughnut`, `pie-exploded`, `doughnut-exploded`), the 5 xy-scatter variants,
and the 2 bubble variants — and reads every colour, face and size from the
theme; it never hardcodes a hex value or a point size.

**Every piece of chart text reads the slide's live pair, not the template.**
`_style_data_labels` and `_style_axes` set their own `ctx.fg()`/`ctx.dim()`, and
`_style_text` sets the chart-wide default so the two pieces of text nobody asks
for — the legend, and the title PowerPoint auto-generates for a single-series
chart — cannot fall through to the presentation theme's dark ink and disappear on
an `inverse` slide. The legend also takes the theme's face and the `caption` rung
rather than python-pptx's 18pt default.

Eleven per-type option frozensets drive the divergence, so a new type is added
by extending a set, never by branching on `spec.type`. A twelfth,
`_SIDE_LABEL_CHART_TYPES`, has its own section below:

- `_AXIS_CHART_TYPES` — everything except `pie`/`doughnut`/`pie-exploded`/
  `doughnut-exploded`, which have no category or value axis
  (`chart.category_axis` raises `ValueError` on one). The xy-scatter and
  bubble types all have both axes, so they join this set too.
- `_GAP_WIDTH_CHART_TYPES` — only the bar/column family (including their
  stacked variants); no other plot class exposes `gap_width` in python-pptx —
  not even the xy-scatter and bubble plots.
- `_PIE_FAMILY_CHART_TYPES` — `pie`, `doughnut`, `pie-exploded` and
  `doughnut-exploded`: one series, coloured per point from the categorical
  palette, named by `show_category_name` rather than a legend or axis.
- `_STRUCTURAL_GRIDLINE_CHART_TYPES` — `radar`, `radar-filled` and
  `radar-markers`: their major gridlines are the rings and spokes the data
  is plotted against, so `_style_axes` leaves them at python-pptx's own
  default instead of driving them from `theme.chart.grid` like every other
  axis-bearing type.
- `_NO_DATA_LABEL_CHART_TYPES` — the 5 `xy-scatter*` variants. python-pptx's
  `CT_ScatterChart` lists `c:dLbls` in its tag sequence but never wires up the
  descriptor, so `plot.has_data_labels` raises `AttributeError` for every
  scatter variant; `add_native_chart` skips the data-labels call for these
  types entirely. `CT_BubbleChart` does define it, so `bubble`/`bubble-3d`
  keep their labels like any other type.
- `_MARKER_CHART_TYPES` — `line-markers` (+ its two stacked variants),
  `radar-markers`, and `xy-scatter`/`xy-scatter-lines`/`xy-scatter-smooth`:
  the types python-pptx itself renders with an auto/default marker, themed
  from `theme.chart.marker_size`/`marker_style` instead. Plain `line`,
  `line-stacked(-100)`, plain `radar`, and the two `*-no-markers` scatter
  variants explicitly render with **no** marker (python-pptx writes
  `<c:symbol val="none"/>` at creation) — forcing one on would fight the
  type's own declared identity. `radar-filled`'s `radarStyle="filled"`
  suppresses a marker regardless of what's set (confirmed by forcing one and
  rendering it — nothing appears). Bubble series inherit `.marker` too, but
  `CT_BubbleSer`'s real schema has no marker child; a bubble's own
  size-driven circle is already its marker.
- `_STROKE_CHART_TYPES` — every `line`/`radar`/`xy-scatter` variant, marker or
  not (14 types). A point on these has no fillable shape of its own — only a
  stroke and, on some types, a marker — so `_fill_point` forces a solid fill
  here regardless of `theme.chart.gradient`: a gradient stored on a shape
  nothing draws is confirmed-invisible (rendered and inspected pixel by
  pixel) and costs two gradient-stop elements for nothing. `bubble`/`bubble-3d`
  are excluded — a bubble's point *is* a visible filled circle, so its
  gradient stays meaningful.
- `_PERCENT_AXIS_CHART_TYPES` — the 5 `*-stacked-100` types. `_style_axes` forces
  a `0%` tick format on the value axis, and `_number_format` drops the series'
  `unit` — an axis already reading in percent has nothing left for a suffix to add.
  The `0%` wins over the unit format: the share is what the renderer computed.
- `_SERIES_FILL_CHART_TYPES` — `area`, `area-stacked`, `area-stacked-100` and
  `radar-filled`: one continuous band per series rather than a mark per point, so
  gradient and shadow are applied to the **series** through `_fill_series`, not
  point by point.
- `_HORIZONTAL_BAR_CHART_TYPES` — `bar`, `bar-stacked` and `bar-stacked-100`.
  Their bars run the other way, so `theme.chart.gradient_angle` is rotated a
  quarter turn and the gradient still runs along the bar rather than across it.
- `_CONNECTED_CHART_TYPES` — every type but `xy-scatter`, which is points and
  nothing else. The rest take a themed stroke; giving one to a pure scatter would
  draw a line through data chosen to have none.

Marker fill always takes the series' own colour from the categorical palette
(`_style_marker`, called once per series) rather than a fixed colour, so a
themed marker matches its line instead of introducing a new one.

Editable in PowerPoint (Edit Data), animatable by category or by series,
vector at any zoom, and its labels are real text — visible to a PDF text
extractor and `qa`'s overflow check, unlike a screenshotted image would be.

## Chart build animation

A native chart's own build — bars arriving one category at a time on click,
rather than the whole chart appearing at once — is the slide-level `animate:`
field, same field as any other component's click build:

```yaml
title: Adoption climbs every quarter
animate: by_category    # or by_series
place:
  - at: {cols: full}
    chart:
      kind: column
      data:
        - {category: Q1, value: 12}
        - {category: Q4, value: 91}
```

`by_category` and `by_series` map to `add_chart_build`'s `by="category"` /
`by="series"`, which the `chart` component calls directly on the chart
`graphicFrame` — this is a different OOXML mechanism from the `<p:bldP>`
visibility toggle every other component's `animate:` uses
(`one_at_a_time`/`together`), because a chart is a `graphicFrame` build
(`<p:bldGraphic>`/`<a:bldChart>`), not a shape-visibility one. Asking for either
value on a non-chart component is rejected rather than silently downgraded. See
`docs/pptx-deck-building.md`'s Animations section for the OOXML and the
verification caveat.

**Keynote does not play a chart build.** The same file that builds one category per
click in PowerPoint shows the chart whole in Keynote — `<p:bldGraphic>`/`<a:bldChart>`
is the one construct here with a known consumer gap. For a Keynote audience use
`animate: together`, or split the categories across slides.

**Not every kind can build by category.** `_BUILDABLE_BY_CATEGORY` in
`charts/model.py` names the ones that can, and `by_category` on anything else
raises. A category build reveals one category's marks per click, so it needs the
category to *be* a mark: a bar, a wedge, a point on a line. On a radar the
categories are vertices of one closed outline — filled, they are a single
polygon — so the build emits a click per category and nothing moves. Observed in
Keynote on `radar-filled`: six clicks, no change. This is the same refusal
`_HIGHLIGHTABLE_KINDS` makes, for the same reason.

`by_series` is not restricted: every kind has series, and a chart with one series
builds in a single click, which is honest rather than dead.

## Room for the labels a bar chart sets on its left

A bar chart's category labels run down the left of the plot, and nothing in the
file says how much room they get — so each renderer decides. LibreOffice shrinks
the plot area to fit them; Keynote does not, and a long label runs off the slide.

`_reserve_label_column` writes an explicit `c:manualLayout` on the plot area,
sized from the longest label at the caption rung, floored so the bars keep at
least `_MIN_PLOT_FRACTION` of the frame. Every renderer honours a manual layout,
so the reservation is stated once, in the file.

Only the bar family (`_SIDE_LABEL_CHART_TYPES`) gets one. A column chart's labels
sit *under* the plot, in width they already have, and pinning its plot area would
take room away for nothing.

## Negative values, and why the render cannot check them

**A bar or column chart carrying negative values writes correct OOXML and renders wrongly
through the path `render` and `qa` both use.** The bar is drawn on the *positive* side at
its absolute length, and its data label loses the minus sign — while the value axis
correctly scales to include the negatives.

What was measured, so nobody re-investigates it:

| | |
|---|---|
| The chart's own `numCache` | holds `-146.0` |
| Its embedded workbook | holds `-146` |
| `c:crosses` | `autoZero`, and no `min`/`max` is pinned |
| Stripping `c:dPt`, or setting `invertIfNegative="0"` | changes nothing |
| The same chart built with **bare python-pptx** | renders identically wrong |
| A **line** series with the same values | renders correctly, sign and all |

So the file is right and deckwright is not implicated: LibreOffice 26.2.5.2 plots and labels
the absolute value of a `barChart` datapoint. PowerPoint is expected to draw it correctly;
the contact sheet you check it on will not, and neither will `qa`. The documented workflow
for every other chart — build it, render it, look at it — is the one thing that cannot
settle this one, so `qa` raises a `chart-negative` warning saying exactly that.

So for a diverging comparison, reach for
[`diverge`](components.md#diverge--signed-bars-either-side-of-a-centre-rule) instead. It
draws the same shape as geometry rather than as a chart, which renders identically
everywhere, at the cost of not being an editable chart object in PowerPoint.

A chart whose values are all positive is unaffected.

## Where the legend and the labels go

A legend goes **under the plot** on every kind but the bar family, which reserves a
column beside its category labels instead (below). A mid-right legend costs a quarter of
the frame's width and leaves the plot crowded against it; under the plot it costs one
line of height.

On the line and scatter kinds a data label sits **above** its point. The theme's
default `label_position` is `outside_end`, which is a bar position — a line has no bar
end, so the label lands on the point it names and collides with its own marker. A theme
that names a position the kind can honour keeps it.

**A position is written only where the chart group offers one.** `inside_end` reaches the
bar family and a pie; area, doughnut and radar take no position at all, and writing one
into those parts is what makes PowerPoint ask to repair the file.

## Room the legend takes

A legend sits to the right of the plot, so on the bar family — where the plot area is
pinned by hand so the left-hand category labels fit — the same manual layout measures
a column for the longest series name. Both columns come out of one budget, and the
plot never drops below 45% of the frame however long the words are.

The legend is also taken out of the plot's layout (`c:overlay` off). Left at
PowerPoint's default it is drawn *over* the plot, which a manual layout cannot then
account for — that is what put a legend on top of its own bars.

## The places a data label prints

The places are read off the data: the most any plotted value carries, so a series of
`11.2, 9.6, 5.1, 4.8` labels to one place and a series of whole numbers labels to none.
Values past four places are taken as arithmetic noise and capped.

`decimals:` overrides that in either direction — `0` rounds a noisy series back to
whole numbers, `2` pads a mixed series to a fixed width.

The `*-stacked-100` kinds are no exception. Their *axis* shows the share the renderer
computed, but each data label still prints that series' own authored value, so a
stack of `11.2` and `88.8` labels those two numbers and needs its decimal place like
any other chart. What those kinds do drop is `unit:` — the axis already reads in per
cent, so a `%` on the label would be a second sign.

The places have to be written into the format code because `unit:` is a quoted
literal (`0.0"%"`) rather than Excel's `%` code — a quoted suffix cannot ride on a
general format, so a format with a unit and no places stated is a format that rounds.

## Turning one series' labels off

`plot.has_data_labels` and `plot.data_labels` are the whole plot, so the theme's label
settings arrive all-or-nothing. `labels:` names the series that opt out, and
`_hide_series_labels` writes a `c:dLbls` carrying `showVal="0"` on that `c:ser`: a series'
own element overrides the plot's, and it is the only place the dissent can be stated.

The suppressed series keeps its stroke, its palette colour and its legend entry — only the
numbers go, which is what a benchmark line wants.

python-pptx exposes `series.data_labels` on the five category series classes and on neither
`XySeries` nor `BubbleSeries`. The block's refusal covers that: those kinds, like the
`value:` shorthand, fold their rows into a single unnamed series, and `labels:` addresses
series by name.

## The unit reaches the axis too

A `unit:` says what the numbers are, and that is as true of the scale as of the values on
it. `_number_format` computes one code and `_style_axes` puts it on the value axis, so a
line whose points read `11.2%` sits against ticks reading `0.0%` rather than a bare `0-12`.

The axis takes the format **only when the chart carries a unit**. Places and digit grouping
are label-scoped by design, and pinning a code with no unit would print `12.0` for a tick
the renderer would otherwise draw as `12`. With no unit the ticks stay the renderer's to
choose.

## Refusing a truncated axis

`y_min` / `y_max` reach the native chart's value axis directly. Set them
explicitly to stop auto-scaling to the data's own min/max — the same
auto-scale that can make a 12-point move look identical to a 90-point one.
Leaving both unset keeps automatic scaling.

## The categorical palette

Multiple series (or wedges on a pie/doughnut/pie-exploded/doughnut-exploded)
cycle the palette's accent ramp — `accent-1`…`accent-N`, counting only the
accents a theme genuinely binds — so each is visually distinct without a legend
doing all the work. `highlight` overrides whichever colour the cycle assigns to
that one category with the second accent. A single series stays `accent-1`; the
ramp only engages once colour has to carry a distinction between two or more
series or wedges. Keep an example inside the theme's accent count: past it the
cycle repeats, and two series share a colour.

## Adding a new chart type

1. Add it to `ChartSpec`'s `_TYPES` in `charts/model.py` — a type outside this
   set never reaches the renderer. If its data shape isn't one value per
   category, add it to `_XY_CHART_TYPES` or `_BUBBLE_CHART_TYPES` too, so
   `_shape()` and the `points`-vs-`values` validation pick it up.
2. Map it to an `XL_CHART_TYPE` in `charts/native.py`'s `_CHART_TYPES` — 29 of
   `XL_CHART_TYPE`'s 73 members are creatable through python-pptx; the other
   44 raise `NotImplementedError`.
3. Measure the new type against each of the twelve option frozensets in
   [The native renderer](#the-native-renderer) before assuming it matches its
   family — `gap_width` and `has_data_labels` are both silent no-ops or raise
   `AttributeError` on the wrong plot class, so a wrong guess here fails
   quietly rather than loudly. Build a real chart of the type and probe it
   directly rather than reasoning from the plot class's name.
