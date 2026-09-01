# Imagery — photographs, and the text on them

How `src/deckwright/imagery/` fits a photograph to a box, measures the pixels a line of
text will sit on, and solves the scrim that makes it legible. This doc covers the
**engine's internals**: the fit arithmetic, the sampler, the auto-opacity solve, and
what each of those writes into OOXML.

**To write `image:` or its `scrim:` in a deck spec, read
[`docs/components.md`](components.md#image--a-photograph-and-any-text-reversed-out-of-it);
for a slide's `background:`, [`docs/authoring.md`](authoring.md#background).** The
messages an author sees are [`docs/errors.md`](errors.md). This doc explains what
happens after the spec is parsed.

---

## Table of Contents

- [Why this subsystem exists](#why-this-subsystem-exists)
- [The pipeline](#the-pipeline)
- [Fitting: `cover`, `contain`, `crop`](#fitting-cover-contain-crop)
- [Masks square the box first](#masks-square-the-box-first)
- [Sampling: what "the colour behind this text" means](#sampling-what-the-colour-behind-this-text-means)
- [The scrim solve](#the-scrim-solve)
- [Gradients and the reach fraction](#gradients-and-the-reach-fraction)
- [`Backdrop.behind()` — the one question everything asks](#backdropbehind--the-one-question-everything-asks)
- [Painting order, and the page exception](#painting-order-and-the-page-exception)
- [What reaches OOXML](#what-reaches-ooxml)
- [The manifest and the render check](#the-manifest-and-the-render-check)
- [Adding a new fit or mask](#adding-a-new-fit-or-mask)

## Why this subsystem exists

Everywhere else in deckwright a colour pair is known before anything is drawn: the palette
contrast-checked `ink` against `page` when the theme loaded, and the manifest records
both. A slide painted on a photograph has no such pair. What is behind a title in one
corner is not what is behind a footer in the other, and neither is the theme's paper.

So imagery does not assume — it **measures**. Every contrast number a picture slide
records is read out of the source's own pixels, and the scrim opacity is solved to a
target rather than chosen by eye.

## The pipeline

```
fit_image()      aspect arithmetic  → ImageFit (dest rect + srcRect trim)
place_picture()  python-pptx + XML  → the picture shape, cropped never squashed
cells()          PIL                → the window averaged to a grid of colours
resolve()        the solve          → Scrim (colour, ink, opacity, gradient)
paint_scrim()    XML                → a translucent rect over the picture
Backdrop         held on the ctx    → every later line asks it what it is really on
```

`paint_backdrop()` in `imagery/paint.py` runs that sequence for a slide background;
the `image` component runs the same steps for one placement. Both end by setting or
returning a `Backdrop`, which is the object the rest of the build interrogates.

## Fitting: `cover`, `contain`, `crop`

All of `imagery/fit.py` is arithmetic on aspect ratios. **A source is never distorted
to fit** — it is cropped or it is inset:

- **`cover`** trims the source to the box's shape and fills the box. `dest` is the box.
- **`contain`** shrinks a copy of the box to the source's shape and letterboxes.
  `dest` is smaller than the box, positioned by `align`/`anchor`.

`crop:` applies **first**, centred, trimming the source to a named aspect before the
box gets a say — that is how a portrait shot is told to read as a 16:9 band. The two
trims are composed back onto source fractions by `_compose`, because the second trim
is taken of an already-trimmed window.

The trim is carried as the four fractions `a:srcRect` wants, so the source file is
never rewritten. `align`/`anchor` only matter under `contain`; under `cover` the
fitted picture already fills the box.

## Masks square the box first

`circle` on an oblong box would draw an ellipse. `square()` takes the largest square
inside the box and places it by `align`/`anchor`, so the mask is actually round. The
mask itself is a preset geometry swap on the picture's own `spPr` — `rect`, `ellipse`
or `roundRect` — not a clip path.

## Sampling: what "the colour behind this text" means

`imagery/sample.py` opens the source, crops the window that shows behind a rect, and
averages it down to a grid whose long edge is `CELLS` cells.

That grid size is the whole design. Finer, and one antialiased pixel decides the
scrim for the entire slide. Coarser, and a specular highlight small enough to sit
inside a single letter averages away — which is exactly the highlight that breaks the
letter. The constant is tuned to roughly glyph-stroke scale; it lives in
`sample.py`, not here.

Two more rules make the measurement honest:

- **Transparent pixels are composited onto the base colour first**, because that is
  what the renderer will show through them.
- **`weakest()` returns a percentile, not the minimum.** `TOLERANCE` of the cells are
  allowed to be worse than the reported colour. A hard minimum would let one stray
  specular pixel black out a whole slide.

Decoded images are cached on path plus size and mtime, so editing a source
invalidates it but reusing it across twenty slides costs one decode.

## The scrim solve

A scrim's colour and its ink are **one contrast-checked palette pair**, so full
opacity is legible by construction. What has to be measured is everything short of
that: the least opacity that still clears the target.

`solve_alpha()` walks opacity upward in fixed steps, compositing the scrim over the
weakest sampled cell at each one, and returns the first that clears `required`. It is
always solvable — at opacity 1.0 the scrim *is* its pair's background colour, and the
palette already checked that pair against its own ink.

This is why an `opacity:` an author writes by hand and an `auto` one are recorded
differently: the auto one is a measurement, and `scrim.checked()` exists to report
what an explicit one *really* produces so QA can disagree with the author.

## Gradients and the reach fraction

A `top` or `bottom` gradient scrim is at full opacity at one edge and clear at the
other, so text near the clear end gets less scrim than the peak opacity suggests.

`gradient_fraction()` answers how much of the peak actually reaches a band, **at the
band's weakest point** — a `bottom` gradient is weakest at the band's top edge, a
`top` one at its bottom. The solve then divides by that fraction to get the peak
opacity to draw.

Two failure modes fall out, and both raise `LayoutError` with the fix in the message:

| Situation | Why it cannot be solved |
|---|---|
| The text sits where the gradient is fully clear | No peak opacity makes it legible. Give an explicit `opacity:` or drop the gradient. |
| The required peak exceeds 1.0 | The text reaches too far into the clear end. Move it toward the gradient's edge, or use a flat scrim. |

## `Backdrop.behind()` — the one question everything asks

`Backdrop` holds the placed picture, the colour painted under it, and the resolved
scrim together. Every line of text drawn afterwards calls `behind(rect, ink=...)` and
gets the hex colour it is *really* on — sampled from the pixels that show at that
rect, composited with the scrim at the opacity the scrim reaches over that band.

A `contain` fit leaves letterbox bands inside the placement. `window_under()` returns
`None` there rather than a lie about the photo, and `behind()` falls back to the
painted base. That fallback is why a caption in a letterbox band still records a
truthful background.

## Painting order, and the page exception

**Any backdrop is painted as a colour first, then embellished with an image.** A theme
that ships no art still renders its own ink legibly, and a picture that fails to cover
the canvas has a known colour underneath rather than whatever the master carries.

The `page` background is the exception, handled by `paint_inherited()`. A master's own
paint is whatever its designer chose — a stretched photograph on some templates, a
`bgRef` on others — so:

- The template paints a **picture**: it is left alone and sampled instead, so the
  brand's art survives and every line records the pixels it truly sits on. The slide
  itself is marked as carrying a backdrop, since deckwright adds no picture shape here and
  the render check would otherwise have nothing to see.
- The template paints a **colour**: deckwright paints over it unless
  `theme/surface.py`'s `inherited_surface()` says that exact colour is already down.
- The template declares **nothing**: that is still a colour. Every renderer shows
  white there, and it is treated as white.

Assuming a master carries the page colour is what once put a deck of dark titles on a
dark blue photograph with the contrast check reporting nothing wrong.

## What reaches OOXML

python-pptx has no API for a masked picture or a translucent fill, so `imagery/draw.py`
writes the elements directly:

| Effect | Element |
|---|---|
| Crop without rewriting the file | `a:srcRect` (via python-pptx's `crop_*` properties) |
| Mask | `prst` on the picture's own `a:prstGeom`, `a:gd` for a rounded radius |
| Flat scrim | `a:solidFill` with `a:alpha` inside the colour |
| Gradient scrim | `a:gradFill`, two stops, `a:lin` running down the shape |

A scrim shape clears every existing fill element before inserting its own, and drops
its line and shadow — a scrim is a pane of glass, not a plate.

## The manifest and the render check

The picture shape is recorded with `rendered="picture"`. That flag is one trigger for
the one QA check that reads pixels instead of the manifest: `qa/imagery.py` opens the
render, measures the **modal** colour around each text box in horizontal bands, and
compares against WCAG AA.

The second is the slide-level `backdrop` flag, set by `paint_inherited()` when the
template's own master paints the picture. There is no shape to carry `rendered`
there — deckwright placed nothing — so without it every deck built on a picture-painting
template would skip the one check that can see what its text really sits on.

The mode, not the mean — glyphs cover a minority of a text box, so averaging drags the
estimate toward the ink and understates how bad the real background is. Bands, not one
box, so a gradient is judged where it is weakest. It is the only check that catches a
scrim the build thought was sufficient and the renderer composited differently. See
[`docs/qa.md`](qa.md).

## Adding a new fit or mask

A **fit** (a third strategy beside `cover`/`contain`):

1. Add the name to `FITS` in `imagery/fit.py` and a branch in `fit_image()` returning
   an `ImageFit`. Express the crop as source fractions — never resize the source.
2. Confirm `window_under()` still tells the truth for it. If the fit can leave part of
   the placement without picture, it must return `None` there.
3. Add an exercise to `src/deckwright/conform/photos.py` (see
   [`testing.md`](testing.md)) — that is the test.

A **mask**:

1. Add the name to `MASKS` in `fit.py` and to `_PRST` in `imagery/draw.py`, mapping it
   to a preset geometry.
2. If the shape is only correct on a square, route the box through `square()` at the
   call site the way `circle` does.
3. Add an exercise.
