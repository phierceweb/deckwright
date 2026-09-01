# Motion — builds, reveals and transitions

How a deck moves: what a click reveals, and how the show arrives at a slide. This
documents the subsystem's **behaviour**. The wire format is
[`authoring.md`](authoring.md) for the spec side and [`theme.md`](theme.md) for the
theme side — never this file.

Do not confuse the two things called motion here: a **build** is a shape appearing on a
slide (`<p:timing>`), and a **transition** is the move between slides
(`<p:transition>`). They are different OOXML elements with nothing in common but the
subject, and a slide can carry one of each.

---

## Table of Contents

- [Why this is raw XML](#why-this-is-raw-xml)
- [The modules](#the-modules)
- [Motion roles](#motion-roles)
- [What a click covers](#what-a-click-covers)
- [The build list, and who may be in it](#the-build-list-and-who-may-be-in-it)
- [Transitions](#transitions)
- [Verification](#verification)
- [Adding an entrance kind](#adding-an-entrance-kind)

## Why this is raw XML

python-pptx models neither timing nor transitions, so every module here appends OOXML
strings that PowerPoint itself would emit. That has two consequences worth stating
before anything else:

1. **Nothing type-checks it.** A typo in a `filter` string validates clean and silently
   produces no visual effect, because the attribute is `xsd:string`.
2. **The render loop cannot see it.** LibreOffice draws the final state of a slide, so
   a build mid-reveal is invisible, and a transition produces byte-identical images with
   and without one.

Hence [Verification](#verification), which is the most important section here.

## The modules

`src/deckwright/motion/` is one module per concern over a shared skeleton.

| Module | Writes | Owns |
|---|---|---|
| `_tree` | — | The `<p:timing>` skeleton, the effect table, `attach()` (one timing tree per slide, in schema order) and `bld_p_list()`. |
| `builds` | `<p:timing>` | Shape reveals on the main sequence: all at once, or one group per click. |
| `chartbuild` | `<p:timing>` | A native chart's own build, by category or series. |
| `interactive` | `<p:timing>` | Click-a-shape-to-reveal-another, off the main sequence. |
| `transition` | `<p:transition>` | How the show arrives at a slide. |

`layouts/motion.py` is the layer above: it reads `ctx.spec` and `ctx.theme.motion` and
decides which of the above to call. Components never call any of them.

## Motion roles

A component reports **what it is**; the theme decides how that kind of thing moves.
Neither the component nor the spec ever names an OOXML preset — the same indirection
`accent-1` uses onto a palette slot, and for the same reason: otherwise a deck drifts
off-brand one hardcoded effect at a time.

A component returns reveal groups whose items are either a bare shape id (the `text`
role) or a `(shape_id, role)` tuple. `layouts/motion.py` resolves each role through
`theme.motion.roles` to a wire kind before any XML is written.

```python
# components/rule.py — "I am a line being drawn"
return BodyResult(groups=[[(line.shape_id, "line")]], height=0.0)
```

Five roles — `text`, `surface`, `line`, `datum`, `figure` — and three entrance kinds.
A role outside the five is a `LayoutError` naming the component that reported it. The
bindings themselves, and what each role means, are [`theme.md`](theme.md#motion-roles).

**`animate: together` discards roles.** It routes through `add_click_build`, which gives
every shape the same fade, so there is nothing for a per-shape role to say. This is
deliberate: `add_click_build` is the only helper byte-verified against PowerPoint's own
output, and re-expressing it as a one-group sequence would forfeit that.

## What a click covers

Three different things spend a click, and they compose differently.

**Two of them are slide keys and one is a theme key**, which the `Where` column below
states because it is the thing readers most often go looking for in the wrong file.
`animate:` and `reveals:` are written on a slide, in the spec. Everything under
`motion.` — `advance`, `beat_ms`, `stagger_ms`, `roles`, `transition` — is written in
the theme, so a deck moves the same way throughout and one edit changes every slide.
`docs/authoring.md`'s slide-field table correctly does not list `advance:`.

| | Where | Clicks | Notes |
|---|---|---|---|
| `animate: together` | slide | 1 for the slide | Every reveal group flattened into one build. |
| `animate: one_at_a_time` | slide | 1 per group | What a group *is* belongs to the component — a bullet column, a callout row, a stat tile. |
| `motion.advance: after_previous` | **theme** | 1 for the slide | The first group waits for a click; the rest are `afterEffect` nodes `beat_ms` apart. Deck-wide by design — it is not a slide field. |
| `reveals:` | slide | 0 | An `interactiveSeq` fires on clicking a named shape, in any order, and never advances the slide. A trigger placement contributes one `interactiveSeq` per shape it drew, so any part of it is clickable. Chain them — click one to reveal the next — but a ring is refused at build: every placement in it would be waiting on something itself hidden. |

`stagger_ms` offsets shapes *within* one click, so it reads very differently in the
first two rows: across the whole slide under `together`, inside a single group under
`one_at_a_time`.

**A slide carries one `<p:timing>`.** `attach()` refuses a second and names the
collision. That is why `reveals:` and `animate:` cannot share a slide, and why two
charts both building on one slide is an error rather than a silently invalid file.

## The build list, and who may be in it

A main-sequence build emits a `<p:bldLst>` beside the timing. Omitting it was the
original cause of PowerPoint's "needs repair" prompt, so it is not optional — but its
contents are constrained in a way that is easy to get wrong:

- **`<p:bldP>` is only legal for text-bearing shapes.** `[MS-OI29500]` §19.5.16(c)
  requires its `spid` to name an `sp` holding a `t` element with textual data. Pictures,
  connectors, chart frames and text-free icons animate perfectly well, but get no entry.
- **An empty `<p:bldLst/>` is invalid.** `CT_BuildList` requires a child. So when every
  animated shape on a slide is text-free — a slide of images or icons — the build list
  is omitted entirely.
- **`grpId` exists only to name a build-list entry, so it is dropped per shape.** Any
  animated shape that got no `bldP` carries no `grpId` either — including a picture
  sitting on a slide whose text-bearing neighbours did get one. A slide with no build
  list at all is just the case where that holds for every shape. `[MS-OI29500]`
  §19.5.33(h) says a `cTn`'s `grpId` must match one in the `bldLst`; it does not say
  *of the same shape*, so the per-shape reading is the natural inference rather than the
  literal text. The schema makes both optional.

A chart is different again: it is a `graphicFrame`, so its build is a
`<p:bldGraphic>`/`<a:bldChart>` declaration rather than a `<p:bldP>` visibility toggle.
`<a:chart>` requires a `bldStep` attribute; omitting it is schema-invalid.

## Transitions

`<p:transition>` is a sibling of `<p:timing>` under `<p:sld>`, with no timing machinery
at all: a choice of at most one of 21 effect elements, an optional sound, and three
attributes. The whole vocabulary is declared in the schema, so unlike an entrance preset
nothing about it is inferred.

**The transition belongs to the destination slide** — it says how the show moves *to*
this slide from the one before it. Reading it the other way puts every transition in a
deck one slide out.

**Child order is the hazard.** `CT_Slide` is an `xsd:sequence`: `cSld, clrMapOvr,
transition, timing, extLst`. A bare `append` after an animation lands the transition in
the wrong place, and **LibreOffice silently repairs the order on import** — so a round
trip cannot show the corruption. Both writers insert rather than append.

**Direction vocabularies are per element.** `strips` takes corner directions only, the
"orientation" effects take `horz`/`vert` under a `dir` attribute (not `orient`, whatever
most summaries say), and the rest take edges. One shared direction list produces a file
that is invalid the moment it meets `strips`. The table is [`theme.md`](theme.md#the-decks-transition).

Only the base 21 are written. The 2010-era extension set — ripple, glitter, prestige,
morph — is deliberately absent: `mc:AlternateContent` does not validate against
`pml.xsd`, most of them do not survive a LibreOffice round trip even in their fallback,
and morph additionally needs cross-slide shape identity that deckwright does not have.

## Verification

Four layers, and **only the last is real**.

| Layer | Catches | Where |
|---|---|---|
| XSD validation | Required-attribute omissions, wrong child order, bad enums, empty lists. | `tests/test_ooxml_schema.py` against the schemas vendored in `tests/schemas/ooxml/` |
| Structural readback | Literal `presetID` / `filter` / `delay` / `spid` values. | `tests/utils/`, `tests/layouts/` |
| Corpus | That a build survives every brand template in `templates/`. | `tests/test_templates.py` — gitignored, and CI never has it |
| Real PowerPoint | Repair prompts, playback, direction, timing. | A human, per change |

What LibreOffice actively *hides*: wrong element order (it repairs it), schema
invalidity (deliberately invalid probes convert to PDF without complaint), `bldP` loss
on round trip, `advClick`, and several direction inversions.

Confirmed at playback in real PowerPoint: `add_click_build`, `add_click_sequence`, and
`add_chart_build` including `bldStep`. **Keynote does not play a chart build** — the
chart arrives whole; for a Keynote audience use `animate: together` or split the
categories across slides.

Not yet confirmed at playback: transitions, `after_previous`, the `wiperight` entrance,
`reveals:`, and the text-bearing `bldP` filter.

When something does repair, the recovery is the learn-back loop in
[`pptx-deck-building.md`](pptx-deck-building.md): author the effect once in real
PowerPoint on named shapes, save, read that slide's `<p:timing>`, and reproduce it
verbatim.

## Adding an entrance kind

1. Add it to `_EFFECTS` in `motion/_tree.py` — `(presetID, presetSubtype, filter,
   duration_ms)`. `ENTRANCES` and the theme's validation follow automatically.
2. **Do not take the preset ID from a blog post or a single implementation.** Two
   independent sources at minimum, and then the learn-back loop before it ships: a wrong
   ID produces a file PowerPoint offers to repair, which strips every animation on the
   slide.
3. Bind a role to it in `theme.md`'s table, and add a case to
   `tests/test_ooxml_schema.py`.
4. The docs gate reads the entrance list, so a kind with no documentation fails the
   suite.
