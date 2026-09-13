# Extending — writing a component

Two ways to add one. **A deck-local component** goes in a Python module the deck names
with `extends:`, and is right when the shape only makes sense for that deck.
**A built-in** lives in `src/deckwright/components/`, and is right when the shape recurs.
The component API is identical; only the registration and the checklist differ.

The API surface itself is [`docs/authoring.md`](authoring.md#adding-a-component-the-spec-cannot-express).
This page is the part that page does not cover: the things that go wrong, and the
checklist for promoting a component into the library.

---

## Table of Contents

- [The seven that bite](#the-seven-that-bite)
- [Promoting a deck-local component to a built-in](#promoting-a-deck-local-component-to-a-built-in)
- [What the gates check](#what-the-gates-check)

---

## The seven that bite

Every one of these is a real failure from writing five components in an afternoon, not a
list of things that could theoretically go wrong.

### 1. A shape you do not return is on screen from the first beat

Returning the reveal groups is documented. The consequence of *leaving a shape out* is
not: it is not merely unanimated, it is **visible before the first click**. A row of
icons omitted from their rows' groups all appear at once, ahead of the text they belong
to, and the slide looks broken in a way the spec cannot explain.

So drawing a shape is three steps, not two: draw it, `record` it, and put its id in the
group it belongs to. `place_icon` returns its shape for exactly this reason.

The build manifest is where you check, not the render:

```
groups: [4, 3, 3, 3]   an icon per row is missing — those icons are on screen at once
groups: [4, 4, 4, 4]   each icon arrives with its row
```

### 2. `align` and `anchor` are enums inside a component

The spec writes `align: right`; inside a component that is `PP_ALIGN.RIGHT`, and an
anchor is `MSO_ANCHOR.MIDDLE`. Passing the spec's own string raises
`ValueError: 'middle' is not a valid MSO_VERTICAL_ANCHOR` from deep inside python-pptx.

Use `ctx.text_align()` and `ctx.text_anchor()` when the placement's own values are what
you want. A component whose layout cannot honour them should **refuse** them with a
message saying why — `callouts` and `diverge` both do, because their type is set against
a rail that centring would pull it off.

### 3. The colour accessors do not all return the same type

| Call | Returns | For |
|---|---|---|
| `ctx.color(role)` | `RGBColor` | fills and strokes — the unguarded read |
| `ctx.fg()` / `ctx.dim()` | `RGBColor` | type on the slide's own pair |
| `ctx.accent(size_pt=…)` | **hex `str`** | accent *text*, contrast-guarded at that size |
| `ctx.ink_on(fill)` | **hex `str`** | type on a fill your component painted |
| `ctx.rgb(hex)` | `RGBColor` | turning either hex back into something `para()` takes |

Mixing them gives `assigned value must be type RGBColor` or
`int() can't convert non-string with explicit base`.

`ctx.accent()` may hand back the ink instead of the accent — that is the guard working,
not a bug. A brand orange under AA at caption size is not readable, and the guard says
so.

When a component needs the accent regardless because size and weight carry the
distinction, do not reach for `ctx.color("accent-1")` and comment around it. Take a
`color:` field instead, and follow what `_shape.stroke` and `nav` both do: **a role the
author named is used as asked and refused only when it cannot be seen at all** — under
about 1.2:1 against the slide's own paper. The default stays guarded, so the component
is readable for someone who did not think about it and obedient for someone who did. An
unguarded read hard-coded into the component takes that choice away from every deck.

### 4. Painting your own ground means inking against it, in the manifest too

A component that fills its rect must ink its type with `ctx.ink_on(fill)` **and record
that colour**. Type set on the slide itself takes `ink, paper = ctx.text_ink(box, size_pt=…)`
for the box it sits in, because a `panel` or a picture placed under it is its real ground,
and records `fg=ink, bg=paper`. `ctx.pair.fg` is the *slide's* ink; recording it on a band you painted
reports clean while the type is unreadable, because `qa`'s `contrast` check reads the
manifest and believes it.

A fill another placement's text may be laid over goes on `ctx.painted` once it is drawn:
`ctx.painted.append((rect, fill))`, or `(rect, Disc(fill))` for a round one
(`from deckwright.layouts.registry import Disc`). Without it, `text_ink` over your fill
measures the page.

### 5. Reserved regions apply to what you draw, not to your rect

`ctx.body_rect` already clears the theme's `reserve:` regions. Anything you draw *wider
than that rect* does not. A full-bleed band drawn from a placement that sits above the
logo wedge will still run into it, and `qa`'s `reserved` check will say so.

The fix is usually not to clamp: it is that decoration wider than the placement belongs
to a separate placement with `bleed: true`, and the component should take a `pair:` and
paint its own rect instead.

### 6. Tag each revealed shape with its motion role

A reveal group's items are `(shape_id, role)`: `text` for a shape carrying words,
`surface` for a filled shape carrying none, `line` for a stroke, `figure` for a picture or
glyph, `datum` for a chart. The theme's `motion.roles` turns the role into an entrance, so
a component never names an effect. A bare `shape_id` still works and enters with `fade`
whatever the theme binds, which is the look nothing else on the slide has once a theme
changes a role. [`theme.md`](theme.md#motion-roles) has the table.

### 7. Refuse with `LayoutError`; anything else is reported as a bug

Raise `LayoutError` from `deckwright.errors` for content you cannot place, with a message that starts `slide N (component 'name'):`. It reaches the author as that one line. Any other exception from your code keeps its traceback and gets a final line naming the slide and component. That is right for a bug and wrong for a refusal, so do not let a `KeyError` stand in for "this field is required".

---

## Promoting a deck-local component to a built-in

A deck-local component needs only `@component("name")` and the `extends:` line. A
built-in has a checklist, and three of its steps are enforced by nothing.

### Code

1. **`src/deckwright/components/<name>.py`** — the module. It needs a double-quoted
   `@component("<name>")`, a module-level `_FIELDS` tuple written as one parenthesised
   line of double-quoted names, and the literal call `known_fields(ctx, _FIELDS)`. Those
   three shapes are grepped for, not parsed, so a clever rewrite of any of them fails the
   gates. Item mappings take `known_item_fields`.
2. **`src/deckwright/components/__init__.py`** — add it to the import list. There is no
   autoloader; without this the module never registers and the component does not exist.
3. **`src/deckwright/conform/`** — add an exercise to the family module that owns the
   shape. Per
   [`testing.md`](testing.md) **that is the test** for the layout
   arithmetic: it runs against every real brand template. A unit test re-checking the
   same maths is explicitly not wanted.
4. **Unit tests for what a successful build cannot reach** — every `raise`, and any
   invariant the shape exists for. `diverge` draws a negative value to the left of its
   rule; a corpus build renders that correctly either way, so a test pins it.

### Docs

`docs/components.md` and `docs/authoring.md` are gated: add the `### ` section with its
field table, and the row in the component index. **Do not add the section last** — the
gate's regex looks ahead for the next heading and raises rather than failing readably.

`docs/errors.md` quotes the whole component list inside two error messages, and that is
gated too — those rows are transcripts a reader compares against character by character,
and they had lost two components before anyone noticed.

Then the ungated ones, which nothing will catch:

- The component **count in prose** — `docs/components.md`, `docs/authoring.md`,
  `docs/README.md`, `CLAUDE.md` and `docs/errors.md` each spell it out in words.
- A row per error the component raises, under `## Components`. Every message on that page
  is real output — generate it, do not transcribe it from the source.

---

## What the gates check

| Gate | Refuses |
|---|---|
| `tests/test_docs.py` | A field in `_FIELDS` that no doc names, a documented field the code does not read, and a component missing from either registry listing quoted in `docs/errors.md`. |
| `tests/components/test_unknown_fields.py` | A component that declares `_FIELDS` or `_ITEM_FIELDS` and never enforces it — declaring the tuple for the docs gate's benefit and skipping the check is how the last five got there. |
| `bin/check-layers` | A component importing from `cli`, `conform`, `compile` or `qa`. |
| `bin/check-framework` | `logging`, `os.environ`, a bare `ValueError`, `print()`, a hand-rolled atomic write. Raise `LayoutError` from `deckwright.errors`. |
| `python -m pf_core.guards` | The file over its size budget. |
