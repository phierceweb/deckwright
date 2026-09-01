"""The docs enumerate the code's vocabularies, and drift makes this fail. Each case below fails on
the *next* addition that skips its doc, which is the only moment the omission is cheap to fix."""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
COMPONENTS = ROOT / "src/deckwright/components"

# Components whose keys are checked somewhere other than a module-level _FIELDS tuple. The field
# gate cannot read them; their section is still required. Only `chart` remains — its keys are
# `charts.model._CHART_KEYS`, checked by test_the_chart_block_documents_every_key_it_accepts below.
_NO_FIELDS_TUPLE = frozenset({"chart"})


def _shipped() -> dict[str, str]:
    """Every component the package registers, mapped to its module's source. Read from the files,
    not ``registered_components()``, which also holds whatever a test fixture registered."""
    out = {}
    for path in COMPONENTS.glob("*.py"):
        text = path.read_text()
        for name in re.findall(r'@component\("([\w-]+)"\)', text):
            out[name] = text
    return out


def _doc(name: str) -> str:
    return (DOCS / name).read_text()


def _missing(names, text: str, fmt: str = "`{}`") -> list[str]:
    return sorted(n for n in names if fmt.format(n) not in text)


def test_every_component_has_a_section_in_the_components_reference():
    absent = _missing(_shipped(), _doc("components.md"), "### `{}`")
    assert absent == [], f"components with no section: {absent}"


def test_every_component_has_a_row_in_the_authoring_index():
    """The index is how a reader decides which section to load, so a component absent
    from it is a component nobody finds — even with its section written."""
    index = re.search(r"^## Components$(.*?)^---$", _doc("authoring.md"), re.S | re.M).group(1)
    rows = "\n".join(re.findall(r"^\| \[`[^|]+\|.*$", index, re.M))
    assert _missing(_shipped(), rows) == []


def test_every_component_is_placed_in_the_treatment_cost_table():
    """`treatments.md`'s cost table is a total partition of the registry, not a sample: a component
    missing from it reads as costing nothing, and nothing else in this file covers that doc."""
    section = re.search(
        r"^## What a treatment costs$(.*?)^## ", _doc("treatments.md"), re.S | re.M
    ).group(1)
    rows = "\n".join(re.findall(r"^\|.*$", section, re.M))
    assert _missing(_shipped(), rows) == []


def test_the_quoted_registry_listings_match_the_registry():
    """Two rows in errors.md quote a message that *prints the whole registry*. They are transcripts,
    so only an exact-string check catches a list that is present but short."""
    shipped = ", ".join(sorted(_shipped()))
    text = _doc("errors.md")
    for lead in ("known components: ", "reveals, "):
        quoted = re.findall(rf"{lead}([a-z, ]+)`", text)
        assert quoted, f"no errors.md row quotes the registry after {lead!r}"
        assert quoted == [shipped] * len(quoted), (
            f"errors.md quotes a stale registry after {lead!r}: {quoted} != {shipped!r}"
        )


@pytest.mark.parametrize("component", sorted(_shipped()))
def test_every_component_field_is_documented(component):
    """Read off the component's own ``_FIELDS``. A component validating its keys some other way has
    no tuple to read and is skipped here; its section is still required by the test above."""
    text = _shipped()[component]
    declared = re.search(r"^_FIELDS[^=]*= \(([^)]*)\)", text, re.M)
    if declared is None:
        # Six components validate their keys another way and have no tuple to read. Named rather
        # than skipped silently, so a component that *loses* its _FIELDS shows up here.
        assert component in _NO_FIELDS_TUPLE, (
            f"{component} has no _FIELDS tuple and is not a known exception — either give "
            f"it one, or add it to _NO_FIELDS_TUPLE with the reason"
        )
        pytest.skip(f"{component} declares no _FIELDS tuple")
    fields = re.findall(r'"(\w+)"', declared.group(1))
    section = re.search(
        rf"### `{component}` —(.*?)(?=\n### |\n## )", _doc("components.md"), re.S
    ).group(1)
    documented = {d.split("[")[0] for d in re.findall(r"^\| `([\w\[\]().]+)`", section, re.M)}
    assert not [f for f in fields if f not in documented], (
        f"{component}: undocumented fields {[f for f in fields if f not in documented]}"
    )


