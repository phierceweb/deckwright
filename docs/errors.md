# Errors — every build message, beside its fix

A lookup doc. Arrive with the message in hand and search this page for the words in it.
Every message below is the real output of `bin/run build` on a real broken spec: the
compiler prints one line and exits `1`. (Long messages wrap in a terminal; they are
single lines.) The last three sections carry the refusals the other commands make before
they write anything; a tool or runtime failure from `render` and `qa` is
[`docs/services.md`](services.md).

Nothing here explains the format — that is [`docs/authoring.md`](authoring.md), and the
per-component field tables are [`docs/components.md`](components.md). A finding on a deck
that *did* build comes from `deckwright qa` instead: [`docs/qa.md`](qa.md).

---

## Table of Contents

- [Old-format constructs](#old-format-constructs)
- [The deck document](#the-deck-document)
- [The slide](#the-slide)
- [A placement](#a-placement)
- [The chrome block](#the-chrome-block)
- [Placement geometry](#placement-geometry)
- [The chart block](#the-chart-block)
- [Components](#components)
- [Images, themes and templates](#images-themes-and-templates)
- [Too much content](#too-much-content)
- [External tools](#external-tools)
- [The command line](#the-command-line)
- [The glyph bundle](#the-glyph-bundle)

---

## Old-format constructs

Every deleted construct fails with a message naming its replacement.

| Message | Fix |
|---|---|
| `bad.deck.yaml: slide 1: 'layout' is gone — a slide has no layout; put components under 'place:' and pick a backdrop with 'background:'` | Delete `layout:`. Add `background: inverse` if the slide was a `title`, `divider` or `close`; put its component in a `place:` entry. |
| `bad.deck.yaml: slide 1: 'body' is gone — a component's name is its own key inside a 'place:' entry, e.g. place: [{at: {cols: [0, 12]}, bullets: {items: [...]}}]` | Delete the `body:` wrapper and put the component in a placement, keyed by its own name. |
| `slide 1 (component 'chart'): chart kind 'pie' takes one series, got 2 ('Ours', 'Theirs') — a pie is one whole cut into named parts, so a second series has nowhere to go. Chart the one that matters, or use 'column-stacked-100' to compare both` | A pie or doughnut colours one series per point; a second has nowhere to go, and python-pptx keeps only the first. |
| `slide 1 (component 'chart'): 'type' is gone — a chart's type is now 'kind', e.g. kind: column-stacked` | Rename `type:` to `kind:`. |
| `slide 1 (component 'chart'): 'categories' is gone — each category is a row in 'data', e.g. data: [{category: Q1, values: {Ads: 20, Organic: 15}}, ...]` | Replace the `categories` list with one `data:` row per category. |
| `slide 1 (component 'chart'): 'series' is gone — series names are the keys of each row's 'values' mapping in 'data', e.g. data: [{category: Q1, values: {Ads: 20, Organic: 15}}, ...]` | Move each series' numbers into the `values:` mapping on the row they belong to. |
| `slide 1 (component 'chart'): 'highlight' is gone as a top-level index — it's now per-row: set 'highlight: true' on the row you want highlighted` | Delete the index and put `highlight: true` on the row itself. |
| `bad.deck.yaml: slide 1: 'reveal' is gone — use 'animate', e.g. animate: one_at_a_time instead of reveal: per-item` | Rename to `animate:` and use the new vocabulary. |

The old component names are gone too: `bullet-column` is `bullets`, `callout-list` is `callouts`, `stat-tiles` is `stats`, `doc-card` is `document`. So are the four layouts and every field only they read — `name:`, `tagline:`, `heading:`, `date:`, `part:`. A divider is now `background: inverse` with a `kicker:` and a `title:`.

## The deck document

| Message | Fix |
|---|---|
| `bad.deck.yaml: deck config: missing required field 'theme'` | Add `theme: base` to the first document. |
| `bad.deck.yaml: no slides — a deck needs at least one slide document` | Add a `---` and a slide document after the deck document. |
| `bad.deck.yaml: no output path — set 'out:' in the deck config or pass --out` | Add `out: ../out/name/Name v1.pptx` — its own directory, because `render` and `qa` both write beside the deck and two decks sharing a directory overwrite each other's slides. |
| `bad.deck.yaml: deck config: 'sections' must be a list, got str` | Use YAML list syntax: `sections: [One, Two]`, not `sections: One, Two`. |
| `bad.deck.yaml: deck config: unknown field 'section'; did you mean 'sections'?` | The deck document's chapter list is plural. `section:` is a *slide* field. |
| `bad.deck.yaml: deck config: unknown field 'author'; known fields: theme, title, sections, extends, out` | The deck document takes exactly those five. |
| `bad.deck.yaml: invalid YAML — while scanning a quoted scalar …` | A quoting or indentation mistake. The message names the line and column. |
| `extension module not found: /path/to/my_components.py` | `extends:` is resolved beside the deck spec, and the message names the full path it tried. |
| `failed to import extension module my_components.py: body component 'card' is already registered` | The custom component's `@component("…")` name collides with one that ships. Rename yours. |

## The slide

| Message | Fix |
|---|---|
| `bad.deck.yaml: slide 1: unknown field 'subtile'; did you mean 'subtitle'?` | A typo. Take the suggestion. |
| `bad.deck.yaml: slide 1: unknown field 'footer'; known fields: title, kicker, subtitle, notes, section, animate, transition, background, place, chrome` | A slide takes exactly those ten. Content goes in a placement. |
| `bad.deck.yaml: slide 1: 'background' must name a colour pair ('page', 'inverse', 'accent-1', …) or be a mapping with 'image:', got ['dark']` | A background is one pair name or an image mapping, never a list. |
| `no colour pair 'dark'; declared pairs: accent-1, accent-2, accent-3, accent-4, inverse, page, page-muted, surface` | The name is not a pair this theme declares. The message lists the ones that are, which depends on how many accents the theme binds. |
| `bad.deck.yaml: slide 1 (component 'bullets'): item 2 is a dict, not a line of text — a bullet holding a comma or a colon needs quoting, or YAML reads it as a mapping` | `- One thing, then another` is a YAML *mapping*, not a string. Quote it: `- "One thing, then another"`. |
| `bad.deck.yaml: slide 1 placement 2 (card): [11.20, 3.00, 3.00, 1.00]in falls outside the canvas [0.00, 0.00, 13.33, 7.50]in` | A `box:` may leave the content band but not the slide. To run off an edge deliberately, add `bleed: true`. |
| `bad.deck.yaml: slide 1: section 'Three' is not in the deck's sections (One, Two)` | Use a name from the deck's `sections:` list, or add it to that list. |
| `bad.deck.yaml: slide 3 resumes section 'Alpha', which ended at slide 1 when 'Beta' began — a chapter runs once, so 'sections:' cannot describe this order` | A reorder left one chapter's slides scattered. Move the slide back into its run, or give it the section it now sits in. A slide with no `section:` does not break a run. |
| `bad.deck.yaml: slide 1: expected a mapping, got list` | A slide document must be a mapping. You probably left a `-` at the start of a line. |
| `slide 1: unknown animate 'per-item'; expected one of none, together, one_at_a_time, by_category, by_series` | Use one of the five listed values. |
| `slide 1: animate 'by_category' only applies to a native chart` | `by_category`/`by_series` need a `chart:`. Use `one_at_a_time` or `together` otherwise. |
| `slide 1 (component 'chart'): a 'radar-filled' chart cannot build by category — its categories are vertices of one outline, not separate marks…` | A radar, scatter or bubble has no per-category mark to reveal. Use `animate: together`, or one of the kinds the message lists. |
| `this slide already carries an animation timeline, and a slide can hold only one…` | Two charts on one slide both asked to build. PowerPoint allows one timeline per slide; a second is an invalid file that LibreOffice converts without complaint. Give one chart a slide of its own, or drop the slide to `animate: together`. |
| `theme t.yaml: unknown motion key 'staggerms'; known keys: stagger_ms, advance, beat_ms, roles, transition` | A typo in the theme's `motion:` block. |
| `theme t.yaml 'scale': unknown key 'gutterr'; known keys: body_top, columns, gutter, margin, rows` | A typo in `scale:`. The value was previously dropped and the default stood, so the theme read as if it had been honoured. |
| `theme t.yaml 'scale.margin': unknown key 'topp'; known keys: bottom, left, right, top` | A typo in the `margin:` sub-block. The four sides are the whole vocabulary. |
| `theme t.yaml 'type': unknown key 'wibble'; known keys: face, heading_face, line_weight_pt, min_pt, mono, ramp, reference_height` | A typo in `type:`. A rung goes inside `ramp:`, not beside it. |
| `theme t.yaml: motion advance must be one of on_click, after_previous, got 'whenever'` | `advance:` takes those two. `after_previous` chains a build onto one click. |
| `theme t.yaml: motion beat_ms is -50; a pause between groups cannot be negative` | `beat_ms` is the gap between auto-advanced groups. |
| `theme t.yaml: unknown motion role 'squiggle'; known roles: datum, figure, line, surface, text` | Those five are the whole vocabulary. A component reports one; the theme binds it. |
| `theme t.yaml: motion role 'line' names unknown entrance 'explode'; known entrances: fade, wiperight, wipeup` | Three entrance kinds exist. Adding a fourth means adding a verified preset to the motion code, not to the theme. |
| `theme t.yaml: motion roles must be a mapping of role to kind, got ['line']` | `roles:` is a mapping — `roles: {line: {kind: wiperight}}`. |
| `theme t.yaml: motion transition must be a mapping with 'kind:', got 'fade'` | Write `transition: {kind: fade}`, not `transition: fade`. |
| `theme t.yaml: unknown transition key 'sped'; known keys: kind, dir, speed` | A typo inside `motion.transition`. |
| `theme t.yaml: transition speed must be one of slow, med, fast, got 'quick'` | The base schema has three speeds and no duration attribute. |
| `slide 1: component 'rule' reports motion role 'squiggle', which the theme does not bind; known roles: …` | A custom component returned a role outside the five. Return one of them, or a bare shape id. |
| `slide 1 (card): 'reveals: answer' names itself` | A placement cannot be its own trigger. |
| `slide 1: left waits on right waits on left — every placement in that ring is hidden until one of the others is clicked` | The `reveals:` graph closes on itself, so nothing on the slide can ever be shown. Give one placement in the ring no `reveals:` — that is the one the room clicks first. |
| `slide 1 (card): 'reveals:' needs both placements to draw something that can be revealed, and one of them reported no shapes` | One end is a component that returns no reveal groups, so there is nothing to hide or to click. |
| `this slide already carries a transition` | Internal: two `add_transition` calls on one slide. A spec cannot cause this — a slide takes the theme's transition once. |
| `slide 1 (card): 'reveals: answer' names no placement on this slide; ids here: question` | `reveals:` names another placement's `id:` on the same slide. Give the trigger an `id:`. |
| `slide 1: 'reveals:' and 'animate: one_at_a_time' cannot share a slide…` | A slide carries one animation timeline. Interactive reveals and a click build are different kinds — drop one. |
| `slide 1: transition 'push' — a slide may only say 'none', for a deliberate hard cut…` | Which transition a deck uses is the theme's `motion.transition`. A slide may only refuse it. |
| `theme t.yaml: transition 'strips' has no direction 'l'; it accepts: lu, ru, ld, rd` | Each effect has its own direction vocabulary. `strips` takes corners only. |
| `theme t.yaml: transition 'fade' takes no direction, got 'l'` | Ten of the twenty-one effects take no `dir:` at all. |
| `theme t.yaml: unknown transition 'ripple'; known transitions: blinds, checker, …` | Only the 21 base-schema effects. The 2010-era extension set (ripple, glitter, morph…) is not written. |
| `theme t.yaml: motion stagger_ms is -40, which would schedule an item before the click that reveals it; use 0 or more` | A stagger is an offset after the click, so it cannot be negative. |

## A placement

| Message | Fix |
|---|---|
| `bad.deck.yaml: slide 1: 'place' must be a list, got dict` | `place:` is a list of placements — each entry starts with `- at:`. |
| `bad.deck.yaml: slide 1: placement 1: missing required field 'at'` | Every placement says where it goes. `at: {cols: [0, 12]}` is the full width. |
| `bad.deck.yaml: slide 1: placement 1: no component — a placement needs exactly one component key; known components: bullets, callouts, card, chart, code, connector, diverge, document, ellipse, fanout, flow, grid, icon, image, nav, panel, prose, rule, stats, swatches, table, versus` | Add one of those keys beside the `at:`. |
| `bad.deck.yaml: slide 1: placement 1: more than one component — found 'bullets' and 'stats'; give each its own placement` | Split them into two entries under `place:`. |
| `bad.deck.yaml: slide 1: placement 1: unknown field 'bulets'; did you mean 'bullets'?` | A typo. Take the suggestion. |
| `bad.deck.yaml: slide 1: placement 1: unknown field 'footer'; known fields: at, id, bleed, align, anchor, reveals, bullets, callouts, card, chart, code, connector, diverge, document, ellipse, fanout, flow, grid, icon, image, nav, panel, prose, rule, stats, swatches, table, versus` | A placement takes `at`, `id`, `bleed`, `align`, `anchor`, `reveals`, and one component key. |
| `bad.deck.yaml: slide 1: placement 1: 'align' must be one of left, center, right, got 'justify'` | Those are the three. `justify` is not offered. |
| `bad.deck.yaml: slide 1: placement 1: 'anchor' must be one of top, middle, bottom, got 'baseline'` | Those are the three. |
| `bad.deck.yaml: slide 1: placement 1: component 'bullets' must be a mapping, got str` | Components take a block. `bullets:` then `items:`, not `bullets: a`. |
| `bad.deck.yaml: slide 1: placement 1: 'at' needs 'cols' or 'box'` | `rows:` bounds a column span; it cannot stand alone. |
| `bad.deck.yaml: slide 1: placement 1: 'at.box' cannot be combined with 'cols' or 'rows'` | A `box:` is the escape hatch from the grid. Pick one or the other. |
| `bad.deck.yaml: slide 1: placement 1: 'at': cols is a name or a mapping, not a list — write {from: 6, to: 12}, or one of: full, left-half, …` | A span is a named fraction or `{from:, to:}`. A positional list is the form this replaced. |
| `bad.deck.yaml: slide 1: placement 1: 'at': cols 'left-quarter' names no fraction; one of: full, left-half, right-half, left-third, mid-third, right-third, left-two-thirds, right-two-thirds` | Quarters have no name — say `{from:, to:}`, or use the thirds and halves that do. |
| `bad.deck.yaml: slide 1: placement 1: 'at': cols from 6 must be less than to 6` | An empty span. |
| `bad.deck.yaml: slide 1: placement 1: split 1: a split child has no 'at' — the band gives it its rectangle` | Drop the child's `at:`; `split:` is what places it. |
| `bad.deck.yaml: slide 1: placement 1: a placement with 'split' takes only 'at' and 'split'` | A `split:` has no component of its own — its children carry them. |
| `bad.deck.yaml: slide 1: placement 1: 'split' divides a column band, so its 'at' takes 'cols' and 'rows', not 'box'` | Narrow the band with `cols:`, or place a `box:` on its own. |
| `bad.deck.yaml: slide 1: placement 1: 'at.cols' start 6 must be less than end 6` | The span is half-open, so the end is one past the last column. |
| `bad.deck.yaml: slide 1: placement 1: 'at': box is keyed, not a list — write {x: 0%, y: 0%, w: 100%, h: 100%}, in percents of the canvas` | A box names its four sides and states them in percents. |
| `bad.deck.yaml: slide 1: placement 1: 'at': box.x is a percent of the canvas, got 0.5 — write '50%' for half of it` | A bare number is refused rather than guessed at: `0.5` and `0.5in` look alike and only one is meant. |
| `bad.deck.yaml: slide 1: placement 2: duplicate id 'x'` | An `id:` names one rectangle on the slide. Rename one of them. |
| `bad.deck.yaml: slide 1: placement 1: 'bleed' must be true or false, got 'yes'` | Unquoted `true`/`false`. YAML reads `'yes'` as a string. |

## The chrome block

| Message | Fix |
|---|---|
| `bad.deck.yaml: slide 1: unknown chrome field 'eyebrow'; known fields: kicker, title, subtitle` | Those are the three chrome fields. A fourth line is a placement, not chrome. |
| `bad.deck.yaml: slide 1: 'chrome' sets 'subtitle' but the slide has no 'subtitle' text, so there is no line to place` | Give the slide the text, or drop the override. |
| `bad.deck.yaml: slide 1: chrome field 'title': box {…} leaves the canvas — a chrome box is percents of the canvas, never inches` | Divide the inches by the canvas size and write a percent. `11.3in` of `13.333in` is `84.7%`. |
| `slide 1: chrome field 'title' wraps to 1.12in but its box is only 0.60in tall — it would be drawn through the line below; deepen the box, shorten the text, or drop to a smaller rung` | Deepen the box, shorten the text, or drop to a smaller rung; the estimate is the same wrap measure the stacked chrome uses. Better, write `h: auto` in that box and the depth follows the text — a title that changes between builds then cannot leave a hand-measured height behind. |
| `bad.deck.yaml: slide 1: chrome field 'title': align must be one of left, center, right, got 'justify'` | Those are the three. |
| `chrome field 'title' sets anchor 'bottom' but no 'at:' — a stacked line shares the stack's frame, so it has no frame of its own to anchor in; give it an 'at:'` | Add an `at:` to the same field. |
| `theme 'base' has no type role 'headline'; known roles: body, caption, display, head, hero, kicker, lead, stat, subtitle, title` | A chrome `rung:` names a rung of the theme's ramp. |
| `no colour pair 'accent-9'; declared pairs: accent-1, accent-2, …` | A chrome `pair:` names a declared palette pair. |

## Placement geometry

Shape errors above come from the parser, before any inch exists. These come from the placement engine, once `at:` has been resolved against the theme's grid.

| Message | Fix |
|---|---|
| `slide 1 placement 1 (bullets) overlaps slide 1 placement 2 (stats)` | Two placements claim the same space. Make the spans disjoint — `cols: [0, 6]` and `cols: [6, 12]`, not `[0, 7]` and `[6, 12]`. |
| `slide 1 (component 'panel'): align 'center' has nothing to act on — 'panel' sets no text of its own; drop the align` | `align`/`anchor` set type. `panel`, `chart`, `connector` and `document` draw no type of their own. |
| `slide 1 (component 'callouts'): align 'center' would pull each row's text away from its dot; 'callouts' sets text flush to the dot rail` | Drop the `align`. `anchor` still works. |
| `slide 1 placement 1 (bullets): [0.00, 0.00, 6.67, 3.75]in falls outside the content area [0.73, 1.65, 11.87, 5.40]in` | A `box:` that leaves the content band. Move it inside, or add `bleed: true` if running off the edge is the point. |
| `slide 1 placement 1 (bullets): overlaps the reserved region 'logo-wedge'` | A `box:` landing on a region the theme keeps for the brand. Move it, or switch to `cols:`/`rows:`, which the compiler narrows for you. |
| `slide 1 placement 1 (bullets): cols [0, 13] out of range — a span runs 0..12 with start < end` | The end is one past the last column, so 12 is the maximum. |
| `slide 1 placement 1 (bullets): rows [6, 13] out of range — the content band has 12 rows and a span runs 0..12 with start < end` | Rows are 12 divisions of the content band, indexed the same half-open way. |

## The chart block

| Message | Fix |
|---|---|
| `slide 1 (component 'chart'): unknown field 'legend'; known fields: kind, data, unit, decimals, labels, y_min, y_max` | Delete it. The chart block takes exactly those seven. |
| `slide 1 (component 'chart'): 'kind' must be one of bar, column, column-stacked, … got 'donut'` | Use a name from [the 29](authoring.md#all-29-chart-kinds). It is `doughnut`, not `donut`. |
| `slide 1 (component 'chart'): 'data' must be a non-empty list of rows` | Add `data:` with at least one row. |
| `slide 1 (component 'chart'): row 1 needs a 'category'` | Every category row needs its own label. |
| `slide 1 (component 'chart'): row 2 (category 'Q2') needs a 'value' or 'values'` | Give the row a number. |
| `slide 1 (component 'chart'): row 1 (category 'Q1') carries both 'value' and 'values' — use one` | Pick one. |
| `slide 1 (component 'chart'): row 2 (category 'Q2') uses 'values' but row 1 (category 'Q1') uses 'value' — use one or the other for the whole chart` | Convert every row to the same form. |
| `slide 1 (component 'chart'): row 2 (category 'Q2') is missing series 'Organic' (present in row 1 (category 'Q1'))` | Every row must carry every series. Add it, with `0` if that is the truth. |
| `slide 1 (component 'chart'): row 2 (category 'Q2') has series 'Referral', which no other row defines; known series: Ads` | Either a typo, or a series the first row is missing. The first row defines the set. |
| `slide 1 (component 'chart'): row 1 has unknown field 'color'; known fields: category, values, value, highlight` | Colour is the theme's business. Delete it. |
| `slide 1 (component 'chart'): row 1 (category 'Q1') has a non-numeric 'value': 'twelve'` | Use a number, unquoted. |
| `slide 1 (component 'chart'): row 1 (category 'Q1') series 'Ads' has a non-numeric value: 'high'` | Same, inside a `values:` mapping. |
| `slide 1 (component 'chart'): row 1 (category 'Q1') 'values' must be a non-empty mapping of series name to number, got {}` | Fill in the mapping, or use `value:` for a single series. |
| `slide 1 (component 'chart'): row 1 (category 'Q1') 'highlight' must be true or false, got 3` | `highlight` is a flag on the row, not an index. |
| `slide 1 (component 'chart'): only one row may set 'highlight: true' — row 1 (category 'Q1') and row 2 (category 'Q2') both do` | Highlight one datapoint. |
| `slide 1 (component 'chart'): row 1 carries 'x'/'y' but chart kind 'column' is category-shaped; use 'category' and 'values'` | Either switch the rows to `category`, or switch the kind to an `xy-scatter*` one. |
| `slide 1 (component 'chart'): row 1 carries 'category' but chart kind 'xy-scatter' takes 'x'/'y', not 'category'` | The mirror image of the above. |
| `slide 1 (component 'chart'): row 1 needs a 'y'` | Both `x` and `y` are required on every xy and bubble row. |
| `slide 1 (component 'chart'): row 1 needs 'size' for chart kind 'bubble'` | Bubble rows need a third number. |
| `slide 1 (component 'chart'): row 1 has a non-positive bubble size: 0.0` | A bubble of zero area cannot be drawn. |
| `slide 1 (component 'chart'): 'annotate' is gone — it was validated but no renderer ever drew it` | Delete it. For a callout on one point, place a `callouts` or `prose` beside the chart. |
| `slide 1 (component 'chart'): 'decimals' is 99; it must be between 0 and 6` | Data labels print at most six places. Omit the key and the places are read off the data. |
| `slide 1 (component 'chart'): 'decimals' is how many decimal places the data labels print, so it must be a whole number, got 1.5` | It counts places, so `2` — not `0.01`, not `'two'`. |
| `slide 1 (component 'chart'): 'labels' is a mapping of series name to true or false, e.g. labels: {Platform average: false}; got False` | It names series, so it takes a mapping — not a bare flag. To print no labels anywhere, set the theme's `label_position` to `none`. |
| `slide 1 (component 'chart'): 'labels' names the series whose data labels are turned off, so the chart's series need names. The 'value' shorthand and the xy/bubble kinds have one unnamed series; name them with a 'values' mapping on each row` | Convert the rows to `values: {Name: n}`. With one unnamed series there is nothing to single out. |
| `slide 1 (component 'chart'): 'labels' names series 'Platfrom average', which no data row defines; known series: Ours, Platform average` | A typo, or a name that differs from the one in the first row's `values:`. The rows define the set. |
| `slide 1 (component 'chart'): 'labels' entry 'Ours' must be true or false, got 3` | It is a flag, not a count. Write `false` unquoted. |
| `slide 1 (component 'chart'): 'y_min' must be a number, got 'zero'` | Use a number. |
| `slide 1 (component 'chart'): must be a mapping, got str` | `chart:` takes a block, not a bare value. You wrote `chart: column` instead of `chart:` then `kind: column`. |
| `slide 1 (component 'chart'): chart kind 'line' cannot show 'highlight' — its data points have no fill of their own. Kinds that can: …` | The only `highlight` error whose fix is the *kind*, not the row. Switch to a bar/column, pie/doughnut or bubble kind, or drop `highlight:` and make the point with the title or `animate:`. The kinds that take one are listed under [the chart block](authoring.md#the-chart-block). |
| `theme 'brand' declares 1 accent role(s); 'highlight' marks a point with the second accent, so a palette with fewer cannot show one` | Internal: a `bind:` layers over the built-in roles, which always carry four accents, so no theme file can reach this. It guards a palette assembled in code. |

## Components

| Message | Fix |
|---|---|
| `slide 1 (component 'bullets'): unknown field 'colums'; known fields: items, columns, heading` | Every component refuses a key it does not read, naming the ones it does. A misspelled field is never accepted in silence. |
| `slide 1 (component 'bullets'): 'items' must be a non-empty list` | Add `items:` with at least one entry. Also what you get for a misspelled `items`. |
| `slide 1 (component 'bullets'): must be a mapping, got list` | Components take a block. `bullets:` then `items:`, not `bullets: [a, b]`. |
| `slide 1 (component 'callouts'): item 1 needs a 'head'` | Every callout item needs `head:`. |
| `slide 1 (component 'flow'): step 2 needs a 'head'` | Every flow step needs `head:`. |
| `slide 1 (component 'flow'): step 1 has the unknown field 'title'; a step reads: body, head, icon` | A step carries those three keys and nothing else. |
| `slide 1 (component 'flow'): a flow needs at least 2 steps to be a sequence — a single step is the 'card' component` | Add a step, or use `card`. |
| `slide 1 (component 'flow'): 'current' is the 1-based step to highlight, so it runs 1 to 4 for these items; got 5` | Count from 1, not 0. |
| `slide 1 (component 'stats'): item 1 needs a 'value'` | Every stat tile needs `value:`. |
| `slide 1 (component 'stats'): item 1 has the unknown field 'and the critical path'; an item reads: icon, label, value — a key that reads like prose is an unquoted comma; quote the value` | YAML read `label: of a run, and the critical path` as *two* keys, so the label is truncated as well. Quote it. Every unknown-field message says this when the key holds a space, which is the only way one can. |
| `slide 1 (component 'callouts'): item 1 has the unknown field 'note'; an item reads: body, head, icon` | A callout row carries those three. Same unquoted-comma trap as above. |
| `slide 1 (component 'card'): a card needs a 'heading', a 'body' or an 'icon' — an empty plate is the 'panel' component` | Give it one of the three, or use `panel`. |
| `slide 1 (component 'card'): 'radius' is a fraction of the plate's short side, 0..0.5 (0.5 is a stadium); got 0.75` | Radius is a fraction, not inches. |
| `slide 1 (component 'table'): row 2 cell 1 has no key 'bold'; a cell reads: text, across, down, align, valign, emphasis, pair` | Bold is `emphasis: true`. The cell-key table in [`components.md`](components.md) says what each of the seven does. |
| `slide 1 (component 'table'): row 2 is a list, not a cell — a row holding a comma needs quoting, or YAML reads it as one` | An unquoted comma inside a cell made YAML read the cell as a list. Quote that cell. |
| `slide 1 (component 'bullets'): field 'columns' must be an int, got 'two'` | Use a number. |
| `slide 1 (component 'document'): 'source' is required` | Point at a markdown file. |
| `slide 1 (component 'document'): source not found: examples/nope.md — looked beside the deck spec and in /path/you/ran/from` | Looked for beside the deck spec first, then as given. The message names both places. |
| `slide 1 (component 'document'): 'side' must be one of left, right, full, got 'middle'` | Use one of the three. |
| `slide 1 (component 'document'): 'lines' must look like '12-40' — one-based and inclusive, got '12'` | A range needs both ends. Write `lines: '12-40'`; quote it so YAML keeps it a string. |
| `slide 1 (component 'document'): 'lines' must start at 1 or more and end at or after its start, got '5-2'` | Lines are numbered from 1, and the range reads low to high. |
| `slide 1 (component 'document'): 'lines' starts at 11 but docs/qa.md has only 10 line(s) — the excerpt is gone from the source, so the card would be empty` | The source shrank past the range. Re-read the file and pick the lines you meant — this is the drift `lines:` exists to surface rather than card an empty box. |
| `slide 1 (component 'table'): 'rows' must be a non-empty list` | Add `rows:` with at least one row. Also what you get for a misspelled `rows`. |
| `slide 1 (component 'table'): row 1 covers 2 column(s) but the table is 3 wide — a table is rectangular, so add a cell, or widen one with 'across:'` | Give the row its missing cell. The count includes any column a `down:` cell above already covers. |
| `slide 1 (component 'table'): row 2 covers 3 column(s) but the table is 2 wide — a table is rectangular, so this row has a cell too many — a column a 'down:' cell above already covers is not written again` | Delete the cell that stands under the reaching one. If *every* column is covered, the table wants one row fewer. |
| `slide 1 (component 'table'): the first row fixes the table's width, so it cannot be the empty row that a 'down:' cell above leaves behind — give the table a 'header:', or start it with real cells` | An empty first row leaves the table no columns to be. |
| `slide 1 (component 'table'): row 2 has no cells of its own — every one of its columns is covered by a 'down:' cell above, so the row is height and nothing else. Drop it, and drop a row from the 'down:' that reached into it: the table you meant is the same table without either` | Shorten the `down:` by one and delete the row. |
| `slide 1 (component 'table'): row 1 cell 1 sets 'down' to 4, reaching past the last of the table's 2 row(s) — count the header and total rows, which are rows of the table too` | A `down:` counts rows of the built table, not entries in `rows:`. |
| `slide 1 (component 'table'): row 2 cell 1 reaches across a column that a 'down:' cell above already covers — cells cannot overlap` | The row's `across:` walks into a column the row above claimed. Split the span, or move the `down:`. |
| `slide 1 (component 'table'): row 1 cell 1 sets 'down' to 0 — it is how many rows the cell covers, itself included, so it is a whole number from 1` | A cell covering only itself is `1`, not `0`. Same message for `across:`. |
| `slide 1 (component 'table'): 'align' is one entry per column, so it needs 3; got ['left', 'right']` | `align:` is per column, not one value for the table. `valign:` is the opposite — one value for the whole table. |
| `slide 1 (component 'table'): 'valign' is one of top, middle, bottom, got 'centre'` | Those are the three. A cell's own `valign` takes the same three. |
| `slide 1 (component 'table'): 'rules' is one of rows, header, grid, none, got 'dotted'` | Those are the four. Rule weight and colour are `weight:` and `color:`. |
| `slide 1 (component 'table'): 'density' scales the cell padding, so it is a positive number — 0.6 for a dense table, 1.4 for an airy one; got 0` | `density:` is a multiplier, never inches. |
| `slide 1 (component 'table'): 'widths' entries must be positive numbers, got 0` | Widths are relative weights; a column of zero has no room for its own padding. |
| `slide 1 (component 'fanout'): 'source' is the call the branches leave from` | Add `source:` — the call the plate carries. |
| `slide 1 (component 'fanout'): a fanout needs at least 2 items — one consequence is the 'connector' component` | Add a consequence, or draw the single link with `connector`. |
| `slide 1 (component 'fanout'): item 1 needs a 'text'` | Every branch says what it sets off; the `icon:` is optional. |
| `slide 1 (component 'fanout'): item 1 has the unknown field 'colour'; an item reads: icon, text` | A branch carries those two. |
| `slide 1 (component 'prose'): 'paragraphs' is a non-empty list of strings, one per paragraph` | Give it a YAML list. A single string is one paragraph in a one-item list. |
| `slide 1 (component 'prose'): 3 paragraph(s) need 6.10in at this measure but the body rect is only 5.30in — split the slide or shorten the copy` | The measure is capped for readability, so more copy means more depth, not a wider line. |
| `slide 1 (component 'fanout'): 'weight' scales the bus stroke, 0.5 to 4.0; got 99` | It is a multiple of the default stroke, not a point size. |
| `slide 1 (component 'fanout'): the source plate and the bus leave 0.62in for the consequences — widen the placement` | The placement is too narrow to carry both halves. |
| `slide 1 (component 'versus'): anchor 'middle' has nothing to act on — a versus fills its placement and sets its own type; drop the anchor, or bound the placement with 'rows:'` | It stretches to whatever rectangle it is given, so drop the anchor or bound the placement with `rows:`. Same message for `align`. |
| `slide 1 (component 'versus'): 'left' needs a 'value' and a 'label' — a versus is two named magnitudes` | Each side names itself and carries a number. |
| `slide 1 (component 'versus'): 'left' has the unknown field 'colour'; a side reads: highlight, label, note, value` | A side carries those four. Colour comes from `highlight:` and the theme. |
| `slide 1 (component 'versus'): both sides set 'highlight' — it marks the one the slide is arguing for, so only one side takes it` | Drop one. Marking both says nothing. |
| `slide 1 (component 'versus'): the two sides need 2.06in and 2.06in to set their own type but the placement leaves 2.73in for both — widen the placement, or shorten the longest value or label` | Each plate has to hold the longest word of its value, label and note without breaking it; the two floors and the glyph between them need the room. |
| `slide 1 (component 'diverge'): 'items' must be a non-empty list` | Add `items:` with at least one row. Also what you get for a misspelled `items`. |
| `slide 1 (component 'diverge'): item 1 needs a 'label' and a 'value'` | Every row names itself and carries the signed number its bar draws. |
| `slide 1 (component 'diverge'): item 1 has value 'lots' — a value is the signed number the bar draws` | A value is a number. The sign is what decides which side of the rule it draws on. |
| `slide 1 (component 'diverge'): item 1 has the unknown field 'colour'; an item reads: label, note, value` | A row carries those three. Colour comes from the sign and the theme's accents, never from the spec. |
| `slide 1 (component 'diverge'): 'peak' is a positive magnitude; got 0` | `peak:` is what the longest bar stands for, so it is greater than zero. |
| `slide 1 (component 'diverge'): 'label_width' is a fraction of the placement's width, 0.1 to 0.6; got 3` | It is a fraction, not inches or a column count. |
| `slide 1 (component 'diverge'): align 'center' would pull the labels off the centre rule they are set against; 'diverge' sets each label flush to the rule` | Drop the `align`. |
| `slide 1 (component 'nav'): 'items' must be a non-empty list of section names` | Add `items:` with at least one section name. Also what you get for a misspelled `items`. |
| `slide 1 (component 'nav'): active 'Evidenec' is not one of the items (Problem, Evidence, Next)` | `active:` names one of `items:` exactly. Refused rather than ignored: a renamed section would silently mark nothing. |
| `slide 1 (component 'nav'): color 'line' is EDEDED against this slide's FFFFFF, 1.17:1 — a label that close to the paper cannot be seen; name a role that stands off it` | A role you name is honoured however low its contrast, but not when it is invisible. Name an accent or `ink`. |
| `slide 1 (component 'image'): 'src' must name an image file` | Add `src:`. Also what you get for a misspelled `src`. |
| `slide 1 (component 'image'): a circle mask needs 'fit: cover'. 'contain' letterboxes the picture down to the source's own aspect, and the mask drawn on that oblong is an oval, not a circle — crop it with 'crop: 1:1' instead` | Drop the `fit: contain`, or use `mask: rounded`. |
| `slide 1 (component 'image'): mask must be one of none, circle, rounded, got 'hexagon'` | Use one of the three. |
| `slide 1 (component 'image'): 'radius' is a fraction of the picture's short side, 0..0.5 (0.5 is a circle); got 0.75` | Radius is a fraction, not inches. |
| `slide 1 (component 'image'): 'widescreen' is not an aspect — write it as '16:9' or 1.78` | `crop:` takes an aspect. Quote it: `crop: "16:9"`. |
| `slide 1 (component 'image'): every 'over' line needs a 'text', got {'rung': 'title'}` | Each `over:` entry is a string or a mapping containing `text:`. |
| `slide 1 (component 'image'): an inset of 0.9 leaves the text no width inside a picture 11.87in wide` | `inset:` is a fraction of canvas width, and it is applied to both edges. |
| `slide 1 (component 'image'): scrim has no key 'colour'; known keys: pair, opacity, gradient` | A scrim's colour comes from its `pair:`, never a literal. |
| `slide 1 (component 'image'): a 'bottom' gradient scrim cannot make this legible — the text reaches far enough into the clear end that it would need 486% peak opacity; move the text toward the bottom edge or use a flat scrim` | The text sits in the gradient's clear end. `anchor: bottom` the placement, or drop `gradient:`. |
| `slide 1 (component 'ellipse'): the label 'Discovery phase' needs more than the 0.48in across the middle of a 0.68in disc at 12.0pt — grow the placement, raise 'size', or name a smaller 'rung'` | A label is refused rather than clipped, and it is measured across the *inscribed* width, not the diameter. Widen the placement, raise `size:`, or name a smaller `rung:`. |
| `slide 1 (component 'connector'): 'from' is required — give it a placement id, or two numbers, x then y, as fractions of the canvas` | Both ends are required. Same message for a missing `to:`, and for either one misspelled. In the spec the pair is a list: `from: [0.5, 0.5]`. |
| `slide 1 (component 'connector'): 'to' names the placement id 'summary', which this slide does not declare; ids here: discover` | The end names an `id:` that no placement **on this slide** carries. The message lists the ids that exist; a connector cannot reach onto another slide. |
| `slide 1 (component 'connector'): 'from' must be a placement id, or two numbers, x then y, as fractions of the canvas; got [0.5]` | An end given as a list must hold exactly two numbers, each a fraction of the canvas. A bare string is read as a placement id instead. |
| `slide 1 (component 'connector'): 'from' and 'to' resolve to the same point on the canvas, so the line has no direction` | The two ends are the same placement, or two identical `[x, y]` pairs. A line needs somewhere to go. |
| `slide 1 (component 'icon'): needs a 'name:' saying which glyph to draw — one of 4,001 names, catalogued in docs/glyphs.md` | Add `name:`. Also what you get for a misspelled `name`. The catalogue is [`docs/glyphs.md`](glyphs.md). |
| `slide 1 (component 'rule'): align 'center' has nothing to act on — a horizontal rule spans its placement's whole width; use anchor to move it across, or narrow the placement` | A rule already fills one axis, so the key that would move it *along* that axis does nothing. Use the other key — `anchor:` for a horizontal rule, `align:` for a vertical one — or narrow the placement. |

## Themes written before the cutover

| Message | Fix |
|---|---|
| `type ramp entry 'title': 'rung' (points per inch of canvas height) was replaced by 'pt' — the size at the theme's reference_height` | State the point size: `title: {pt: 34}`, with `type.reference_height:` naming the canvas it is for (7.5in by default). |
| `type ramp entry 'title': 'size' (point size) was replaced by 'pt' — the size at the theme's reference_height` | Same key, new name. |

| `slide 1 (component 'code'): needs 'lines' (a list) or 'text' (a block scalar) — a listing with nothing in it draws an empty plate` | Give it one of the two. |
| `slide 1 (component 'code'): give 'lines' or 'text', not both — 'text' is a block scalar, 'lines' a list` | Pick one. `text:` is for pasting a listing whole; `lines:` for building it up. |
| `slide 1 (component 'code'): 6 lines need 3.10in but only 2.40in is left — shorten the listing, split the slide, or lower 'size'` | A listing is as deep as its line count at its point size. Do one of the three. |
| `slide 1 (component 'code'): 'size' is a point size, got 'small'` | `size:` is a number of points, not a name. |
| `slide 1 (component 'code'): 'size' 8.0pt is below the theme's 10.5pt minimum` | The theme sets the floor; raise the size or lower `type.min_pt` in the theme. |
| `slide 1 (component 'swatches'): 14 roles in 8 columns need 3.40in but the body rect is only 2.60in — show fewer roles or split the slide` | Name a subset in `roles:`, or give the placement more rows. |
| `slide 1 (component 'swatches'): 'roles' is a list of palette role names; omit it to show every role the theme declares` | Either give a list, or drop the key. |
| `slide 1 (component 'swatches'): no palette role(s) brand-blue; declared roles: accent-1, accent-2, …` | Roles are the theme's semantic names, not brand words. The message lists the ones that exist. |
| `slide 1 (component 'grid'): the placement is 0.40in tall, too short to draw a grid in` | Give it more rows — a grid needs depth to read as one. |
| `slide 1 (component 'callouts'): a 'heading' needs 0.42in and the placement is only 0.30in tall` | Drop the heading, or give the placement more rows. |

## Images, themes and templates

A slide's `background: {image:}`, an `image` or `card` component's `src:`, and a theme's
`marks.media:` all resolve the same way, so they all fail the same way. The not-found
messages name every directory they searched, because "not found" alone cannot tell you
whether your path or your theme is at fault.

| Message | Fix |
|---|---|
| `image 'cover.jpg' does not exist` | An absolute name is taken exactly as written and nothing is searched. Check the path. |
| `image 'cover.jpg' was not found in authoring/q4, and the theme names no template to fall back on — put the file beside the deck spec, or give the theme a 'template:' that carries it` | A themeless theme has no archive to fall back into, so the deck's own directory was the only place to look. |
| `image 'cover.jpg' was not found in authoring/q4, nor inside brand.pptx at ppt/media/cover.jpg` | Every place was searched and named. Either the file is somewhere else, or the name it carries inside the template's archive is not the one you wrote. |
| `image '../shared/cover.jpg' climbs out of every directory it would be looked for in — name it relative to the deck spec or the theme's template, or give the full path` | A `..` leaves every search directory, so no search order can apply to it. Move the file beside the spec, or write the absolute path. |
| `unknown theme 'acme': no theme file at templates/acme.theme.yaml (set DECKWRIGHT_THEME_DIR to search elsewhere) and no packaged theme of that name (packaged: base). Onboard a brand template with 'deckwright conform <brand>.pptx --adopt acme', or pass a path to a theme file` | The deck's `theme:` (or `--theme`) is a name, and neither the theme directory nor the package holds it. Onboard the brand template with `deckwright conform templates/Brand.pptx --adopt acme`, point `DECKWRIGHT_THEME_DIR` at wherever your themes live, or use `theme: base`. |
| `theme file not found: templates/acme.theme.yaml — that is read as a path, and nothing is searched. To load a theme by name, pass the bare name (e.g. 'base'), which is looked up in templates and then in the packaged themes` | Anything with a suffix or a directory in it is a path, taken exactly as written. Fix the path, or drop to the bare name so the theme directory and the packaged themes are searched. |
| `theme 'tidewater' binds 'accent-1' to 'accent1', which reads as a template slot name, but the theme names no 'template:' — give a literal RRGGBB, or name a template to bind its slots` | A slot name needs a template's `clrScheme` to resolve against. Write the colour itself (`accent-1: E4572E`), or give the theme a `template:`. |
| `theme 'scale': rows is a whole number of rows, got 'twelve'` | The `scale:` block's `rows:` and `columns:` are counts — write the number. `columns:` gives the same message under its own name, and `.inf` (`got inf`) is refused with everything else that is not a count. |
| `type ramp entry 'title': pt is a point size, got 'huge'` | A ramp entry's `pt:` is a number of points at the theme's `type.reference_height`. |
| `theme templates/acme.theme.yaml: type is a mapping of settings, got 5` | A block was written as a scalar or a list. `scale`, `bind`, `marks`, `chart`, `motion`, `type.ramp` and the `scale:` block's own `margin` all give this message under their own name. |
| `theme templates/acme.theme.yaml: type.reference_height is a canvas height in inches, got 'tall'` | `type.reference_height` is the canvas height in inches the ramp's point sizes are written for. |
| `theme templates/acme.theme.yaml: type.reference_height is 0.0; it is the canvas height the ramp's point sizes are written for, so it must be above zero` | Give it a positive number (7.5 by default), or drop the key and keep the default. Every size in `type:` is a ratio to it, so zero has no meaning even with no `ramp:` at all. |
| `theme templates/acme.theme.yaml: type.min_pt is a point size, got 'small'` | `type.min_pt` and `type.line_weight_pt` are numbers of points at the theme's `reference_height`; `line_weight_pt` gives the same message under its own name. |
| `theme templates/acme.theme.yaml: motion stagger_ms is a whole number of milliseconds, got 'soon'` | `motion.stagger_ms` and `motion.beat_ms` are counts of milliseconds; `beat_ms` gives the same message under its own name. |
| `template brand.pptx is not a readable .pptx: PackageNotFoundError: Package not found at 'brand.pptx'` | The theme's `template:` is corrupt, truncated, or another application's format under a `.pptx` name. The message names the path and what python-pptx made of it. |
| `deck Deck v3.pptx is not a readable .pptx: PackageNotFoundError: Package not found at 'Deck v3.pptx'` | The same refusal from `inspect`, about the deck you handed it rather than a template. `qa` reports an unreadable deck as a `package` finding instead. |

## Too much content

These fire at build time with the real measurements, so the number in the message is the number to fix.

| Message | Fix |
|---|---|
| `slide 1 (component 'bullets'): 30 bullets in the longest column need 10.08in but only 5.30in is available — split the slide, add a column, or shorten the list` | Do one of the three things it suggests. |
| `slide 1 (component 'callouts'): 6 items need 13.35in of height but the body rect is only 5.40in — split the slide or shorten the copy` | Rows are as deep as their own copy, so the ceiling is the total depth of the words, not a fixed item count. Cut a row, or cut the wordiest body. |
| `slide 1 (component 'stats'): 5 items in 1 columns need 8.22in of height but the body rect is only 5.30in — split the slide or reduce the items` | Raise `columns:` (up to 4) or drop a tile. |
| `slide 1 (component 'flow'): 6 steps and the 0.36in lanes between them need more than the 2.00in this placement runs across — drop a step or grow the placement` | Widen the `at:`, or switch to `direction: vertical`. |
| `slide 1 (component 'flow'): a numbered disc is 0.60in across at this canvas's head size, and each step is only 3.79x0.50in — grow the placement or drop 'numbered'` | Give the flow more rows, or set `numbered: false`. |
| `slide 1 (component 'table'): 41 rows need 17.30in of height but the placement is only 5.30in — split the table or shorten the cells` | Split the table across slides, or cut rows. |
| `slide 1 (component 'table'): 60 columns leave 0.20in each, less than the 0.36in the theme's gutter pads a cell by — drop a column, widen the placement, or tighten it with 'density:'` | Six or seven columns is the practical ceiling on a 12-column placement at the default density; `density: 0.6` buys a couple more. |
| `slide 1 (component 'document'): the card came out 14.92in tall but only 5.30in is available — card fewer lines with 'lines: 12-40', raise 'max_width' to set the type smaller, or use 'side: left'/'side: right' to narrow it. Do not copy part of the file into a shorter one; the copy is what this component exists to avoid` | The markdown file is too long for one slide. Narrow it with `lines:` — copying an excerpt into a second file is the drift this component exists to prevent. |
| `slide 1 (component 'card'): the card's type wants 4.59in but only 0.05in is left inside the plate — shorten the copy or grow the placement` | A card is a plate with an inset, so the type gets less room than the placement suggests. Cut the `body:`, or give it more rows. |
| `slide 1 (component 'card'): the icon alone wants 1.20in of the 0.90in inside the plate — grow the placement or drop the icon` | The glyph is sized off the `head` rung, so a short placement cannot hold one. |
| `slide 1 (component 'card'): the placement is smaller than the 0.18in the theme's gutter insets a card by on every side` | The placement is smaller than the plate's own padding. Widen the `at:`. |
| `content is 8375px tall but the render canvas is only 4000px — the browser clipped it; raise DECKWRIGHT_SHOT_CANVAS_H to at least 8375 or shorten the source` | A far longer `document:` source — the browser clipped it before the card guard above could measure it. Shorten the file. |
| `the height probe did not run and the content reaches the last row of the 4000px render canvas, so the browser clipped it — raise DECKWRIGHT_SHOT_CANVAS_H or shorten the source` | The same clip, caught in the pixels because the source swallowed the height probe: a raw `<plaintext>`, `<textarea>` or `<xmp>`, or an unterminated `<script>`, ends the parse before the appended script. Fix the stray tag, or raise the canvas. |

The last two are the only messages here that arrive with a Python traceback above them: a browser that clipped the page is an external-renderer failure, not a spec mistake, so they are logged as errors rather than reported as validation messages. Every other message on this page is a single clean line and an exit code of `1`.

## External tools

Five commands shell out — LibreOffice, Poppler's `pdftoppm` and `pdftotext`, a
Chromium-family browser, and fontconfig's `fc-list`. The first four raise when the
binary is absent, and each failure names the one it could not use, so the fix is always
"install that one, or point the matching `DECKWRIGHT_*` variable at it"; which command
needs which tool is in [`docs/cli.md`](cli.md#external-tools). `fc-list` has no message
here — the `doctor` row and the `font-substituted` check that ask it go silent instead.

A tool that is **absent** and a tool that **ran and failed** are different errors. The
first is about the machine and prints as one line; the second is a renderer fault and is
logged with a traceback, because there is a crash to report.

| Message | Fix |
|---|---|
| `soffice not found (/path/to/soffice) — needed by render, and QA's render-based checks; brew install --cask libreoffice, or set DECKWRIGHT_SOFFICE to the path of an installed one` | LibreOffice is not installed, or `DECKWRIGHT_SOFFICE` names something that is not there. The message carries the install command for this platform. |
| `pdftoppm not found (/path/to/pdftoppm) — needed by render, and QA's render-based checks; brew install poppler, or set DECKWRIGHT_PDFTOPPM to the path of an installed one` | Poppler is not installed, or `DECKWRIGHT_PDFTOPPM` names something that is not there. |
| `no Chrome/Chromium binary found — needed by shot and any 'document:' slide; brew install --cask google-chrome, or set DECKWRIGHT_CHROME to the path of an installed one` | Only `shot` and a `document:` component need a browser; everything else builds without one. |
| `could not start the browser at '/path/to/chrome' — brew install --cask google-chrome, or set DECKWRIGHT_CHROME to the path of an installed one` | `DECKWRIGHT_CHROME` (or a `chrome=` argument) names something that is not there, or is not executable. Correct the path, or unset the variable to fall back to autodetection. |
| `<any of the above>` + `Or re-run with --no-render for the checks that need no external tool: bounds, placement, reserved regions, type sizes and contrast.` | `qa` adds this line to any missing-tool failure. `--no-render` runs every manifest-based check and skips only overflow and render contrast. |
| `LibreOffice PDF conversion failed` | `soffice` ran and exited non-zero — installing it is no fix. The deck, or the profile directory, is what it refused; the log record carries both. |
| `LibreOffice reported success but wrote no PDF. Two things cause this: an input path it could not read (<path>), or a leftover soffice process holding the profile this run needed — check with 'pgrep -fl soffice'` | `soffice` exited 0 having converted nothing. The message names the absolute path it tried, so check that first; otherwise end the leftover process. The previous run's PDF is removed before every conversion, so this is reported rather than rasterised as if it were this deck. |
| `no deck to render at /abs/path/deck.pptx` | The input does not exist at the path it resolved to. Both the input and `--outdir` are resolved before LibreOffice sees them, so a relative path is taken from your shell's directory. |

A missing tool is a configuration failure, not a validation one: the CLI prints the
message alone and exits 1, since the fix is on the machine and not in the stack. In a
`conform` run either kind fails the one exercise that needed the tool and the run
continues.

## The command line

An argument the command cannot use, and a destination already holding a file, are both
checked before the command reads or writes anything.

| Message | Fix |
|---|---|
| `--as must be 'yaml' or 'md', got 'txt'` | `deckwright extract` writes a draft spec (`yaml`) or a transcript (`md`). Those are the two. |
| `a deck needs a name, got '———'` | `deckwright new` slugs the name down to letters and digits for the deck's directory, and this one left nothing. Give it a name carrying at least one of those. |
| `authoring/q4/q4.deck.yaml is the spec being compiled — writing the deck there would leave nothing to rebuild it from. Give --out a .pptx path` | `deckwright build --out` aimed at its own input. Rebuilding over an existing `.pptx` is fine and stays fine; a spec is the one destination nothing can rebuild. |
| `out/q4/q4.yml is a YAML path, and a deck is never written to one — this is how --out lands on a spec. Give it a .pptx path` | The same refusal, widened: `--out` a character off the spec's name, or aimed at a directory of specs, reaches a spec without being the spec. |
| `deck decks/Bord Update.pptx is not a readable .pptx: no file at that path` | `deckwright extract` names its default destination after the deck, so it checks the deck is there before deriving anything from the name. A typo, or a directory where a file was meant. |
| `Board Update.deck.yaml already exists — pass --force to replace it` | `deckwright extract` will not write over what is at its destination, which on a second run of the same deck is the draft you have been editing. Give `--out` another path, or pass `--force` if the edits are expendable. `deckwright sample` refuses the same way about the template it writes. |
| `authoring/q4-review/q4-review.deck.yaml already exists — a scaffold never overwrites a deck you have written. Pick another name, or edit that one.` | `deckwright new` has no `--force`: a scaffold is one command to re-run, and the spec at that path is not. Pick another name, or edit the one that is there. |

## The glyph bundle

The ~4,000 Material Symbols `icon:` draws from ship as one archive with a manifest
pinning it. These fire when that pair is missing or disagrees — see
[`docs/cli.md`](cli.md#glyphs--the-built-in-icon-set).

| Message | Fix |
|---|---|
| `no icon 'rocket_launch': the built-in glyph bundle is missing from …/glyphs.zip — run 'bin/setup', or 'deckwright glyphs sync' to rebuild it` | The archive is absent, so *every* name misses. This is an install problem, not a typo, which is why no near-miss is offered. |
| `the glyph bundle …/glyphs.zip is gone` | It disappeared between being opened and being read — a rebuild or a `git clean` mid-run. Re-run the command. |
| `no glyph manifest at …/glyphs.sum — the checkout is incomplete` | `glyphs.sum` is committed beside the archive; restore it (`git checkout` it) rather than regenerating, or the pin is lost. |
| `glyph manifest …/glyphs.sum names no upstream commit` | Its header carries the upstream ref. Restore the file, or re-run `deckwright glyphs sync --ref <commit>` to write both files together. |
| `glyphs can only be synced from a source checkout` | `deckwright glyphs sync` rewrites files in the repo; an installed wheel has nowhere to put them. Run it from a clone. |
| `could not fetch the glyph upstream at <ref>` | `sync` needs `git` and a network, and clones ~119MB into a temp directory. The error's context carries git's own stderr. |

`deckwright glyphs verify` reports the same disagreements without raising — it is what
`bin/setup` runs, and what `deckwright doctor` reports as `glyphs.bundle`.
