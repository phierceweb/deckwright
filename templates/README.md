# templates/

**Everything about a brand lives here, and nowhere else.** Drop a `.pptx` in this
directory, derive a theme from it, and both stay side by side for as long as you use
them. Nothing is ever copied somewhere else.

```
templates/
  Acme.pptx           the brand template — you put this here
  acme.theme.yaml     the theme derived from it — conform writes this here
  README.md
```

**Nothing here except this README is committed.** A brand template is someone else's
licensed artwork and a derived theme carries their palette; `.gitignore` refuses both
rather than trusting anyone to remember.

## Onboarding a template

```bash
cp ~/Downloads/Acme.pptx templates/
bin/run conform templates/Acme.pptx --adopt acme
```

That derives a theme from the template, builds every capability against it one slide at
a time, reports what it carries, and — because of `--adopt` — keeps the theme as
`templates/acme.theme.yaml`, beside the file it binds to.

Then build against it: `theme: acme` in a deck's config document is all it takes.

**A template is adopted where it lives.** Adopting one from outside this directory is
refused, and the error names the `mv` to run first. That is the rule that keeps a single
copy under a single name — the alternative is a second copy whose filename drifts from
the first.

## This directory is kept, not scratch

`out/` is disposable; this is not. The `.pptx` you drop is the one every deck named
`theme: acme` loads at build time, and the one the test suite drives. Delete it and the
theme stops resolving.

## Re-deriving, and keeping your edits

The derivation is a first draft — [`docs/conform.md`](../docs/conform.md) says to read
and edit it, and most themes get hand-tuned.

Re-running `conform --adopt acme` on the same template is a **refresh**: the theme
sitting beside the template is that run's sidecar, so your edits are carried through
verbatim and re-validated against every exercise. Nothing is lost, and you do not have
to keep a copy anywhere.

- **`--force`** is the only thing that discards tuning: it ignores the sidecar and
  derives again from scratch.
- Adopting a *different* template under a name already bound to one that is still here
  is refused — that would repoint someone's theme at another brand's artwork.

## The test suite drives what is here

`tests/test_templates.py` builds every capability in `src/deckwright/conform/exercise.py`
against each brand template in this directory, then checks bounds, reserved regions,
contrast, readback and package structure. It is the suite's primary guard.

- **Any diverse set works** — different palettes, fonts, master backgrounds, reserved
  logo regions. Marketplace templates are fine.
- A file ending `-4-3` is treated as the 4:3 twin of another design and skipped, and a
  generated `deckwright sample` is refused by its own `docProps` mark.
- The guard is exactly as strong as the variety of what is here. **One template is not a
  variance test**, and neither is one template plus its own 4:3 twin.
- `DECKWRIGHT_TEMPLATES_MIN=<n>` makes a smaller set a test failure instead of a quiet pass.
  Unset — the normal case — any number is accepted. The release runbook sets it so a tag
  cannot be cut against a thin set.

Because this directory is gitignored, the module skips in CI and on any machine without
templates, and a green suite there is the unit tests only. `tests/test_templates_gate.py`
runs everywhere and keeps those assertions honest by handing them a blank Office file.
