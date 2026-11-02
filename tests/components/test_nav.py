"""`nav`'s colour policy, and what a successful build never reaches. The fixture accent reads
2.58:1 on white, under the 4.5:1 its 13pt caption type demands — every colour literal below
is that arithmetic written out."""

from __future__ import annotations

import pytest

import deckwright.components  # noqa: F401 — registers the built-ins
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component

ITEMS = ["Problem", "Evidence", "What shipped"]
ACTIVE = "Evidence"


def _ctx(ctx_factory, **body):
    return ctx_factory({"nav": {"items": ITEMS, "active": ACTIVE, **body}})


def _runs(ctx) -> dict[str, object]:
    """The drawn run behind each label."""
    runs = {}
    for shape in ctx.slide.shapes:
        para = shape.text_frame.paragraphs[0]
        runs[para.runs[0].text] = para.runs[0]
    return runs


def test_a_colour_the_author_named_is_used_as_asked(ctx_factory):
    """An accent under AA still marks the section when asked for. Route the named role through
    `ctx.accent()` instead and this returns the give-way ink below."""
    ctx = _ctx(ctx_factory, color="accent-1")
    get_component("nav")(ctx)
    assert str(_runs(ctx)[ACTIVE].font.color.rgb) == "27B94C"


def test_the_default_gives_way_to_ink_the_reader_can_read(ctx_factory):
    """No author named it, so the accent has to earn its place and here it cannot."""
    ctx = _ctx(ctx_factory)
    get_component("nav")(ctx)
    assert str(_runs(ctx)[ACTIVE].font.color.rgb) == "2D0937"


def test_a_colour_too_close_to_the_paper_is_refused(ctx_factory):
    """`line` is EDEDED — 1.17:1 on white. Honouring the author stops short of invisible."""
    with pytest.raises(LayoutError, match=r"cannot be seen"):
        get_component("nav")(_ctx(ctx_factory, color="line"))


def test_the_active_label_is_also_larger_and_bolder(ctx_factory):
    """Colour is never the only thing marking it — drop `_ACTIVE_SCALE` to 1.0 or the `bold=on`
    and the default-coloured eyebrow marks its active section with nothing at all."""
    ctx = _ctx(ctx_factory)
    get_component("nav")(ctx)
    runs = _runs(ctx)
    assert runs[ACTIVE].font.bold is True
    assert runs["Problem"].font.bold is not True
    assert runs[ACTIVE].font.size > runs["Problem"].font.size


def test_the_manifest_records_the_ink_actually_drawn(ctx_factory):
    """`contrast` reads the manifest, so recording ink we did not use lies to it: inactive
    labels are drawn in `dim()`, not the pair's brighter foreground."""
    ctx = _ctx(ctx_factory)
    get_component("nav")(ctx)
    inactive = [r for r in ctx.manifest.slides[0].shapes if r.lines == ["Problem"]]
    assert len(inactive) == 1
    assert inactive[0].fg == "573C65"


def test_the_eyebrow_draws_no_reveal_group(ctx_factory):
    """Chrome does not cost a click. A group here spends the slide's first beat on it."""
    ctx = _ctx(ctx_factory)
    result = get_component("nav")(ctx)
    assert len(ctx.slide.shapes) == len(ITEMS), "nothing was drawn, so this proves nothing"
    assert result.groups == []


def test_an_active_section_that_is_not_among_the_items_is_refused(ctx_factory):
    """Silently marking nothing is the failure — a renamed section reads as no section."""
    with pytest.raises(LayoutError, match=r"active 'Evidenec' is not one of the items"):
        get_component("nav")(ctx_factory({"nav": {"items": ITEMS, "active": "Evidenec"}}))


def test_no_active_section_is_allowed(ctx_factory):
    """A title or closing slide is in no section; every label draws dim."""
    ctx = ctx_factory({"nav": {"items": ITEMS}})
    get_component("nav")(ctx)
    assert {str(r.font.color.rgb) for r in _runs(ctx).values()} == {"573C65"}


@pytest.mark.parametrize("items", [[], "Problem"])
def test_items_must_be_a_non_empty_list(ctx_factory, items):
    with pytest.raises(LayoutError, match=r"'items' must be a non-empty list"):
        get_component("nav")(ctx_factory({"nav": {"items": items}}))


def test_a_nav_with_no_items_takes_the_decks_sections_and_marks_the_slides_own(ctx_factory):
    """Repeated by hand on every slide, `items:` goes stale at the first rename."""
    ctx = ctx_factory({"nav": {}}, section="Two", sections=("One", "Two", "Three"))
    get_component("nav")(ctx)
    runs = _runs(ctx)
    assert list(runs) == ["One", "Two", "Three"]
    assert runs["Two"].font.bold is True
    assert runs["One"].font.bold is not True


def test_a_defaulted_nav_on_a_slide_with_no_section_marks_nothing(ctx_factory):
    ctx = ctx_factory({"nav": {}}, section=None, sections=("One", "Two"))
    get_component("nav")(ctx)
    assert not any(run.font.bold for run in _runs(ctx).values())


def test_labels_that_do_not_name_the_slides_section_mark_nothing(ctx_factory):
    """Short labels for long section names are not a misspelled `active:`."""
    ctx = ctx_factory(
        {"nav": {"items": ["Why", "How"]}}, section="Why it matters", sections=("Why it matters",)
    )
    get_component("nav")(ctx)
    assert not any(run.font.bold for run in _runs(ctx).values())


def test_explicit_items_naming_the_slides_section_mark_it(ctx_factory):
    ctx = ctx_factory({"nav": {"items": ["One", "Two"]}}, section="Two")
    get_component("nav")(ctx)
    assert [label for label, run in _runs(ctx).items() if run.font.bold] == ["Two"]


def test_a_nav_with_no_items_in_a_deck_with_no_sections_is_refused(ctx_factory):
    ctx = ctx_factory({"nav": {}}, sections=())
    with pytest.raises(LayoutError, match=r"no 'items' and the deck declares no 'sections:'"):
        get_component("nav")(ctx)
