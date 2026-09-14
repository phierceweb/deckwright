# Changelog

Notable changes to deckwright, newest first. The project is pre-1.0 — pin to a tagged
release; `main` is the development line.

## v0.4.0 — 2026-09-14

### Accessibility

- `image`, `icon`, `document` and `chart` take `alt:`, written as the shape's alternative
  text, and `decorative: true`, written as Office's decorative flag. Giving both is refused.
- A slide's background image or theme art, and a `card`'s picture icon beside its words,
  are marked decorative. `card` takes `alt:` and `decorative:` for its icon.
- Pictures no longer carry their file name as alternative text.
- `qa` reports `alt-text`: a picture or chart with neither alt text nor the decorative
  flag, or with only a file name. WARN.
- The manifest records `alt` and `decorative` per shape.
- `extract` writes each dropped figure's alt text into the draft as a comment.

### Links

- A slide takes `id:`, and a placement takes `goto:` naming a slide id or a relative jump
  (`first`, `previous`, `next`, `last`). Every shape the placement drew jumps when clicked.
  A goto naming no slide, its own slide, or sitting on a `reveals:` trigger is refused.
- `qa` reports `link`: a jump to a slide the show no longer contains, an unknown relative
  jump, or a web link that is not an `http`, `https` or `mailto` address.
- Copy takes `[words](address)` links to `http`, `https` or `mailto` addresses, in the
  line's own ink and underlined. `code` keeps markup as written; a chart refuses a link;
  `\[` escapes a bracket. `extract` writes linked runs back as markup.
- The manifest records `goto` and `links` per shape, and a linked line's text as its words.
- `relationship` no longer reports an empty `r:id`, which PowerPoint writes for click
  actions that relate to nothing.

### CJK

- Chinese, Japanese and Korean text is measured at one em per ideograph, kana, hangul
  syllable and fullwidth form, instead of the widest Latin glyph, and wraps where the
  renderer breaks it: between ideographs and kana, at spaces in Korean, with kinsoku
  (closing punctuation and small kana never start a line, opening brackets never end one)
  and a trailing full stop or comma hanging past a full line.
- Each run carrying CJK is written with its `lang` and the theme's face for its script. The
  theme takes those faces from `type.ea` (`ja`, `ko`, `zh-Hans`, `zh-Hant`), else from the
  template's `fontScheme` script entries.
- The deck and each slide take `lang:`. **Han-only text with no `lang:` is refused on a theme
  that sets Japanese and Chinese in different faces**, which most brand templates do.
- `qa`'s `font-substituted` reads the fonts the rendered PDF embeds (Poppler `pdffonts`),
  falling back to `fc-list`. A face installed but unreachable by LibreOffice is now reported.
- `qa` reports `cjk-unrendered`: a slide with CJK text whose render embeds no CJK font. ERROR.

### Reading decks

- `inspect` and `diff` read a shape stored inside `mc:AlternateContent` from its fallback.
  `inspect` listed nothing for one, and `diff` reported it `gone`.

## v0.3.0 — 2026-09-12

- Licensed **Apache-2.0**, replacing MIT, with a `NOTICE` file. The distribution's
  `license` metadata is `Apache-2.0`.
- `python-pptx` is pinned to `~=1.0.2`.

### Theme and conform

- `conform` derives `inverse` against the page a slide shows. A dark master gets a light
  `inverse` and its own `inverse-ink`; a light-page template derives as before.
  **Re-adopting a dark-page template changes its inverse surfaces.**
- Loading a theme whose `inverse` is within 3:1 of its `page` logs
  `theme_inverse_matches_page`. Re-adopting its template rebinds `inverse` and
  `inverse-ink`, bound or left at the default; `conform` without `--adopt` reports it.
- Re-adopting a theme keeps its comments and layout: only the lines whose values change
  are rewritten. A change a line edit cannot make, such as a flow-style `bind:`, rewrites
  the file and logs `theme_comments_dropped` when it had comments.
