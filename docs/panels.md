# Panels — HTML rendered onto a slide as a picture

A panel is HTML rendered by headless Chrome to a PNG and placed on a slide as
one picture shape — the mechanism behind `document` and any future
HTML-backed component. A panel is not a native shape: a slide's chrome and the
`callouts` / `stats` / `bullets` components draw real python-pptx text frames
and autoshapes; a panel is a single rasterized image with no shape structure
PowerPoint can see inside it.

For AI assistants: [`pptx-deck-building.md`](pptx-deck-building.md) covers the render/QA loop
end to end; this doc is the full reference for the panel pipeline
specifically.

---

## Table of Contents

- [What a panel is, and when to use one](#what-a-panel-is-and-when-to-use-one)
- [The theme-as-CSS-variables contract](#the-theme-as-css-variables-contract)
- [The cache and its key](#the-cache-and-its-key)
- [The render canvas ceiling](#the-render-canvas-ceiling)
- [Region slicing](#region-slicing)
- [The costs](#the-costs)
- [The markdown raw-HTML sharp edge](#the-markdown-raw-html-sharp-edge)
- [`source` is resolved beside the deck spec, then as given](#source-is-resolved-beside-the-deck-spec-then-as-given)
- [Adding a new panel-backed component](#adding-a-new-panel-backed-component)

## What a panel is, and when to use one

`deckwright.panels.model.Panel` is HTML plus a target width in CSS pixels.
`deckwright.panels.place.place_panel(ctx, panel, left=, top=, width=|height=,
render=)` renders it once, then adds it to the slide as a picture, scaled to
fit the given inches while preserving aspect ratio.

Use a panel when the content is a document, a code listing, or a file tree —
something that is easier to show *as itself* than to re-typeset as bullet
text, and where the audience benefits from seeing the real artifact rather
than a paraphrase. `document` (`deckwright.components.doccard`) is the current
example: it reads a real markdown file and renders it into a macOS-style
window card via `deckwright.services.htmlcard.markdown_card`.

Do not reach for a panel when a native component already says what you need —
see [The costs](#the-costs) for why.

## The theme-as-CSS-variables contract

`deckwright.panels.css.panel_css(theme)` emits a `:root` block declaring the
theme's resolved colours (`--c-<role>`), type sizes (`--t-<role>`), and faces
(`--font`, `--font-mono`). Pass it as `content_css` (or append it to your own
CSS) so the browser-rendered half of the slide draws from the same theme as
the python-pptx half. `deckwright.services.htmlcard`'s own rules consume these
with hardcoded fallbacks (`var(--c-bg, #ffffff)`), so a card rendered without
a theme still looks reasonable. This is a real, verified contract — set a
theme's `bg` role to a colour and the panel's background changes to match.

**A `var()` fallback only fires when the variable is undefined.** `--font`
and `--font-mono` are always declared by `panel_css`, so a card rule reading
`font-family: var(--font, sans-serif)` never falls back to `sans-serif` even
when the theme's own face isn't installed in the browser rendering it — the
declaration just collapses to the bare face name. `panel_css` bakes a
generic fallback into the custom property's own value instead
(`--font: "Calibri", -apple-system, "Segoe UI", Roboto, Helvetica, Arial,
sans-serif;`), and the face is quoted so a multi-word name still tokenises.

## The cache and its key

`deckwright.panels.cache.cached_png(panel, scale=, theme_hash=, render=)` keys on
`sha256(html, width, scale, theme_hash)`, truncated to 20 hex chars, under a
`panels/` subdirectory of `DECKWRIGHT_CACHE_DIR` — which defaults to
`.deckwright-cache`, so `.deckwright-cache/panels`, and the subdirectory is appended
to whatever the var is set to. A hit skips the Chrome invocation entirely and
logs `panel_cache_hit`; a miss renders to a temp file and `os.replace`s it into
place, so a killed process or a concurrent build never observes a torn PNG.
The theme's hash is part of the key on purpose:
edit the template and every cached panel invalidates, because the palette a
stale PNG shows would otherwise silently drift from the theme.

## The render canvas ceiling

Chrome screenshots a window of a fixed size — `DECKWRIGHT_SHOT_CANVAS_H` CSS px
tall, 4000 by default — and content below that line is simply not in the
image. Nothing downstream can see the loss: the picture is recorded
`rendered: "image"`, so `qa`'s overflow check skips it by design, and a
truncated card is *shorter* than a whole one, so `document`'s
too-tall-for-the-body-rect guard does not fire either.

`render_html_to_png` therefore measures the document itself. It appends a
script that publishes `document.documentElement.scrollHeight` onto an
attribute, asks the same Chrome run for `--dump-dom`, and raises `RenderError`
naming the required height and the canvas limit if the document was taller.
Raise `DECKWRIGHT_SHOT_CANVAS_H` (or shorten the source) to clear it.

The measurement is the browser's own, not a guess about the image — but it
depends on the injected script actually running, and the page decides that.
The probe is appended *after* the document, so a source whose content model
swallows the rest of the parse takes the probe with it: a raw `<plaintext>`,
`<textarea>` or `<xmp>`, or an unterminated `<script>`, turns everything that
follows into text. A `document:` source is a real markdown file someone else
wrote, so this is not an edge case reserved for arbitrary HTML fed to
`deckwright shot` — one stray tag reaches it. A CSP blocking inline scripts, or
a browser ignoring `--dump-dom`, defeats it the same way.

The pixels are the fallback, and they are read rather than shrugged at. A card
floats on white, so ink on the render's **last** row with none on its **first**
means the canvas cut the content off, and that raises `RenderError` naming the
canvas height — the same fix as the measured case. Ink on *both* rows is the one
case that still only warns (`html_shot_height_unknown`) and renders unchecked: a
page bleeding to both edges is a deliberate full-bleed design, which only
`deckwright shot` produces, and no pixel test can tell it from a clip.

## Region slicing

`Panel.regions` names sub-rectangles (in CSS pixels) of the rendered HTML.
Pass `slice_by=<name>` to `place_panel` and it crops one picture per region
from the *same* cached render — Chrome runs once regardless of how many
regions come out of it. Slicing exists so parts of one rendered document can
animate independently (a click-reveal per region) without paying for a
separate render per part.

## The costs

State these to whoever is deciding whether a slide's content becomes a
panel — they are not edge cases, they are what a panel *is*:

- **Unselectable.** A panel is one image; nothing inside it can be
  copy-pasted as text.
- **Unsearchable.** PowerPoint's own text search finds nothing inside it.
- **Invisible to the overflow check.** `deckwright qa`'s `overflow` check reads
  `pdftotext` output; a panel's text was never text to the PDF extractor, so
  a line that got cut off inside the picture produces no finding. `bounds`
  and `reserved` still check the *picture's own box* against the slide edge
  and the theme's reserved regions, but nothing checks what got cut off inside it.
- **Does not reflow.** A panel is a fixed-aspect raster at the size it was
  rendered. Resize the placement and the image scales; it does not
  re-wrap text, and PowerPoint cannot re-wrap it for you.

Chrome, and any text the deck needs someone to actually find,
select, or have read aloud stay native. Panels are for dense bodies — a real
document, a code listing, a file tree — where showing the artifact itself is
worth more than the text being machine-readable.

`place_panel` scales to the `width`/`height` you pass and places it there —
it does not check that the result fits the slide unless you ask it to. Pass
`max_height` and it raises `LayoutError` naming the slide, the placed height,
and the budget if the picture comes out taller; omit it and an oversized
picture places silently, for `bounds`/`reserved` to catch (or not) later.
`document`, the only panel-backed component today, does **not** pass it: it
places the panel and then compares the picture's own height against
`ctx.body_rect`, raising with advice specific to its content ("shorten the
source file"). So the `max_height` backstop is currently written and never
armed, and `document`'s own check is the only guard in force. Every new
panel-backed component should pass `max_height` — it is the one part of the
pipeline where the final size can't be known until after the render, and a
documented convention that one component forgot is why this is a parameter
rather than advice in this doc.

## The markdown raw-HTML sharp edge

`deckwright.services.htmlcard.markdown_card` calls `markdown.markdown()`, which
passes raw HTML straight through by design — this is standard markdown
behaviour, and deckwright does not suppress it, because doing so would also
break HTML someone embedded in the document on purpose. The hazard: a
document containing `a<b` or `List<Item>` is not safely inert. `<b` opens a
real `<b>` tag, and everything until markdown finds a matching `</b>` (which
may be the rest of the paragraph, or the rest of the document) renders bold.
`document` exists to pipe real, unedited files onto a slide — so a source
file with a stray `<` followed by a letter can silently reformat everything
after it. There is no automated check for this; it is only caught by eye on
the rendered card.

## `source` is resolved beside the deck spec, then as given

`document`'s `source` is looked for beside the deck spec first — the rule `extends:`,
`image:`'s `src` and `background:`'s image all follow — and then as given, absolute
or relative to the working directory.

Write `source:` relative to the spec, and the deck directory stays movable. The
as-given fallback is what keeps a deck written against the repo root building; it is
a fallback, not the rule. When neither place holds the file the error names both.

## Adding a new panel-backed component

1. Build the HTML — reuse `deckwright.services.htmlcard` helpers
   (`window_card`, `markdown_card`, `filetree_card`) or hand-author your own.
2. Wrap it in a `Panel(html=..., width=<css px>)`, adding `regions=(...)` only
   if parts of it need to animate independently.
3. Call `place_panel(ctx, panel, left=, top=, width=|height=, max_height=,
   render=_render)` where `_render` wraps
   `deckwright.services.htmlshot.render_html_to_png`. Route through a thin
   module-level `_render` function (as `doccard.py` does) so tests can
   monkeypatch it without shelling out to Chrome.
4. Return a `BodyResult` with `height=picture.height / 914400` so the caller
   knows the vertical extent it consumed.
5. Pass `max_height=ctx.body_rect.height` (or whatever rect you placed
   against) — `place_panel` raises `LayoutError` naming the slide, the placed
   height and the budget if the picture comes out taller, rather than
   silently shipping one that intrudes on a reserved region. This is the backstop,
   not a replacement for a domain-specific check: `document` compares the placed
   picture's height against its own rect and raises with advice specific to its
   content ("shorten the source file") — do the same when your component's
   overflow has an actionable, content-specific fix. `max_height` is what would
   catch everything else, including a bug in that check; `document` passes none,
   so it is the one component running without that net.
