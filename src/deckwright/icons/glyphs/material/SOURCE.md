# Material Symbols — vendored

| | |
|---|---|
| Source | [google/material-design-icons](https://github.com/google/material-design-icons) |
| Commit | `50f0603134ce7b70b2d71b686cc13e8b57ccb74c` (2026-07-31) |
| Selection | `symbols/web/*/materialsymbolsrounded/*_fill1_24px.svg` — the Rounded style, filled |
| Licence | Apache 2.0, `LICENSE` beside this file |
| Shipped | 4,001 of the 4,117 upstream files |

The set is packed into `glyphs.zip` beside this file, with `glyphs.sum` — one
`<sha256>  <name>.svg` line per glyph — pinning it. The commit above is repeated in that
manifest's header, and the manifest is what `deckwright glyphs verify` checks the bundle
against. Entries are **stored rather than deflated**: git and the wheel both compress the
bundle themselves, so pre-compressing it costs space in both and makes every glyph read
slower.

The members are upstream's bytes, renamed from `<name>_fill1_24px.svg` to `<name>.svg`.
Two deviations, both measured rather than assumed:

**67 files gained a `viewBox`.** They are legacy 24px-grid drawings carrying only
`width`/`height`; the loader refuses an SVG without a `viewBox`, and every coordinate in
them falls inside 0..24, so `viewBox="0 0 24 24"` was inserted. The rest declare
`0 -960 960 960` (4,018) or `0 96 960 960` (32) and are untouched.

**116 files were dropped.** deckwright emits every subpath of a glyph into one DrawingML
`a:path`, and that is filled **even-odd** — two concentric same-direction circles come out
as a ring, two overlapping same-direction rectangles come out with a hole. Material
Symbols declare no `fill-rule`, so upstream means nonzero. The two rules agree wherever
contours nest without overlapping, which is 4,001 of the set; they disagree on the
`*_off` variants, whose slash bar overlaps the body it crosses and so punches a hole
through it instead of painting over it. Those are unusable here and are not shipped.

The two rules are compared by area, above a floor that keeps rounding out of it: across
the upstream set, coincident crossings disagree by at most 5e-17 of the viewBox and the
faintest real disagreement is 4e-6, with nothing in between.

## Re-vendoring a newer upstream

```bash
bin/run glyphs sync --ref <commit>
bin/test
git diff src/deckwright/icons/glyphs/material/glyphs.sum
```

`deckwright glyphs sync` is the recipe above as code — the same blobless sparse checkout
(~119 MB into a temp directory it deletes afterwards), the same rename, the same
`viewBox` insertion, and the even-odd filter applied automatically rather than by hand.
It rewrites `glyphs.zip` and `glyphs.sum` together, so the pin and the hashes cannot
disagree, and prints what was added, removed or redrawn.

The manifest is the review surface: **a re-vendor is read as a text diff**, one line per
glyph, never as a binary. `tests/icons/test_vendored.py` then re-measures the even-odd
rule over whatever the sync produced — it shares `icons/vendor.py`'s measure with the
command — so a newly nonzero-dependent glyph reddens the suite rather than shipping
broken. Without `--ref`, `sync` rebuilds the pinned set instead of moving it, which is
how a damaged checkout is repaired.
