# Placement — `at:` resolves to a rect

How `layouts/place.py` turns a placement's `at:` mapping into an inch rectangle,
and what it refuses; and how `layouts/chrome.py` places a slide's chrome lines.
This doc covers the **engine's internals**: the three `at:` forms, the
reserved-region edge rule, and the chrome bands.

**To write `at:` in a deck spec, read [`docs/authoring.md`](authoring.md)
instead** — it owns the wire format and the error messages an author sees.

---

## Table of Contents

- [The three forms](#the-three-forms)
- [`align` and `anchor`](#align-and-anchor)
- [The content band](#the-content-band)
- [Clearing a corner wedge, per placement](#clearing-a-corner-wedge-per-placement)
- [Chrome bands](#chrome-bands)
- [What is rejected](#what-is-rejected)

## The three forms

| Form | Units | Resolves against |
|---|---|---|
| `cols: <name>` | a named fraction — halves and thirds | `Grid.col_x` / `Grid.span_w` |
| `cols: {from, to}` | whole column indices, half-open | `Grid.col_x` / `Grid.span_w` |
| `rows: <name>` \| `{from, to}` | the same over `Grid.rows` | the content band passed in as `area` |
| `box: {x, y, w, h}` | percents of the whole canvas | `Scale.x` / `Scale.y` |

A placement carrying `split:` is expanded by the spec layer into one placement per
child, each holding a `Share` — the band, its index in it, how many shares it takes,
and how many there are. The band stays unresolved until `_col_span` meets the grid,
because whether the shares are whole column spans or an even division of inches
depends on the theme's `columns:`. `_share` takes the first branch whenever the band
divides, so a four-way split is bit for bit the `cols:` spans it replaces.

`rows` is optional and only pairs with `cols`; without it a span fills the
`area` top to bottom. The 12 rows divide the **area passed in**, not the canvas:
for a body placement that is the content band, so a row never reaches above
`body_top` or below the bottom margin. `box` is the escape hatch and combines
with neither. It is measured against the **canvas**, not the content band, which is
what makes it an escape: a box may sit above `body_top` or below the bottom margin,
reaching parts of the slide the grid deliberately cannot. It must still land on the
slide, and still clears reserved regions, unless it declares `bleed: true`.

That asymmetry is the point. A `cols`/`rows` placement is carved out of the content
band and is checked against it; a `box` is coordinates the author wrote, and holding
those to the band meant no box could reach the top fifth of a slide even when its
title had been moved away.

## `align` and `anchor`

A placement also carries `align` (`left` | `center` | `right`) and `anchor`
(`top` | `middle` | `bottom`), defaulting to `left`/`top`. They reach a component
as `ctx.text_align()` and `ctx.text_anchor()`, describing how it sets its text inside
the rect.

**`anchor` also moves what the placement drew.** The rect never moves, but a component
whose content is shorter than its rect leaves slack, and `compose._settle` translates
every shape it drew so that extent sits where `anchor` says in the rect — then patches
the manifest boxes to follow. So a one-line `prose` in a band from 2.1in to 5.7in on a
7.5in canvas lands at:

| `anchor` | Top of the text | Down the canvas |
|---|---|---|
| `top` (default) | 2.10in | 28% |
| `middle` | 3.77in | 50% |
| `bottom` | 5.43in | 72% |

A tall band therefore does **not** centre its content by itself: the default is `top`,
and the content sits at the top of the band however deep the band is. Reach for
`anchor: middle` rather than narrowing the band to fake it.

A component that sets no text of its own (`chart`, `connector`, `document`, `panel`)
refuses a non-default value via `_shared.require_default_align()`, and `callouts` refuses
`align` because its rows are set flush to the dot rail. Accepting them silently
would leave an author looking at a slide that did not move with nothing to read
that says why.

## The content band

`content_rect()` starts inside the margins at `body_top`, drops to `_CHROME_GAP`
(4% of canvas height) below the chrome stack when the chrome reaches further than
that, then applies each reserved region:

- spans the band's full **width** — cuts from whichever horizontal edge it
  reaches (a top banner pushes the top down, a footer band lifts the bottom).
- spans the band's full **height** — cuts from a vertical edge (a left or right
  rail moves that side in).
- spans neither — a corner wedge — leaves the band alone. It is enforced per
  placement instead (below), so a short body keeps the full content width.

A region covering both axes, or one that leaves nothing, is a `ThemeError`.

## Clearing a corner wedge, per placement

`clear_reserved()` narrows a **grid-derived** rect horizontally until it clears
every region it touches, keeping one gutter's clearance. Only the rect's own
vertical extent counts, via `Reserved.x_span()`: a placement bounded by `rows:`
above the wedge keeps the full content width, while a full-height one gives up
the columns the diagonal reaches into. A region reaching in from both sides
raises, naming the region — there is nowhere left to step aside to.

This is what keeps `at: {cols: full}` — the commonest placement there is —
usable under a brand that reserves a logo corner: every full-height placement
reaches into a brand's logo wedge, so rejecting rather than narrowing would make the
theme unusable.

A `box:` is never narrowed. It is exact geometry the author stated outright, so
moving it would be a lie about what was asked for; it meets the reserved regions
in `check_placements` instead and raises.

## Chrome bands

`chrome_bands()` places whichever of `CHROME_ORDER` (`kicker`, `title`,
`subtitle`) the slide carries, and returns a `ChromeBand` each. Every field has a
`ChromeField` — the theme's `chrome:` block, with the slide's `chrome:` merged key
by key over it — and the field decides which of two paths the line takes:

| `ChromeField` | Where the band lands | `stacked` |
|---|---|---|
| no `at:` | down from the top margin, in `CHROME_ORDER`, at the content width | `True` |
| `at: {box: …}` | exactly there, in canvas fractions | `False` |
| `at: {cols: …}` alone | that column span's x and measure, sized to the wrapped text — but keeping its place in the stack, so three fields narrowed to the same columns are three lines down the page, not three drawn over each other | `True` |
| `at: {cols: …, rows: …}` | that span, `rows` dividing **the whole canvas** | `False` |

A chrome `at:` resolves against the whole canvas, not the content band — chrome is
what defines where the band starts, so it cannot be measured from it. No absolute
inch appears anywhere: a chrome box outside 0..1 on either axis is a `LayoutError`
naming the fractions it should have been, which is what catches an inch value
pasted in from a measured deck.

A field may also name a `rung:` (any type-ramp role, so a cover title can be set
at `display` without moving the theme's `title` rung), a `pair:` (any declared
palette pair, so a line reversed out of a painted panel takes that panel's ink) and
an `ink:` (a bare role, when the ink is all that moves). Neither colour key is safe
by construction: `compose` re-measures the ink it settles on against what the slide
**actually painted** behind the band, and raises when that falls below the ratio the
band's size needs. A pair being contrast-checked at palette construction says
nothing about the panel or photograph the line really lands on.

`anchor` needs a frame of its own, so setting it on a field with no `at:` raises:
stacked lines share one frame. A cols-only field carries an `at:` and so passes
that check, but it is still stacked and still shares its run's frame — the anchor
has nothing of its own to act in.

A band is `LINE_HEIGHT ×` its point size tall **per wrapped line**, not per
field: `utils.text.wrapped_lines()` estimates how many lines the text takes at
the band's width, so a 60-character title reserves two lines and the subtitle
under it starts two lines down. Sizing every band at one line puts a wrapping
title straight through the subtitle, and nothing downstream can see it —
`check_placements` never receives the chrome, and QA's `bounds` and `overflow`
both pass on a slide whose chrome is illegibly doubled up.

`content_rect()` derives the content band's top from the **stacked** bands only.
A placed line is exact geometry like a `box:` placement: it may sit beside the
body or over it, which is what a column title and a title on a colour panel need.
`content_rect()` raises when the stack leaves no band at all.

### Chrome is drawn last

`render_slide()` *places* chrome first — the content band starts below the stacked
lines — but *draws* it after every placement, so a title told to sit on a painted
panel lands on top of the panel rather than under it. Chrome is never animated, so
moving it to the end of the z-order changes no reveal.

### The wrap estimate, and why chrome is one frame

`wrapped_lines()` is an estimate, but a measured one. Each call routes the face the
text will be set in to a per-character advance table baked in `utils/_metrics.py`
from real font metrics — Calibri/Carlito, Arial/Helvetica and the brand faces
`MEASURED_FAMILIES` lists have tables of their own (bold folded into a per-character
max), and any face without one gets the conservative `CEILING` table. The summed width carries a single
small safety margin (`_MARGIN` in `utils/text.py`) for what per-character summation
cannot see: kerning, hinting, renderer spacing. It errs long by design — a band
sized one line short of its text draws over what sits below it — but only by that
margin, so a reserved line the render does not use is the rare case, not the rule. A
single word too long for its line is the exception: it breaks where its real width does.

`compose._write_chrome()` then writes the **stacked** chrome lines into a text
frame per run of consecutive bands sharing a measure, one paragraph each, rather
than one box per band. That is the belt to the estimate's braces: if a renderer
wraps a title wider than estimated, paragraph flow carries the subtitle down the
frame instead of drawing it through the title's last line. Only lines of the same
measure can share, so a field narrowed to its own `cols:` starts a new frame. A
line placed with a `box:` or with `rows:` gets its own frame — that is what lets it
carry an `anchor`, and it has no sibling below it to run into.

## What is rejected

`check_placements()` raises `LayoutError` when a rect leaves the content band,
overlaps a reserved region (named), or overlaps another placement (both named).
Comparisons carry a 0.007in epsilon, so placements that merely share an edge are
a touch, not a collision. A placement declaring `bleed: true` is exempt from all
three — that is how a full-canvas image is expressed.

The label in every message is the `where` string the caller passed in;
`place.py` builds none of it, so `layouts/compose.py` owns slide and component
naming.