- `conform`'s report names the `page`, `ink` and `inverse` of the theme it wrote, each
  with its contrast, instead of the colour scheme's pair; an unbound one is marked
  `(default)`.
- A template outside the theme directory whose filename is already taken there is refused
  without printing an `mv` over it, by `conform --adopt` and by a `theme:` naming it.
- A template symlinked into the theme directory is adopted where the link is.

### Spec

- A number in a spec prints as it was written: `1.10` and `2.50` stay as typed in a table
  or a stat. What YAML 1.1 reads in another base — `007`, `0x1F`, `1:30` — loads as the
  text written, and an unquoted `crop: 16:9` is that aspect. A whole-number field such as
  a column index refuses one by name.

### Colour

- **Text a component sets on the slide is inked for what is painted under it**: prose, bullets,
  callouts, captions, `nav`, `fanout`, `diverge`, `code`, `grid` and a chart's labels, axis text
  and legend over a `panel` or a picture, and a table's body cells on an inverse band. The
  manifest records that ground, and a picture's scrim is part of it.
- A `bleed:` card, disc, callout dot, `versus` or `fanout` plate, `diverge` plate or bar, or
  `grid` bar is the ground for text laid over it, as a panel is. A disc covers its inscribed
  square.
- Text over a picture laid on top of a panel is inked for the picture.

### Type

- Width tables for Poppins, Open Sans, Montserrat, Amatic, Sniglet, Bebas Neue and Barlow
  Semi Condensed. **Decks in those faces lay out against their real widths**, so prose,
  cards, tables and titles take less room than the conservative estimate gave them.
- A fit refusal whose estimate ran on a face with no width table says so.
- **A `card` heading or body, a `stats` value or label, or a `flow` step holding a run wider
  than its frame is refused**, naming the run and the width it needs, measured without the
  sizing margin. A run ends at a space, after a hyphen or dash, and at each CJK character.
  A word that fits its line is no longer counted as two lines by the wrap estimate that
  sizes cards, flow steps, discs, chrome lines, prose, table rows, picture text and swatch
  captions, and that `qa`'s `text-fit` check measures against.

### Components

- `nav` with no `items:` takes the deck's `sections:`, and with no `active:` marks the
  slide's own `section:` when it is one of the items.
- `SlideCtx.text_ink` and `SlideCtx.accent_at` return an ink for a box and the ground painted
  under it, for components written outside the package; `ctx.painted` takes a `Disc` for a round
  fill.

### Motion

- **`animate: one_at_a_time` reveals a single-column `bullets` list one bullet per click**, as a
  PowerPoint build by paragraph in one text box. A list with several columns still reveals a
  column per click, and `together` is unchanged.
- Every component reports a motion role for each shape it reveals, so `motion.roles`
  binds how text, surfaces, lines, figures and charts enter; a chart's own build takes the
  `datum` entrance. **The lines in a `fanout` and between `flow` steps now wipe by default**,
  as `rule` and `connector` do; a vertical stroke wipes along its length.

### Charts

- Area, doughnut and bubble charts print their data labels.
- An area chart's first and last data labels are moved in off the plot edge, so they do not
  sit on the value axis.
- `xy-scatter-smooth` and `xy-scatter-smooth-no-markers` draw curves.
- A data label drawn on a series' fill (pie and doughnut wedges, area bands, stacked bars,
  `inside_end` bars) is inked for that fill, per wedge where wedges differ.
- A chart with one named series is not titled with that series' name.
- A chart's data labels, axis text and legend are recorded in the manifest with the ink and
  ground they are drawn on, so `qa`'s `contrast` and `min-font` checks cover them.
- **A bar or column chart's value axis starts at zero** when every value is zero or more.
  `y_min` still overrides it; line, area, radar, scatter and bubble keep automatic scaling.

### QA