@pytest.mark.parametrize("component", sorted(_shipped()))
def test_every_item_key_is_documented(component):
    """The same gate one level down, for the keys inside a component's item mappings. Deliberately
    looser: an item key is asserted to be named *somewhere in the section* rather than pinned to a
    table cell, since components spell the same schema differently."""
    text = _shipped()[component]
    declared = re.search(r"^_(?:ITEM|SIDE)_FIELDS[^=]*= frozenset\(\{([^}]*)\}\)", text, re.M)
    if declared is None:
        pytest.skip(f"{component} declares no item mapping")
    keys = re.findall(r'"(\w+)"', declared.group(1))
    section = re.search(
        rf"### `{component}` —(.*?)(?=\n### |\n## )", _doc("components.md"), re.S
    ).group(1)
    named = set(re.findall(r"`([\w\[\]().…/]+)`", section))
    tails = {n.split(".")[-1].split("]")[-1].lstrip("…") for n in named} | named
    assert not [k for k in keys if k not in tails], (
        f"{component}: item keys named in code but not in docs/components.md: "
        f"{[k for k in keys if k not in tails]}"
    )


def test_the_chart_block_documents_every_key_it_accepts():
    """The table says "no other field is accepted", so it has to list them all. Read from the
    table's rows, not the prose, which names `legend` only to deny it."""
    from deckwright.charts.model import _CHART_KEYS

    block = re.search(r"### The block's own fields(.*?)###", _doc("authoring.md"), re.S).group(1)
    rows = "\n".join(re.findall(r"^\| `[^|]+\|.*$", block, re.M))
    assert _missing(_CHART_KEYS, rows, "`{}`") == []


def test_every_chart_kind_is_named_in_the_authoring_reference():
    from deckwright.charts.native import _CHART_TYPES

    assert _missing(_CHART_TYPES, _doc("authoring.md")) == []


def test_every_animate_value_is_in_the_authoring_reference():
    """`animate:` was the one author-facing vocabulary with no gate: a sixth value leaves
    `authoring.md`'s five-row table and `errors.md`'s hardcoded message both lying."""
    from deckwright.layouts.motion import _ANIMATIONS

    assert _missing(_ANIMATIONS, _doc("authoring.md")) == []


def test_the_documented_animate_error_lists_exactly_the_legal_values():
    """`errors.md` quotes the compiler's own message. Asserting the joined list, not each value —
    a bare substring check passes on 'none' appearing anywhere in English prose."""
    from deckwright.layouts.motion import _ANIMATIONS

    assert f"expected one of {', '.join(_ANIMATIONS)}" in _doc("errors.md")


def test_the_documented_unknown_field_error_lists_every_slide_field():
    from deckwright.spec.parse import _SLIDE_FIELDS

    assert f"known fields: {', '.join(_SLIDE_FIELDS)}" in _doc("errors.md")


def test_every_slide_field_is_documented_in_the_authoring_reference():
    from deckwright.spec.parse import _SLIDE_FIELDS

    assert _missing(_SLIDE_FIELDS, _doc("authoring.md")) == []


def test_every_transition_effect_is_in_the_theme_reference():
    """Every effect has its own direction vocabulary. A reader picking one the doc does not
    list gets a build error the doc cannot explain."""
    from deckwright.motion.transition import EFFECTS

    assert _missing(EFFECTS, _doc("theme.md")) == []


def test_every_transition_direction_is_in_the_theme_reference():
    """The per-element direction table is the point — a shared l/u/r/d list produces a
    schema-invalid file at `strips`."""
    from deckwright.motion.transition import EFFECTS

    directions = {d for dirs in EFFECTS.values() for d in dirs}
    assert _missing(directions, _doc("theme.md")) == []


