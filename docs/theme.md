# The built-in design system

`deckwright` owns a complete design system that renders correctly against a **blank
presentation**. A template is an explicit override surface, never the source of the
theme — nothing is inferred at build time. Everything below lives in
`src/deckwright/theme/defaults.py` and is reachable as `from deckwright.theme import ...`.

To write a deck spec, read [`docs/authoring.md`](authoring.md); this doc is the
reference for what a spec gets *for free* when it names no template.

---

## Table of Contents

- [No template at all](#no-template-at-all)
- [What a theme file may contain](#what-a-theme-file-may-contain)
- [Colour: roles and pairs](#colour-roles-and-pairs)
- [Type: points at a reference height](#type-points-at-a-reference-height)
- [The face, and whether deckwright can measure it](#the-face-and-whether-deckwright-can-measure-it)
- [Geometry: fractions, not inches](#geometry-fractions-not-inches)
- [Chrome: the theme's title treatment](#chrome-the-themes-title-treatment)
- [Icons: the brand's own, or ours](#icons-the-brands-own-or-ours)
- [Motion](#motion)
- [Motion roles](#motion-roles)

## No template at all

```python
from deckwright.theme import load_theme

theme = load_theme()                                   # 13.333 x 7.5in
theme = load_theme(slide_w=26.666, slide_h=15.0)       # same system, twice the canvas
```

`load_theme()` with no path returns the built-in system with `theme.template is
None`. `blank_presentation(slide_w=..., slide_h=...)` builds the empty canvas it is
measured against — the grid is derived from the presentation's own EMU-rounded size,
so `theme.grid.slide_w` equals what the saved `.pptx` really holds.

A template-free `Presentation()` defaults to 10 x 7.5in, so the canvas is always set
explicitly. The built-in theme composes on its `Blank` layout, the one layout such a
presentation is guaranteed to offer.

A themeless theme carries no `marks:`, so an `inverse` slide has no art to lay down.
It is still painted: the compiler fills the slide with the `inverse` pair's own
background colour and draws that pair's ink over it. Art is an embellishment on a
painted surface, never the thing that makes the surface dark.

## What a theme file may contain

Thirteen top-level keys, and an unknown one is a `ThemeError` naming every known key —
a theme is not a place where a typo is silently ignored. Everything is optional except
`name`; a file with only a name is the built-in system under another label.

| Key | What it does |
|---|---|
| `name` | How a deck's `theme:` refers to it. |
| `template` | The brand `.pptx` this theme specializes into, relative to the theme file. Without one the built-in system stands alone: `bind:` then resolves literal colours only, and `marks:` is refused as having nowhere to look. |
| `compose_layout` | Names the layout generated slides compose on, for a template whose ambiguity ranking cannot resolve. The escape hatch, never a requirement — the ranking itself lives in `layouts/resolve.py`. |
| `drop_template_slides` | Delete the template's own slides after loading it. Almost always `true` for a brand template, whose slides are examples rather than content. |
| `bind` | Maps semantic roles onto the template's `clrScheme` slots, or onto literal `RRGGBB` values. Literals need no template. |
| `scale` | Margins, `columns`, `rows` and gutter. `rows` is the divisor a placement's `rows:` indexes — 12 by default, and stated here so an author can read the number they are indexing. |
| `type` | `face`, `heading_face`, `mono`, `reference_height`, `min_pt`, `line_weight_pt`, and per-rung `ramp` overrides written in `pt`. |
| `chart` | The chart renderer's aesthetic knobs — gap width, gradients, shadows, markers, gridlines, label position. See [`charts.md`](charts.md). |
| `chrome` | Where each chrome line sits and how it is set. |
| `icons` | A directory of `.svg` glyphs searched before the shipped set. |
| `marks` | Art laid over a painted backdrop. A mark's name *is* the background it decorates, so `marks.inverse` is the only one there is. Its `media:` resolves the same way a deck's image does — beside the template, then out of the template's own `ppt/media/` — and may not climb out of those with `..`; an absolute path is taken as written. |
| `reserve` | Polygons a placement may not intrude on — a logo wedge, a footer band. |
| `motion` | How the brand paces a reveal. See [Motion](#motion). |

Every block layers over the built-in system rather than replacing it: a theme restates
only what it wants to move, and everything it omits keeps the default below.

## Colour: roles and pairs

Twelve semantic roles. No brand words — `eyebrow`, `amber`, `deep`, `navy` and the
rest are one deck's vocabulary and appear nowhere in the system.

| Role | Hex | | Role | Hex |
|---|---|---|---|---|
| `page` | `FFFFFF` | | `inverse` | `12161B` |
| `ink` | `1A1D21` | | `inverse-ink` | `FFFFFF` |
| `muted` | `5F6672` | | `accent-1` | `1F5FA8` |
| `line` | `E3E6EA` | | `accent-2` | `0F6E63` |
| `surface` | `F2F4F7` | | `accent-3` | `A8431C` |
| `surface-ink` | `1A1D21` | | `accent-4` | `6A3FA0` |

**The pair is the unit.** A foreground may only be painted on a background it was
declared with, so a component never invents a combination nobody vetted. Every pair is
measured against WCAG AA (4.5:1) when the `Palette` is constructed, and a shortfall is
logged as `theme_pair_below_aa` — **it does not refuse the theme.** A real brand file
whose own accent cannot carry AA text would otherwise be unusable, and the decision
belongs where it can be made properly: [`deckwright qa`](qa.md) judges contrast against
what was really painted, including the photograph a pair of nominal colours cannot see.

| Pair | fg on bg | Ratio |
|---|---|---|
| `page` | `ink` on `page` | 16.91:1 |
| `page-muted` | `muted` on `page` | 5.78:1 |
| `surface` | `surface-ink` on `surface` | 15.35:1 |
| `inverse` | `inverse-ink` on `inverse` | 18.16:1 |
| `accent-1` | auto ink on `accent-1` | 6.44:1 |
| `accent-2` | auto ink on `accent-2` | 6.12:1 |
| `accent-3` | auto ink on `accent-3` | 6.03:1 |
| `accent-4` | auto ink on `accent-4` | 7.42:1 |

`line` carries no pair — it is a stroke, never a text colour. An accent pair's
foreground is `AUTO_INK`: whichever of `ink` and `page` reads better on it. An
accent none of them clears falls back to black or white, so a pair always resolves.

**An accent is a fill colour, and becomes text only where it is measured.** A slide's
live pair is the one its `background:` names, and `SlideCtx.fg()`/`dim()`/`paper()`
all read off it. An accent role has no pair at all — nothing declares it readable as
text on anything — so:

| Call | Returns |
|---|---|
| `accent_on(bg, size_pt=…, name=…)` | the accent when it clears `required_ratio(size_pt)` against `bg`, else `ink_on(bg)` |
| `accent(size_pt=…, name=…)` | the same, measured against the slide's own paper |
| `ink_on(bg)` | whichever of `ink` and `page` reads on an arbitrary fill — the choice `AUTO_INK` makes for a declared pair |
| `color(role)` | the unguarded read, for fills and strokes |

`required_ratio` is `AA_LARGE` (3:1) from 18pt up and `AA_NORMAL` (4.5:1) below —
the same rule QA's contrast check applies, so a component cannot pick a colour QA
will then warn about.

**The background is whatever the component actually painted.** A stat tile is filled
with `line`, so its text measures against `line`, not against the slide. Getting this
wrong is what produced accent text at 2.2:1 inside a light tile on a white page,
where the slide-level measurement said the accent was fine. Text a component sets straight
onto the slide is measured the same way, against what is painted under its own box: prose
laid over a `panel`, a table on an inverse band, a caption over a scrimmed picture, a chart's
labels, axis text and legend over a panel. Every component that paints a fill — a panel, a
card, a disc, a `versus` or `fanout` plate, a `diverge` bar, a `grid` bar — counts as what is
under a later placement laid over it with `bleed: true`. A disc covers only its inscribed
square; text in the corners of its frame is also measured against what the disc was laid on.
`text_ink(box, size_pt=…, muted=…)` and `accent_at(box, size_pt=…)` return the ink and the
colour it really sits on, and that pair is what the manifest records. A component painting a
fill nothing readable sits on gets a `ThemeError` naming the fill, not a warning.

A pair names **roles**, not hex: `DEFAULT_PAIRS` holds `("ink", "page")`, and
`build_palette` resolves it. Rebinding a role therefore moves every pair citing it,
instead of leaving a stale copy of the old colour behind.

`DEFAULT_PALETTE.accents` is a tuple of **role names** in use order, not hex, so a
binding that repoints `accent-1` moves everything that cycles the ramp with it.

**The ramp is never shorter than four.** A theme's `bind:` layers over the built-in
roles rather than replacing them, so it can repoint an accent or declare a fifth, but
it cannot remove one: an accent nothing binds — or one bound to a slot still holding
Microsoft's shipped value, which is ignored — keeps its built-in hex. Series colours
cycle whatever that leaves, which is four roles on a template that binds none.

The consequence worth knowing is that a chart's `highlight:` is `accent-2`. Derive a
theme from a template that yields only `accent-1` and the highlighted point is painted
`0F6E63` — deckwright's own colour, sitting in a chart otherwise drawn in the brand's.
Bind every accent you want a chart to cycle, or read the highlight as a system colour.

### What the template already paints

A `bind:` value is a template slot name **or** a literal `RRGGBB`. The literal is
there because a template's real surface need not be in its `clrScheme` at all: every
one of the sixteen sample templates declares a background on its master, and two of
them paint a photograph. A palette bound only to scheme slots describes a page that
is not on the slide.

**Literals need no template.** A theme naming no `template:` is a colour palette of
its own — the fastest way to a deck that is not in deckwright's navy:

```yaml
name: tidewater
bind:
  page: '10212A'
  ink: F2F5F7
  muted: A8B2BD
  inverse: F2F5F7
  inverse-ink: '10212A'
  accent-1: E4572E
  accent-2: '17BEBB'
```

Note that `muted` and `inverse` moved with `page`. The defaults are tuned for a light
page. Inverting the page alone leaves `page-muted` below AA, which the load logs as
`theme_pair_below_aa`. It also leaves the default `inverse` (`12161B`) so close to a dark
page that every inverse plate disappears into it, which the load logs as
`theme_inverse_matches_page` once the two are within 3:1. Neither refuses, since `qa`
judges what was really painted. On a dark page, `inverse` is the light surface, so its
ink has to be dark.

A slot name in that theme is refused, since there is no `clrScheme` to name a slot in.
An accent bound to a *slot* still holding Microsoft's shipped value is ignored — that
slot says the brand set no accent there — but a literal is what you typed and is kept
whatever it equals.

Every role you leave out keeps its system default, so a palette can be two lines. A
`type: {face: …}` beside it sets the faces — but name one this machine has not got and
`qa` reports `font-substituted` and declines to judge the render, because what it
measured is not what your audience will see.

`inherited_surface` resolves what the composed layout will really show — a `bgPr`'s
own fill, or a `bgRef` indexed into the theme's `bgFillStyleLst` with its colour
standing in for `phClr` — and the result reaches the deck as `Theme.surface`:

| The template paints | deckwright does |
|---|---|
| a picture | leaves it, and samples its pixels behind every line |
| a colour the palette calls `page` | nothing; the promise is already kept |
| any other colour, or nothing at all | paints `page`, so what renders is what the palette declared |

The page is not painted *only* when the template has already laid down that exact
colour. Assuming a master carries the page colour is what put a deck of dark titles
on a dark blue photograph with the contrast check reporting nothing wrong.

**A line crossing an edge is measured against the worse side.** Whatever was painted
last over the whole of a line's rectangle replaces what is beneath it, in paint order
whichever kind each is, so a picture laid over a panel is what the line sits on.
Something covering only part of it is one more surface that line crosses, and the
reported paper is whichever of them reads worst against the ink being tried. Either
single answer is wrong in one direction — report the page and white ink passes while
half the line is lost on a dark panel; report the panel and dark ink passes while half
is lost on the page.

Where no ink reads across the whole of it, the line is given a plate of the slide's own
paper. An ink the
author asked for by name never moves — it raises instead.

## Type: points at a reference height

**A theme writes point sizes.** `body: {pt: 16}` is 16pt on a canvas
`type.reference_height` inches tall — 7.5in unless the theme says otherwise, which is
the 16:9 slide almost every deck is.

```yaml
type:
  reference_height: 7.5
  ramp:
    body:  {pt: 16}
    title: {pt: 34}
```

What the engine keeps is the **rung**: points per inch of canvas height, `pt` divided
by `reference_height`. Height is the right normalizer — a 4:3 10x7.5in deck and a 16:9
13.33x7.5in deck are viewed at the same physical size and take the same type size,
which a width-based rule gets wrong by 33%. So the ramp still scales with the canvas;
only what an author writes changed, because "14pt body" is the thing they mean and
`2.1333` is not.

`min_pt` and `line_weight_pt` are read the same way.

`DEFAULT_RAMP` is modular — `2.13 * 1.25 ** step` — so the whole ramp moves with one
number. `caption` takes a half step: a `kicker` is bold and set in caps, and a caption — the
rung a chart's axis, a code listing, a stat's label and a citation are set at — is neither,
so one size for both left the caption the smaller of the two to read.
`TypeStyle.rung` holds the rung; `TypeStyle.size` returns resolved points.

| Rung | Value | at 7.5in | at 15in |
|---|---|---|---|
| `kicker` | 1.704 | 12.8pt | 25.6pt |
| `caption` | 1.9051 | 14.3pt | 28.6pt |
| `body` | 2.13 | 16.0pt | 31.9pt |
| `lead` | 2.6625 | 20.0pt | 39.9pt |
| `subtitle` | 2.6625 | 20.0pt | 39.9pt |
| `head` | 3.3281 | 25.0pt | 49.9pt |
| `title` | 4.1602 | 31.2pt | 62.4pt |
| `stat` | 4.6512 | 34.9pt | 69.8pt |
| `display` | 5.2002 | 39.0pt | 78.0pt |
| `hero` | 6.5002 | 48.8pt | 97.5pt |

These ten names are the complete vocabulary; a spec may not name a rung outside it.
`kicker`, `head`, `title`, `stat`, `display` and `hero` are bold; `subtitle`, `title`,
`stat`, `display` and `hero` render in the heading face. A theme's own `ramp:` entry
inherits both for its rung — `title: {pt: 34}` resizes the title without un-bolding
it — and states `bold:` or `face:` to override. The minimum readable size is
`MIN_RUNG_DEFAULT = 1.40` — 10.5pt at 7.5in — and `Theme.min_pt` holds it resolved.

A rung's `face:` names one of the theme's own faces by role — `face: body`, `face: heading`,
`face: mono` — or a literal typeface. The three aliases are the whole vocabulary; a value
matching one only in case (`face: Mono`) is a literal, and warns as
`theme_ramp_face_alias_case` because no machine has a typeface by that name.

A figure-heavy deck can give `stat` — and `caption`, for axis-style labels — the mono face.
Numerals then align in a column and read as measurements rather than display type. This is a
suggestion, not a rule: it suits decks whose slides carry figures, and reads as an affectation
on decks that do not.

```yaml
type:
  mono: IBM Plex Mono
  ramp:
    stat: {pt: 34, face: mono}
```

The built-in faces are body `Helvetica`, headings `Helvetica`, monospace `Courier New`.
A theme's own `type: face` / `heading_face` / `mono` overrides them; failing that, a
template's `fontScheme` supplies the face — which is why a theme derived by `conform`
counts the faces its slides really use rather than trusting that scheme.

Those defaults are chosen to survive the trip to another machine. A `.pptx` names one
face and the viewer substitutes whatever it has, so the only safe names are the ones
that land on a metric clone everywhere a deck gets opened: Helvetica is native on
macOS/Keynote, mapped to Arial by Windows Office, and Liberation Sans under
LibreOffice; Courier New is native on macOS and Windows, and Liberation Mono under
LibreOffice. **Never default to a Microsoft-only face** — Calibri, Aptos and Consolas
have no counterpart off Windows, so they substitute to something unrelated without
saying so.

## Where the built-in theme lives

`base.yaml` ships **inside the package**, at `src/deckwright/theme/builtin/base.yaml`,
and nowhere else. A checkout has no copy of it in `templates/`.

A `theme:` name resolves against the theme directory first (`templates`, or
`DECKWRIGHT_THEME_DIR`) and falls back to the packaged built-ins — which is why
`theme: base` works from an installed wheel with no checkout anywhere near it. A file
of the same name in the theme directory always wins, so a brand theme can be called
`base` if you insist.

**Do not edit it to make a brand theme.** You would be editing the file that ships in
the wheel, and the next install replaces it. Derive one instead:
`deckwright conform templates/<brand>.pptx --adopt <name>`, which writes
`templates/<name>.theme.yaml` — gitignored, because it carries a client's palette.

## The face, and whether deckwright can measure it

Every wrap decision in a build — how deep a callout row is, whether a table row needs a
second line, whether a title costs the body some height — is computed from the face's own
per-character advances. deckwright ships those advances for these families:

| Family | Covers |
|---|---|
| Calibri / Carlito | Calibri, and the metric clone LibreOffice substitutes for it |
| Arial / Helvetica / Liberation | Arial, Helvetica, and the clone that stands in for both |
| Poppins, Open Sans, Montserrat | the families of those names |
| Amatic | Amatic and Amatic SC |
| Sniglet, Bebas Neue | the families of those names |
| Barlow Semi Condensed | that cut only — plain Barlow is wider and is not covered |

A face outside those is laid out against `CEILING`, the widest advance measured across
Carlito, Liberation Sans, Verdana and DejaVu Sans, per character. For a face no wider than
those it is safe: a box is never sized *short* of its text. A wide display face can outrun
it (Sniglet's ExtraBold does, which is why it has a table), and for every face it is loose
in a way nothing downstream reveals, so the theme loader says so:

```
warning  theme_face_unmeasured  theme=brand role=heading_face face='Aptos Display'
```

A fit refusal built on that estimate — `prose`, `card`, `versus`, an `ellipse` label, a
chrome box too short for its text — ends by saying so, so a refusal of copy that would have
fitted names its reason:

```
... split the slide or shorten the copy ('Segoe UI' has no width table, so this estimate errs wide)
```

**A heavy or black weight is unmeasured on purpose.** Its advances are wider than the
regular's, so the ceiling is the honest answer rather than a table that would under-size
every line.

### `theme_face_unmeasured` and `font-substituted`

One is about the width tables deckwright ships, the other about the fonts the machine has.
They take different fixes.

| | `theme_face_unmeasured` | `font-substituted` |
|---|---|---|
| Where it shows | a build warning, from the theme loader | a `deckwright qa` finding, severity WARN |
| What is wrong | deckwright ships no advance table for the face | the face is not installed on the machine that rendered |
| What it costs | wrap estimates fall back to the loose `CEILING` width | the render, and every finding drawn from it, shows a typeface the deck does not carry |
| What fixes it | name a measured face, or accept the slack | install the face here, or read `overflow` and `render-contrast` as approximate |

A face can hit either, both, or neither. The build warning covers `face` and
`heading_face`; the QA check covers every face the theme names, `mono` and any per-rung
`face` included. `font-substituted` says nothing when fontconfig cannot be asked — no
`fc-list` on the machine is an absent answer, not a clean one.

### A face that is not a face

OOXML lets a run name `+mj-lt` or `+mn-lt` instead of a typeface — a reference meaning
*whatever the template's font scheme calls major latin*. `deckwright conform` resolves those
against the template's own scheme before deriving a face. A theme adopted before it did
carries the reference itself, which no renderer resolves, so the deck sets its type in a
string and every machine substitutes. `load_theme` warns as `theme_face_scheme_reference`,
names the key and the token, and falls back to the template's scheme entry; re-adopt the
template to settle it.

### The three machines a face has to survive

The face named in a theme is a *request*. Whether it renders is a property of the machine
opening the file, and there are three machines in play: the one that measured the layout,
the one that rendered the contact sheet you checked it on, and the one your audience
opens it with. A face that is unmeasured *and* uninstalled means all three disagree — the
build reserves ceiling-width space, the renderer substitutes something narrower, and the
viewer substitutes something else again. Text that overlaps for your reader and not for
you is this, every time.

So a deck face wants to be both **measured** by the table above and **installed** where
the deck will be opened. On macOS, Helvetica is both; Aptos and Calibri are frequently
neither, whatever the template's own `fontScheme` says.

## Geometry: fractions, not inches

`default_grid(scale)` returns a `Grid` whose fields are fractions and whose
read-backs are inches. Horizontal fractions are of the width, vertical of the height.

| Fraction | Value | at 13.333x7.5in |
|---|---|---|
| left / right margin | 0.055 of width | 0.733in |
| top / bottom margin | 0.060 of height | 0.450in |
| gutter | 0.014 of width | 0.187in |
| `body_top` | 0.22 of height | 1.650in |
| columns | 12 | `col_w` 0.818in |

Corpus margins run 4.4%–14.6% of slide width, so no universal value exists; the
system default sits near the low end and a theme's `scale:` block overrides it.
Doubling the canvas doubles every inch — a change of slide size is a no-op.

A theme YAML's `scale:` block is an override, key by key: omit `gutter` and the
built-in gutter applies, omit the block entirely and the whole built-in grid does.

## Chrome: the theme's title treatment

A theme's `chrome:` block says where each chrome line sits and how it is set. Omit it
and all three stack from the top margin at the content width — the built-in default.

```yaml
chrome:
  kicker:   {at: {box: {x: 0%, y: 5.5%, w: 100%, h: 5%}}, align: center}
  title:    {at: {box: {x: 0%, y: 10.5%, w: 100%, h: 10%}}, align: center}
  subtitle: {at: {box: {x: 0%, y: 21.5%, w: 100%, h: 5%}}, align: center}
```

The keys are `at`, `align`, `anchor`, `rung`, `pair` and `ink`, documented for authors under
[Moving the chrome](authoring.md#moving-the-chrome) — a slide's own `chrome:` block
takes the same keys and merges over the theme's, key by key.

**Fractions only.** A `box` outside 0..1 on either axis is a `ThemeError`, because a
theme declaring inches is a transcription of one deck at one canvas size, which is
exactly what a fraction-based system exists to stop. `align`/`anchor` are the only
non-geometric values, and neither has a size.

## Icons: the brand's own, or ours

`icons:` names a directory of `.svg` glyphs beside the theme file. It is searched
before the set that ships with deckwright, so a brand that has drawn its own `target`
gets it everywhere without a single deck changing.

```yaml
icons: assets/icons        # relative to this theme file
```

The template's *own* glyphs are not used, and cannot be: 81% of the corpus's 4,019
freeform paths are `schemeClr`-linked and would recolour correctly, but they are named
`Google Shape;#;p12` and `Freeform: Shape 41`. Nothing can ask for the one that means
"calendar", which is the whole job an icon name does.

A glyph is painted the first brand accent that clears 3:1 where it lands — WCAG's
non-text floor (1.4.11) — falling back to the surface's ink. Every accent is tried,
not only `accent-1`: a lime brand has nothing that reads on a near-white plate, and
stopping at the first would black out a violet one too.

**`cols:` narrows the measure and keeps the stack.** Templates put artwork in a
corner and expect the title beside it, so all three fields commonly take the same
column range; they stack down the page rather than piling at the top margin. Lines
sharing a measure share one frame, which is what lets a title that wraps wider than
estimated push its subtitle down instead of drawing through it — so a field given
its own columns starts a new frame. `deckwright conform` writes this block when the
template's background leaves a wide enough clear run to aim at.

## Motion

A deck spec says how many beats an argument has — `animate: one_at_a_time` versus
`together`. The theme says what a beat looks like. This is the same split that keeps
colour out of a spec: retheming a deck changes its pacing along with its palette,
and a deck cannot drift off-brand one hardcoded timing at a time.

| Key | What it does |
|---|---|
| `stagger_ms` | Offsets each shape after the first *within one click*, so what that click reveals cascades. `0` (the default) keeps it simultaneous. |
| `advance` | `on_click` (default) spends a click per reveal group. `after_previous` chains them onto **one** click. |
| `beat_ms` | The pause between groups under `after_previous`. Default `400`. |
| `roles` | Binds each semantic motion role to an entrance kind. See [Motion roles](#motion-roles). |
| `transition` | The deck's default slide transition — a mapping of `kind`, optional `dir`, and `speed`. See [The deck's transition](#the-decks-transition). |

### One click, or one per beat

```yaml
motion:
  advance: after_previous
  beat_ms: 350
```

`animate: one_at_a_time` normally spends a click per group — four stat tiles, four
clicks. Under `after_previous` the first click starts the sequence and the rest follow
themselves, `beat_ms` apart. The slide still builds in order; you just stop tapping.

The spec is unchanged either way — how many beats an argument has is the deck's
business, whether you advance them by hand is the brand's.

### Motion roles

A component reports **what it is**; the theme decides how that kind of thing moves.
Neither the component nor the spec ever names an OOXML preset — the same indirection
`accent-1` uses onto a palette slot.

```yaml
motion:
  roles:
    line: {kind: wiperight}    # a rule draws itself left to right
    text: {kind: fade}
```

| Role | Reported for | Default |
|---|---|---|
| `text` | a shape that carries words, on its own fill or not: `prose`, `bullets`, callout and card copy, a stat tile, a table, a `code` listing, a caption, words over a picture | `fade` |
| `surface` | a filled shape that carries no words: a card's plate, a `panel`, an `ellipse`, a callout's dot, a bar, a swatch chip, a scrim | `fade` |
| `line` | a stroke: `rule`, `connector`, the join between `flow` steps, a `fanout`'s trunk, spine and branches | `wiperight` |
| `datum` | a chart, and each part of a chart's own build | `wipeup` |
| `figure` | a picture, a glyph (`icon`, or a mark on a card, callout, stat or fanout), a document card | `fade` |

Three entrance kinds exist: `fade`, `wipeup`, `wiperight`. A role bound to anything else
is refused when the theme loads, and so is a role name outside the five above.

A wipe runs along one axis, so a shape more than eight times as long across that axis as
along it — a vertical join between `flow` steps, a `fanout`'s spine — takes the other wipe:
`wiperight` becomes `wipeup` on a vertical stroke, and `wipeup` becomes `wiperight` on a
horizontal one.

**`animate: together` ignores roles.** It gives every shape on the slide the same fade
through a different build, so there is nothing for a per-shape role to say. A deck that
wants its rule to wipe needs `one_at_a_time`.

```yaml
motion:
  stagger_ms: 80        # 0 (the default) reveals a group's items simultaneously
```

`stagger_ms` offsets each shape after the first *within one click* by `i * stagger_ms`
milliseconds. It never changes how many clicks a slide takes — only what happens
inside one.

What a click covers differs by mode, so the same number reads differently:

| `animate:` | One click covers | What a stagger does |
|---|---|---|
| `together` | every shape on the slide | The cascade you probably want — a row of tiles arriving left to right. |
| `one_at_a_time` | one reveal group | Offsets the parts *of* a group. A `stats` group is one tile, so its label trails its number by `stagger_ms`; a `callouts` row's text trails its dot. Subtle, and easy to set too high. |

A negative value is refused at load: it would schedule a shape before the click that
reveals it.

### The deck's transition

```yaml
motion:
  transition: {kind: fade, speed: fast}    # dir: only where the effect takes one
```

**A transition belongs to the slide it arrives at** — it says how the show moves *to*
this slide from the one before it. Every slide gets the theme's; a slide writes
`transition: none` for a deliberate hard cut, and that is the only thing a slide may
say about it. Naming a *different* transition would be naming a look, which is what
this block exists to hold.

`speed` is `slow`, `med` or `fast`. There is no duration knob — the base schema has
no `dur` attribute, and the sub-second form needs a 2010-namespace extension deckwright
does not write.

Twenty-one effects, and **each takes its own direction vocabulary** — a shared
`l/u/r/d` list is invalid the moment it meets `strips`:

| `dir:` accepts | Effects |
|---|---|
| *(none)* | `circle`, `cut`, `diamond`, `dissolve`, `fade`, `newsflash`, `plus`, `random`, `wedge`, `wheel` |
| `horz`, `vert` | `blinds`, `checker`, `comb`, `randomBar` |
| `l`, `u`, `r`, `d` | `push`, `wipe` |
| `l`, `u`, `r`, `d`, `lu`, `ru`, `ld`, `rd` | `cover`, `pull` |
| `lu`, `ru`, `ld`, `rd` | `strips` |
| `out`, `in` | `split`, `zoom` |

A bad kind, direction or speed is refused when the **theme loads**, not at the slide
that first uses it.

> For a business deck, `fade` or a `push` is usually the whole answer. The rest are
> in the schema, not in good taste.

> Nothing in a static render shows a transition — `bin/run render` produces identical
> images with and without one, and `deckwright qa` reads the manifest, which a transition
> does not touch. Only presentation mode shows it.

> A still render cannot show a stagger — LibreOffice draws the final state of every
> slide. Only real PowerPoint shows the cascade.