- `qa` warns `fill-ground` when a shape filled to stand off its ground (an inverse or accent
  panel, card or disc, a plate, a bar, a dot) is separated from it by neither luminance nor
  colour.

### Errors

- **Slides whose chapters run out of the order `sections:` lists are refused**, naming both.
- A `theme:` naming a `.pptx`, at a path or by bare filename, is refused with the theme already
  adopted from it, or else the `conform --adopt` command that onboards it, paths quoted and the
  move into the theme directory included. A theme file that is not UTF-8 text is a
  `ThemeError`.
- Commands printed by `sample` and by `conform --adopt`'s refusal quote their paths.
- An exception from a component's own code keeps its traceback and ends with a line
  naming the slide and component. A component's `LayoutError` is unchanged.

## v0.2.0 — 2026-09-04

- **The project is `deckwright`.** The package, the `deckwright` command, the
  `DECKWRIGHT_*` variables and the `.deckwright-cache` directory follow the name. A
  `.env` carrying `PPTXKIT_*` needs its prefix changed; a `.pptxkit-cache` left behind
  can be deleted. Decks and manifests already built are unaffected — a `.pptx` never
  carried the package name.
- On pf-core 0.22.

### Extract

- `deckwright extract <deck>.pptx` drafts a `.deck.yaml` from a deck deckwright did not build.
  Kickers, titles, subtitles, body text, tables and speaker notes convert; every shape it
  cannot turn into words is named in a `# not converted:` comment on the slide it came
  from, repeats collapsed into `N × kind`. `--as md` writes a plain transcript instead,
  `--out` chooses where it lands, and `--theme` is loaded, so the draft's `rows:` spans
  that theme's grid and an unknown name fails before anything is written. `out:` defaults
  to `out/<slug>/<title> v1.pptx`, the same slug `deckwright new` uses.

- `extract` walks grouped shapes, reads chrome back out of the shape names `build`
  writes, so a deck deckwright built keeps its kicker, title and subtitle, and takes a
  slide's first block as its title when it is one line set larger than everything else
  on the slide. Shapes overlapping vertically are one row, read left to right. An element
  python-pptx cannot build — `p:contentPart`, `mc:AlternateContent` — is named by its
  tag.

- `extract` recovers a slide's `background:` when the colour painting the whole canvas is
  one the named theme declares. A colour it does not declare is written into the draft as
  a comment naming the hex.

- The bullet marker `build` writes is taken off again on the way in, so a deck survives
  any number of extract-and-rebuild round trips. The draft is not otherwise a fixed point
  — a columned list comes back as one placement per column — but its words are. A leading
  dot in a deck deckwright did not build is left as content.

- `build` refuses an `--out` (or an `out:`) that is the spec being compiled, or that names
  any `.yaml`/`.yml` path — a deck written over its spec leaves nothing to rebuild it from.
  Rebuilding over an existing `.pptx` is unchanged. The spec snapshot under `.build/` is
  now taken before the deck is written rather than after.

- `extract` refuses a destination that already holds a file, so the second run over a
  deck does not replace the draft you edited after the first; `--force` overwrites. That
  refusal and an `--as` that is neither `yaml` nor `md` are both raised before the deck
  is read.

- An extracted draft builds as written. A table placement gets the rows its own height
  will demand at build; every other placement gets a fixed two.
  A slide holding more than the grid can band runs its blocks together and columns a long
  list; whatever still does not fit is written in as comment lines.

### Motion

- `qa` reads a deck's timing: `beats` reports each animated slide's rhythm, `beat-size`
  warns when one beat of a staged build reveals more than `DECKWRIGHT_MAX_BEAT_SHAPES`
  (default 6), and `dead-trigger` reports an interactive reveal that cannot fire or that
  reveals what is already on screen. `animate: together`, a chart build and a `reveals:`
  trigger are exempt from `beat-size`: one click is what each of them declares.

- Every build writes `<deck>.beats.md` beside `<deck>.content.md` — the reveal order in
  words, click by click, each section headed by its slide's title.