def test_every_transition_speed_is_in_the_theme_reference():
    from deckwright.motion.transition import SPEEDS

    assert _missing(SPEEDS, _doc("theme.md")) == []


def test_every_motion_theme_key_is_documented():
    from deckwright.theme.blocks_motion import MOTION_KEYS, TRANSITION_KEYS

    assert _missing(MOTION_KEYS, _doc("theme.md")) == []
    assert _missing(TRANSITION_KEYS, _doc("theme.md")) == []


def test_every_theme_key_is_in_the_theme_files_own_table():
    from deckwright.theme.blocks import _KNOWN_KEYS

    assert _missing(_KNOWN_KEYS, _doc("theme.md"), "| `{}` |") == []


def test_every_palette_role_and_pair_is_documented():
    from deckwright.theme.defaults import DEFAULT_PAIRS, DEFAULT_ROLES

    theme = _doc("theme.md")
    assert _missing(DEFAULT_ROLES, theme) == []
    assert _missing(DEFAULT_PAIRS, theme) == []


def test_every_type_rung_is_documented():
    from deckwright.theme.defaults import DEFAULT_RAMP

    assert _missing(DEFAULT_RAMP, _doc("theme.md")) == []


def test_every_ramp_face_alias_is_documented():
    """The alias set is a vocabulary an author types; a name missing from the doc is a
    face that silently becomes a literal typeface no machine has."""
    from deckwright.theme.blocks import _FACE_ALIASES

    assert _missing(_FACE_ALIASES, _doc("theme.md"), "`face: {}`") == []


def test_every_legacy_glyph_name_is_listed():
    """These are the names spelled deckwright's way rather than Material's, so they are
    the ones an author cannot guess. A doc that drops one hides that it still works."""
    from tests.conftest import LEGACY_GLYPHS

    assert _missing(LEGACY_GLYPHS, _doc("icons.md")) == []


def test_every_curated_alias_is_in_the_glyph_catalogue():
    """An alias is a name invented for authors. One no doc names is one nobody reaches."""
    from deckwright.icons.aliases import ALIASES, OVERRIDES

    assert _missing(list(ALIASES) + list(OVERRIDES), _doc("glyphs.md")) == []


def test_every_glyph_the_catalogue_names_still_resolves():
    """A catalogue of dead names is worse than none, and re-vendoring is what kills one."""
    from deckwright.errors import SpecError
    from deckwright.icons.load import load

    seen, dead = [], []
    for cell in re.findall(r"^\|([^|]+)\|", _doc("glyphs.md"), re.M):
        for name in re.findall(r"`([a-z0-9_-]+)`", cell):
            seen.append(name)
            try:
                load(name)
            except SpecError:
                dead.append(name)
    assert len(seen) > 100, f"only {len(seen)} names matched — the table shape changed"
    assert dead == []


def test_every_chrome_field_and_key_is_documented():
    from deckwright.layouts.chrome import CHROME_ORDER, _CHROME_KEYS

    authoring = _doc("authoring.md")
    assert _missing(CHROME_ORDER, authoring) == []
    assert _missing(_CHROME_KEYS, authoring) == []


def test_every_at_form_is_documented():
    from deckwright.layouts.place import AT_KEYS

    assert _missing(AT_KEYS, _doc("placement.md")) == []


def test_every_table_cell_key_is_documented():
    from deckwright.components._tablespec import CELL_KEYS

    assert _missing(CELL_KEYS, _doc("components.md")) == []


def test_every_cli_command_has_a_section():
    cli = (pathlib.Path(__file__).resolve().parents[1] / "src/deckwright/cli.py").read_text()
    commands = re.findall(r"@app\.command\(\)\ndef (\w+)", cli)
    assert _missing(commands, _doc("cli.md"), "## `{}`") == []


