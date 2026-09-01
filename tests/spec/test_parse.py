import textwrap

import pytest

from deckwright.errors import SpecError
from deckwright.spec import parse_deck, parse_deck_text
from deckwright.spec.model import Background

MINIMAL = """
    theme: base
    title: Demo
    sections: [One, Two]
    out: out/Demo.pptx
    ---
    kicker: Q3 RESULTS
    title: Revenue up 40 percent
    subtitle: A subtitle
    background: inverse
    ---
    section: One
    title: First
    notes: Speaker notes here.
    animate: one_at_a_time
    place:
      - at: {cols: left-half}
        bullets: {items: [a, b]}
"""


def _parse(text, tmp_path):
    return parse_deck_text(textwrap.dedent(text), source=tmp_path / "d.deck.yaml")


def test_deck_config_is_read_from_the_first_document(tmp_path):
    deck = _parse(MINIMAL, tmp_path)
    assert deck.theme == "base"
    assert deck.title == "Demo"
    assert deck.sections == ("One", "Two")


def test_each_later_document_is_a_slide(tmp_path):
    assert len(_parse(MINIMAL, tmp_path).slides) == 2


def test_slides_are_indexed_from_one(tmp_path):
    assert [s.index for s in _parse(MINIMAL, tmp_path).slides] == [1, 2]


def test_chrome_fields_land_on_the_slide(tmp_path):
    slide = _parse(MINIMAL, tmp_path).slides[0]
    assert slide.kicker == "Q3 RESULTS"
    assert slide.title == "Revenue up 40 percent"
    assert slide.subtitle == "A subtitle"


def test_a_named_background_is_read(tmp_path):
    assert _parse(MINIMAL, tmp_path).slides[0].background == Background(kind="inverse")


def test_background_defaults_to_the_page(tmp_path):
    assert _parse(MINIMAL, tmp_path).slides[1].background == Background(kind="page")


def test_an_image_background_keeps_its_path(tmp_path):
    slide = _parse("theme: t\n---\nbackground: {image: cover.png}\n", tmp_path).slides[0]
    assert slide.background == Background(kind="image", image="cover.png")


def test_a_background_that_is_neither_a_name_nor_an_image_is_rejected(tmp_path):
    """A name is checked against the theme's own pairs at build; a list is never one."""
    with pytest.raises(SpecError, match=r"slide 1: 'background' must name a colour pair"):
        _parse("theme: t\n---\nbackground: [dark]\n", tmp_path)


def test_a_background_naming_an_undeclared_pair_fails_against_the_palette(tmp_path):
    from deckwright.errors import ThemeError
    from deckwright.theme.defaults import DEFAULT_PALETTE

    spec = _parse("theme: t\n---\nbackground: dark\n", tmp_path)
    with pytest.raises(ThemeError, match=r"no colour pair 'dark'; declared pairs:"):
        DEFAULT_PALETTE.pair(spec.slides[0].background.pair)


def test_an_image_background_with_extra_keys_is_rejected(tmp_path):
    with pytest.raises(
        SpecError,
        match=r"background has no key 'tint'; "
        r"known keys: image, fit, crop, scrim",
    ):
        _parse("theme: t\n---\nbackground: {image: a.png, tint: 20}\n", tmp_path)


def test_the_remaining_slide_fields_are_read(tmp_path):
    slide = _parse(MINIMAL, tmp_path).slides[1]
    assert slide.section == "One"
    assert slide.notes == "Speaker notes here."
    assert slide.animate == "one_at_a_time"


def test_out_path_resolves_relative_to_the_spec_file(tmp_path):
    assert _parse(MINIMAL, tmp_path).out == (tmp_path / "out/Demo.pptx")


def test_a_layout_field_names_its_replacement(tmp_path):
    with pytest.raises(SpecError, match=r"slide 1: 'layout' is gone.*'place:'"):
        _parse("theme: t\n---\nlayout: content\ntitle: T\n", tmp_path)


def test_a_body_field_names_its_replacement(tmp_path):
    with pytest.raises(SpecError, match=r"slide 1: 'body' is gone.*'place:'"):
        _parse("theme: t\n---\nbody: {type: bullets}\n", tmp_path)


def test_a_reveal_field_names_animate_as_the_replacement(tmp_path):
    with pytest.raises(SpecError, match=r"slide 1: 'reveal' is gone.*'animate'"):
        _parse("theme: t\n---\nreveal: per-item\n", tmp_path)


def test_an_unknown_slide_field_lists_what_is_accepted(tmp_path):
    with pytest.raises(
        SpecError,
        match=r"slide 1: unknown field 'colour'; known fields: "
        r"title, kicker, subtitle, notes, section, animate, "
        r"transition, background, place",
    ):
        _parse("theme: t\n---\ncolour: blue\n", tmp_path)


def test_a_misspelled_slide_field_suggests_the_closest_match(tmp_path):
    with pytest.raises(SpecError, match=r"slide 1: unknown field 'titel'; did you mean 'title'\?"):
        _parse("theme: t\n---\ntitel: Oops\n", tmp_path)


def test_a_misspelled_place_suggests_the_closest_match(tmp_path):
    with pytest.raises(SpecError, match=r"slide 1: unknown field 'plce'; did you mean 'place'\?"):
        _parse("theme: t\n---\nplce: []\n", tmp_path)


def test_the_offending_slide_is_numbered(tmp_path):
    with pytest.raises(SpecError, match=r"slide 2: unknown field 'titel'"):
        _parse("theme: t\n---\ntitle: ok\n---\ntitel: Oops\n", tmp_path)


