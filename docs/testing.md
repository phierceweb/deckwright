# Testing

How this library is tested: what the template test guards, what only a unit test can
guard, and how to tell a test that fails when the behaviour breaks from one that cannot
fail at all.

This is about the **library's own test suite**. For checks that run against a *built
deck* — bounds, safe zones, min font size, contrast, render overflow — see
[`qa.md`](qa.md). `deckwright qa` is a product feature; this doc is about `bin/test`.

---

## Table of Contents

- [Why these rules](#why-these-rules)
- [The template test is the primary guard](#the-template-test-is-the-primary-guard)
- [What only a unit test can guard](#what-only-a-unit-test-can-guard)
- [Tests that cannot fail](#tests-that-cannot-fail)
- [Proving one either way](#proving-one-either-way)
- [Fixtures that dodge the defect they name](#fixtures-that-dodge-the-defect-they-name)
- [Redundant tests](#redundant-tests)
- [Raw OOXML has its own gate](#raw-ooxml-has-its-own-gate)
- [Adding a capability](#adding-a-capability)
- [Adding a unit test](#adding-a-unit-test)

## Why these rules

Real defects have shipped through a green suite. Every one was a *template-variance*
defect — the code trusting something a synthetic fixture always gets right — and every
one was found by building a deck on a real template and looking at the render, not by
adding tests.

Draw both lessons, not one. Unit tests are the only guard on a large share of this
codebase — guard clauses, error types, defaults, manifest vocabulary — so "write fewer
unit tests" is the wrong conclusion. But a test count is not a measure of safety, and
tests written against machinery invented alongside them mostly assert that the
machinery agrees with itself.

Do not add figures to this doc. Counts of tests, exercises, templates, or coverage rot
on the next commit and settle nothing; the rules below are what survives, and each one
names the mutation that defeats the test it argues against.

## The template test is the primary guard

`tests/test_templates.py` builds every capability in
`src/deckwright/conform/` against **every brand template in `templates/`** — the
same directory decks resolve `theme:` from, with `-4-3` twins skipped and a generated
`deckwright sample` refused by its own `docProps` mark. It then asserts on the resulting
deck and its manifest: every exercise builds, the deck reads back, the package holds no
duplicate shape id or broken relationship, no ink is unreadable on what was really
painted behind it, nothing lands outside the slide or intrudes on a reserved region, and
the derived theme bound a real brand accent.

It answers the one question nothing else can — *can the library build a deck on a design
it did not choose?* Each run re-derives the theme by measurement, so what it exercises is
genuine brand variance rather than a fixture shaped to pass.

**The guard is worth exactly the variety of `templates/`.** Read that off the directory;
`deckwright doctor` reports it. One template is not a variance test, and neither is one
template plus its 4:3 twin. `templates/` is gitignored, so the module skips where it is
empty and **a green suite on a machine with no brand template proves almost nothing**.

**Read every finding, not only the errors.** A contrast assertion that filtered to errors
once stayed green while every line of a deck sat at 1.0:1 against its real backdrop, with
the warnings the suite was choosing not to look at.

**A check that reads what the code recorded can agree with itself.** Assertions that read
`Theme.palette` answered "our defaults exist" rather than anything about the template — a
blank `Presentation()` passed nearly all of them. They now read `derive`'s own `bind` and
resolve each slot against the template's `clrScheme`, so an unbound accent is an empty
result rather than a default one. Never assert a template's properties through a loaded
`Theme`.

Because a rule nobody can see rots the same way twice, **`tests/test_templates_gate.py`**
hands those assertion functions a blank Office file and fails if they accept it, with the
generated sample as the negative control — they must reject the blank *and* accept a
designed template. It needs no template, browser or build, so it runs in CI and on a
fresh clone, which is where a rotted assertion would go unnoticed longest.

### What it structurally cannot cover

- Any path a *successful* build does not execute — every `raise`, every validation
  message, every "template is malformed" branch.
- Values nothing downstream observes — a default that only affects appearance, a manifest
  field no check reads, a CLI line nobody asserts on.
- Anything behind a capability with no exercise. Missing exercise, missing coverage.
- **What a renderer does with what the compiler wrote.** It reads the deck back out of the
  file; it never opens one. A table row that is entirely a vertical merge is legal OOXML,
  builds against every template and reads back correct — and LibreOffice imports it
  wrongly, dropping a row and moving the table. **Build a deck and look at it before
  calling a capability done**, whatever this test says.

## What only a unit test can guard

Write one when the behaviour is unreachable from a successful build, or invisible in its
output:

- **Guard clauses and their error type.** Every validation raise in `spec/parse.py`,
  `theme/load.py`, `theme/chartstyle.py`, `charts/model.py` and the components is
  unit-tested and only unit-tested. Neutering one to `if False:` passes the rest of the
  suite. A `ThemeError` degrading into a raw `TypeError` is a real regression nothing
  else sees.
- **Silent acceptance of unknown keys.** Replacing an `unknown = sorted(set(cfg) - set(_KEYS))`
  check with `unknown = []` is invisible everywhere except its own unit test — and a spec
  field silently dropped is the failure the parser exists to prevent.
- **Defaults and constants with no downstream assertion.** A build succeeds with any of
  them mutated. Pin the value with a literal, never by reading the constant back.
- **Values that only exist in the manifest.** Its geometry and contrast are checked; its
  vocabulary is not. An unknown `rendered` value written straight through corrupts the QA
  contract silently.
- **Wiring between layers that end-to-end output hides.** `tests/compile/test_build_body.py`
  reaches no unique source lines and is still the sole guard on the `animate:` → manifest
  wiring; a coverage-only reading would delete it.

Use a **real template** wherever behaviour depends on template variance. Swapping the
major and minor font faces in `theme/clrscheme.py` is invisible to any synthetic fixture,
because stock Office uses the same face for both.

## Tests that cannot fail

Three shapes. They are written as sketches rather than file references on purpose: the
shape is what recurs, and a citation rots the moment a test is renamed.

Recognise one by asking what single source line you would change to redden it. If the
answer is "nothing", or "the test itself", it is one of these.

### True by construction

Holds for every possible implementation.

```python
# The key can only appear if the source contained it — true for any parser
# that does not fabricate keys.
assert "chart" not in slide.content

# (L+0.05)/(L+0.05) for ANY luminance function, including `return 0.5`.
assert contrast_ratio(x, x) == 1.0

# python-pptx already defaults a bubble plot's dLbls to True. Skipping the
# labelling entirely leaves this green.
assert chart.plots[0].has_data_labels is True

# `height` is derived from `rect`, so anything built from it satisfies both
# bounds. Returning `rect.height` outright passes.
assert 0 < result.height <= rect.height
```

Assert what our code *writes* — the themed font, colour, number format.

### Circular — asserting a property with the function under test

```python
# WRONG — `accent_on` decides using this same `contrast_ratio`.
assert contrast_ratio(accent, inverse.bg) >= AA_LARGE

# RIGHT — a literal value for a literal palette.
assert ctx.accent(size_pt=24) == "1F3864"
```

The wrong version passes with `contrast_ratio` forced to 21.0, with `required_ratio`
forced to 0.0, and with the give-way branch deleted — the exact behaviour it claims to
test.

### Vacuous negative

`not hasattr`, `x not in y`, `== []` over a surface the code never writes, or with a
fallback that swallows the failure.

```python
# The `or ""` holds whenever labels are absent ENTIRELY, so gutting
# `_style_data_labels` to an immediate return leaves this green.
assert '"%"' not in (labels.number_format or "")
```

Never put `or ""`, `or {}`, or `.get(k, default)` inside an assertion about what the code
produced. Assert the object is present first.

## Proving one either way

Break the line the test claims to guard, clear `__pycache__` — a stale `.pyc` makes a
mutated file keep passing — and run the test alone. Then run its directory: if a sibling
reddens and the test itself does not, the behaviour is guarded and the test is redundant
rather than a hole. That distinction decides whether to delete it or rewrite it.

## Fixtures that dodge the defect they name

A cache-staleness test whose fixture wrote the edited template to a *sibling filename*
never hit the stale key it existed to catch: the mutation it guards against passed the
whole suite. It now edits the template in place.

When a test names a defect, construct the exact condition that defect requires. If the
setup takes a shortcut, the test measures the shortcut — and reports green for precisely
the bug it was written to catch.

## Redundant tests

Do not write a test asserting internal arithmetic a template build already proves
end-to-end, and do not write one a neighbour already covers strictly.

Two shapes to watch for: a test asserting three fields where a sibling asserts the whole
object, and a per-case test standing beside a parametrized sibling that already covers
its case.

Prove redundancy before deleting — delete the test, re-apply the mutation it claimed to
guard, and confirm the suite still reddens. "It looks redundant" is how a real guard gets
thrown away. Coverage is not the criterion in either direction: several files reaching no
unique source lines are load-bearing under mutation (`tests/qa/test_model.py`,
`tests/layouts/test_compose_geometry.py`, `tests/compile/test_build_body.py`) — the lines
run elsewhere, but nothing elsewhere asserts on the *values*.

## Raw OOXML has its own gate

`src/deckwright/motion/` writes `<p:timing>` and `<p:transition>` as raw strings, because
python-pptx models neither. **No other layer in this project can check that output.**

- LibreOffice converts schema-invalid timing to PDF without complaint.
- `deckwright qa` renders the final state of a slide, which a build mid-reveal and a
  transition are both invisible to.
- A `filter` string is `xsd:string`, so a typo validates and silently does nothing.

The gap is not hypothetical: a missing required attribute on chart builds reached
delivered files because nothing mechanical looked.

`tests/test_ooxml_schema.py` validates every writer against the ISO/IEC 29500-4:2016
schemas vendored in `tests/schemas/ooxml/`, and carries a negative control that strips a
required attribute and asserts the gate reddens. Without that control, a validator that
silently passed everything would look identical to one that works.

**Schema-valid is a floor, not proof.** Only real PowerPoint says whether a file opens
without a repair prompt. See [`motion.md`](motion.md#verification).

## Adding a capability

A new component, chart kind, layout, or slide-level feature gets an entry in
the family module in `src/deckwright/conform/` that owns the shape. That is the test.

1. Add a key to `EXERCISE` — a plain-content slide dict written the way a real deck would
   use the feature. No brand words: the point is what the *template* can carry.
2. Keep it minimal but representative. `conform` builds each exercise as its own one-slide
   deck so a failure names itself, then builds one whole deck from everything that passed.
3. Run `bin/test tests/test_templates.py`. The feature is now driven against every
   template you hold, and its geometry, contrast and reserved-region behaviour checked on
   each.

Do not follow this with a unit test for the same feature's arithmetic. It is redundant by
construction — see [Redundant tests](#redundant-tests).

## Adding a unit test

Before writing it, answer both:

1. **What single line would I change to make this test fail?** If the answer is "nothing"
   or "the test itself", it is one of the shapes above. Do not write it.
2. **Does a successful template build already execute this line and observe its result?**
   If yes, that is the guard. Do not write it.

Then verify the first answer by hand: break the line, watch the test go red, put it back.
A test never observed failing has never been tested.