def test_every_qa_check_is_named_in_the_qa_reference():
    """A check nobody can find is a check nobody reads a finding from, and `qa.md` is the only place
    a `check=` string is explained."""
    names = set()
    for path in (ROOT / "src/deckwright/qa").rglob("*.py"):
        names |= set(re.findall(r'check="([a-z][a-z-]*)"', path.read_text()))
    assert names, "no check names found at all — the Finding call shape changed"
    assert _missing(names, _doc("qa.md")) == []


def test_every_cli_flag_has_a_mention_in_the_cli_reference():
    """The command gate above passes a command whose flags are all undocumented — a
    reader then knows `qa` exists and not that `--fail-on` is how they gate CI on it."""
    cli = (ROOT / "src/deckwright/cli.py").read_text()
    flags = set(re.findall(r'"(--[a-z][a-z-]*)"', cli))
    assert flags, "no flags found at all — the declaration shape changed"
    assert _missing(flags, _doc("cli.md")) == []


def test_every_env_var_the_code_reads_is_documented():
    """A knob nobody can find is a knob nobody can turn."""
    src = pathlib.Path(__file__).resolve().parents[1] / "src/deckwright"
    used = set()
    for path in src.rglob("*.py"):
        used |= set(re.findall(r'"(DECKWRIGHT_\w+)"', path.read_text()))
    assert _missing(used, _doc("cli.md")) == []


def test_the_docs_index_lists_every_doc():
    """A partial index is worse than none: readers treat it as exhaustive."""
    listed = set(re.findall(r"\[`([\w-]+\.md)`\]", _doc("README.md")))
    actual = {p.name for p in DOCS.glob("*.md")} - {"README.md"}
    assert actual <= listed, f"unlisted: {sorted(actual - listed)}"


@pytest.mark.repo
def test_no_doc_names_a_file_or_module_that_is_gone():
    root = pathlib.Path(__file__).resolve().parents[1]
    # Gitignored by design — brand templates and the themes bound to them — so a
    # fresh clone correctly lacks them; `out/` is the same case, simply never scanned.
    absent_ok = ("templates/",)
    dangling = []
    for doc in DOCS.glob("*.md"):
        text = doc.read_text()
        for ref in re.findall(r"`((?:src/|tests/|bin/|examples/)[\w./-]+)`", text):
            if not ref.startswith(absent_ok) and not (root / ref).exists():
                dangling.append(f"{doc.name}: {ref}")
        for ref in re.findall(
            r"`((?:charts|icons|imagery|layouts|components|theme|qa"
            r"|spec|compile|conform|panels|services|utils)/[\w./-]+\.py)`",
            text,
        ):
            if not (root / "src/deckwright" / ref).exists():
                dangling.append(f"{doc.name}: {ref}")
    assert dangling == []


# A count in prose rots on a commit that touches nothing near it. Prose should not carry
# one at all; these are transcripts, where the number is the point, so they get a gate.
_QUOTED_EXERCISE_COUNT = {
    "docs/conform.md": r"\b\d+/(\d+) exercises\b",
}


def test_every_component_that_refuses_a_spec_has_a_row_in_the_error_reference():
    """Read off the prefix the code *emits*, never the filename or the bare name: `doccard.py` emits
    `(component 'document')`, and "ellipse" appears in `errors.md` only inside *other* components'
    known-components enumerations."""
    errors = _doc("errors.md")
    emitted = set()
    for path in (ROOT / "src/deckwright").rglob("*.py"):
        emitted |= set(re.findall(r"\(component '(\w+)'\)", path.read_text()))
    assert emitted, "no component prefixes found at all — the message shape changed"
    undocumented = sorted(c for c in emitted if f"(component '{c}')" not in errors)
    assert undocumented == [], f"refuses a spec with no row of its own: {undocumented}"


@pytest.mark.parametrize("relpath,pattern", sorted(_QUOTED_EXERCISE_COUNT.items()))
def test_the_exercise_count_the_docs_quote_is_the_real_one(relpath, pattern):
    from deckwright.conform.exercise import EXERCISE

    found = re.search(pattern, (ROOT / relpath).read_text())
    # Without this the gate goes vacuous the moment someone rewords the sentence —
    # a green check over a claim it can no longer find is worse than no check.
    assert found, f"{relpath}: the sentence this gate reads has been reworded"
    assert int(found.group(1)) == len(EXERCISE)


