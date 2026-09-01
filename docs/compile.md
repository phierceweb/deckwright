# Compiling — spec to `.pptx`, and the manifest beside it

How `compile/build.py` turns a parsed spec into a package, what the build records while
it draws, and what the two files written beside the deck are for. This doc covers the
**engine's internals**: the order the pipeline runs in and why that order is forced, how
a shape gets its name, and what a manifest *is* as a set of dataclasses.

**To write a `.deck.yaml`, read [`docs/authoring.md`](authoring.md)** — it owns the wire
format. **To read a manifest**, read [`docs/qa.md`](qa.md#what-the-manifest-records) — it
owns the key-by-key description of the JSON and the checks that consume it. This doc is
the writing side of that same file.

For AI assistants: [`pptx-deck-building.md`](pptx-deck-building.md) covers the
build → render → QA loop; this doc is the reference for the compiler itself.

---


## Calling it from Python

`deckwright.build_deck` is the compiler as a function, re-exported from the package for a
caller generating specs rather than writing them:

```python
import deckwright

result = deckwright.build_deck("deck.deck.yaml")          # theme from the spec's `theme:`
result = deckwright.build_deck("deck.deck.yaml", theme_path="templates/brand.theme.yaml",
                            out="out/deck/Deck v2.pptx")
print(result.deck, result.manifest, result.slides)
```

It returns a `BuildResult` — the deck, its manifest, and the slide count — and raises
the exceptions the package exports: `SpecError`, `ThemeError`, `LayoutError`,
`MissingToolError` when an external tool is absent, and `RenderError` when one ran and
failed.

`deckwright.load_theme` reads a theme without building anything, taking either a bare theme
name — resolved the same way a spec's `theme:` is — or a path to a theme file:

```python
theme = deckwright.load_theme("base")                     # the packaged built-in
theme = deckwright.load_theme("acme")                     # templates/acme.theme.yaml
theme = deckwright.load_theme("templates/acme.theme.yaml")  # an explicit file
theme = deckwright.load_theme()                           # the design system, no template
print(theme.palette.pair("page"), theme.grid.columns)
```

A name that resolves to nothing raises `ThemeError` naming the directory searched, the
`DECKWRIGHT_THEME_DIR` that moves it, and the `deckwright conform … --adopt` that creates the
file; a path that does not exist is reported as a path, not as an unknown name.

There is no Python API for *composing* a slide. Components are chosen by name in the
spec, and one the format cannot express is added by registering it — see
[`extending.md`](extending.md) — never by calling into the layout engine, whose
signatures are internal and documented below as such.

## Table of Contents

- [The order the build runs in](#the-order-the-build-runs-in)
- [The starting file](#the-starting-file)
- [What a manifest is](#what-a-manifest-is)
- [Recording a shape](#recording-a-shape)
- [How a shape gets its name](#how-a-shape-gets-its-name)
- [Portable paths, and when they are applied](#portable-paths-and-when-they-are-applied)
- [The spec snapshot](#the-spec-snapshot)
- [The two derived views](#the-two-derived-views)
- [Adding a field to a record](#adding-a-field-to-a-record)
- [Recording a new kind of shape](#recording-a-new-kind-of-shape)

## The order the build runs in

`build_deck` is a straight line, and its order is not free. Every step below is held in
place by the one after it:

1. **Parse, then load the theme.** The spec names the theme; `theme/load.py`'s
   `resolve_theme(name)` answers with `theme_dir() / "<name>.theme.yaml"` when that file
   exists and the packaged built-in otherwise, unless `theme_path` overrides both. That
   fallback is what lets `theme: base` resolve from an installed wheel with no checkout
   around it, and a same-named file in the theme directory always wins. `theme_dir()`
   reads `DECKWRIGHT_THEME_DIR` at call time, never at import — copy that shape for a new
   knob. Both resolvers live beside `load_theme`, one layer below the compiler, so a
   caller can load a theme by name without importing the build.
2. **Open the starting presentation, drop the template's slides, flatten the master
   background, pick the compose layout.** All four before the first slide is added,
   because a slide added first would be deleted by step two and would inherit the
   unflattened background.
3. **Per slide: `add_slide`, `begin_slide`, build a `SlideCtx`, `render_slide`.** The
   recorder must be told the slide has started before any component records against it;
   `record()` raises `PreconditionError` otherwise, rather than appending to the previous
   slide's list.
4. **Save into a `BytesIO`, then `atomic_write_bytes` the payload.** The buffer exists so
   `deck_hash` is a digest of exactly the bytes that land on disk. Writing then re-reading
   would hash a file another process could already have touched.
5. **Set `manifest.provenance`, then write the manifest.** Provenance carries `deck_hash`,
   so it cannot be assembled until the deck exists — which is why a build interrupted
   mid-deck leaves no manifest at all, the honest state.
6. **Write `<deck>.content.md` and `<deck>.beats.md`** from the same recorder.

`build_id` is a digest of the spec hash, the theme hash and the deckwright version, so the
same three inputs give the same id. `_version()` records `"unknown"` when nothing is
installed rather than guessing — a fabricated version is worse than an absent one.

## The starting file

A theme with no `template:` starts from `blank_presentation()` at the theme's canvas size;
otherwise the template is opened through `utils/deck.py`'s `open_presentation`, which turns
python-pptx's four unrelated failure classes into one `ThemeError` naming the file.

**Dropping the template's slides** is opt-in per theme (`drop_template_slides`) and deletes
newest index first, so the indices ahead of the cursor stay valid as the list shrinks.
Layouts and masters are untouched — only the sample slides go.

**Flattening the master background** (`compile/background.py`) composites a master's
background *picture* onto the page pair's background colour, and only where that picture
has real transparency. Transparent pixels are composited over white by PowerPoint and
LibreOffice and over black by Keynote; nothing in the file says which is right, and a
slide-level `<p:bg>` cannot be inserted beneath an inherited one. Only the built deck's
copy of the image is rewritten — the template on disk is never modified.

**The compose layout is resolved twice**, and deliberately. `theme/load.py` resolves one on
its own `Presentation` to read the master's theme XML for fonts and colours; `build_deck`
resolves it again on the presentation it will actually add slides to, because a layout
object belongs to the package it came from. Both calls go through
`layouts/resolve.py`'s `pick_compose_layout` with the same `prefer`, so they cannot
disagree. The chosen layout's name is recorded — nothing else in the deck says which
layout every slide was composed on.

## What a manifest is

Two modules, split by audience:

- **`compile/record.py`** — the dataclasses and the readers. `Provenance`, `Box`,
  `ShapeRecord`, `SlideRecord`, the `Rendered` literal, and the free functions `box_of`
  and `canvas_of`. Import from here.
- **`compile/manifest.py`** — `ManifestRecorder`, the build-time accumulator.

The split is the point: `qa/` and the read-back only ever *read* a manifest, and importing
the recorder to get at `box_of` would drag the whole build path behind it.

`Box` is inches from the slide's top-left and iterates left, top, width, height, so
`Rect(*box)` and `tuple(box)` hold. Read a recorded box with `box_of(shape)` rather than
indexing: a raw JSON `dict` survives `tuple()` by yielding its *key names*, so a call site
that skipped the helper corrupts silently instead of raising. `box_of` raises `SpecError`
naming the rebuild when it meets a manifest whose boxes are positional.

`SlideRecord.texts()` returns the lines a PDF extractor should be able to find — `native`
records only, one entry per line. Anything `image` or `picture` is excluded by
construction, which is what keeps the overflow check from reporting every rasterized
panel as missing text.

`_slim` is what makes the JSON readable: a record is written as a dict less every field
still at its default. **The defaults live on the dataclass**, so what is omitted and what
a reader falls back to cannot drift apart. Slimming is one level deep — a nested dataclass
goes through `asdict`, so a `Box` writes all four keys even when three are zero, and a
list of dataclasses is slimmed element-wise.

Inches round to three decimals (`_INCH_DP`) and points to two (`_POINT_DP`), at the moment
a value is recorded rather than when it is read. An EMU is 1/914400in, so dividing back out
leaves binary residue that would otherwise rewrite fourteen digits per diff for a one-EMU
nudge; both roundings sit an order of magnitude inside QA's tolerances.

## Recording a shape

`ManifestRecorder.record(shape, ...)` takes anything exposing `shape_id`, `name`, and
EMU `left`/`top`/`width`/`height`. It does not have to be a real shape: `components/table.py`
records each cell through a `_CellBox` standing in for one, because a cell has no id and no
position of its own and QA would otherwise see a table as a single box and never measure a
column.

Three refusals, all `InvalidInputError` or `PreconditionError`:

- `rendered` outside `native` / `image` / `picture`.
- `record()` before `begin_slide()`.
- a `line_pt` whose length does not match `lines`. It is one size per recorded line, for a
  shape mixing rungs; a mismatch would make `text-fit` measure a body line at its heading's
  size, so the two are not allowed to drift.

Two flags are set around a call rather than passed to it. `bleeding` is set by
`layouts/compose.py`'s `_draw` for the duration of a placement the author declared
`bleed: true`, and cleared in a `finally` — every shape recorded inside carries the intent
out of the bounds check. `mark_backdrop()` is a slide-level flag, not a shape record:
nothing was drawn, and the render checks need to know the pixels behind the slide are a
photograph rather than a palette colour.

`record_animation(kind, groups)` stores one step per click. Entries arrive as shape ids
(some carrying an already-resolved motion role) and are stored as **names**, because an id
says nothing to a reader and is not unique on a slide — every cell of a table reports its
frame's. A shape animated but never recorded stores as `shape 4`, which at least says
which one. What the motion roles do is [`docs/motion.md`](motion.md).

## How a shape gets its name

`compose.py` sets `manifest.origin` to the spec node about to draw — `s7.p2.card`, or
`s7.hero.card` where the placement carries an `id:` — and clears it afterwards. Assigning
an origin resets the per-origin part counter and the shared-frame set, so naming state
never leaks from one placement into the next.

Within an origin, `_name` produces `origin.part` when the caller passed a `part`
(`s7.p4.table.r2c3`) and `origin#N` when it did not (`s7.p2.card#1`). **`N` counts every
shape the origin draws, parted ones included** — a component that parts some shapes and
numbers others will show gaps in its numbering, which is correct: the counter is a draw
order, not a dense index.

The name is written **into the package as well as the manifest**, whenever the recorded
object has an `_element` (a `_CellBox` does not, so cells are named only in the manifest).
PowerPoint preserves shape names through a hand-edit, so this is the join that lets a
delivered deck be read back against the build that made it.

**Shared frames collapse to the bare origin.** Chrome's stacked lines are paragraphs in one
textbox, and one shape cannot hold three names. The first parted record names the package
shape `s7.chrome.kicker`; the second record against that same `shape_id` renames it to
`s7.chrome`. The manifest keeps the per-part names either way. Sharing is keyed on
`shape_id`, never on the lxml proxy's identity — a freed proxy's address is reused by
another element, which would collapse two unrelated shapes onto one name.

A separate `_named` map carries the package name each `shape_id` ended up with, and is
what `record_animation` resolves against. It is cleared in `begin_slide` because shape ids
restart on every slide.

With no origin set, `_name` returns the shape's existing name unchanged and writes nothing
into the package. **A component that draws a shape and never records it therefore keeps
python-pptx's default name**, is invisible to every manifest-driven QA check, and shows up
in a read-back as `added` — "added by hand" — because nothing in the build claims it. Record
every shape you place.

## Portable paths, and when they are applied

`ManifestRecorder.write()` rewrites `spec`, `deck` and `theme_path` relative to the
manifest's own directory. An absolute path puts the build machine's home directory — and
its username — into a file that gets handed over beside the deck, and a relative pair
survives that pair being moved, which absolute does not. `qa` resolves `theme_path` back
against the manifest's location.

When the two share nothing but the filesystem root, the relative form would climb out
through that same home directory, so the absolute path stays — nothing about such a build
is portable anyway.

**The rewrite lives in `write()`, not in `to_dict()`**, and it copies rather than mutating
the recorder — so an in-process consumer of `to_dict()` sees the paths exactly as recorded,
and writing the same manifest to two locations gives each one paths relative to itself.
Serialising `to_dict()` yourself skips the rewrite and ships whatever absolute paths the
build machine had.

## The spec snapshot

Every build copies the spec that made it to `<out dir>/.build/<deck stem>.deck.yaml`
(`SCRATCH` in `src/deckwright/paths.py`; use `scratch(outdir)` rather than the literal). One
snapshot per version, so overwriting a spec leaves the builds that came from earlier
states of it still rebuildable.

The snapshot carries the spec and nothing else. A deck naming an `extends:` module, a
`document:` source or its own images still needs those files to rebuild — which is why
[`out/README.md`](../out/README.md) still asks whether a
file under `out/` can be recreated *right now* before anything there is deleted.

## The two derived views

Both are generated from the manifest and are never authoritative. Regenerate them; do not
edit them.

**`<deck>.content.md`** (`compile/content.py`) is the deck's words — a small fraction of
the manifest by line, though how small depends entirely on the deck: a table-heavy one
records a row per cell and lands near 4%, a chart-heavy one nearer 27%. `split_name` reverses the naming scheme above to group a slide's records
back into chrome, table grids and body blocks in draw order. A block with no words is
labelled with its component (`*(chart)*`) so a slide that is one chart does not read as
empty — except for the components in `_UNSPOKEN`, which are the slide's own paint, a
divider and a join, and say nothing a reader wants. It is written from the same
`to_dict()` that produced the JSON, so the two cannot disagree.

**`<deck>.beats.md`** (`compile/beats.py`) is the same build's *timing*: which click
reveals what, in words. Its section headings carry the slide **title**, not just the index,
so a diff across two builds shows an animation that moved to a different slide — the failure
a count of animated slides reports as no change. It reads `clicks` off each recorded
animation rather than counting steps, because those differ: `animate: together` fades every
group onto one click, an `after_previous` chain spends one for the whole build, a chart build
spends one per part plus one for its axes, and an interactive `reveals:` spends none.

**Read-back** (`compile/readback.py`) compares a deck on disk against the manifest that
built it. `_edited` hashes the file and compares against `deck_hash`; the shape comparison
runs from the **deck** side, because one package shape can answer for several records —
chrome's stacked lines again — and only the deck knows which names the package really
carries. A shape claims its own record and any record whose name extends it with a dot, so
`s1.chrome` claims `s1.chrome.title`; a table frame is `…table#1` and so claims no cells,
which are never shapes.

It reports four kinds — `moved`, `retyped`, `added`, `gone`. A move must exceed `_MOVED`
(0.01in, twenty times the largest error three-decimal rounding can introduce) to count, so
float dust is not a move. All four of left, top, width and height are compared, so a pure
resize is caught — and reported as `moved`, which is the label to search for when a shape
changed size but not position. **Only geometry and text are compared**: a recoloured or
re-fonted shape reads as unchanged, and `render_drift` says so outright when the file's
hash differs but no shape does.

## Adding a field to a record

1. Add it to the dataclass in `compile/record.py` **with a default**. A field with no
   default is written on every record; `_slim` omits a field only when it equals its
   declared default, which is also what a reader falls back to.
2. Give it a default that means "absent" for the overwhelmingly common case, or it will
   appear on thousands of records for the handful that need it.
3. Pass it through `ManifestRecorder.record()` as a keyword-only argument. If it is
   position- or size-derived, round it in `record()` with `_INCH_DP` or `_POINT_DP` — every
   number in the manifest is rounded at the point it is recorded, never at the point it is
   read.
4. If two fields must stay consistent (as `lines` and `line_pt` do), refuse the mismatch in
   `record()`. A validator there is the only place both values are present at once.
5. Document it in [`docs/qa.md`](qa.md#what-the-manifest-records) — that doc owns the
   reader's view of the format, and a field nothing documents is a field no check will ever
   consume.

## Recording a new kind of shape

A component records through `ctx.manifest.record(...)`. What to pass:

- **A text shape** — `lines=` (one entry per rendered line) plus `font_pt`, and `line_pt`
  when the lines sit at different rungs. Pass `fg` and `bg`, both resolved: `contrast`
  skips any record missing either, silently, so an unpassed colour is not a neutral
  default but a check that never ran.
- **A picture** — `rendered="picture"` when it is a photograph text may sit on, and
  `rendered="image"` when it is rasterized content that *was* text (a panel). The two are
  not interchangeable: `image` is what tells the overflow check to skip a row it could
  never verify, and `picture` is what tells the render checks the pixels behind a line are
  a photograph. See [`docs/panels.md`](panels.md) and [`docs/imagery.md`](imagery.md).
- **Something that is not a shape** — build a small frozen dataclass exposing `shape_id`,
  `name` and EMU `left`/`top`/`width`/`height`, as `components/table.py` does for cells. It
  is recorded and checked but never renamed in the package, because there is no element to
  rename.
- **A repeated element with a meaningful identity** — pass `part=` so its name says what it
  is (`r2c3`) rather than where it fell in the draw order. A numbered `#N` beats an
  invented label.

Then check the result the way downstream will. `qa/geometry.py` de-duplicates on
`(shape_id, box)` for its geometry checks — one box is one geometry however many paragraph
records share it — while the typography checks read every row, because deduplicating there
would drop a paragraph's own size and colours. So a second record at the same box buys a
typography row and nothing else.
