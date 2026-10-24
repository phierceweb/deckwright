# Contributing to deckwright

Thanks for your interest. deckwright compiles declarative deck specs into branded
PowerPoint files; contributions that keep it well-tested and documented are
welcome.

## Scope — read this first

deckwright compiles a **declarative spec** into a deck. That shapes what belongs here:

- **A new capability is a slide the compiler can build**, and it lands as an exercise
  in `src/deckwright/conform/exercise.py` — which is what drives it against every brand
  template. A component that only one deck needs belongs in that deck's `extends:`
  module, not the library.
- **Design decisions live in the theme**, never in a component. If a change makes a
  component name a colour, a font or an inch, it is in the wrong place.
- **Decks are not library content.** A deck written for an audience is yours and stays
  out of the repo; `examples/` holds only specs that exercise the compiler.

## Development setup

Python 3.12+ is required.

```bash
git clone https://github.com/phierceweb/deckwright
cd deckwright
bin/setup        # venv + editable install + .env + pre-commit hooks
```

Rendering and QA additionally use local external tools — LibreOffice
(`soffice`), Poppler (`pdftoppm`, `pdftotext`), and a Chrome/Chromium for HTML
panels. Everything else runs without LibreOffice and Poppler, but the unit suite needs
the browser: it builds the capability catalogue, whose `document:` exercise starts one.

## Before you open a pull request

These checks run in CI and as pre-commit hooks — run them locally first:

```bash
bin/test    # pytest; a whole-suite run uses every core (docs/testing.md)
bin/lint    # ruff (lint + format) + mypy + structural gate + import layering + framework-first
```

**Expect skips.** `tests/test_templates.py` — the primary behavioural guard — builds
every exercise against real brand templates in `templates/`. Those are licensed
artwork, so they are not in the repo and the module skips for you and in CI; the full
corpus is run against a release before it ships. Don't try to check templates in.

And hold the change to these standards:

- **Tests travel with code.** New capability belongs in
  `src/deckwright/conform/exercise.py` (driven by the corpus), not a new unit
  test file; error paths and defaults get unit tests. See
  [`docs/testing.md`](docs/testing.md) for what makes a test worth
  keeping.
- **Docs travel with code.** Components, chart kinds, theme keys, CLI flags,
  and glyph names are all documented; `tests/test_docs.py` fails if you add
  one without writing it up.
- **Framework first.** deckwright builds on [pw-foundation](https://pypi.org/project/pw-foundation/)
  for logging, config, errors, atomic writes and content hashing —
  `bin/check-framework` refuses hand-rolled equivalents and names the
  replacement in every failure. Never reach for a third-party library when
  pw-foundation already provides it. Its module reference is its own docs, which
  `bin/setup` symlinks to `docs/pw-foundation/`; without the symlink, resolve them
  with `bin/py -c "import pw_foundation, pathlib;
  print(pathlib.Path(pw_foundation.__file__).parent / 'docs')"`. `bin/setup` also copies
  pw-foundation's starter rules into the gitignored `.ai/rules/`; where one disagrees
  with `bin/check-framework`, the gate is deckwright's rule.

## Coding conventions

The essentials:

- Modern Python 3.12+ syntax — `X | None`, lowercase `dict`/`list`/`tuple`.
- Type hints on every public signature; Google-style docstrings on public APIs.
- Structured logging via `pw_foundation.log.get_logger(__name__)` — never bare
  `print` outside the CLI entry point.
- Raise from `deckwright.errors` — never a bare `Exception`.

## Versioning

Stability lives in **tags**. `main` may contain unreleased work between
version tags — pin to a tagged release for production use. Pre-1.0, a minor
bump (`0.X.0`) may include breaking changes, always called out in
`CHANGELOG.md`; a patch bump is fixes only.

## Questions

Open an issue for bugs and feature requests. For anything security-sensitive,
follow [`SECURITY.md`](SECURITY.md) instead of filing a public issue.
