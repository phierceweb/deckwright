"""Every component refuses a field it does not read. `tests/test_docs.py` reads these same
`_FIELDS` tuples, so a declared-but-unenforced tuple reads as documented and validated."""

from __future__ import annotations

import pathlib
import re

import pytest

import deckwright.components  # noqa: F401 — registers the built-ins
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component

COMPONENTS = pathlib.Path(__file__).resolve().parents[2] / "src/deckwright/components"

# Minimal valid bodies for the components a bare ctx can drive. `card`, `connector`,
# `document`, `icon`, `image` and `table` need a file, a sibling placement or a real glyph.
BODIES = {
    "bullets": {"items": ["alpha", "beta"]},
    "callouts": {"items": [{"head": "H", "body": "B"}, {"head": "H2", "body": "B2"}]},
    "nav": {"items": ["One", "Two"], "active": "Two"},
    "panel": {},
    "stats": {"items": [{"value": "20", "label": "x"}]},
}


def test_every_component_declaring_fields_also_enforces_them():
    """Catches the next component to add `_FIELDS` for the docs gate's benefit and skip the
    call that enforces it."""
    offenders = [
        path.name
        for path in sorted(COMPONENTS.glob("*.py"))
        if re.search(r"^_FIELDS\s*=", path.read_text(), re.M)
        and "known_fields(ctx, _FIELDS)" not in path.read_text()
    ]
    assert offenders == [], f"declare _FIELDS but never enforce it: {offenders}"


@pytest.mark.parametrize("name", sorted(BODIES))
def test_an_unknown_field_is_refused(ctx_factory, name):
    ctx = ctx_factory({name: {**BODIES[name], "colums": 2}})
    with pytest.raises(LayoutError, match=r"unknown field 'colums'"):
        get_component(name)(ctx)


@pytest.mark.parametrize("name", sorted(BODIES))
def test_the_known_fields_are_still_accepted(ctx_factory, name):
    """The refusal above is worthless if it also rejects the real thing."""
    get_component(name)(ctx_factory({name: BODIES[name]}))


# The same check one level down, inside an item. YAML is what makes silence expensive:
# `label: a, b` is two keys, not one value, so an unquoted comma still builds clean.
ITEM_BODIES = {
    "callouts": ("items", {"head": "H", "body": "B"}),
    "stats": ("items", {"value": "20", "label": "x"}),
}


def test_every_component_declaring_item_fields_also_enforces_them():
    """Either the shared helper or the older inline set-difference counts as enforcing."""
    offenders = []
    for path in sorted(COMPONENTS.glob("*.py")):
        source = path.read_text()
        if not re.search(r"^_ITEM_FIELDS\s*=", source, re.M):
            continue
        if "known_item_fields(" not in source and "- _ITEM_FIELDS" not in source:
            offenders.append(path.name)
    assert offenders == [], f"declare _ITEM_FIELDS but never enforce it: {offenders}"


@pytest.mark.parametrize("name", sorted(ITEM_BODIES))
def test_an_unknown_key_inside_an_item_is_refused(ctx_factory, name):
    field, item = ITEM_BODIES[name]
    ctx = ctx_factory({name: {field: [{**item, "and the rest": "x"}]}})
    with pytest.raises(LayoutError, match=r"has the unknown field 'and the rest'"):
        get_component(name)(ctx)


@pytest.mark.parametrize("name", sorted(ITEM_BODIES))
def test_the_known_item_keys_are_still_accepted(ctx_factory, name):
    field, item = ITEM_BODIES[name]
    get_component(name)(ctx_factory({name: {field: [item]}}))


# --- the split-value cause, said where the message is read -------------------------

_PROSE = "unquoted comma"


def test_a_prose_key_on_a_component_names_the_split(ctx_factory):
    """`{show: columns, caption: a, b}` — YAML already split it, so `b` is the tail of a
    truncated value and not a field anybody typed."""
    ctx = ctx_factory({"title": "T", "grid": {"show": "columns", "and the rest": 1}})
    with pytest.raises(LayoutError, match=_PROSE):
        get_component("grid")(ctx)


def test_a_prose_key_inside_an_item_names_the_split(ctx_factory):
    ctx = ctx_factory(
        {"title": "T", "stats": {"items": [{"value": "1", "label": "kept", "and the rest": 1}]}}
    )
    with pytest.raises(LayoutError, match=_PROSE):
        get_component("stats")(ctx)


def test_a_flow_step_says_it_too(ctx_factory):
    """`flow` validates its steps inline rather than through the shared helper, so it is
    the one that silently diverges."""
    ctx = ctx_factory(
        {
            "title": "T",
            "flow": {
                "items": [{"head": "One", "body": "kept", "and the rest": 1}, {"head": "Two"}]
            },
        }
    )
    with pytest.raises(LayoutError, match=_PROSE):
        get_component("flow")(ctx)


def test_a_chart_row_says_it_too(ctx_factory):
    from deckwright.charts.model import ChartSpec

    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match=_PROSE):
        ChartSpec.from_body(
            ctx,
            {
                "kind": "column",
                "data": [{"category": "Power tools", "hand and bench": None, "value": 3}],
            },
        )


@pytest.mark.parametrize(
    "component,body",
    [
        ("grid", {"show": "columns", "colour": 1}),
        ("stats", {"items": [{"value": "1", "label": "kept", "colour": 1}]}),
    ],
)
def test_an_ordinary_misspelling_gets_no_such_hint(component, body, ctx_factory):
    """The tell is the space. A typo is a typo, and saying 'unquoted comma' at it would
    send the reader looking for a comma that is not there."""
    ctx = ctx_factory({"title": "T", component: body})
    with pytest.raises(LayoutError) as excinfo:
        get_component(component)(ctx)
    assert _PROSE not in str(excinfo.value)


def test_a_prose_key_never_gets_a_did_you_mean(ctx_factory):
    """The suggestion and the cause are mutually exclusive: a key holding a comma's tail
    has no nearest spelling, and offering one sends the reader hunting for a typo."""
    from deckwright.utils.keys import unknown_field

    message = unknown_field("and the rest", ("cols", "rows", "box"), suggest=True)
    assert "did you mean" not in message
    assert _PROSE in message


def test_a_near_miss_still_gets_a_did_you_mean():
    from deckwright.utils.keys import unknown_field

    message = unknown_field("col", ("cols", "rows", "box"), suggest=True)
    assert "did you mean 'cols'?" in message
    assert _PROSE not in message
