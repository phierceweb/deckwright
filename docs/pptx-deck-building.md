# Building PowerPoint decks with deckwright

deckwright assembles decks programmatically with **python-pptx** and renders/QAs them
headlessly. This is the general, tool-level guide — the workflow and the
library gotchas that hold for *any* deck.

---

## Table of Contents

- [Toolchain](#toolchain)
- [The build → render → QA loop](#the-build--render--qa-loop)
- [python-pptx patterns & gotchas](#python-pptx-patterns--gotchas)
- [Body components — composing a slide](#body-components--composing-a-slide)
- [Animations — inject `<p:timing>`, verify in PowerPoint](#animations--inject-ptiming-verify-in-powerpoint)
- [Rendering doc / code cards](#rendering-doc--code-cards)
- [Versioned output & sharing](#versioned-output--sharing)
- [Hand-editing a delivered deck — stop rebuilding](#hand-editing-a-delivered-deck--stop-rebuilding)
- [Spinning a generator back up](#spinning-a-generator-back-up)

## Toolchain

| Concern | Module / tool |
|---|---|
| Authoring shapes and text | `pptx` (python-pptx) + `deckwright.utils.shapes` / `deckwright.utils.deck` |
| Animation and slide transitions | `deckwright.motion` — see [Animations](#animations--inject-ptiming-verify-in-powerpoint) |
| Doc / code "cards" (rendered snippets) | `deckwright.services.htmlcard` + `deckwright.services.htmlshot` (headless Chrome) |
| Slide rasterization + overview | `deckwright.services.render` (LibreOffice → PDF → images) + `deckwright.services.montage` (contact sheet) |

External binaries and their env knobs (see `.env.example`):

- **LibreOffice** (`soffice`) — `DECKWRIGHT_SOFFICE`; DPI via `DECKWRIGHT_RENDER_DPI` (default 110).
- **Poppler** (`pdftoppm`, `$DECKWRIGHT_PDFTOPPM`) — the PDF → per-slide image step.
- **A Chromium-family browser** — `DECKWRIGHT_CHROME` (autodetected if unset); `DECKWRIGHT_SHOT_SCALE`
  (default 2), `DECKWRIGHT_SHOT_CANVAS_H` (default 4000 — a card taller than this is clipped by the
  browser and the render is rejected), `DECKWRIGHT_SHOT_TIMEOUT_S` (default 60).

## The build → render → QA loop

To see what the library can do before writing anything, run `bin/run demo` — every
capability in one deck, generated from the exercise registry against any theme, with a
`.content.md` beside it to read instead of opening it.

1. `bin/run build <spec>.deck.yaml` compiles a spec into a `.pptx` and its
   manifest — the normal path, documented in [`docs/authoring.md`](authoring.md).
   A hand-written `build_deck.py` assembling the deck with python-pptx + the
   deckwright helpers is the older one, and still what a deck the spec cannot
   express falls back to.
2. `bin/run render <deck>.pptx --contact-sheet` rasterizes every slide to
   `render/<deck>/slide-NN.jpg` and writes `render/<deck>/contact_sheet.png`.
3. **View the images — that is the real QA.** Overflow, overlap, low contrast, and
   corner collisions only show up by eye; the contact sheet gives the whole deck
   at a glance.

> **QA caveat:** LibreOffice renders the *final* state, so every animated shape
> appears visible. It cannot show reveal / interactive / hidden states — those are
> only verifiable in real PowerPoint (see Animations).

For a deck built by `deckwright build` (i.e. one with a manifest), `bin/run qa <deck>.pptx`
runs automated bounds/reserved/min-font/contrast/overflow checks on top of the eyeball
pass above. See [`docs/qa.md`](qa.md) for what it catches and — the more important
half — what it structurally cannot.

## python-pptx patterns & gotchas

- **Edit existing title runs with `run.text = ...`**, never `text_frame.text = ...`
  (the latter collapses all formatting into one unstyled run).
- **Kill the theme drop shadow** on every autoshape: `shape.shadow.inherit = False`
  (deckwright's `solid()` does this for you).
- **Colors:** `RGBColor.from_string("27B94C")` — no leading `#`, no 8-digit alpha;
  either corrupts the file.
- **Autoshape text anchors MIDDLE** in render — set
  `text_frame.vertical_anchor = MSO_ANCHOR.TOP` and zero the margins for top-left text.
- **Delete a slide with `deckwright.utils.deck.delete_slide(prs, i)`** — it drops the
  relationship *and* the `sldId`. Removing only the `sldId` leaves an orphan part →
  "Duplicate name" zip warning and a corrupt file.
- Reusable primitives in `deckwright.utils.shapes`: `solid`, `para`, `textbox`, `rrect`,
  `rect`, `notes`, `bring_to_front` (z-order — python-pptx has no z-order API).

## Body components — composing a slide

A slide has no layout. `deckwright.layouts.compose.render_slide` paints the
backdrop, places the chrome (`kicker`/`title`/`subtitle`), walks the spec's
placements calling one **component** for each, then writes the chrome over the
top — so a title told to sit on a painted panel lands above it. Components live in
`deckwright.layouts.components` (the registry) with implementations in
`deckwright.components.*`; register one with `@component("name")`. For the spec
side of this — every component's fields and a worked example each — see
[`docs/authoring.md`](authoring.md).

A component takes one argument, `ctx: SlideCtx`, and lays out shapes inside
`ctx.body_rect` — the rectangle its placement was handed. Colour comes off the
slide's live pair, never a fixed role: `ctx.fg()` for text, `ctx.paper()` for
what is behind it, `ctx.dim()` for secondary copy. That is what keeps a
component legible on an `inverse` background as well as on the page.

Paint a fill of your own — a tile, a badge, a panel — and the text on it answers
to *that fill*, not to the slide: `ctx.ink_on(fill)` for readable ink, and
`ctx.accent_on(fill, size_pt=…)` when you want an accent and will accept the ink
where the accent does not measure up. `ctx.accent(size_pt=…)` is the same check
against the slide's own paper. `ctx.color(role)` is the unguarded read, for fills
and strokes.

`ctx.text_align()` / `ctx.text_anchor()` carry the placement's `align:`/`anchor:`;
pass them to `para(align=…)` and `textbox(anchor=…)`. A component that sets no
text calls `_shared.require_default_align(ctx)` so the keys fail loudly instead of
being silently dropped.

It returns a `BodyResult(groups, height)` (frozen dataclass; `as_body_result()` normalizes
a bare group list from a component that skips `height`):

- `groups` — the reveal shape: one list per revealable unit (one bullet
  column, one callout row, …). Each item in a list is either a bare shape id
  (fades in) or `(shape_id, kind)` for a specific entrance, `kind` in `fade` /
  `wipeup` / `wiperight` — see Animations below for how the composer turns
  these into a click build.
- `height` — the vertical inches the component actually consumed, so a caller
  can bound the body against `ctx.body_rect.height` instead of taking the
  component's word for it. `None` if the component doesn't report it.

Worked example: `src/deckwright/components/callouts.py` computes a capped
`row_h` for its own overflow guard, then reuses that same value for
`height=len(items) * row_h` — reuse the guard's value, don't recompute it, or
the guard and the reported height can drift apart.

## Animations — inject `<p:timing>`, verify in PowerPoint

python-pptx cannot author animations; you append raw `<p:timing>` OOXML. `deckwright.motion`
is one module per concern — `builds` (shape reveals), `chartbuild` (a chart's own build),
`interactive` (click-to-reveal), `transition` (how the show arrives at a slide) — over a
shared `_tree` that owns the timing skeleton and the one-timing-per-slide rule. The public
helpers are re-exported from the package:

- `add_click_build(slide, spids)` — all target shapes reveal together on one click.
- `add_click_sequence(slide, groups, stagger_ms=0)` — one group reveals per click;
  each item is a `spid` or `(spid, kind)` with `kind` in `fade` / `wipeup` / `wiperight`.
- `add_click_reveals(slide, pairs)` — click a specific trigger shape to reveal its
  target (interactive, any order). One target may appear under several triggers, and
  routinely does: a placement that drew a plate, an icon and two lines of type is four
  trigger shapes for the same reveal.
- `add_chart_build(slide, spid, by)` — a native chart's own build (`by` in
  `category` / `series` / `element` / `all`), emitting `<p:bldGraphic>`/
  `<a:bldChart>` instead of the `<p:bldP>` visibility toggle the builds above
  use — a chart is a `graphicFrame`, not a shape whose visibility can flip.
  Wired from the spec via `animate: by_category`/`by_series` on a chart slide
  (`deckwright.components.chart`); see [`charts.md`](charts.md).
- `add_transition(slide, kind, direction=, speed=)` — a different element entirely
  (`<p:transition>`, no timing tree). Wired from the theme's `motion.transition`; a slide
  opts out with `transition: none`. See [`theme.md`](theme.md#the-decks-transition).

**The expensive lesson:** LibreOffice accepts malformed timing and converts it to PDF
without complaint, but PowerPoint rejects it — it opens with "needs repair" and silently
strips the animation. A reveal build needs the full main-sequence skeleton **and** a
`<p:bldLst>` (omitting the bldLst was the original repair cause).

Verification is four layers, and only the last is real:

| Layer | Catches | Where |
|---|---|---|
| **XSD validation** | Required-attribute omissions, wrong child order, bad enums, empty lists. | `tests/test_ooxml_schema.py`, against the vendored ISO/IEC 29500-4:2016 schemas |
| **Structural readback** | Literal `presetID`/`filter`/`delay`/`spid` values. | `tests/utils/`, `tests/layouts/` |
| **Corpus** | That a build survives every brand template in `templates/`. | `tests/test_templates.py` — gitignored, and **CI never has it** |
| **Real PowerPoint** | Repair prompts, playback, direction, timing. | A human, per change |

The XSD layer is not optional garnish. `<a:chart>` requires `bldStep`; a `<p:bldLst>`
with no children and a `<p:childTnLst>` with no children are invalid too. None of the
three is visible in a render or a PDF, so only the schema catches them.

**`<p:bldP>` is only legal for text-bearing shapes** — `[MS-OI29500]` §19.5.16(c) requires
its `spid` to name an `sp` holding a `t` element with textual data. A picture, a connector
or a text-free icon animates fine, but gets no build-list entry — and no `grpId` on its own
effect node either, since the attribute exists only to name one. That is decided **per
shape**, so a mixed slide carries `grpId` on its text-bearing shapes and not on the rest.
When *every* animated shape on a slide is text-free the build list is omitted entirely.

- **Only real PowerPoint confirms an animation is repair-free.** All three main-sequence
  helpers have now been opened in it, on a deck built from `base`, with no repair prompt:

  | Helper | Status |
  |---|---|
  | `add_click_build` | Byte-verified against PowerPoint's own output, and confirmed at playback — one click cascades the slide. |
  | `add_click_sequence` | Confirmed at playback: one click per group, in order. |
  | `add_chart_build` | Confirmed at playback, including the required `bldStep` — one click per category. |

  The wipe variants of `add_click_sequence` are still unconfirmed: no component emits a
  kinded reveal item, so only the fade path has been exercised. `add_click_build`'s byte
  comparison was made on a slide whose shapes all bear text, so it says nothing about a
  mixed slide, where some shapes take a `bldP` and a `grpId` and the rest take neither.
- **Keynote does not play a chart build.** The same file that builds one category per
  click in PowerPoint shows the chart whole in Keynote. `<p:bldGraphic>`/`<a:bldChart>`
  is the one construct here with a known consumer gap — for a Keynote audience, use
  `animate: together` or split the categories across slides.
- **Wipe direction is inverted vs. the filter name in practice** — a bar that should grow
  *up* uses subtype 1 / `filter="wipe(down)"`; grow *right* (wipe in from the left) uses
  subtype 2 / `filter="wipe(left)"`. Confirm any new direction in real PowerPoint.
- **When a new animation repairs:** author it once in real PowerPoint on *named*
  shapes → save → read that slide's `<p:timing>` → reproduce it verbatim → diff
  byte-for-byte. (The "learn-back" loop.)

## Rendering doc / code cards

Show what a real doc or snippet *looks like* as a slide image instead of retyping it:

- `deckwright.services.htmlcard.markdown_card(md, filename=...)` wraps markdown in a macOS-style
  window card; `window_card(body_html, filename=..., extra_css=...)` is the generic
  frame for bespoke HTML.
- `filetree_card(folder, rows, filename=..., count=, more=)` renders a file-explorer tree —
  each row is `(label, kind, level)` with `kind` in `file` / `folder` / `hi` (highlighted) —
  the "where this file lives" graphic (docs / rules / skills slides). Scale up with `extra_css`.
- `deckwright.services.htmlshot.render_html_to_png(html, out)` screenshots the card via headless
  Chrome, autocropped to content. `card_to_slide(slide, html, left=, top=, height=)`
  renders **and** places it in one call, returning the picture (use its `.shape_id`
  for animations or `.width.inches` to anchor a callout at its edge).
- Match the card's `max_width` to the render `width` so the shot is tight.
- The `document` body component (`deckwright.components.doccard`) wires this into a
  slide: `document: {source: <path>}` renders a markdown file into a
  window card via `panel_css(theme)` + `place_panel` and places it as a picture
  (`filename`, `max_width`, `side: left|right|full` are optional). `source` is
  resolved **beside the deck spec first**, then as given — the rule `extends:`,
  `image:` and `background:` already follow, so a deck directory stays movable.

## Where everything goes

Three directories, split by how long the thing lives. Getting this wrong is how a
repo ends up with 378MB nobody dares delete.

| Directory | Holds | Committed |
|---|---|---|
| `authoring/` | **Decks you are writing**, and whatever they read. Your content, not the library's. | no |
| `examples/` | **deckwright's own demonstration specs** — the feature tour, the chart catalogue, the table and shape tours. They exist to exercise the library, so they are part of it. | yes |
| `templates/` | **Brand `.pptx` files and the themes derived from them**, side by side. A theme is not deck-specific, so it never lives beside one deck's source. | `README.md` only |
| `out/` | **Everything a command writes** — builds, manifests, renders, PDFs, `qa.md`, `conform/` output. | no |

**`authoring/` and `examples/` are not the same shelf.** A deck you write has no business in
the library's history; a spec that exercises the compiler does. Keeping them apart is
what stops `git add -A` from sweeping your work into a commit — the alternative is
remembering to exclude it every time, which is not a design.

`out/` is disposable by design: deleting the whole directory must never lose anything
but time. If something in there cannot be regenerated by re-running a command, it is
in the wrong place — move it to `examples/`.

**One directory per deck, not one directory of decks.** `render` and `qa` both write
beside the `.pptx` they were given, into `render/<deck>/`, so two decks sharing a
directory keep their slides apart — but they do interleave two decks' output in one
place, which is the thing a deck directory exists to keep separate.

**Inside one deck's directory, four things and no more:**

```
out/smoke/
  Smoke.pptx                 the deck
  Smoke.manifest.json        what `qa` reads; it pairs with the deck by name
  Smoke.content.md           the same build as words, for a human to read
  Smoke.beats.md             the same build as its reveal order, click by click
  render/Smoke/              slide-NNN.jpg, the PDF, qa.md, qa.json, contact sheets
  .build/                    generated inputs and intermediates — hidden on purpose
```

A `.pptx` embeds every picture it places, so once a deck is built the sources that
went into it are scratch, not output. The assembled spec and the stand-in
photographs go in `.build/`; the deck's own directory shows the deck, the manifest,
and the render you look at. `conform` follows the same rule — its per-exercise decks
build and are cleaned up in `.build/`, and an exercise that *failed* is deliberately
left there, because the spec that produced a `FAIL` is what you want when you go to
diagnose it.

**Scratch does not go in the repo.** Probe scripts, one-off experiments and
throwaway renders belong in a temp directory outside it. Every `look/`, `check2/`,
`fix-attempt/` that lands under `out/` survives the session that made it and is
indistinguishable from output that matters a week later.

## Versioned output & sharing

- **Never overwrite a deck you have sent someone** — export each iteration as
  `<Name> vN.pptx` under `out/` and bump `N` every time.
- **A `.pptx` is self-contained.** Every image placed with `add_picture` / `card_to_slide`
  is embedded inside the file (`ppt/media/`), so only the `.pptx` needs to travel (to
  OneDrive, email, etc.) — the `assets/` and rendered-card PNGs stay behind.
- **Fonts are *not* embedded.** The built-in faces travel because every viewer has a
  metric clone of them: Helvetica (Arial on Windows, Liberation Sans under LibreOffice)
  and Courier New for code chips (Liberation Mono under LibreOffice). A brand face is a
  different matter — for guaranteed fidelity on any machine, use PowerPoint → *Save* →
  **Embed fonts in the file** before sharing.

## Hand-editing a delivered deck — stop rebuilding

Once the deck is "done" and being polished by hand in PowerPoint, the spec is no
longer the source of truth — **a rebuild silently wipes every manual edit.** From that point,
change the deck by **surgically editing the latest `.pptx`** with python-pptx:

- `Presentation(path)` → find shapes (`shape_type == MSO_SHAPE_TYPE.PICTURE`, or match on
  `.name` / titlebar text) → reposition (`shape.left/top/width/height = Inches(...)`) → add
  new shapes / `add_picture` → `save()` as the next `vN`.
- Repositioning a picture that a connector points at? Re-aim the connector too (set its
  bounding box), or it will float.
- Verify by rendering **that specific file**: `bin/run render "<Name> vN.pptx" --contact-sheet`.

**See what the edits were, and carry them back.** `bin/run diff "<Name> vN.pptx"` compares
the deck against its build manifest by shape name and reports what moved, was retyped,
added or removed — so a hand-edit can end up in the spec rather than only in the binary.
Every shape is named for the placement that drew it, and PowerPoint keeps that name
through an edit. Full command: [`docs/cli.md`](cli.md#diff--what-a-hand-edit-changed).
- Never rebuild from the spec — treat it as a historical scaffold from that point.

`qa` on a hand-edited deck reports `stale-manifest` and means it: the manifest still
describes the build, so every other finding is about the file that *was* built. The render
is the check that still applies — see [`qa.md`](qa.md#provenance).

## Spinning a generator back up

If you later need to *regenerate* instead of hand-edit, copy the spec snapshot the build
left in `out/<deck>/.build/<name>.deck.yaml` as
the template. The skeleton is small: `Presentation(template)` → one `add_slide(BLANK)` per
slide → place shapes/cards with the `deckwright` helpers → `prs.save(OUT)`. Per-slide card
sources (`_render_*.py` + the `.md` / `.html` snippets) render to `assets/` and are embedded
at build time.
