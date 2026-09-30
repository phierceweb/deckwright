# The CLI — every command, and the knobs behind them

Reference for the thirteen `deckwright` commands and the environment variables they read. Run
them through `bin/run`, which uses the project venv:

```bash
bin/run <command> [args]
```

`bin/run` also resolves pf-core's own console scripts from the venv — `bin/run pf-doctor`
attests the install (loaded copy, extras, env resolution, docs link) and is what `bin/setup`
points at when it finishes. See `docs/pf-core/doctor.md` — a symlink `bin/setup`
creates into the installed pf-core's own docs, so it exists after setup, not on GitHub.

For the workflow these commands compose into — build, look, fix, rebuild — read
[`docs/pptx-deck-building.md`](pptx-deck-building.md). This doc is the surface
reference.

---

## Table of Contents

- [Global options](#global-options)
- [`new` — start a deck](#new--start-a-deck)
- [`build` — spec to deck](#build--spec-to-deck)
- [`demo` — every capability in one deck](#demo--every-capability-in-one-deck)
- [`render` — deck to images](#render--deck-to-images)
- [`qa` — check a built deck](#qa--check-a-built-deck)
- [`diff` — what a hand-edit changed](#diff--what-a-hand-edit-changed)
- [`inspect` — inventory a deck's shapes](#inspect--inventory-a-decks-shapes)
- [`extract` — a draft spec out of any deck](#extract--a-draft-spec-out-of-any-deck)
- [`conform` — onboard a brand template](#conform--onboard-a-brand-template)
- [`shot` — screenshot an HTML file](#shot--screenshot-an-html-file)
- [`sample` — a template to onboard against](#sample--a-template-to-onboard-against)
- [`doctor` — what this install can do](#doctor--what-this-install-can-do)
- [`glyphs` — the built-in icon set](#glyphs--the-built-in-icon-set)
- [Environment variables](#environment-variables)
- [External tools](#external-tools)
- [Exit codes and logging](#exit-codes-and-logging)
- [Adding a command](#adding-a-command)

## Global options

Two options belong to the tool rather than to a command, so they go **before** it:

| Option | Effect |
|---|---|
| `-v` / `--verbose` | Debug logging: `bin/run -v build deck.deck.yaml`. |
| `-V` / `--version` | Print the installed version and exit: `bin/run --version`. |

`doctor` prints the same version as its first row, beside everything else about the
install.

## `new` — start a deck

```bash
bin/run new "Q4 Review"
bin/run new q4-review --theme brand --no-build
```

Writes `authoring/<slug>/<slug>.deck.yaml` and builds it, so the first thing you have
is a deck you can open and a spec you can edit.

Both paths are relative to the current directory, so run outside a checkout it
creates `authoring/` and `out/` where you stand. `--root` moves the source
directory; the build goes wherever the spec's `out:` points.

| Flag | Effect |
|---|---|
| `--theme` / `-t` | Theme the deck names. Default `base`. |
| `--root` | Where the deck's source directory goes. Default `authoring/`. |
| `--build` / `--no-build` | Compile it straight away. On by default. |

The slug keeps letters and digits only, so `Q1/Q2 Review` becomes `q1q2-review` and a
deck never writes outside the `--root` it was given; `/ \\ :` become `-` in the built
deck's filename while the title keeps them. A name that leaves no slug at all is
refused with `a deck needs a name`. A build that fails frees the name it just wrote,
so the retry is not blocked by the directory the first attempt left.

**The scaffold is a working deck, not a stub** — six slides covering the shapes most
decks are made of: a cover, a section divider, bullets with a click build, a `split:`
row of cards, a native chart, and a closing. Each carries one line saying what to
change. Editing something that runs is how these actually get written; composing the
first one from an empty buffer means reading the wire format, the component index and
the placement rules before writing a word.

`"Q4 Review"` and `q4-review` give the same deck — spaces, hyphens and underscores all
slug the same way, and a word keeps the case you typed past its first letter, so
`ML-pipeline` titles as *ML Pipeline*.

It never overwrites. A deck of that name already there is an error naming it, because
this is the one command that would destroy work by succeeding.

## `build` — spec to deck

```bash
bin/run build deck.deck.yaml
bin/run build deck.deck.yaml --theme templates/acme.theme.yaml --out out/deck/deck-v3.pptx
```

Compiles a `.deck.yaml` against a theme into a `.pptx` and three siblings.
`<deck>.manifest.json` records every shape's box, colours and font size — it is what
`qa` reads, so keep the pair together. `<deck>.content.md` is the same build rendered
as the deck's **words**: slide by slide, chrome as headings, tables as tables, speaker
notes as quotes. `<deck>.beats.md` is the same build rendered as its **reveal order** —
what arrives on click one, two, three, and which click fires which trigger. Read those
two; they are derived, so regenerate them rather than edit them.

| Flag | Effect |
|---|---|
| `--theme` / `-t` | Theme file. Default: resolved by the spec's `theme:` name against the theme directory. |
| `--out` / `-o` | Output path, overriding the spec's own `out:`. Must be a `.pptx`: a YAML path, and the spec being compiled above all, is refused rather than written over. Rebuilding over an existing deck is fine. |
| `--keep-layouts` | Keep the template's unused slide layouts and masters, and the media only they reach. Off by default. |

A brand template arrives with every layout its designer drew, and a built deck uses
one of them. The rest are dropped along with the media nothing else reaches — on a
real template that is most of the file, and one of those layouts is often a format
Keynote refuses to import. Pass `--keep-layouts` when you intend to hand-edit the
built deck in PowerPoint and want its other layouts available.

The spec format is [`docs/authoring.md`](authoring.md).

## `demo` — every capability in one deck

```bash
bin/run demo
bin/run demo --theme brand --out out/demo
```

Builds **every capability the library has** into one deck, against any theme you name:
every component, chrome treatment, chart kind, table variant, photograph case and
motion build.

| Flag | Effect |
|---|---|
| `--theme` / `-t` | Theme name, resolved against the theme directory. Default `base`. |
| `--out` / `-o` | Where the deck goes. Default `out/demo`. |

**It is generated, not written.** The catalogue is `EXERCISE` in
`src/deckwright/conform/` — the same slides `conform` drives against real
brand templates. Nothing here is a second copy: [`testing.md`](testing.md)
requires every new capability to land in that registry, and `tests/test_templates.py`
builds all of it against every brand template in `templates/`. So the demo grows with the
library, and a capability cannot go missing from it without the suite going red.

The deck pins nothing — no theme, no words, no placement per capability. Name a different
theme and the same catalogue renders through it.

Read the result with the `.content.md` written beside it rather than by opening every
slide. If a capability fails against a brand theme the build stops at it; reach for
`conform`, which builds each alone and reports every failure rather than the first.

## `render` — deck to images

```bash
bin/run render out/deck/deck.pptx
bin/run render out/deck/deck.pptx --contact-sheet --dpi 140
```

Converts the deck to PDF with headless LibreOffice, then rasterizes each page with
`pdftoppm` into `<pptx-dir>/render/<deck>/slide-N.jpg` — a directory per deck, so a
version series beside it never overwrites these — zero-padded to the deck's own
length — `slide-07.jpg` in a 69-slide deck, `slide-007.jpg` in a 111-slide one, so a
glob wants `slide-*.jpg` rather than a fixed width. **This is how you look at a deck** —
the render is the ground truth, not the spec.

| Flag | Effect |
|---|---|
| `--outdir` / `-o` | Where images go. Default `<pptx-dir>/render/<deck>`. |
| `--dpi` | Rasterization DPI. Default 110, or `$DECKWRIGHT_RENDER_DPI`. |
| `--contact-sheet` | Also write `contact_sheet.png`, the whole deck as one grid. |
| `--cols` | Columns in that grid. Default 4. |

Stale `slide-<n>.<image>` files a previous render wrote are removed first, so a shorter
deck never leaves orphans from a longer one behind — anything else in the directory,
including `contact_sheet.png` and `qa.md`, is left alone. Each run gets its own
LibreOffice profile, so concurrent renders do not silently no-op against a shared lock.

**The render sets the deck's own typefaces.** Before converting, `render` reads every face
the deck names — its theme's font scheme, and the runs, bullets and charts on its masters,
layouts and slides — and links each installed font family with exactly that name into the
LibreOffice profile, every style file of it, as `fc-list` lists them. A LibreOffice that
cannot reach the system's fonts on its own, as on macOS, then sets Helvetica as Helvetica
rather than a substitute. When the deck carries Chinese, Japanese or Korean text, the font
`fc-match` picks for each of those languages is linked too, so that text is drawn instead of
left blank. A face with no installed family of that name is never swapped for a lookalike:
it renders as LibreOffice's own fallback, and `qa` reports it `font-substituted`. Without
fontconfig nothing is linked and the render runs as before.

Each render also writes `.build/render.json` in its output directory: the deck's SHA-256,
the DPI and image format, and a digest of the PDF and every page image. `qa` reads it to
reuse the render rather than convert the deck again.

## `qa` — check a built deck

```bash
bin/run qa out/deck/deck.pptx
bin/run qa out/deck/deck.pptx --fail-on warn --no-render
```

Checks geometry, typography, contrast and overflow against the build manifest, prints
one line per finding, and writes `qa.md` / `qa.json`.

| Flag | Effect |
|---|---|
| `--manifest` / `-m` | Default `<deck>.manifest.json`. |
| `--theme` / `-t` | Default: the theme recorded in the manifest. |
| `--no-render` | Skip the render-based overflow and contrast checks — much faster, much weaker. |
| `--fail-on` | Exit 1 at this severity or worse: `error`, `warn` or `info`. |
| `--outdir` / `-o` | Where `qa.md` / `qa.json` go. Default `<deck-dir>/render/<deck>`. |

**`qa` reuses a matching render.** When its output directory already holds a render of the
deck's exact bytes — left by `render` or an earlier `qa`, at the configured DPI or finer, with
the PDF and every page image unchanged since — `qa` checks those instead of converting the
deck again. `render` and `qa` default to the same directory, so `render` then `qa` converts
once. Any edit to the deck, or a page image that is gone or changed, makes `qa` render
afresh. The log's `qa_rendered` event says which happened (`reused=True` or `False`).

With no LibreOffice on the machine the command fails rather than quietly checking less,
and says to re-run it with `--no-render` — bounds, placement, reserved regions, type
sizes and contrast need no external tool.

Without `--fail-on` the command reports and exits 0, so it is safe in a loop; with it, it
is a gate. What the checks do and do not catch is [`docs/qa.md`](qa.md) — read the
"cannot catch" section before trusting a clean run.

## `diff` — what a hand-edit changed

```bash
bin/run diff "out/my-deck/My Deck v3.pptx"
bin/run diff "out/my-deck/My Deck v3.pptx" --out out/my-deck
```

```
Deck v3.pptx was edited after its build from authoring/deck/deck.deck.yaml
  slide 1  moved    s1.chrome.title  0.8,0.375 11.733×1.05in → 1.55,0.375 11.733×1.05in
  slide 1  retyped  s1.chrome.title  'Smoke Test' → 'Smoke Test, revised'
  slide 1  restyled s1.p1.card#2     size 18/13.5pt → 40/13.5pt; colour 1A1D21 → FF0000
  slide 1  relabelled s1.p1.image#1  alt none → 'The harbour at dawn'
  slide 1  added    TextBox 3        not in the build — added by hand, so no placement made it
  slide 1  gone     s1.bg#1          the build drew this and the deck no longer has it
```

Editing a delivered deck in PowerPoint is a sanctioned workflow here — rebuilding
throws the edit away. This is how you see **what** was edited, so it can go back into
the spec rather than living only in the binary.

| Flag | Effect |
|---|---|
| `--manifest` / `-m` | Default `<deck>.manifest.json`, else the manifest beside the deck that records the deck's build id. |
| `--out` / `-o` | Also write `readback.md` in this directory. |

It works because shapes are named for the spec node that drew them and PowerPoint
keeps a shape name through an edit — see
[what the manifest records](qa.md#what-the-manifest-records). Matching runs from the
deck's side, since one shape can answer for several records: chrome's stacked lines
are paragraphs in a single frame.

A built deck carries its build id, so a copy saved under another name in the same
directory is read against the right manifest with no flag.

A slide is matched by the number in its shapes' names, not by where it sits. A deleted
slide is one `slide-gone` line and every slide after it still matches its own records. A
slide carrying no build-named shape is `slide-added`, and so is a duplicate, which says
which slide it copies. A slide out of build order is `slide-moved`: as few slides are named
as explain the order the deck is now in.

A shape PowerPoint stores inside `mc:AlternateContent` — an equation, a 3D model — is
read from its fallback, the branch a reader of none of the extension namespaces takes.

`retimed` is a slide whose build no longer spends the clicks, reveals the shapes or
listens on the triggers the manifest records, or whose transition changed kind. `restyled` compares a shape's runs as sets: a point size the build never set, or the
recorded ink gone from every run. `relabelled` is the decorative mark set or cleared, or
alternative text changed.

**What it cannot see:** a typeface, a fill, one run recoloured while the rest keep the
recorded ink, or which table cell changed — cells were never shapes, so they carry no
name and answer through their frame. A deck whose bytes changed with
no shape difference says so rather than reporting nothing.

## `inspect` — inventory a deck's shapes

```bash
bin/run inspect "out/my-deck/My Deck v3.pptx"
```

```
deck.pptx: 36 slide(s)
slide 1 (Blank)
  id=2    0.00,0.00 13.33×7.50     's1.bg#1'
  id=3    0.80,0.38 11.73×1.05     's1.chrome'
```

Every slide's shapes with ids, names and inch boxes. This is the tool for **surgical
hand-edits to a delivered deck**: it works on any `.pptx`, needs no manifest, and the
shape ids it prints are what a python-pptx patch script targets.

A deck deckwright built names each shape for the spec node that drew it — `s1.chrome`,
`s3.hero.card#1` — so the name says what to edit and where it came from. On a deck
from anywhere else the names are whatever PowerPoint assigned (`Rectangle 1`).
Names are the stable handle; ids restart on every slide. See
[what the manifest records](qa.md#what-the-manifest-records). A shape stored inside
`mc:AlternateContent` is listed once, from its fallback.

Reach for it when a deck has been hand-edited after its build — see the "don't rebuild
after a hand-edit" rule in [`docs/pptx-deck-building.md`](pptx-deck-building.md).

A file that will not open as a `.pptx` — corrupt, truncated, or another Office app's
format under a renamed extension — is refused with a message naming the path, not a
traceback.

## `extract` — a draft spec out of any deck

```bash
bin/run extract "decks/Board Update.pptx"
bin/run extract "decks/Board Update.pptx" --as md
```

```
90 slide(s) -> decks/Board Update.deck.yaml
12 picture(s) -> decks/Board Update.media
41 shape(s) could not be converted — each is named in Board Update.deck.yaml
```

Reads every slide in reading order and writes it as a draft `.deck.yaml` that builds, or
as a Markdown transcript. Shapes that overlap vertically are one row and are read left to
right, so a row of four cards comes back in the order a reader sees it rather than in the
order of their top edges. This is the way in for a deck that came from somewhere else — a
client's file, last quarter's version, a deck someone sent you — and the way back into a
deck deckwright built whose spec is gone.

| Flag | Effect |
|---|---|
| `--out` / `-o` | Where to write. Default: beside the deck, as `<deck>.deck.yaml` or `<deck>.md`. |
| `--as` | `yaml` for a draft spec, `md` for a transcript. Default `yaml`; any other value is refused. |
| `--theme` / `-t` | Theme the draft names, and the grid it is drafted against. Default `base`. |
| `--force` | Overwrite an existing file at that path, and replace the draft's media folder. Without it, either one already existing is refused. |

A draft is written once. The second `extract` of a deck — the client sent a new version,
the file grew three slides — finds the spec you have been editing at the destination and
refuses rather than replacing it; `--force` is how you say the edits are expendable. The
refusal comes before the deck is read, as does an `--as` that is neither `yaml` nor `md`.
The media folder is checked before anything is written, so its refusal leaves the draft
unwritten too. `--force` replaces a folder there, with everything in it, and refuses a file
or a link at that path.

**The media folder** is `<draft>.media` beside the draft — `Board Update.media` for
`Board Update.deck.yaml` — holding each picture the draft places, named for its slide:
`slide4-2.png` for slide 4's second picture, `slide4-hero.png` for a deckwright placement
with the id `hero`. The draft's `src:` points into it, so the draft builds where it was
written. A picture the slide has no room for is written there too, and named in the
draft. A transcript writes no files; each picture is a line, `*picture: <its alt text>*`.

### A deck deckwright built

Every shape `build` draws is named for the placement that drew it (`s3.q.card#2`), so a
deck deckwright built comes back as its placements, not only its words.

| Placement | Comes back as |
|---|---|
| `card` | its heading, its body and its `pair:` |
| `bullets` | its heading, its items and `columns:` |
| `prose` | its paragraphs and `cite:` |
| `table` | its header and rows |
| `chart` | its kind and data, read from the values the chart caches |
| `image` | its picture, in the media folder; its `alt:` or `decorative:`; its `over:` lines |
| `rule`, `panel` | themselves, a rule's orientation and a panel's `pair:` included |
| any other | bullets of its words — or, holding only a picture like a `document:` does, an `image:` of it — with a comment saying so |

Each is placed at `at: {box: …}`, in percent of the canvas. The box is the rectangle the
build's manifest recorded, when that manifest is beside the deck — or, for a copy saved
under another name, any manifest beside it recording the same build id — and otherwise the
rectangle its shapes cover, rounded outward so words drawn tight in it still fit. An
author's `id:` and a `morph:` name come back, as do a slide's `animate:` and
`transition: morph`. A placement drawn as `p2` keeps that name after `p1` is deleted by
hand, so a rebuild names its shapes as before. A `pair:` comes back when the plate's fill
and ink are a pair the drafted theme declares; `surface`, the default, stays unwritten.

A `reveals:` comes back where a spec can state it: the whole placement revealed, by one
trigger that is itself drafted, in no ring. A trigger added in PowerPoint can say more —
reveal only a card's words, reveal a card from a second shape, or reveal each of two
cards from the other — and each of those is left out with a comment naming it, so the
draft still builds.

What the file does not hold is said in a comment on the slide: a component whose fields
are not in it (`# s8.p1.stats: drafted as bullets: …`), a card's icon, and — over an
image — each line's rung and the scrim's settings. An `icon:` placement's glyph is not in
the file by name either, so the icon is named as the shape it drew. A slide's `chrome:`
overrides — a title moved or set on another rung — do not come back: its chrome returns
as words, in the theme's place for them. Anything added to such a slide by hand
(words, a table, a card, a chart, a picture) is named under the "did not fit" comment
rather than banded, since a band could overlap the placements. A placement grouped by hand
is still read back. One pasted in PowerPoint keeps its original's name, so that name now
covers two placements; both are read as any other deck's shapes are.

### A deck from anywhere else

Kickers, titles, subtitles, body text, tables and speaker notes convert, and a hyperlinked
run comes back as `[words](address)`. So do three kinds of figure.

- **A chart** comes back as a `chart:` block: its kind and its data, read from the values
  the chart caches. An XY or bubble chart, one with an empty value or two series of one
  name, and one whose cache does not cover its categories are named with the reason
  instead.
- **A card** is a filled shape holding one or two paragraphs, or a text box holding them
  that lies on exactly one filled shape. Two lines are a heading and a body; one line is a
  heading when bold, and body copy when not. A filled shape covering 40% of the slide or
  more is a panel the slide's words sit on, not a card.
- **A picture** comes back as an `image:` with its alt text, or `decorative: true` when
  Office marks it decorative, and its file goes in the media folder — a photo filling a
  layout's picture placeholder included. A picture covering the whole slide, and one the
  deck links rather than embeds, are named instead. Words come first: when banding a
  slide's pictures pushes some of its words off it, and leaving them out pushes fewer, the
  pictures are named in the draft and their files still written.

A table of a single row — a label band, a one-row layout table — comes back as bullets,
since it has no body rows to put under a header. A slide painted in one of the theme's
own pair colours comes back with that `background:`. Size, position and every treatment
do not convert: each slide comes back as chrome plus placements banded in the content
band. Every shape that held something and did not convert — a connector, a line, SmartArt,
an unlabelled band or arrow — is named in a `# not converted:` comment on the slide it came
from. Repeats collapse into one line, so twenty-nine freeform icons read as
`# not converted: 29 × freeform`; the count the command prints is one per shape, and so is
larger than the number of comment lines. A dropped shape carrying alternative text also
gets `# alt text on freeform 'Logo': <its alt text>`, or `*alt text on …*` in a transcript,
so what it showed survives; alt text that is only a file name is left out, and so is a
picture's.

A group is walked rather than named: its children convert as though each sat on the slide,
ordered among themselves and taking the group's place in the reading order. Eight levels
of nesting are walked; a group nested deeper than that is named whole in a
`# not converted:` comment instead.

A shape PowerPoint stores inside `mc:AlternateContent` — an equation, a 3D model, ink — is
read from its fallback, as `inspect` and `diff` read it. Its words convert like any other
shape's, and a fallback picture comes back as a picture.

Three things can put a line in the chrome rather than the bullets, in this order.

- A title, centre-title or subtitle placeholder, whatever the shape is named.
- A shape named `s<n>.chrome.title`, `s<n>.chrome.kicker` or `s<n>.chrome.subtitle` —
  the names `build` writes — so a deck deckwright built comes back with the chrome it was
  authored with. One frame named `s<n>.chrome` carries stacked lines: three are read by
  position, since that is the order the compiler stacks them in, and two are ambiguous —
  the larger line is the title and the other is named for the side of it it sits on.
- Failing both, the slide's first block, when it is a single line, is set larger than
  every other block on the slide, and runs at least 1.4× the slide's median type size.
  Anything looser leaves it a bullet.

A background is named only when its colour is one the named theme declares. Drafting a
deck against a theme other than the one it was built on will not match, and the draft says
so — `# this slide was painted 12161B; name a background pair` — leaving the choice of
pair to you.

The bullet marker `build` writes into a `bullets` component is taken off again, so a deck
can be extracted and rebuilt any number of times without the dot accreting. A leading dot
in a deck deckwright did not build is left alone; there it is a character the author typed.

A placeholder outranks a shape name, each field is claimed once, and a losing claim keeps
its place in the reading order as bullets. The size test reads only runs carrying a size
of their own, so a deck that leaves every size to its layout gets no title from it.

Two things are passed over without a comment, because neither held anything: a layout
placeholder nobody typed into, and an empty text box. A shape painting the whole canvas in
a flat colour is passed over too — it is the slide's background, and comes back as one.
The words inside a SmartArt graphic are named without being recovered, and so are a
chart's title and axis titles: its categories and series come back in its `chart:` block,
its own labels do not.

What builds out of a stranger's draft is one rectangle repeated for the length of the
file. [`docs/treatments.md`](treatments.md) is what fixes that — read it and give each
slide the shape its content earns before the deck goes anywhere. The draft's header says
the same thing at the top of the file.

The draft names `--theme` and is drafted against it: a placement's `rows:` spans that
theme's own grid, so a theme declaring `scale: {rows: 6}` gets six-row spans. Each
table placement is given the height that table will ask for at build, so its band is
sized by its contents; a chart or a picture takes half the grid, and every other placement
a fixed two rows. A name that resolves to no theme file and no packaged theme fails here,
before anything is written, rather than later at `build`.

A slide holding more than the grid can band still yields a spec that builds. Its blocks
and cards run together into one list, a long list takes a second or third column
(`columns:` in the draft) — whichever holds the most lines, each measured wrapped to its
column the way `build` measures it — and anything still left over is written in as comment
lines under `# more than one slide holds — these did not fit, and are yours to place:`: a
table's rows, a chart with its numbers, a picture with its file and alt text.

The transcript carries what the draft does: each placement's and card's words as a list,
each picture as its alt text, and a table or a chart's data as a table.

It invents no `sections:` — a `.pptx` cannot say where its sections were, and a guessed
one would make every slide's `section:` a lie. `out:` defaults to
`out/<slug>/<title> v1.pptx` — the same slug `new` uses, so one deck name gives one
output directory whichever command wrote the spec. The draft compiles before it is
touched; a slide that yielded no words at all becomes a titled placeholder rather than a
hole.

## `conform` — onboard a brand template

```bash
bin/run conform templates/brand.pptx --adopt brand
```

Derives a theme from the template, drives every capability through it one slide at a
time, and reports what it carries. Exits non-zero if any exercise failed. Full doc:
[`docs/conform.md`](conform.md).

| Flag | Effect |
|---|---|
| `--out` / `-o` | Output root. Default `out/conform/`. |
| `--adopt` | Keep the derived theme as `templates/<NAME>.theme.yaml`, beside the template it binds. The template must already be in `templates/` — nothing is copied. Refuses a name already bound to another template that is also there. |
| `--force` | With `--adopt`, replace an existing theme of that name. |

`out/` is disposable by design, so a theme left there is a theme you will lose. `--adopt`
is what moves it somewhere durable: after it, `templates/<NAME>.theme.yaml` is the file to
read and edit, and any deck can name it as `theme: <NAME>`.

## `shot` — screenshot an HTML file

```bash
bin/run shot card.html --width 900
```

Renders an HTML file to a PNG with headless Chrome, cropped to content. This is the same
path the `panel` and `document` components use internally; the command exposes it for
building and eyeballing a card's HTML before wiring it into a deck.

| Flag | Effect |
|---|---|
| `--out` / `-o` | Output `.png`. Default: alongside the `.html`. |
| `--width` / `-w` | Layout width in CSS px. Default 1000. |
| `--scale` | Device scale factor. Default 2, or `$DECKWRIGHT_SHOT_SCALE`. |

See [`docs/panels.md`](panels.md) for the CSS-variable contract these cards are themed
through, and the canvas ceiling that clips a too-tall one.

## `sample` — a template to onboard against

```bash
bin/run sample
bin/run conform templates/sample.pptx --adopt sample
```

Writes a small brand template deckwright owns outright, so the `conform` walkthrough runs
with nothing to hunt for. It lands in the theme directory — `templates/` unless
`DECKWRIGHT_THEME_DIR` says otherwise — because `--adopt` reads a template where it lives
and refuses one anywhere else. Pass a path to override; if that path is outside the
theme directory, the printed next step tells you to move it there first.

| Flag | Effect |
|---|---|
| `--force` | Replace an existing file at that path. Without it, an existing file is an error — you may have put your own there. |

It carries a real colour scheme (six accents, none of them Microsoft's, so a derived
theme binds all six and a hued `dk2` becomes `inverse`), a font scheme in a face
deckwright can measure, and slides whose runs use it — because `conform` takes the face
from a template's own slides, so an unmeasured face here would reach every deck built
from the adopted theme.

**It is a pipeline fixture, not brand-variance evidence.** It is shaped like what the
compiler already handles, so a clean `conform` against it proves the pipeline runs —
never that deckwright copes with a template nobody designed against. That question is
only answered by real brand templates in `templates/`, and the sample is stamped in
its `docProps` so [the corpus guard](testing.md) refuses it mechanically rather than
by convention.

## `doctor` — what this install can do

```bash
bin/run doctor
```

```
PASS   glyphs.bundle     4,001 glyphs @ 50f0603134ce
PASS   theme.builtin     base resolves (packaged)
PASS   fonts.base        2 installed: Helvetica, Courier New
WARN   tools.soffice     not found (soffice) — needed by render, and QA's
                         render-based checks; brew install --cask libreoffice
SKIP   templates.brands  no brand template — tests/test_templates.py skips, so a green suite is
                         the unit tests only
```

Read-only ground truth, in pf-core's `pf-doctor` shape (run that one too — it attests
the framework install). Reports the version that answered, the glyph bundle against its
manifest, whether `theme: base` resolves, from where, and whether it loads — a theme
that resolves but will not parse is a `WARN` naming the file and the loader's message —
whether this machine has the faces `base` sets type in, the sample template, the corpus,
and each of the five external tools **resolved exactly as the runtime resolves them, then
checked for existence** — so a `DECKWRIGHT_SOFFICE` or `DECKWRIGHT_CHROME` pointing somewhere
wrong shows up here rather than mid-render.

The `fonts.base` row is only ever about `base`: a brand theme belongs to a deck, so
`qa` covers that one. A face the machine lacks is a `WARN` — the render substitutes
something else, so QA's render-based checks judge type you will not ship. Without
fontconfig the row is a `SKIP`: the question could not be asked. It is a `SKIP` too when
`base` itself did not load, since there are then no faces to ask about — the theme row
carries that failure.

**A missing tool is a `WARN`, never a `FAIL`.** LibreOffice, Poppler, Chrome and
fontconfig are each needed by some commands and irrelevant to others, so absence is a
fact about this machine; every warning names the command that installs it. Two things
`FAIL`, and only a `FAIL` sets a non-zero exit: a glyph bundle that does not match its
manifest, and a `theme: base` that resolves to a path with no file at it. A `base` that
resolves to a real file it cannot parse is a `WARN`, so a malformed theme of your own does
not fail `bin/setup` or CI.

## `glyphs` — the built-in icon set

```bash
bin/run glyphs find globe
bin/run glyphs verify
bin/run glyphs sync --ref 50f0603134ce7b70b2d71b686cc13e8b57ccb74c
```

The ~4,000 Material Symbols that `icon:` draws from ship as one archive,
`glyphs.zip`, beside the `glyphs.sum` manifest that pins them and the set's licence.
Four thousand loose files cost more in per-file overhead than in content — as one
stored archive they are 716KB in the wheel against 16.5MB installed as files, and a
glyph reads faster because there is nothing to decompress.

| Sub-command | Flag | Effect |
|---|---|---|
| `find` | | Print every glyph name containing a substring, aliases included, so `icon:` does not need the catalogue. Exits 1 on no match. |
| `find` | `--limit` | Most names to print, 40 by default; `0` prints all. A capped run says how many it dropped. |
| `verify` | | Check every glyph in the bundle against its manifest hash. Offline, and what `bin/setup` runs. |
| `sync` | | Rebuild the bundle from the upstream commit the manifest already pins — repairs a checkout without moving the set. |
| `sync` | `--ref` | Vendor a **different** upstream commit: fetch, curate, and rewrite both files. |

`find` matches hyphens and underscores alike, and searches the alias tables as well
as the vendored names — so `glyphs find globe` returns `globe`, the alias, rather
than only the `language` it resolves to. [`glyphs.md`](glyphs.md) groups the set by
what a slide is about; `find` is for when you already have the word.

**Updating to newer icons is `sync --ref` and reading a text diff.** The fetch is a
blobless sparse checkout of just the icon selection (~119MB, ~35s, into a temp
directory that is deleted straight after), then three rules are applied — the
`_fill1_24px` suffix comes off the name, a missing `viewBox` is inserted, and any
drawing that only reads right under nonzero winding is dropped, because deckwright fills
every glyph even-odd. The command prints what moved:

```
vendored the set @ 7c1e9ab04d3f (118 dropped — they need nonzero winding)
  added      14  cardiology, chess, deceased, dew_point, …
  changed     3  groups, language, pin_drop
```

Then `git diff` on `glyphs.sum` names every icon that appeared, vanished or was
redrawn — one line each, so **a re-vendor is reviewed as text, never as a binary**.
Run `bin/test` after: the suite re-measures the winding property over whatever the
sync produced, and fails naming any glyph that cannot ship. Provenance and the full
curation rules are in `src/deckwright/icons/glyphs/material/SOURCE.md`.

## Environment variables

Every knob is read from `os.environ` **at call time**, so `.env` changes take effect
between invocations without a reinstall. Entry points load `.env` from the working
directory on startup. Defaults live beside the code that reads them, not here.

| Variable | Governs |
|---|---|
| `DECKWRIGHT_THEME_DIR` | Where a spec's `theme:` name is resolved — `<name>.theme.yaml`, beside the `.pptx` it binds to. Relative to the CWD, so set it when running from outside the repo. A name not found there falls back to the packaged built-ins, so `theme: base` resolves anywhere. |
| `DECKWRIGHT_CACHE_DIR` | Cache root — rendered panel PNGs and media extracted from templates. |
| `DECKWRIGHT_ICON_DIR` | A glyph directory searched *before* the theme's own and the shipped set. |
| `DECKWRIGHT_SOFFICE` | The LibreOffice command `render` invokes. |
| `DECKWRIGHT_PDFTOPPM` | The Poppler `pdftoppm` command that rasterizes the converted PDF. |
| `DECKWRIGHT_RENDER_DPI` | Rasterization DPI for `render`. |
| `DECKWRIGHT_CHROME` | The Chrome/Chromium/Edge binary for `shot` and panels. Autodetected when unset. |
| `DECKWRIGHT_SHOT_SCALE` | Device scale factor for HTML screenshots. |
| `DECKWRIGHT_CHROME_NO_SANDBOX` | Set to `1` to pass `--no-sandbox`. Off by default: a card renders HTML that may not be yours, and the sandbox is the process-level boundary around it — what the HTML itself may do is bounded separately by the content policy in `SECURITY.md`. Needed in containers that deny the unprivileged user namespace Chrome needs; implied when running as root, where the sandbox cannot work at all. A build that dies for want of a sandbox names this variable. |
| `DECKWRIGHT_SHOT_TIMEOUT_S` | How long to wait on headless Chrome. |
| `DECKWRIGHT_SHOT_CANVAS_H` | Render canvas height in CSS px. A taller card is clipped by the browser; the build detects that and tells you to raise this. |
| `DECKWRIGHT_PDFTOTEXT` | The `pdftotext` command QA's text extraction uses. |
| `DECKWRIGHT_PDFTOTEXT_TIMEOUT_S` | Timeout for it. |
| `DECKWRIGHT_MAX_BEAT_SHAPES` | Most shapes one beat of a staged build may reveal before `qa` warns (`beat-size`). Default 6. |
| `DECKWRIGHT_PDFFONTS` | The Poppler `pdffonts` command QA reads a render's embedded fonts with — `font-substituted` and `cjk-unrendered`. Absent, `font-substituted` falls back to `fc-list`. |
| `DECKWRIGHT_PDFFONTS_TIMEOUT_S` | Timeout for it. |
| `DECKWRIGHT_FC_LIST` | The fontconfig `fc-list` command that answers which faces this machine has — the font files `render` hands LibreOffice, `doctor`'s `fonts` row and QA's `font-substituted` check. Absent, `render` links no fonts and the other two go silent rather than guess. |
| `DECKWRIGHT_FC_MATCH` | The fontconfig `fc-match` command `render` asks for the font to draw each CJK language with, when the deck carries Chinese, Japanese or Korean text. Absent, none is linked. |
| `DECKWRIGHT_FC_LIST_TIMEOUT_S` | Timeout for `fc-list` and `fc-match`. |

pf-core supplies the rest — `LOG_LEVEL`, `LOG_FILE` and the API-key vars. See
`docs/pf-core/config.md` (the symlink `bin/setup` creates).

## External tools

Seven commands shell out. A tool that is not installed fails with a message naming the
binary it looked for, the command that installs it here, and the `DECKWRIGHT_*` knob that
points at one installed elsewhere:

| Tool | Needed by |
|---|---|
| LibreOffice (`soffice`) | `render`; QA's render-based checks |
| Poppler `pdftoppm` | `render`; QA's render-based checks |
| Poppler `pdftotext` | QA's overflow check |
| Poppler `pdffonts` | QA's `font-substituted` and `cjk-unrendered` checks |
| Chrome / Chromium / Edge | `shot`; **building** any deck that uses a `document` component |
| fontconfig `fc-list` | `render`'s font linking; `doctor`'s `fonts` row; QA's `font-substituted` check |
| fontconfig `fc-match` | `render`'s CJK font linking |

`fc-list`, `fc-match` and `pdffonts` are the exceptions to the paragraph above: nothing
fails without them. Without fontconfig, `render` links no fonts into LibreOffice's profile
and renders as LibreOffice alone can. Without `pdffonts`, `font-substituted` falls back to
`fc-list`, and `cjk-unrendered` goes silent; without `fc-list` too, both do.

`inspect` and `qa --no-render` need none of them. `build` needs only Chrome, and only
when the spec uses `document:` — the one component rendered through HTML. `panel:`
paints a native rectangle and needs nothing external, despite the name it shares with
[`panels.md`](panels.md).

## Exit codes and logging

`0` on success. `1` for a domain failure — a bad spec, a template that cannot yield a
theme, a `--fail-on` threshold met, or a `conform` run with any failure. Unexpected
errors exit non-zero with a traceback in the log.

A missing or failing external tool exits 1 with its message and no traceback: the fix
is on the machine, not in the stack. Debug logging is `-v` / `--verbose` — see
[Global options](#global-options).

## Adding a command

1. Add a `@app.command()` function to the concern module it belongs with, under
   `src/deckwright/cli/`: `build.py` (build/render/shot/qa), `reading.py`
   (diff/inspect/extract), `onboarding.py` (new/demo/conform/sample/doctor), or
   `glyphs.py` — or a new sibling module for a new concern. Keep it thin: parse
   arguments, call **one** service or orchestrator function, print the result. No
   business logic: the command parses arguments and calls one function.
2. Raise the project's own errors (`SpecError`, `ThemeError`, `LayoutError`) for bad
   input; pf-core's CLI scaffold maps them to exit codes and messages already.
3. Add the command to this doc's table of contents and give it a section.
4. If it introduces an env knob, follow the wrapper-function recipe in
   `compile/build.py`'s `theme_dir()` — a module constant for the default, a
   wrapper calling `pf_core.utils.env.resolve_*` so a malformed value warns and falls
   back rather than crashing, and the read happening at call time — then add it to
   `.env.example` **and** the table above.
