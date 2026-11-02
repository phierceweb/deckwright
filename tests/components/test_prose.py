import pytest

import deckwright.components  # noqa: F401 — registers the built-ins
from deckwright.errors import LayoutError
from deckwright.layouts.components import get_component


def _ctx(ctx_factory, **body):
    return ctx_factory({"title": "T", "prose": body})


@pytest.mark.parametrize("bad", [None, [], "just a string", [""], [3]])
def test_paragraphs_must_be_a_non_empty_list_of_strings(bad, ctx_factory):
    ctx = _ctx(ctx_factory, paragraphs=bad)
    with pytest.raises(LayoutError, match="non-empty list of strings"):
        get_component("prose")(ctx)


def test_too_much_copy_for_the_rect_is_refused(ctx_factory):
    ctx = _ctx(ctx_factory, paragraphs=["Words to wrap at the capped measure. " * 40] * 6)
    with pytest.raises(LayoutError, match="split the slide or shorten the copy"):
        get_component("prose")(ctx)


def test_the_frame_is_capped_at_the_measure_not_the_placement(ctx_factory):
    ctx = _ctx(ctx_factory, paragraphs=["A short paragraph."])
    get_component("prose")(ctx)
    frame = ctx.slide.shapes[0]
    assert frame.width / 914400 < ctx.body_rect.width - 1.0


def test_a_cite_adds_an_attribution_line_and_sets_the_copy_italic(ctx_factory):
    ctx = _ctx(ctx_factory, paragraphs=["Quoted words."], cite="A. Speaker")
    get_component("prose")(ctx)
    tf = ctx.slide.shapes[0].text_frame
    assert tf.paragraphs[-1].runs[0].text == "— A. Speaker"
    assert tf.paragraphs[0].runs[0].font.italic is True


def test_without_a_cite_the_copy_is_upright(ctx_factory):
    ctx = _ctx(ctx_factory, paragraphs=["Plain words."])
    get_component("prose")(ctx)
    run = ctx.slide.shapes[0].text_frame.paragraphs[0].runs[0]
    assert not run.font.italic


def test_a_prose_refusal_on_an_unmeasured_face_says_the_estimate_errs_wide(ctx_factory, theme):
    import dataclasses

    unmeasured = dataclasses.replace(theme, face="Segoe UI", heading_face="Segoe UI")
    ctx = ctx_factory(
        {"title": "T", "prose": {"paragraphs": ["Words to wrap at the capped measure. " * 40] * 6}},
        theme_override=unmeasured,
    )
    with pytest.raises(LayoutError, match=r"'Segoe UI' has no width table"):
        get_component("prose")(ctx)
