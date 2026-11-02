# Icons — SVG in, native geometry out

How `src/deckwright/icons/` finds a glyph by name, converts its SVG paths into DrawingML,
and paints it a colour that reads where it lands. This doc covers the **subsystem's
internals**: the search order, what an SVG file must contain, the path conversion, and
how to add a set.

**To place an `icon:` in a deck spec, read
[`docs/components.md`](components.md#icon--a-vector-mark)**; to pick *which* glyph, read
[`docs/glyphs.md`](glyphs.md). For how a theme points at a brand's own glyph directory,
read [`docs/theme.md`](theme.md#icons-the-brands-own-or-ours).

---

## Table of Contents

- [Why icons come from files](#why-icons-come-from-files)
- [Plain shapes are presets, not art](#plain-shapes-are-presets-not-art)
- [The search order](#the-search-order)
- [What an SVG file must be](#what-an-svg-file-must-be)
- [SVG path → DrawingML](#svg-path--drawingml)
- [The unit grid and a non-square viewBox](#the-unit-grid-and-a-non-square-viewbox)
- [Drawing: a freeform, squared and centred](#drawing-a-freeform-squared-and-centred)
- [Every subpath is filled even-odd](#every-subpath-is-filled-even-odd)
- [The colour a glyph is painted](#the-colour-a-glyph-is-painted)
- [The set that ships](#the-set-that-ships)
- [Adding an icon, or a whole set](#adding-an-icon-or-a-whole-set)

## Why icons come from files

A brand template is full of usable vector marks — 4,019 `custGeom` freeforms across the
eleven sample templates, and 81% of their paths are `schemeClr`-linked, so they would
recolour correctly. They are unusable anyway, because they are named `Google Shape;#;p12`
and `Freeform: Shape 41`.

Nothing can ask that collection for the one that means "calendar", and asking by name is
the entire job an icon does. So icons come from `.svg` files named for what they depict,
and the template's own glyphs are left alone.

They are drawn as **native DrawingML geometry**, not embedded images: it is the idiom a
`.pptx` renders most reliably, it scales without resampling, and it takes a solid fill —
which is what lets a glyph be recoloured per slide.

## Plain shapes are presets, not art

`circle`, `square`, `triangle`, `diamond` and `ring` never reach the search below.
They are DrawingML preset geometry — `OVAL`, `RECTANGLE`, `ISOSCELES_TRIANGLE`,
`DIAMOND`, `DONUT` — listed in `icons/shapes.py`.

For these the geometry *is* the meaning, and an icon set only draws its idea of one.
Material's `square` is round-cornered; its `diamond` is a faceted gem, and a geometric
scan of all 4,001 glyphs — single contour, square-ish bounding box, area about half of
it — found no rhombus in the set at all. The name had no honest answer while it
resolved to a drawing.

A preset is exact at any size, carries none of a set's optical styling, and is a real
shape in PowerPoint rather than a freeform. The cost is that it cannot be restyled by
dropping in a file — so it is not: **a configured directory is asked first**, and a
`circle.svg` in `$DECKWRIGHT_ICON_DIR` or the theme's own directory is used instead.

`star` and `flag` stay glyphs. Their character is drawn, not geometric; an author
choosing `star` is choosing a look, not a polygon.

## The search order

`icons/load.py`'s `roots()` returns where `<name>.svg` is looked for, in order:

1. `$DECKWRIGHT_ICON_DIR`, if set — read at call time, so it can be changed per run.
2. The theme's own `icons:` directory, resolved relative to the theme file.
3. `icons/glyphs/material/glyphs.zip` — the vendored Material Symbols, the only set
   that ships. The first two are directories of files; the shipped set is one archive
   read by member name, which is why `Source` exists rather than a bare path.

**A directory this run configured is tried first and on its own.** A name found there
wins outright, which is what lets a brand override a single glyph — drop `target.svg`
into the theme's directory and every deck gets the brand's target, with nothing else
changed, and no table below can take it back.

Three more steps then run, in this order:

- **The override table** (`icons/aliases.py`'s `OVERRIDES`) — the four names the set
  spends on something else. Material's `pin` is a keypad for a PIN code, its `globe` is
  a continent disc, and `arrow_left`/`arrow_right` are small carets rather than the
  shafted arrows the names promise. This is the one step that can shadow a real glyph,
  which is why it holds four entries and why each was chosen against a render.
- **The name, then its hyphenated spelling.** The vendored set names its files
  upstream's way, with underscores. `icon: rocket-launch` and `icon: rocket_launch` both
  reach `material/rocket_launch.svg`, so a deck can stay in deckwright's own style
  throughout.
- **The alias table** (`icons/aliases.py`'s `ALIASES`) — curated names for glyphs the
  set calls something else: `deploy` → `rocket_launch`, `team` → `groups`, `compliance`
  → `verified_user`. An alias is consulted last, so it can never shadow a name that
  already resolves. The list, grouped by what a slide is about, is
  [`docs/glyphs.md`](glyphs.md).

A name must be lowercase letters, digits, hyphens and underscores. It names a file, not a
label, and the error says so. A miss names the closest real glyphs and the directories it
searched — with four thousand names available, printing the vocabulary stopped being help.

Parsed glyphs are cached on their `Source` — a configured file, or a member of the
bundle — since a deck reuses the same icon many times.

## What an SVG file must be

Two hard requirements, each with an error message that explains itself:

- **A `viewBox` with four values.** deckwright scales by it; without one the drawing has no
  size to scale from.
- **At least one `<path>` with a `d`.** `<circle>`, `<rect>`, `<line>` and stroked
  outlines are *not* read — flatten the drawing to filled paths before saving.

Every `<path>` in the file becomes one subpath of a single `a:path` body, so an inner
contour cuts a hole rather than drawing a second opaque shape. Stroke widths, per-path
fills, transforms and styling are all ignored: the file supplies geometry, the palette
supplies the colour. The `fill-rule` attribute is ignored too — but the geometry is not
rule-free, and [what it gets instead](#every-subpath-is-filled-even-odd) is the first
thing to check before dropping a foreign set in.

## SVG path → DrawingML

`icons/path.py` parses the `d` attribute into `moveTo` / `lnTo` / `cubicBezTo` / `close`
commands. It implements the full command set — `M L H V C S Q T A Z`, absolute and
relative — plus the two implicit-repeat rules that trip up naive parsers:

- A repeated argument set implies the previous command.
- A repeated argument set after a `moveto` implies `lineto`, the one case where the
  letter is not the command.

Three conversions happen on the way:

| SVG | DrawingML | Why |
|---|---|---|
| Quadratic (`Q`, `T`) | Cubic bézier | DrawingML has no quadratic segment; the elevation is exact. |
| Smooth (`S`, `T`) | Explicit control point | The implied control is the previous one reflected through the pen. |
| Arc (`A`) | A run of cubic béziers | See below. |

**Arcs become béziers rather than `a:arcTo`.** SVG parameterizes an arc by its endpoint
and DrawingML by its sweep; converting between them is the same trigonometry as the
bézier approximation, with a second chance to get a sign wrong. The arc is split so no
segment spans more than a quarter turn, which is where the cubic approximation stays
within a fraction of a unit of the true curve.

The tokenizer matches **any** letter, not only the known commands, so an unrecognized one
raises `SpecError` naming it. Matching only the known set would silently drop it and draw
a truncated path — an icon that is subtly wrong, which is worse than one that fails.

## The unit grid and a non-square viewBox

Points are emitted on a fixed logical grid (`UNITS` in `path.py`), large enough that
rounding to integers is invisible at any size an icon is drawn.

A non-square `viewBox` is **fitted and centred** on that grid, not stretched to it, so a
wide glyph keeps its drawn proportions instead of being distorted into a square.

## Drawing: a freeform, squared and centred

`icons/draw.py`'s `place_icon` is the single entry point, and it chooses between the two
kinds: a name in `icons/shapes.py` becomes a preset (see
[Plain shapes are presets, not art](#plain-shapes-are-presets-not-art)); everything else
is drawn here. Both are squared off and centred the same way.

For a glyph it writes a `p:sp` with a `custGeom` directly, because python-pptx has no
freeform-with-arbitrary-path API. Two details matter:

- **The box is squared off and centred first.** An icon drawn on a square viewBox and
  stretched to a wide placement is the one distortion nothing downstream can undo.
- **The shape id is one past the highest in the tree.** A duplicate id opens as a corrupt
  file, and python-pptx does not assign one for a hand-built element.

Note the import: `pptx.oxml.parse_xml`, not lxml's — python-pptx keys its shape classes
off its own parser, and an element built by plain lxml comes back as a base shape.

## Every subpath is filled even-odd

Measured, not assumed: two concentric circles wound the *same* direction render as a
ring, and two overlapping same-direction rectangles render with a hole where they cross.
Under nonzero winding both would be solid. This is the constraint that decides whether
any foreign icon set can be used at all.

It is good news for most sets. Even-odd is what `fill-rule="evenodd"` art already assumes
(Heroicons solid, Bootstrap Icons), and it is what a hole wound opposite to its outline
gets under either rule. Real PowerPoint art winds its holes the safe direction — the
1,720 multi-contour `custGeom` freeforms in the eleven sample brand templates are 99.2%
renderer-agnostic in exactly this way.

Material Symbols declare no `fill-rule`, so upstream means nonzero. 4,001 of the 4,117
are drawn so the two rules agree; the other 116 — almost all `*_off` variants — draw the
slash bar as a stroke *overlapping* the body it crosses, which even-odd XORs into a white
gash through the middle of the glyph. Those are not shipped, and
`tests/icons/test_vendored.py` fails if a re-vendoring lets one back in.

For an author that means there is no `videocam_off`, `bar_chart_off`, `sync_disabled` or
any other slashed "off" glyph. Nothing is aliased to the positive glyph in their place —
that would be a worse answer than the error, which at least says what is missing. Put the
positive glyph beside a `close`, or draw the negation with the deck's own shapes.

## The colour a glyph is painted

An `ink:` names a palette role and that is what is used. Otherwise the colour is solved
where the glyph lands: the first brand accent clearing **3:1** there — WCAG's non-text
minimum (1.4.11) — falling back to the surface's ink.

Every accent is tried, not just `accent-1`. A lime brand has nothing that reads on a
near-white plate, and stopping at the first would also black out a violet one that had a
perfectly good second accent.

A mark is deliberately not held to a text ratio. But an accent invisible on the surface
it sits on is an accent nobody sees, and unlike a heading there is no wording to reveal
it — so the floor is enforced.

Where a template's artwork is light under one half of the glyph and dark under the
other, no single colour clears the floor across it. The mark then gets the same last
resort a chrome line does: a plate of the slide's own paper painted behind it, the
accents tried again against that plate, and the slide pair's ink where none clears
even there.

The plate is padded around the glyph — a fifth of its own height on each edge, so the
mark has paper to sit on rather than a shape cut to its outline — and then **clipped to
the placement**. A chrome line's plate is not, because chrome owns the band it sits in;
a mark's plate would otherwise paint over the placement below it. `qa` cannot see that
overrun: `placement-fit` exempts every plate, since a plate is by definition a surface
drawn wider than the thing it backs.

## The set that ships

One set: **4,001 vendored Material Symbols** (Rounded, filled), Apache 2.0, packed into
`icons/glyphs/material/glyphs.zip` with their licence, their `SOURCE.md` provenance and
the `glyphs.sum` manifest that pins them beside it. Names are upstream's —
`rocket_launch`, `trending_up` — and the hyphenated spelling works too. Which one to
reach for is [`docs/glyphs.md`](glyphs.md).

They travel as one archive because 4,001 files cost far more in per-entry overhead than
in content: 716KB in the wheel and 2.9MB installed, against 2.1MB and 16.5MB as loose
files. The entries are **stored, not deflated** — both places the bundle lives, git and
the wheel, compress it themselves, and a pre-compressed archive defeats both while
making every glyph read slower. `deckwright glyphs sync` builds it and
`deckwright glyphs verify` checks it against the manifest; see
[`docs/cli.md`](cli.md#glyphs--the-built-in-icon-set).

One style throughout is the point of a single set. A hand-drawn glyph beside a Material
one shows: sharp corners against soft, part-outline against solid, and nothing in the
spec says which a name will get.

### The names decks are already written against

Forty-five names are a compatibility surface — decks in the wild ask for them, so each
one resolves and draws the thing it names.

Five reach no set at all: `circle`, `square`, `triangle`, `diamond` and `ring` are
[preset geometry](#plain-shapes-are-presets-not-art), so `diamond` is a true rhombus
rather than Material's cut gem, and `ring` a `DONUT` rather than `trip_origin`.

Nineteen are Material's own word and reach the glyph directly: `bolt`, `check`,
`close`, `cloud`, `download`, `flag`, `folder`, `info`, `layers`, `lightbulb`, `list`,
`lock`, `mail`, `search`, `shield`, `star`, `target`, `upload`, `warning`.

The remaining twenty-one go through the two tables, and are the reason those tables
exist:

| Name | Draws | Note |
|---|---|---|
| `plus` | `add` | |
| `minus` | `remove` | |
| `arrow-up` | `arrow_upward` | |
| `arrow-down` | `arrow_downward` | |
| `arrow-left` | `arrow_back` | override — `arrow_left` is a caret |
| `arrow-right` | `arrow_forward` | override — `arrow_right` is a caret |
| `grid` | `grid_view` | |
| `user` | `person` | |
| `users` | `group` | |
| `gear` | `settings` | |
| `bell` | `notifications` | |
| `clock` | `schedule` | |
| `calendar` | `calendar_today` | |
| `document` | `note` | |
| `eye` | `visibility` | |
| `heart` | `favorite` | |
| `globe` | `language` | override — `globe` is a continent disc |
| `pin` | `location_on` | override — `pin` is a PIN-code keypad |
| `chart-bar` | `bar_chart_4_bars` | ascending, on a baseline |
| `chart-line` | `area_chart` | |
| `chart-pie` | `incomplete_circle` | a cut wedge; `pie_chart` is segmented |

To count the set, or search it, without opening this file:

```bash
bin/py -c "from deckwright.icons.load import available; print(len(available()))"
```

An icon nobody drew fails the build with a message naming the closest real glyphs, so a
typo and a missing glyph are told apart at build time rather than in the render.

## Adding an icon, or a whole set

**One glyph, for one brand:** save `<name>.svg` into the directory the theme's `icons:`
points at. Flatten to `<path>` elements, keep the `viewBox`, and drop fills and strokes.
It now outranks everything, including the overrides.

**One name, for everyone:** add a row to `icons/aliases.py`. Nothing hand-drawn goes into
`icons/glyphs/material/` — it is a vendored set with its own licence, and a stray file
there is lost the next time it is re-vendored. A name the set genuinely has no drawing
for is a name to leave failing, since the error at least says so.

**A whole set:** point `$DECKWRIGHT_ICON_DIR` at the directory to try it without touching a
theme; make it permanent by adding `icons:` to the theme file.

In all three cases, verify the result — a glyph that fails to parse fails the build with
a message, but one that parses and draws wrongly (a stroke-only source, an unflattened
transform) only shows up in the render.