- The manifest records the **clicks** an animation spends, which is not the number of
  beats its components grouped: `animate: together` and an `after_previous` chain spend
  one, a chart build spends one per part plus one for its axes, and an interactive
  `reveals:` spends none and names its trigger.

- A ring of `reveals:` is refused at build. Chains still build — click one to reveal the
  next is real staging.

### Charts

- A pie or doughnut carrying more than one series is refused by name. python-pptx
  keeps only the first, so the second reached a strict `zip` and came out as a bare
  traceback.

- A radar series carries no `c:smooth`. python-pptx writes one for every connected
  kind and `CT_RadarSer` has no such child, so the chart part did not validate.

- A chart's `labels:` names the series that print their data labels, so a flat reference
  series stops stamping the same number over every point.

- A chart's value axis takes the same number format its data labels do, so a line whose
  points read `11.2%` sits against a scale reading `0.0%`.

- Chart data labels keep their decimal places, read off the data — `11.2, 9.6, 5.1, 4.8`
  labels to one place, whole numbers to none. `decimals:` overrides it, `0` included, and
  the `*-stacked-100` kinds are no exception: their axis shows the computed share while
  each label prints its own series value.

- `qa` warns as `chart-datapoints` when a bar or column chart plots fewer than four
  values, quoting `choosing.md`'s rule. A warning, not a refusal.

- A chart legend goes under the plot on every kind but the bar family, which keeps the
  column it reserves beside its category labels. The bar family's legend gets a measured
  column out of the same budget as those labels, and the plot keeps at least 45% of the
  frame.

- A data label takes a position only where the chart group offers one: `inside_end` is
  written for the bar family and a pie, the line and scatter kinds sit above their point,
  and area, doughnut and radar are left without one. A theme naming a `label_position`
  does not get to write it into a group that has none.

- `versus` sizes each plate in proportion to its value, so a side 60% larger is 60%
  wider. Values with no number keep the even split, and so do two written in
  different units — `2 days` against `4 hours` reads 2 against 4 and would draw the
  longer span smaller. A magnitude suffix is part of the unit: `$1.2M` and `$480K` do
  not compare, and neither does a singular against its own plural: the unit is matched
  whole, because no string rule separates `hrs`/`hr` from `ms`/`m`. The smaller plate
  never drops below the width its longest word needs, so a lopsided pair widens rather
  than breaking type mid-word; a placement too narrow for both sides is refused.

- The chart block's `annotate:` key is gone; a deck still carrying one is refused by
  name. For a callout on one point, place a `callouts` or `prose` beside the chart.

### Type and colour

- A typo in a theme's `scale:`, `scale.margin:` or `type:` block is refused by name.
  Only the top level was checked, so a misspelled key was dropped and the built-in
  default stood — the theme read as though it had been honoured.

- The packaged `base` theme sets larger type. At its 7.5in reference height: body 14 →
  16pt, caption 12 → 14, subtitle 16 → 18, lead 18 → 20, head 19 → 22, stat 32 → 34.
  `kicker`, `title`, `display` and `hero` are unchanged. A deck on `theme: base` reflows
  on its next build: copy that only just fitted may overflow, and a placement whose
  contents no longer fit their band fails the build rather than shipping short.

- A theme with no `template:` sets colours: `bind:` accepts a literal `RRGGBB` for any
  role, so a palette is a theme of five lines. A slot name in such a theme is refused,
  naming the two ways out; `marks:` still needs a template.

- A `bind:` to a literal accent is kept even where it equals a colour Microsoft ships.
  The stock-accent guard applies to template slots only.

- A type-ramp rung reaches the theme's monospace face with `face: mono`, alongside
  `face: body` and `face: heading`. A `face:` matching an alias only in case is a literal
  typeface and warns.

- The `caption` rung takes a half step of the modular scale — 14.3pt at the default
  reference height, up from 12.8pt — so it no longer shares a step with the bold,
  capitalised `kicker`.