# --- the repo explains its own shape ----------------------------------------------

_IGNORED_DIRS = {"build", "node_modules"}


def _content_dirs() -> list[pathlib.Path]:
    """Every top-level directory a person or an agent lands in."""
    return sorted(
        p
        for p in ROOT.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name not in _IGNORED_DIRS
    )


@pytest.mark.repo
def test_every_top_level_directory_is_named_in_the_root_readme():
    """A directory nobody documented is one an agent guesses at."""
    readme = (ROOT / "README.md").read_text()
    absent = [p.name for p in _content_dirs() if f"{p.name}/" not in readme]
    assert absent == [], f"top-level directories the root README never mentions: {absent}"


@pytest.mark.repo
def test_every_directory_that_holds_content_says_what_belongs_in_it():
    """These are where a deck's parts get put, and putting one in the wrong place is the
    failure this guards — not a missing file for its own sake."""
    for name in ("authoring", "examples", "templates", "out"):
        assert (ROOT / name / "README.md").is_file(), f"{name}/ has no README"


# Counts stated in prose across the doc tree. Each maps a pattern to the code that
# answers it, so adding a component or a chart kind names every file to update instead
# of leaving twenty sentences quietly wrong.
_WORDS = {"seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40}
_UNITS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}


def _component_count() -> int:
    return len(_shipped())


def _chart_kind_count() -> int:
    from deckwright.charts.native import _CHART_TYPES

    return len(_CHART_TYPES)


def _glyph_count() -> int:
    from deckwright.icons.load import available

    return len(available())


def _exercise_count() -> int:
    from deckwright.conform.exercise import EXERCISE

    return len(EXERCISE)


_STATED_COUNTS = (
    (r"\b([\w,-]+) (?:native )?chart kinds?\b", _chart_kind_count),
    (r"\b([\w,-]+) (?:slide )?components?\b", _component_count),
    (r"\b([\w,-]+) (?:vendored )?(?:Material Symbols|glyphs)\b", _glyph_count),
    (r"\b([\w,-]+) exercises?\b", _exercise_count),
)


def _as_number(token: str) -> int | None:
    """The integer a prose token states, or None when it is not stating one.

    A tilde-prefixed form is deliberately not a claim about the exact count and is
    left alone — that is the drift-proof way to write these.
    """
    token = token.strip().lower()
    if token in _WORDS:
        return _WORDS[token]
    tens, _, unit = token.partition("-")
    if unit and tens in _TENS and unit in _UNITS:
        return _TENS[tens] + _UNITS[unit]
    try:
        return int(token.replace(",", ""))
    except ValueError:
        return None


_MARKDOWN = sorted(
    [ROOT / "README.md", ROOT / "CLAUDE.md", ROOT / "CONTRIBUTING.md", ROOT / "CHANGELOG.md"]
    + list(DOCS.glob("*.md"))
)


@pytest.mark.parametrize("path", _MARKDOWN, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_every_count_the_docs_state_is_the_real_one(path):
    if not path.is_file():
        pytest.skip(f"{path.name} is not in an sdist — it is repository documentation")
    text = path.read_text()
    wrong = []
    for pattern, actual in _STATED_COUNTS:
        for match in re.finditer(pattern, text, re.I):
            token = match.group(1)
            # A tilde marks an approximation, which claims nothing exact.
            if text[max(0, match.start() - 1) : match.start()] == "~":
                continue
            stated = _as_number(token)
            if stated is not None and stated != actual():
                wrong.append(f"{match.group(0)!r} — the code says {actual()}")
    assert wrong == [], (
        f"{path.relative_to(ROOT)} states a count that has drifted:\n  " + "\n  ".join(wrong)
    )
