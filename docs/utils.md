# Utils — the shared primitives, and why none of them is a pf-core call

What lives in `src/deckwright/utils/`: colour maths, string measurement, the fraction
vocabulary, polygon geometry, the deck-name rules, the one wording for an unknown key,
the typed narrowing over pf-core's env resolver, and the python-pptx primitives every
component draws with. This doc covers what each module is for, the constraints that keep it callable
from every layer above it, and the pf-core check each one has already been through.

These are library internals with no project content in them. Nothing here reads a deck
spec, a theme or a `SlideCtx` — a helper that needs one of those belongs in the
subsystem that owns it. `utils/spans.py` is the near-exception, and the section on it
says exactly how far it goes.

Before adding anything here, check whether pf-core already has it — that is a rule
with teeth, and `bin/check-framework` is what enforces it.

---

## Table of Contents

- [The tier utils sits in](#the-tier-utils-sits-in)
- [`color.py` — the WCAG maths](#colorpy--the-wcag-maths)
- [`text.py` and `_metrics.py` — measuring a string](#textpy-and-_metricspy--measuring-a-string)
- [`spans.py` — names, never inches](#spanspy--names-never-inches)
- [`naming.py` — one answer per deck name](#namingpy--one-answer-per-deck-name)
- [`keys.py` — one wording for an unknown key](#keyspy--one-wording-for-an-unknown-key)
- [`env.py` — the resolver, narrowed to `str`](#envpy--the-resolver-narrowed-to-str)
- [`poly.py` — reserved-region geometry](#polypy--reserved-region-geometry)
- [`shapes.py` and `deck.py` — the python-pptx primitives](#shapespy-and-deckpy--the-python-pptx-primitives)
- [`xml.py` — parsing XML somebody else wrote](#xmlpy--parsing-xml-somebody-else-wrote)
- [`mce.py` — shapes inside `mc:AlternateContent`](#mcepy--shapes-inside-mcalternatecontent)
- [`a11y.py` — alternative text and the decorative flag](#a11ypy--alternative-text-and-the-decorative-flag)
- [`links.py` — `[words](address)` in copy](#linkspy--wordsaddress-in-copy)
- [What was checked against pf-core](#what-was-checked-against-pf-core)
- [Adding a helper here](#adding-a-helper-here)

## The tier utils sits in

`bin/check-layers` ranks `utils` at L2, beside `motion` and `services`. It may import
the standard library, python-pptx, and the L1 modules — `src/deckwright/errors.py`,
`config.py`, `paths.py`. It may not import `theme`, `spec`, `layouts`, `components`,
`charts`, `qa` or anything above them, and the refusal is exercised rather than assumed:
`tests/test_layer_gate.py` writes `import deckwright.components` into a copy of
`utils/deck.py` and asserts the gate exits 1 naming it.

That rank is the whole admission test. **A helper that needs the theme, the grid or a
slide context is not a util** — it is a method on the context or a function in the
subsystem holding that state. What survives the constraint is arithmetic and python-pptx
mechanics, which is exactly what is here.

Two consequences, both easy to break by habit:

- **No module here logs.** These are pure functions; they raise, and the caller with the
  context decides whether that is worth a log line.
- **No module here reads the environment or writes a file.** A tunable belongs in the
  subsystem that owns it; a helper that ever
  needs to write one calls `pf_core.utils.io.atomic_write_text` / `_json` / `_bytes`
  rather than reinventing the rename dance.

## `color.py` — the WCAG maths

`relative_luminance`, `contrast_ratio`, `required_ratio`, `delta_e` (CIE76 colour difference, which
`qa`'s `fill-ground` pairs with luminance so a saturated accent on a pale page is not called
invisible) and `normalize_hex`, plus the
`AA_NORMAL` / `AA_LARGE` / `LARGE_PT` constants. `theme/palette.py`, every component that
picks ink against a fill, `imagery/scrim.py`'s auto-opacity solve and `qa/geometry.py`'s
contrast check all decide against this one implementation, so a slide that passes at
build time and a `deckwright qa` finding cannot disagree about what 4.5:1 means.

The constants stay in code and out of both the theme and the environment. WCAG's
thresholds are the standard the QA check claims to implement, not an operational knob —
a deck that could lower `AA_NORMAL` in its theme would be reporting on a bar it moved
itself. `LARGE_PT` is 18.0 and WCAG's separate 14pt-bold allowance is deliberately not
honoured: components and QA both size bold text against the normal ratio.

`normalize_hex` raises `ThemeError` for anything that is not six hex digits. It takes no
`error:` parameter: every caller is holding a colour that came from a palette or a
template's colour scheme, so one class is right for all of them.

**Never assert a colour property using `contrast_ratio` to compute the expectation** —
`docs/testing.md` uses exactly that as its canonical circular test.
`tests/utils/test_color.py` pins the sRGB channel weights with literals (0.2126, 0.7152,
0.0722) for the same reason: a flat channel average also maps white to 1.0 and black to
0.0, so testing only the extremes cannot tell a correct implementation from a wrong one.

## `text.py` and `_metrics.py` — measuring a string

`text_em(text, face)` returns a width in ems; `wrapped_lines(text, width_in=, size_pt=,
face=)` returns how many lines it takes in a box. `LINE_HEIGHT` (1.2) is the line advance
those lines are multiplied by. Chrome band heights (`layouts/chrome.py`), card and table
geometry (`components/_tablegeom.py`, `components/card.py`), category-label room in
`charts/native.py` and QA's own geometry check all size off this pair, so a change here
moves the whole build at once.

`_metrics.py` holds per-character advance tables baked as literals from real font files:
`CALIBRI` (Carlito), `ARIAL` (LiberationSans), and `CEILING`, the per-character max
across Carlito, Liberation Sans, Verdana and DejaVu Sans. `_metrics_faces.py` holds the
brand families the bundled themes name (Poppins, Open Sans, Montserrat, Amatic, Sniglet,
Bebas Neue, Barlow Semi Condensed), each packed as one string of advances in `GLYPHS`
order so seven tables stay a few dozen lines; `CEILING` does not fold them in, so adding a
family never moves the estimate for a face that has none. **No font file ships and none is
read at runtime** — that is
the point of baking them. Each family table is itself a max over its Regular and Bold
cuts, so no caller passes a bold flag, and `table_for` routes a heavy or black cut to
`CEILING` rather than its family, those being wider than the Bold folded in.
`theme/load.py` warns `theme_face_unmeasured` when a theme's face has no table of its
own, and every fit refusal built on the estimate appends `estimate_caveat(face)` — the
fallback is loose, a wide display face can outrun it, and nothing downstream can see either.

Three traps for anyone editing this pair:

- **`measured()` compares tables by identity** (`table_for(face) is not CEILING`). Return
  a copy from `table_for` and it silently reports every face as measured. `table_for` is
  `lru_cache`d and returns the module-level dicts; keep it that way.
- **`_MARGIN` in `utils/text.py` errs long by design.** It covers what
  per-character summation cannot see — kerning, hinting, a renderer's own spacing.
  Lowering it is not tuning: a band sized one line short of its text draws straight
  through what sits below it, and neither QA's `bounds` check nor its `overflow` check
  can see a doubled-up chrome stack.
- **A lone word is measured without `_MARGIN`.** `overlong_word` refuses a build rather
  than sizing a box, and `wrapped_lines` breaks a word too long for its line where the
  real width does; an allowance in either refuses, or reserves a second line for, a word
  that fits its widest cut.
- **`advance_em` over-counts every character no table carries**, charging it the widest
  measured glyph of its class, so an accented run is never under-counted. CJK is the
  exception: `_cjk.py` charges every ideograph, kana, hangul syllable and fullwidth form
  `CJK_EM` (1.0), the em square those scripts are drawn on in every face.

**CJK lines break where the renderer breaks them.** `wrapped_lines` sends any text carrying
CJK to a simulator built on `_cjk.atoms`: each ideograph and kana is breakable, a Latin or
hangul word moves whole (Korean breaks at spaces), a closing bracket, full stop, comma,
small kana or `ー` joins the character before it, an opening bracket joins the character
after it, and a trailing `、。，．` hangs past a full line. The classes are W3C JLREQ's and
UAX #14's, pinned against LibreOffice renders in `tests/utils/test_cjk.py`, which also holds
`text_em` to never measure CJK narrower than any installed CJK font draws it. Latin-only
text never reaches the simulator.

`tests/utils/test_metrics.py` is both the gate and the generator. Run as a script
(`bin/py tests/utils/test_metrics.py`) it prints freshly measured dict literals
to paste in; run as a test it re-measures every baked value against the fonts it came
from, and separately holds `text_em` to never under-predict the real rendered width of
the heaviest cut of each routed family. Both halves skip when the measuring fonts are
absent, like the corpus.

The brand families are measured from Google Fonts' OFL files, which the repo does not carry.
Fetch each family's Regular and Bold cut (Sniglet's ExtraBold, Bebas Neue's single
Regular; Open Sans and Montserrat as their variable fonts, measured at the `Regular` and
`Bold` instances) and its `OFL.txt` from `github.com/google/fonts/tree/main/ofl/<family>`
into `~/.cache/deckwright/metric-fonts/<family>/`, under the file names
`_FACE_SOURCES` in the test module lists. Without them the brand-face gates skip.

`closest_match(name, options)` shares the module but nothing else: it is the "did you
mean…" behind spec validation errors, a thin wrapper over `difflib.get_close_matches`
with a fixed cutoff.

## `spans.py` — names, never inches

The named fractions a placement can use (`COL_SPANS`, `ROW_SPANS`), the `Share` record a
`split:` child carries, and the parsers `parse_span`, `parse_box` and `percent`.

It lives in utils because it has two readers on the same tier: `spec/_place.py` rejects
an unknown name while parsing, and `layouts/place.py` resolves a known one against the
theme's grid. Either home would make the other import sideways for two tables of eight
strings.

**It knows names, never inches.** `divides(name, divisor, key=)` and
`resolve(name, divisor, key=)` answer in indices against a divisor the caller supplies;
the grid, the canvas and the content band all stay in `layouts/place.py`. What those
indices then become is [`placement.md`](placement.md); what an author writes is
[`authoring.md`](authoring.md).

Two design points to preserve when adding a name or a parser:

- **The parsers take the caller's error class.** The same malformed `at:` is a
  `SpecError` from a slide and a `LayoutError` from a chrome field, and utils cannot know
  which — so it raises the class it is handed. Follow that whenever a helper's failure
  means different things to different callers.
- **`spans_for` raises on an unknown axis key** rather than defaulting to one of the two
  vocabularies. A `rows:` error offering the column names reads as though the author
  wrote nonsense, when the code picked the wrong table. It raises a bare `KeyError`, and
  that is deliberate: an axis key that is neither `cols` nor `rows` is a caller's
  mistake, not an author's, so it has no place in an error an author will read.

## `naming.py` — one answer per deck name

`slug_and_title(name)` returns a deck's directory name and its display title from
whichever of the two was typed; `deck_filename(title)` folds the separators a path would
read (`/`, `\`, `:`) out of a leaf filename; `NO_FOLD` is the PyYAML dump width that
keeps a long title on one line.

Like `spans.py` it is here for its two readers: `compile/scaffold.py` writes the spec for
a new deck and `spec/draft.py` writes one drafted from a `.pptx` deckwright did not build.
Both have to land on the same directory and the same `out:` path for the same name.

The slug keeps letters and digits only, so a name carrying a slash or a `..` cannot steer
a write out of the deck root. Case past a word's first letter survives, so `ML-pipeline`
titles as *ML Pipeline*. A name with nothing left after slugging raises `SpecError` unless
the caller passed a `fallback`.

## `keys.py` — one wording for an unknown key

`unknown_field(key, known, *, where=, lead=, label=, suggest=)` is the sentence every
"you named a key nobody declared" error ends in, and `prose_hint(key)` is the clause it
appends when the key holds a space. Spec parsing, placement, charts, the shape
components and the theme's chart block all raise through it, so `docs/errors.md` can
document one shape and an author sees the same wording from every layer.

Two behaviours to keep when touching it:

- **A key with a space in it is an unquoted comma.** Every declared field is snake_case,
  so a space means YAML split a flow mapping and truncated the value with it. The hint
  says to quote the value, and the "did you mean" suggestion is suppressed for that key:
  the nearest spelling of `items: one, two` is never the answer.
- **The caller owns the sentence around it.** Pass `where=` for a full message, or
  leave it off for a fragment the caller prefixes; `lead=` and `label=` are the only
  wording that differs between callers. Do not build a second unknown-key message by
  hand — the `errors.md` rows quote this one.

## `env.py` — the resolver, narrowed to `str`

`env_str(arg, env_var, *, default=)` is `pf_core.utils.env.resolve_str` with its return
narrowed from `str | None` to `str`. Every deckwright knob passes a real default, so the
None arm never happens; the wrapper says so once for the type checker instead of at each
call site. Use it for every `DECKWRIGHT_*` string knob — a binary path, a directory — and
keep the precedence it gives you: the caller's argument, then the variable, then the
default. Integer and boolean knobs call pf-core's `resolve_int` / `resolve_bool`
directly; those already return the narrow type.

This is the one module here whose whole body is a pf-core call, and it must never grow
into a resolver of its own. Two of pf-core's semantics ride through it unchanged: an
empty string is a value, not an absence — `DECKWRIGHT_CHROME=` is "configured to nothing",
and `services/htmlshot.py` strips and tests for exactly that — and only an unset
variable falls to the default.

## `poly.py` — reserved-region geometry

`point_in_poly`, `segments_cross`, `poly_hits_box` and `poly_x_span`, in whatever units
the caller passes. `Reserved` in `layouts/place.py` is the only consumer: it stores a
region as canvas fractions, scales the points to inches, and asks whether a placement's
rect touches the region and how far the region reaches into a horizontal band.

The polygon is the reason this module exists. A brand's reserved corner is usually a
triangular wedge, and a bounding box around it would forbid the usable space above the
diagonal. `poly_x_span` is what lets a placement bounded by `rows:` above the wedge keep
the full content width.

`poly_hits_box` tests vertex containment **both ways and then the edges**, because two
rectangles can cross in a `+` with no vertex of either inside the other. Deleting the
edge pass leaves a gap no build would notice: the failure is a placement quietly allowed
to sit across a logo.

## `shapes.py` and `deck.py` — the python-pptx primitives

`shapes.py` is the drawing floor every native component sits on: `solid`, `para`,
`textbox`, `rrect`, `rect`, `notes`, `bring_to_front`. Positions and sizes are inches,
colours are `RGBColor` — resolution from theme roles happens above, in the component.
`DEFAULT_FONT` is only the fallback for a caller that passes no font; components pass
`ctx.theme.face` or `ctx.theme.font_for(style)` on every call.

Three behaviours in here are not python-pptx defaults and are relied on everywhere:

- `solid()` clears the shadow (`shape.shadow.inherit = False`), which templates ship on
  by default for autoshapes.
- `para()` reuses the frame's first paragraph when `first=True` and that paragraph is
  still empty, so a text frame does not open with a blank line.
- `ALIGN` and `ANCHOR` are both the enum maps and the accepted vocabulary: `ALIGNS` and
  `ANCHORS` are what `spec/_place.py`, `components/_tablespec.py` and `layouts/chrome.py`
  validate against, so adding a key adds it to the wire format at the same instant.

`deck.py` holds the two presentation-level operations python-pptx does not expose.
`open_presentation(path, what=, error=)` exists because python-pptx surfaces a corrupt,
truncated or foreign package as any of `PackageNotFoundError`, `KeyError`, `ValueError`
or `XMLSyntaxError` — four classes sharing no base, which reach the CLI as a traceback
with no path in it. Every reader goes through it: `compile/build.py` and `theme/load.py`
for a template (default `ThemeError`), `qa/inspect.py` and `compile/readback.py` for a
built deck (`error=SpecError`, `what="deck"`). `delete_slide(prs, index)` drops the
slide's `sldIdLst` entry and releases its part relationship; `compile/build.py` calls it
newest-index-first to strip a template's own sample slides, because indices shift under
a forward loop.

Both modules carry deliberately broad `except Exception` clauses, each with a
`noqa: BLE001` and a stated reason — no shared base class, a shape with no adjustment
handle, a relationship already dropped. **Do not read those as licence to widen it.**
Swallowing an exception silently is still forbidden; these are three named
python-pptx surfaces, not a house style.

## `xml.py` — parsing XML somebody else wrote

```python
from deckwright.utils.xml import fromstring
root = fromstring(archive.read("ppt/slides/slide1.xml"))
```

One function, and every `lxml` parse in the package goes through it. `lxml`'s default
parser expands entities declared in an inline DTD; this one refuses them, refuses
network access, and refuses the huge-tree relaxation.

That matters because a `.pptx` is usually **not ours**: `conform`, `qa`, `inspect` and
`diff` all read a package the user was handed. With expansion on, a file that merely
*declares* deckwright's own sample marker as an entity is accepted as one of ours, and a
DTD a few lines long expands to whatever size it likes.

`tests/test_xml_safety.py` is the gate, and it has two halves: the behaviour, and a
sweep refusing any direct `etree.fromstring` elsewhere in `src/deckwright`. Reach for the
helper, not the library.

## `mce.py` — shapes inside `mc:AlternateContent`

```python
from deckwright.utils.mce import resolved_shapes
for shape in resolved_shapes(slide.shapes): ...
```

python-pptx's `slide.shapes` skips an `mc:AlternateContent`, which is how PowerPoint stores
an equation, a 3D model and other shapes from a newer namespace. `resolved_shapes` returns
the same proxies with each wrapper replaced by one branch: the `mc:Fallback`, or the first
`mc:Choice` when there is none. That is the branch ISO/IEC 29500-3 §7.5 gives a reader that
understands none of the extension namespaces, which deckwright is.

`qa/inspect.py` and `compile/readback.py` read through it, so `inspect` lists the shape and
`diff` stops reporting it `gone`. `spec/_tree.py` (`extract`) and `qa/package.py` do not:
extract names the wrapper in `dropped`, and the package check walks both branches.

## `a11y.py` — alternative text and the decorative flag

`describe(shape, alt=, decorative=)` writes a shape's `descr`, or Office's
`adec:decorative` extension inside `cNvPr`'s `a:extLst`. Without `alt` it **removes** any
existing `descr`, because python-pptx's `add_picture` writes the image's file name there.
`described(shape)` and `description(cNvPr)` read both back; the manifest and `extract` read
through the first, and `qa`'s `alt-text` check, which has no shape proxies, through the second.
`is_file_name(text)` is the one test for a description that is only a file name.

## `links.py` — `[words](address)` in copy

`spans(text)` splits a line into runs around its links, `plain(text)` is what the line shows,
and `addresses(text)` lists where it links. `text.py` and `versus`'s word floor measure
`plain`, so an address never widens a line, and `figure_text` stores `alt:` as `plain`.
`shapes.para()` writes one run per span, a link through `link_run`; `ManifestRecorder.record`
stores the words and the addresses; `spec/parse.py` refuses a bad address before anything is
drawn; and `spec/_tree.py` writes a hyperlinked run back as markup for `extract`.
`para(links=False)` and `record(literal=True)` keep markup as written, which is what `code`
asks for. `web_address_problem` is the one test of an address, shared by the spec check,
`para()` and `qa`'s `link` check.

## What was checked against pf-core

`bin/check-framework`'s own `EXEMPT` table records the deliberate non-adoptions
project-wide. These are the ones specific to this package, so the check does not have to
be redone from memory:

| Helper here | Nearest pf-core | Why it stays |
|---|---|---|
| `color.py` | nothing | pf-core carries no colour module; the maths is the WCAG spec, not a utility choice |
| `text_em`, `wrapped_lines`, `_metrics.py` | nothing | font advances are a PowerPoint-shaped problem the framework has no reason to know about |
| `poly.py` | nothing | four functions of plane geometry; a C-extension dependency would cost more than it saves |
| `shapes.py`, `deck.py` | nothing | pf-core knows nothing about OOXML or python-pptx |
| `xml.py` | `pf_core.parsers` | not a match: that is a stdlib `html.parser` walker rendering article HTML to plain text plus link records. pf-core does not depend on `lxml` at all, and has no XML tree parser to harden |
| `closest_match` | `pf_core.utils.similarity` | different question, and the numbers say so — below |
| `keys.py` | nothing | pf-core's `InvalidInputError` carries a message, not a vocabulary; the wording is deckwright's |
| `env.py` | `pf_core.utils.env.resolve_str` | it *is* the call, wrapped once to narrow the return type |

`pf_core.utils.similarity.is_near_duplicate` is the one that looks like a hit and is not.
It answers "are these two bodies of text near-duplicates" with a boolean, over character
4-shingles at a 0.75 Jaccard threshold. `closest_match` answers "which one of these
short identifiers did the author mean" and must rank a vocabulary and return `None` when
nothing is close enough. Shingling is the wrong instrument at that length: `titel` and
`title` share no 4-gram at all, so Jaccard scores them 0.0 and `is_near_duplicate` says
no, where `difflib.SequenceMatcher` scores 0.8 and the suggestion lands. `difflib` is
also standard library, not the third-party reach the framework-first rule is aimed at.

Nothing here hand-rolls what the framework does provide either: no `logging`, no
`os.environ`, no atomic-write dance, and no builtin `ValueError` or `RuntimeError` where
a `deckwright.errors` class belongs. `bin/check-framework` enforces all of that and names
the replacement in every failure.

## Adding a helper here

1. **Check pf-core first.** Start at `docs/pf-core/modules.md` (the symlink `bin/setup`
   creates); [`../CLAUDE.md`](../CLAUDE.md) states the rule. The gate refuses the common cases, but
   it only knows the rules someone wrote down — the index is the actual check.
2. **Check the tier.** If it needs the theme, the grid, a spec document or a slide
   context, it is not a util; put it in the subsystem that owns that state. L2 cannot
   import L3, and `bin/check-layers` runs in pre-commit and CI.
3. **Keep it pure.** Inputs and outputs, no logging, no environment reads, no file
   writes. Take units from the caller rather than assuming inches or fractions —
   `poly.py` is unit-agnostic for exactly this reason.
4. **Raise a `deckwright.errors` class.** Default it (as `deck.py` does with `ThemeError`)
   when one class is nearly always right; take it as an `error:` parameter (as
   `spans.py` does) when the same failure means different things to different callers.
5. **Test the thing a build cannot see.** A helper's arithmetic is usually exercised by
   the corpus already, and `docs/testing.md` says not to restate that. What needs a
   unit test is what a green build hides: every `raise`, every baked constant nothing
   downstream asserts on, and any measurement whose error direction matters — the wrap
   estimate has a floor test precisely because under-predicting is invisible until a
   render.
6. **Write it up here** and add the row to [`README.md`](README.md) if the module is new.