### Layout

- `swatches` reserves the depth its caption actually wraps to rather than a flat two
  label lines, so a placement that would have held it is no longer refused.

- A placement's `anchor:` applies to the shapes that placement drew and to nothing else,
  so editing one slide cannot move another.

- A mark's contrast plate stays inside the placement that asked for it.

- A chrome box may declare `h: auto` and take the depth its text wraps to.

- `prune` matches layouts by part name, so it cannot drop a layout a slide is still on.

- A `section:` that resumes after another chapter has begun is refused, naming both
  slides. A slide carrying no `section:` of its own does not break the run it falls in.

### QA and doctor

- `deckwright qa` adds `placeholder`: recorded text and speaker notes that read like copy
  nobody meant to ship — four phrases `deckwright new` seeds, plus `lorem`, `ipsum`, `TODO`,
  `FIXME`, `[insert` and a run of three or more `x` in either case. WARN.

- `deckwright qa` adds `font-substituted`: one finding per theme face the rendering machine
  cannot set. It runs only when `qa` renders, and is silent when fontconfig cannot be
  asked. WARN.

- A line the rendered page does not hold is asked for again inside the shape's own
  box before `overflow` reports it. pdftotext merges side-by-side placements row by
  row, so two `prose` in adjacent columns spliced each other's wrapped lines and the
  slide was reported twice over.

- `qa` falls back to the `theme` *name* a manifest records when the `theme_path` it
  records is not there, so a deck handed over on its own is checked against the
  packaged `base` rather than refused. A name resolves against the reader's own theme
  directory first, so `theme-substituted` reports a file that answered to the name but
  hashes differently from the one the deck was built against.

- `deckwright doctor` reports whether this machine has the faces the `base` theme sets type
  in; without fontconfig, or when `base` did not load, that row is a `SKIP`.

- `deckwright doctor` loads the `base` theme it resolved. One that resolves but will not
  parse is a `WARN` naming the file and the loader's message.

### Theme and conform

- `deckwright conform` resolves the `+mj-lt` and `+mn-lt` font references a template may
  carry against its own font scheme. `load_theme` warns when a theme on disk already
  holds one and names the template to re-adopt.

- Counts and margins in `scale:`, point sizes in `type:`, millisecond timings in
  `motion:`, and every block that must be a mapping are checked at load; a value that will
  not convert raises `ThemeError` naming the key and the value. `deckwright doctor` prints
  its full table even when a check raises.

### Rendering and the CLI

- `render` resolves the deck path as well as `--outdir`, so a relative input works from
  any directory, and a relative `--outdir` lands where the render created it. An input
  that is not there is reported as itself.

- A conversion that writes no PDF is reported instead of rasterising the previous run's,
  and the failure names the leftover process.

- `render` leaves no `render/share` directory behind: LibreOffice starts in the
  throwaway profile it already owns.

- `deckwright glyphs find <substring>` searches the 4,001 glyph names and the alias tables.
  Hyphens and underscores match either way; `--limit` caps the output and a capped run
  says how many it dropped.

- Build errors from inside a composite name the component the author wrote — a `flow`
  reported `component 'card'` — and the chrome-box error names its slide.

- fc-list (fontconfig) is a new optional external tool; the `doctor` fonts row and the
  `font-substituted` check are silent without it. `DECKWRIGHT_FC_LIST` and
  `DECKWRIGHT_FC_LIST_TIMEOUT_S` point at another binary and cap the call.

- Every external tool deckwright reads — pdftotext, fc-list, LibreOffice, pdftoppm — is
  decoded as UTF-8 rather than the platform locale, and the CLI's own output degrades
  instead of raising on a console that cannot encode a deck's em dashes.

### Documentation

- `treatments.md` says the claim should land a beat before the evidence, and applies the
  run test to `animate:`. `choosing.md` gives the recipe for staging a table's total row
  into its own beat.

