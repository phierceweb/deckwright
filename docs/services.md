# Services — where deckwright leaves its own process

`src/deckwright/services/` holds the four modules that stand between deckwright and something
it does not implement. Two shell out to a system binary — `render.py` to LibreOffice and
Poppler, `htmlshot.py` to headless Chrome; `montage.py` is Pillow arithmetic; and
`htmlcard.py` leaves the process not at all, being a pure string builder over the
third-party `markdown` package. This doc covers what each
asks its tool for, what it does with what comes back, and what it raises when the tool is
absent, slow, or lying.

The layers above own the rest. [`panels.md`](panels.md) owns the panel pipeline that sits
on top of `services/htmlshot.py` — the CSS-variable contract, the cache key, region
slicing. [`qa.md`](qa.md) owns what a render is then checked *for*. [`cli.md`](cli.md)
owns the commands, their flags, and every `DECKWRIGHT_*` default. None of that is repeated
here.

---

## Table of Contents

- [The four modules](#the-four-modules)
- [Which command needs which binary](#which-command-needs-which-binary)
- [`render.py` — LibreOffice, then Poppler](#renderpy--libreoffice-then-poppler)
- [`htmlshot.py` — headless Chrome](#htmlshotpy--headless-chrome)
- [`htmlcard.py` — the HTML, and nothing else](#htmlcardpy--the-html-and-nothing-else)
- [`montage.py` — the contact sheet](#montagepy--the-contact-sheet)
- [What is cached — nothing here](#what-is-cached--nothing-here)
- [The failure table](#the-failure-table)
- [Adding a service that shells out](#adding-a-service-that-shells-out)

## The four modules

| Module | Shells out to | Entry | Returns |
|---|---|---|---|
| `services/render.py` | LibreOffice `soffice`, then Poppler `pdftoppm` | `render_to_images` | the page images, sorted |
| `services/htmlshot.py` | a Chromium-family browser | `render_html_to_png` | the PNG path |
| `services/htmlcard.py` | nothing — a pure string builder | `window_card`, `markdown_card`, `filetree_card` | an HTML document |
| `services/montage.py` | nothing — Pillow | `contact_sheet` | the sheet's path |

Every knob each one reads is declared in its own module docstring and resolved through
`pf_core.utils.env` **at call time**, so a `.env` edit takes effect between invocations
with no reinstall. The precedence is always kwarg > env > default.

The fourth external binary a deck workflow touches, `pdftotext`, is not in this package:
`qa/textflow.py` invokes it directly, beside the check that consumes its output.

## Which command needs which binary

| Command | Path through the package | Needs |
|---|---|---|
| `render` | `cli.py` → `render_to_images`; `--contact-sheet` adds `contact_sheet` | `soffice`, `pdftoppm` |
| `qa` | `qa/runner.py` → `render_to_images`, then `qa/textflow.py`'s `extract_pages` on the PDF that render left | `soffice`, `pdftoppm`, `pdftotext` |
| `qa --no-render` | manifest and package only | nothing |
| `shot` | `cli.py` → `render_html_to_png` | a browser |
| `build` | only when a slide carries `document`: `components/doccard.py` → `panels/place.py` → `render_html_to_png` | a browser, conditionally |
| `new` | builds the deck it scaffolds, which carries no `document` | nothing |
| `demo`, `conform` | build every exercise, and `conform/layout.py` includes a `document` | a browser |
| `diff`, `inspect` | read the saved package | nothing |

`document` is the only component that reaches a browser. The `panel` component
(`components/panel.py`) is a native filled block — it draws an autoshape and never
renders HTML.

## `render.py` — LibreOffice, then Poppler

`render_to_images(pptx_path, outdir, *, dpi=, soffice=, pdftoppm=, fmt="jpeg")` runs two
subprocesses, sweeps between them, and returns the page images sorted. Both subprocesses
run with `check=True` and `capture_output=True`; both wrap `CalledProcessError` **and**
`FileNotFoundError` into one `RenderError`, so a missing binary and a failing one produce
the same message naming the command that was tried.

### A user profile per conversion

`soffice` locks one shared user profile. A second conversion starting while the first
holds it exits `0` having converted nothing — the failure then arrives as a missing PDF
rather than as an error. Each conversion therefore gets a temporary profile of its own
via `-env:UserInstallation=file://<tempdir>`, removed when the conversion returns. The
`file://` prefix is load-bearing: `soffice` ignores a bare path here and falls back to the
shared profile, silently reinstating the collision. `tests/services/test_render_profile.py`
pins all three facts off the argv, because racing real conversions to state them is the
flakiest possible test.

### The PDF is output, not scratch

The conversion writes `outdir/<pptx stem>.pdf`, and its absence raises `RenderError`
naming the path it looked for. That file stays: `qa/runner.py` re-reads it with
`pdftotext` for the overflow check. It is not an intermediate to clean up.

### The stale-page sweep

Before rasterizing, `_rendered_pages(outdir)` is deleted — otherwise a deck that got
shorter leaves the previous run's trailing pages behind, and the same function reports
them back as this render's output.

`--outdir` is a free-form user path, so the sweep is scoped three ways: the glob
`slide-[0-9]*`, a raster suffix from `_PAGE_SUFFIXES`, and `re.fullmatch(r"slide-\d+")`
against the whole stem, over entries that are files. What survives is as important as what
goes: `slide-2-notes.md` (wrong suffix), `slide-3-final.png` (a name someone chose, not a
prefix match), a *directory* called `slide-9.jpg` (unlinking it would raise and take the
render down). What goes is `slide-99.jpg` from a ninety-nine-page previous run. The sweep runs *after*
the conversion, so `slide-deck.pdf` from a deck named `slide-deck.pptx` is already on disk
and in the sweep's path when it walks: what saves it is the suffix filter, `.pdf` not
being a raster page, and not the ordering. `tests/services/test_render_outputs.py` holds
one case per line of that paragraph.

The directory is walked with `Path.glob`, not `glob.glob`: a deck directory named
`Deck [v2]` is a character class to the latter, which then matches no page at all.

### Rasterizing

`pdftoppm -jpeg -r <dpi> <pdf> <outdir>/slide` — `fmt` maps `"jpeg"` to `-jpeg` and
anything else to `-<fmt>` unvalidated, so a bad format surfaces as Poppler's own non-zero
exit inside `RenderError`. Poppler names and zero-pads the pages to the deck's own length,
which is the only reason the plain `sorted()` on the way out is page order.

Neither subprocess carries a timeout. A wedged `soffice` blocks the caller for as long as
it wants — unlike `htmlshot.py` (`DECKWRIGHT_SHOT_TIMEOUT_S`) and `qa/textflow.py`
(`DECKWRIGHT_PDFTOTEXT_TIMEOUT_S`), which both cap their wait.

## `htmlshot.py` — headless Chrome

`render_html_to_png(html, out_path, *, width=1000, scale=, chrome=, canvas_height=,
autocrop=True, pad=20, timeout=)` writes the HTML to a temp file, screenshots it, checks
the result was not clipped, and crops it to content. The destination is `unlink`ed before
the browser starts, so a failed run cannot leave the previous PNG in place looking fresh.

### Finding a browser

`_resolve_chrome` takes the explicit argument, then `DECKWRIGHT_CHROME`, then the first
entry of `_CHROME_CANDIDATES` that exists — bare names through `shutil.which`, macOS
app-bundle paths through `os.path.exists`. First match wins, so a machine with both gets
Chrome before Chromium and Chromium before Edge. Nothing found raises
`RenderError` naming `DECKWRIGHT_CHROME`, before any work is done.

### The invocation

`_chrome_cmd` builds one argv that both screenshots and dumps the DOM: `--headless=new`,
a `--user-data-dir` inside the same temp directory as the HTML, `--force-device-scale-factor`,
`--window-size=<width>,<canvas height>`, `--screenshot=<out>`, `--dump-dom`, and the
`file://` URL last. The flags disabling background networking, component update, breakpad,
sync and pings stop full Chrome waking its updater and crash reporter on every panel.
`--dump-dom` rides the same run as the screenshot, so the height probe below costs no
second launch.

stdout and stderr go to **files** in the temp directory, never a `PIPE`. Full Chrome
reparents daemon children that would hold a pipe open long after the screenshot is done.

### Waiting on the file, not the process

`_await_screenshot` polls every 0.3s until the PNG exists and its size has been unchanged
for 0.6s, then returns; `_terminate` then SIGTERMs the browser and SIGKILLs it if it
ignores that for five seconds. Full Chrome writes the image in about a second and then
lingers 30–60s on those children, so waiting for a clean exit would add that to every
panel in a deck.

Two failures come out of the wait, both carrying the last 1500 characters of Chrome's
stderr as `context["stderr_tail"]`: the process exited with no file at all
(`RenderError`, "Chrome exited without a screenshot"), or the deadline passed
(`RenderError`, "headless Chrome timed out"). A third is checked after: a file that exists
but is zero bytes raises "Chrome produced no screenshot".

### The clip check

Chrome screenshots a window `canvas_height` CSS px tall and simply omits anything below
that line, with no error. `_check_not_clipped` decides between four outcomes:

| Evidence | Outcome |
|---|---|
| Probe height ≤ canvas | proceeds |
| Probe height > canvas | `RenderError` naming the height needed and `DECKWRIGHT_SHOT_CANVAS_H` |
| No probe height, ink on the render's last row and not its first | `RenderError` naming the canvas height |
| No probe height, any other ink pattern — both edge rows, neither, or the first alone | logs `html_shot_height_unknown`, proceeds |

Only the third row raises: ink on both edge rows is a deliberately full-bleed page, which
only `deckwright shot` produces, and everything that is not "bottom inked, top clear" stays on
the warn-only path.

The probe is an inline script appended after the document that publishes
`document.documentElement.scrollHeight` onto `data-deckwright-doc-h`, read back out of the
dumped DOM with a regex. [`panels.md`](panels.md) owns *why* the pixel fallback exists and
what defeats the probe; `tests/test_htmlshot.py` covers the decision table with synthetic
DOMs and images, and `tests/test_htmlshot_browser.py` drives both rejections through a
real browser, skipping when none is installed.

A `canvas_height` of zero or less raises `ConfigurationError` before the browser is
launched.

### The crop

With `autocrop` (the default), the PNG is replaced by its bounding box of everything
differing from white by more than `_INK_THRESHOLD` (8 per channel), plus `pad` pixels
clamped to the image. A render with **no** ink has no bounding box and is returned
untouched at full canvas size — a card whose CSS painted the whole canvas does not raise,
it just ships enormous. That is the contract `htmlcard.py`'s white `body` exists to keep.

### `card_to_slide`

Renders a card and adds it to a slide as a picture in one call. No component uses it:
components go through `place_panel` in `panels/place.py`, which caches the render, records
the picture in the build manifest as `rendered: "image"`, and can slice it into regions.
`card_to_slide` does none of those, and with `png_path` omitted it leaves its `mkstemp`
PNG behind.

## `htmlcard.py` — the HTML, and nothing else

Pure functions. No subprocess, no file I/O, no theme lookup — they take strings and return
one HTML document.

- `window_card(body_html, *, filename, max_width=1000, extra_css="", body_class="content")`
  — the macOS-window frame every card shares: traffic-light titlebar, centred filename,
  rounded card, drop shadow. `extra_css` lands after the frame's own rules, which is where
  a caller styles the body.
- `markdown_card(md_text, *, filename, extensions=None, content_css="", max_width=1000)` —
  `markdown.markdown` with `["extra"]` by default, wrapped in the frame with the default
  document typography plus `content_css`. `components/doccard.py` passes `panel_css(ctx.theme)`
  there; that is the whole mechanism by which a card takes the deck's palette.
- `filetree_card(folder, rows, *, filename, count=None, more=None, max_width=470,
  extra_css="", indent_base=20, indent_step=22)` — a folder heading and monospace rows,
  each `(label, kind, level)` with `kind` in `file`, `folder`, `hi`. An unrecognised
  `kind` raises `KeyError` out of the icon lookup rather than one of the project's errors,
  so validate before calling.

Two constraints hold this module in place:

**The `body` background is white on purpose.** `htmlshot`'s `_autocrop` finds the card by
difference from white; a themed body makes the whole canvas ink, the bounding box becomes
the canvas, and every card comes back canvas-height. Theme colour belongs on `.window` and
inside it, which is exactly where `panel_css`'s variables land.

**Nothing is escaped.** `filename`, `folder` and row labels are interpolated straight into
the markup, and `markdown.markdown` passes raw HTML through by design.
[`panels.md`](panels.md) has the failure this produces on a real document, and why
suppressing it would be worse.

The third-party `markdown` dependency is deliberate, and named as such in
the framework-first check: `pf_core.web.markdown.safe_markdown` renders a narrow
escape-first subset for untrusted web content, which drops the tables, fenced code and
definition lists these cards are for.

## `montage.py` — the contact sheet

`contact_sheet(images, out_path, *, cols=4, thumb_width=480, pad=12, bg=…, numbers=True)`
stitches page images into one grid PNG with Pillow, and is reached only from
`deckwright render --contact-sheet`. Nothing in a build calls it.

Each image is scaled to `thumb_width` keeping aspect; the cell height is the *tallest*
thumbnail, so a deck of mixed page sizes gets a ragged grid rather than cropped
thumbnails. `cols` is clamped to at least 1. An empty `images` raises `InvalidInputError`
before anything is opened — a caller mistake, not a tool failure, so it is the one error
out of these four modules that is neither `RenderError` nor a configuration problem. Index
badges are drawn with Pillow's default bitmap font, so they do not scale with
`thumb_width`. The format follows `out_path`'s suffix.

## What is cached — nothing here

None of the four caches anything. Every call reconverts, relaunches, re-renders.

The one cache on this path sits a layer above: `panels/cache.py`'s `cached_png` keys on
the HTML, width, scale and theme hash, so a build that places the same document twice
launches the browser once. [`panels.md`](panels.md) owns the key and its invalidation.
Two consequences follow from the cache being *there* rather than in the service:

- **`deckwright shot` bypasses it.** The CLI calls `render_html_to_png` directly, so it
  always launches a browser — which is what makes it usable for iterating on a card's HTML.
- **`render` and `qa` re-run LibreOffice every time.** `render_to_images` overwrites the
  PDF and the page images in place, so a QA loop costs one full conversion per iteration
  and the previous render is gone.

## The failure table

| Condition | Raised | The message names |
|---|---|---|
| No browser binary found | `RenderError` | `DECKWRIGHT_CHROME` |
| `canvas_height` ≤ 0 | `ConfigurationError` | `DECKWRIGHT_SHOT_CANVAS_H` and the value given |
| Browser exits without writing the PNG | `RenderError` | the stderr tail |
| Browser outlives `DECKWRIGHT_SHOT_TIMEOUT_S` | `RenderError` | the timeout and the stderr tail |
| PNG exists but is empty | `RenderError` | the output path |
| Document taller than the render canvas | `RenderError` | the height needed and `DECKWRIGHT_SHOT_CANVAS_H` |
| Probe swallowed, content on the canvas floor | `RenderError` | `DECKWRIGHT_SHOT_CANVAS_H` |
| `soffice` missing, or exits non-zero | `RenderError` | the `.pptx` and the soffice command |
| Conversion produced no PDF | `RenderError` | the PDF path expected |
| `pdftoppm` missing, or exits non-zero | `RenderError` | the PDF and the pdftoppm command |
| `contact_sheet` with no images | `InvalidInputError` | — |
| `filetree_card` with an unknown row kind | `KeyError` | — |

`RenderError` is deckwright's own subclass of `ClientError` (`src/deckwright/errors.py`), and
raising the base instead throws away the log key that says an external renderer was the
thing that broke — `bin/check-framework` is what enforces it.

## Adding a service that shells out

1. **One module per tool**, named for the tool's job. Put the env knobs in the module
   docstring; that is where the next reader looks.
2. **Resolve the binary through `pf_core.utils.env.resolve_str` at call time**, caller's
   kwarg first, so precedence stays kwarg > env > default
   (a module constant for the default, a wrapper over `pf_core.utils.env.resolve_*`,
   read at call time). Then document the variable in [`cli.md`](cli.md):
   `tests/test_docs.py` fails on any `DECKWRIGHT_*` the code reads and that table omits.
3. **Raise `RenderError`**, with the binary name and the input path in `context=`. Catch
   `FileNotFoundError` alongside `CalledProcessError`: a missing tool and a broken one
   want the same message.
4. **Never `capture_output` a process whose children may outlive it.** Write stdout and
   stderr to files in a temp directory and put a tail of stderr in the error context, as
   `render_html_to_png` does.
5. **Decide the timeout deliberately.** `DECKWRIGHT_SHOT_TIMEOUT_S` and
   `DECKWRIGHT_PDFTOTEXT_TIMEOUT_S` are the pattern; a tool that can hang and has no cap
   hangs the whole build.
6. **Test it against a faked `subprocess.run`, asserting on the argv** —
   `tests/services/test_render_profile.py` is the shape, and it exists because the
   behaviour it protects is a flag, not an output. Behaviour only a real binary exhibits
   gets a skipping end-to-end test instead (`tests/test_htmlshot_browser.py`). Per
   `docs/testing.md` a new *capability* belongs in the conform exercise list, but a
   subprocess contract belongs in a unit test: a successful build never shows the argv.