def test_unknown_section_reference_is_rejected(tmp_path):
    text = "theme: t\nsections: [One]\n---\nsection: Nope\n"
    with pytest.raises(SpecError, match=r"slide 1: section 'Nope' is not in the deck's sections"):
        _parse(text, tmp_path)


def test_a_deck_without_sections_accepts_any_section_value(tmp_path):
    assert _parse("theme: t\n---\nsection: Anything\n", tmp_path).slides[0].section == "Anything"


def test_deck_with_no_slides_is_rejected(tmp_path):
    with pytest.raises(SpecError, match="no slides"):
        _parse("theme: t\n", tmp_path)


def test_missing_theme_is_rejected(tmp_path):
    with pytest.raises(SpecError, match="deck config: missing required field 'theme'"):
        _parse("title: x\n---\ntitle: T\n", tmp_path)


def test_non_mapping_slide_document_is_rejected(tmp_path):
    with pytest.raises(SpecError, match=r"slide 1: expected a mapping"):
        _parse("theme: t\n---\n- just\n- a list\n", tmp_path)


def test_malformed_yaml_is_rejected_as_a_spec_error(tmp_path):
    with pytest.raises(SpecError, match="invalid YAML"):
        _parse("theme: t\n---\ntitle: [unclosed\n", tmp_path)


def test_animate_defaults_to_none(tmp_path):
    assert _parse("theme: t\n---\ntitle: T\n", tmp_path).slides[0].animate is None


def test_parse_deck_reads_from_disk(tmp_path):
    path = tmp_path / "d.deck.yaml"
    path.write_text(textwrap.dedent(MINIMAL))
    assert len(parse_deck(path).slides) == 2


def test_missing_spec_file_is_rejected(tmp_path):
    with pytest.raises(SpecError, match="spec file not found"):
        parse_deck(tmp_path / "absent.deck.yaml")


def test_sections_as_a_bare_string_is_rejected(tmp_path):
    with pytest.raises(SpecError, match=r"'sections' must be a list, got str"):
        _parse("theme: t\nsections: One\n---\ntitle: T\n", tmp_path)


def test_sections_as_a_mapping_is_rejected(tmp_path):
    with pytest.raises(SpecError, match=r"'sections' must be a list, got dict"):
        _parse("theme: t\nsections: {a: b}\n---\ntitle: T\n", tmp_path)


def test_empty_mapping_sections_is_rejected(tmp_path):
    with pytest.raises(SpecError, match=r"'sections' must be a list, got dict"):
        _parse("theme: t\nsections: {}\n---\ntitle: T\n", tmp_path)


def test_empty_string_sections_is_rejected(tmp_path):
    with pytest.raises(SpecError, match=r"'sections' must be a list, got str"):
        _parse('theme: t\nsections: ""\n---\ntitle: T\n', tmp_path)


def test_an_empty_section_list_is_allowed(tmp_path):
    assert _parse("theme: t\nsections: []\n---\ntitle: T\n", tmp_path).sections == ()


def test_null_sections_is_allowed(tmp_path):
    assert _parse("theme: t\nsections:\n---\ntitle: T\n", tmp_path).sections == ()


def test_non_mapping_deck_config_is_rejected(tmp_path):
    with pytest.raises(SpecError, match=r"deck config: expected a mapping"):
        _parse("- a\n- b\n---\ntitle: T\n", tmp_path)


def test_unknown_deck_config_field_is_rejected(tmp_path):
    with pytest.raises(
        SpecError,
        match=r"deck config: unknown field 'colour'; known fields: "
        r"theme, title, sections, extends, out",
    ):
        _parse("theme: t\ncolour: blue\n---\ntitle: T\n", tmp_path)


def test_unknown_deck_config_field_suggests_a_near_miss(tmp_path):
    with pytest.raises(
        SpecError, match=r"deck config: unknown field 'tile'; did you mean 'title'\?"
    ):
        _parse("theme: t\ntile: Oops\n---\ntitle: T\n", tmp_path)


def test_a_section_that_resumes_after_another_began_is_rejected(tmp_path):
    """`sections:` is the source of truth for chapter order, and membership was checked
    while ordering was not — so a reorder that scattered one chapter built clean, and a
    theme drawing no section rail showed nothing."""
    text = (
        "theme: t\nsections: [Alpha, Beta]\n"
        "---\nsection: Alpha\n---\nsection: Beta\n---\nsection: Alpha\n"
    )
    with pytest.raises(SpecError, match=r"slide 3 resumes section 'Alpha', which ended at slide 1"):
        _parse(text, tmp_path)


def test_sections_in_declared_order_are_accepted(tmp_path):
    text = (
        "theme: t\nsections: [Alpha, Beta]\n"
        "---\nsection: Alpha\n---\nsection: Alpha\n---\nsection: Beta\n"
    )
    assert [s.section for s in _parse(text, tmp_path).slides] == ["Alpha", "Alpha", "Beta"]


def test_an_unsectioned_slide_does_not_break_the_run_around_it(tmp_path):
    """A divider carries no section of its own and sits in whatever run it falls in."""
    text = (
        "theme: t\nsections: [Alpha, Beta]\n"
        "---\nsection: Alpha\n---\ntitle: Divider\n---\nsection: Alpha\n---\nsection: Beta\n"
    )
    assert [s.section for s in _parse(text, tmp_path).slides][-1] == "Beta"


def test_a_section_may_be_declared_and_never_used(tmp_path):
    text = "theme: t\nsections: [Alpha, Beta]\n---\nsection: Alpha\n"
    assert _parse(text, tmp_path).sections == ("Alpha", "Beta")