- `motion.md` marks `motion.advance` as a theme key beside the slide-level `animate:` and
  `reveals:`; `placement.md` states that `anchor` moves what a placement drew inside its
  rect, with the measured positions; `components.md` gives the icon sizing arithmetic;
  `qa.md` says `#N` counts shapes as drawn, so a contrast plate takes `#1`.

## v0.1.0 — 2026-08-29

Initial public release.

- Python 3.12+, on pf-core 0.21.
- `deckwright build` compiles a declarative `.deck.yaml` against a theme into a branded
  `.pptx`, a build manifest, and a `.content.md` of the deck's words.
- Twenty-two slide components, 29 native chart kinds, imagery with fit/crop and scrim
  solving, HTML panels rendered through headless Chrome, and animation — builds,
  click-to-reveal and slide transitions.
- The built-in `base` theme ships inside the package, so `theme: base` resolves with no
  checkout. A file of the same name in `DECKWRIGHT_THEME_DIR` takes precedence.
- Default faces are Helvetica and Courier New, which resolve to metric clones in
  Keynote, PowerPoint and LibreOffice alike.
- `deckwright conform <template>.pptx --adopt <name>` derives a theme from a brand template
  and drives every capability through it.
- `deckwright sample` writes a small brand template to conform against, so the walkthrough
  needs no brand file. It lands in the theme directory, where `--adopt` can read it.
- `deckwright qa` checks geometry bounds, reserved regions, WCAG contrast, minimum font
  size and render-based overflow against a built deck's manifest.
- `render` and `qa` write into `render/<deck>/` beside the deck, so two decks in one
  directory never overwrite each other's slides.
- A built deck carries only the slide layouts it uses; `build --keep-layouts` retains
  the rest, and the media only they reach.
- Speaker notes declare their notes master on the presentation, which Keynote requires
  to open the file.
- `deckwright doctor` reports the version, the glyph bundle, theme resolution and the
  external tools, naming the install command for anything missing. `--version` prints
  it on its own.
- An absent external tool names the binary, the `DECKWRIGHT_*` variable that overrides it
  and the install command for the platform; `qa` also names `--no-render`, which runs
  every check that needs no tool.
- ~4,000 Material Symbols ship as one archive; `deckwright glyphs verify` checks it against
  its manifest and `deckwright glyphs sync` re-vendors it from upstream — the one command
  that uses the network.
- Supporting commands: `render`, `shot`, `inspect`, `diff`, `new`, `demo`.
- One directory for a brand: `templates/` holds the `.pptx` and the theme derived
  from it, side by side. `theme: <name>` resolves `<name>.theme.yaml` there, and a
  theme names its template by bare filename — nothing is ever copied. A template is
  adopted where it lives; adopting one from elsewhere is refused.
- Re-running `conform --adopt` on the same template is a refresh that keeps hand
  edits; `--force` re-derives and discards them.
- The suite's primary guard drives every template in that directory
  (`tests/test_templates.py`, `DECKWRIGHT_TEMPLATES_MIN` to require a minimum).
- Headless Chrome runs sandboxed. `DECKWRIGHT_CHROME_NO_SANDBOX=1` passes
  `--no-sandbox`, which is implied when running as root.
- Every rendered card carries a content policy: no frames, objects or embeds, no
  script but deckwright's own height probe, and images and fonts from `data:`/`http(s):`
  only. A `file://` URL in card markdown no longer renders a local file into the deck.
- Importing `deckwright` no longer touches the root logger; handlers land on the
  `deckwright` logger, and an application that configured logging first keeps its own.
- All text is read and written as UTF-8 regardless of the platform locale.
- Every XML part of a `.pptx` is parsed with entity expansion and network access
  refused, so a package from someone else cannot amplify or forge through a DTD.
- The sdist ships a runnable suite: `tests/`, `docs/` and `examples/` travel with
  it, and brand templates and derived brand themes are excluded from both dists.
