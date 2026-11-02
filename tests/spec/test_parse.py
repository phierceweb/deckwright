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
    """A reorder that scatters one chapter must not build, since a theme drawing no section
    rail would show nothing wrong."""
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


_NUMBERS = """
    theme: base
    out: out/N.pptx
    ---
    title: T
    place:
      - at: {cols: full}
        table: {rows: [[Alpha, 1.10, 2.50, 007]]}
      - at: {cols: full}
        image: {src: p.png, crop: 16:9}
"""


def test_a_number_prints_as_it_was_written(tmp_path):
    """YAML reads `1.10` as 1.1; a version column has to print the version written."""
    slide = _parse(_NUMBERS, tmp_path).slides[0]
    cells = slide.place[0].body["rows"][0]
    assert [str(c) for c in cells] == ["Alpha", "1.10", "2.50", "007"]


def test_a_number_written_with_a_source_still_behaves_as_a_number(tmp_path):
    slide = _parse(_NUMBERS, tmp_path).slides[0]
    version = slide.place[0].body["rows"][0][1]
    assert version == 1.1
    assert float(version) + 1 == 2.1


def test_an_unquoted_aspect_is_the_aspect_it_was_written_as(tmp_path):
    """YAML 1.1 reads `16:9` as a base-60 number, which as an aspect draws nothing."""
    from deckwright.imagery.fit import parse_aspect

    crop = _parse(_NUMBERS, tmp_path).slides[0].place[1].body["crop"]
    assert parse_aspect(crop, where="x") == pytest.approx(16 / 9)


def test_a_copied_number_keeps_how_it_was_written(tmp_path):
    import copy

    cells = _parse(_NUMBERS, tmp_path).slides[0].place[0].body["rows"][0]
    assert str(copy.deepcopy(cells)[1]) == "1.10"


@pytest.mark.parametrize("written", ["007", "0x1F", "0b101", "1:30", "-010", "1:30.5"])
def test_a_number_yaml_reads_in_another_base_is_the_text_written(tmp_path, written):
    """YAML 1.1 reads `010` as 8: kept a number, a cell would print 010 and a chart plot 8."""
    text = f"theme: base\n---\ntitle: T\nplace:\n  - at: {{cols: full}}\n    table: {{rows: [[{written}]]}}\n"
    cell = _parse(text, tmp_path).slides[0].place[0].body["rows"][0][0]
    assert type(cell) is str and cell == written


def test_a_parsed_number_dumps_back_as_it_was_written(tmp_path):
    """`safe_dump` refuses an int or float subclass it has no representer for."""
    import yaml

    from deckwright.spec._scalars import SpecLoader

    cells = _parse(_NUMBERS, tmp_path).slides[0].place[0].body["rows"][0]
    dumped = yaml.safe_dump(cells)
    assert dumped == "- Alpha\n- 1.10\n- 2.50\n- '007'\n"
    assert [str(c) for c in yaml.load(dumped, Loader=SpecLoader)] == [
        "Alpha",
        "1.10",
        "2.50",
        "007",
    ]


def _cell(written, tmp_path):
    text = f"theme: base\n---\ntitle: T\nplace:\n  - at: {{cols: full}}\n    table: {{rows: [[{written}]]}}\n"
    return _parse(text, tmp_path).slides[0].place[0].body["rows"][0][0]


_WORDS = [("yes", True), ("no", False), ("on", True), ("off", False)]
_WORDS += [("Yes", True), ("NO", False), ("On", True), ("OFF", False)]


@pytest.mark.parametrize(("written", "truth"), _WORDS)
def test_a_yaml_boolean_word_is_the_text_written(tmp_path, written, truth):
    """YAML 1.1 reads `yes` as True, and a cell would print it that way."""
    assert str(_cell(written, tmp_path)) == written


@pytest.mark.parametrize(("written", "truth"), _WORDS)
def test_a_yaml_boolean_word_keeps_the_truth_yaml_reads_in_it(tmp_path, written, truth):
    """So a field read by truthiness, such as an extension component's own flag, still works."""
    assert bool(_cell(written, tmp_path)) is truth


@pytest.mark.parametrize(("written", "value"), [("true", True), ("False", False), ("TRUE", True)])
def test_true_and_false_stay_booleans(tmp_path, written, value):
    assert _cell(written, tmp_path) is value


def test_a_key_spelled_as_a_boolean_word_is_that_text(tmp_path):
    """A series named `yes` is a name, and beside an unknown key it must still sort."""
    text = (
        "theme: base\n---\ntitle: T\nplace:\n  - at: {cols: full}\n"
        "    chart: {kind: column, data: [{category: A, values: {yes: 1, off: 2}}]}\n"
    )
    row = _parse(text, tmp_path).slides[0].place[0].body["data"][0]
    assert [str(k) for k in row["values"]] == ["yes", "off"]
    with pytest.raises(SpecError, match=r"slide 1: unknown field 'on'"):
        _parse("theme: base\n---\ntitle: T\non: 1\nzz: 2\n", tmp_path)


def test_a_boolean_word_dumps_back_as_it_was_written(tmp_path):
    import yaml

    from deckwright.spec._scalars import SpecLoader

    cells = [_cell("Yes", tmp_path), _cell("off", tmp_path)]
    dumped = yaml.safe_dump(cells)
    assert dumped == "- Yes\n- off\n"
    assert [(str(c), bool(c)) for c in yaml.load(dumped, Loader=SpecLoader)] == [
        ("Yes", True),
        ("off", False),
    ]


def test_a_copied_boolean_word_keeps_its_text_and_truth(tmp_path):
    import copy
    import pickle

    for clone in (
        copy.deepcopy(_cell("off", tmp_path)),
        pickle.loads(pickle.dumps(_cell("off", tmp_path))),
    ):
        assert (str(clone), bool(clone)) == ("off", False)


def test_an_image_background_takes_a_scrim_written_yes(tmp_path):
    slide = _parse("theme: t\n---\nbackground: {image: a.png, scrim: yes}\n", tmp_path).slides[0]
    assert slide.background.scrim is not None and slide.background.scrim.pair == "inverse"


def test_a_bool_tag_on_a_word_that_is_no_boolean_is_invalid_yaml(tmp_path):
    with pytest.raises(SpecError, match=r"invalid YAML — .*'maybe' is not a boolean"):
        _cell("!!bool maybe", tmp_path)


def test_chapters_run_out_of_their_declared_order_are_rejected_naming_both(tmp_path):
    """Contiguous runs can still contradict `sections:`, and a `nav` drawn from it would lie."""
    text = (
        "theme: t\nsections: [Alpha, Beta, Gamma]\n"
        "---\nsection: Beta\n---\nsection: Alpha\n---\nsection: Gamma\n"
    )
    with pytest.raises(
        SpecError,
        match=r"slide 2 begins section 'Alpha' after 'Beta', but 'sections:' lists Alpha, Beta, Gamma",
    ):
        _parse(text, tmp_path)


def test_a_declared_section_with_no_slides_can_be_skipped(tmp_path):
    text = "theme: t\nsections: [Alpha, Beta, Gamma]\n---\nsection: Alpha\n---\nsection: Gamma\n"
    assert [s.section for s in _parse(text, tmp_path).slides] == ["Alpha", "Gamma"]


def _deck(*slides: str) -> str:
    return "theme: base\nout: out/D.pptx\n" + "".join(f"---\n{s}\n" for s in slides)


_CARD_TO = "place:\n  - at: {{cols: full}}\n    goto: {}\n    card: {{heading: Go}}"


def test_a_slide_id_and_a_goto_naming_it_parse(tmp_path):
    deck = parse_deck_text(
        _deck("title: A\n" + _CARD_TO.format("appendix"), "id: appendix\ntitle: B"),
        source=tmp_path / "d.deck.yaml",
    )
    assert deck.slides[1].id == "appendix"
    assert deck.slides[0].place[0].goto == "appendix"


@pytest.mark.parametrize("jump", ["first", "previous", "next", "last"])
def test_a_relative_jump_needs_no_slide_id(tmp_path, jump):
    deck = parse_deck_text(
        _deck("title: A\n" + _CARD_TO.format(jump)), source=tmp_path / "d.deck.yaml"
    )
    assert deck.slides[0].place[0].goto == jump


def test_a_goto_naming_no_slide_lists_the_ids_there_are(tmp_path):
    text = _deck("id: intro\ntitle: A\n" + _CARD_TO.format("apendix"), "id: appendix\ntitle: B")
    with pytest.raises(
        SpecError, match=r"'goto: apendix' names no slide\. Slide ids in this deck: appendix, intro"
    ):
        parse_deck_text(text, source=tmp_path / "d.deck.yaml")


def test_a_goto_in_a_deck_with_no_slide_ids_says_to_give_one(tmp_path):
    with pytest.raises(SpecError, match="none — give the target slide an 'id:'"):
        parse_deck_text(
            _deck("title: A\n" + _CARD_TO.format("appendix")), source=tmp_path / "d.deck.yaml"
        )


def test_a_goto_to_its_own_slide_is_refused(tmp_path):
    with pytest.raises(SpecError, match="is the slide it is on, so the click goes nowhere"):
        parse_deck_text(
            _deck("id: here\ntitle: A\n" + _CARD_TO.format("here")), source=tmp_path / "d.deck.yaml"
        )


def test_two_slides_sharing_an_id_are_refused(tmp_path):
    with pytest.raises(SpecError, match=r"slide 2: duplicate id 'x' — slide 1 already has it"):
        parse_deck_text(
            _deck("id: x\ntitle: A", "id: x\ntitle: B"), source=tmp_path / "d.deck.yaml"
        )


def test_a_slide_cannot_take_a_relative_jumps_name_as_its_id(tmp_path):
    with pytest.raises(SpecError, match="a slide cannot be called 'next'"):
        parse_deck_text(_deck("id: next\ntitle: A"), source=tmp_path / "d.deck.yaml")


def test_a_goto_on_a_reveal_trigger_is_refused(tmp_path):
    slide = (
        "title: A\nplace:\n"
        "  - at: {cols: left-half}\n    id: button\n    goto: next\n    card: {heading: Go}\n"
        "  - at: {cols: right-half}\n    reveals: button\n    card: {heading: Shown}"
    )
    with pytest.raises(SpecError, match="one click cannot both reveal and leave the slide"):
        parse_deck_text(_deck(slide), source=tmp_path / "d.deck.yaml")


def test_a_control_character_in_a_goto_is_refused(tmp_path):
    with pytest.raises(SpecError, match="'goto' 'a\\\\x01' contains the control character"):
        parse_deck_text(
            _deck(
                'title: A\nplace:\n  - at: {cols: full}\n    goto: "a\\x01"\n    card: {heading: Go}'
            ),
            source=tmp_path / "d.deck.yaml",
        )


def test_a_link_to_anything_but_a_web_address_is_refused_with_the_slide_named(tmp_path):
    slide = "title: A\nplace:\n  - at: {cols: full}\n    card: {heading: Go, body: '[here](htps://x.io)'}"
    with pytest.raises(
        SpecError,
        match=r"slide 1: placement 1 \(card\): the link '\[here\]\(htps://x\.io\)' — 'htps://x\.io' is not a web address",
    ):
        parse_deck_text(_deck(slide), source=tmp_path / "d.deck.yaml")


def test_a_link_in_a_title_is_checked_too(tmp_path):
    with pytest.raises(SpecError, match="slide 1: title: the link"):
        parse_deck_text(_deck("title: '[x](mailto:nobody)'"), source=tmp_path / "d.deck.yaml")


def test_a_link_in_a_chart_is_refused(tmp_path):
    slide = (
        "title: A\nplace:\n  - at: {cols: full}\n    chart:\n      kind: column\n"
        "      data: [{category: '[Q1](https://x.io)', value: 1}]"
    )
    with pytest.raises(SpecError, match="a chart's labels are drawn by the chart"):
        parse_deck_text(_deck(slide), source=tmp_path / "d.deck.yaml")


def test_a_link_in_a_section_name_is_checked_with_the_deck_config_named(tmp_path):
    text = "theme: base\nsections: ['[One](ftp://x.io)']\nout: out/D.pptx\n---\ntitle: A\n"
    with pytest.raises(
        SpecError, match=r"deck config: sections: the link '\[One\]\(ftp://x\.io\)'"
    ):
        parse_deck_text(text, source=tmp_path / "d.deck.yaml")


def test_link_markup_in_a_code_listing_is_not_a_link_to_check(tmp_path):
    slide = "title: A\nplace:\n  - at: {cols: full}\n    code: {lines: ['[x](not-an-address)']}"
    assert parse_deck_text(_deck(slide), source=tmp_path / "d.deck.yaml").slides[0].place


def test_a_deck_and_a_slide_name_the_language_their_cjk_is_in(tmp_path):
    deck = parse_deck_text(
        "theme: base\nlang: zh-Hans\nout: out/D.pptx\n---\ntitle: A\n---\nlang: zh-Hant\ntitle: B\n",
        source=tmp_path / "d.deck.yaml",
    )
    assert deck.lang == "zh-Hans"
    assert [s.lang for s in deck.slides] == [None, "zh-Hant"]


def test_a_lang_that_is_not_a_language_tag_is_refused(tmp_path):
    with pytest.raises(
        SpecError,
        match="'lang' is a language tag like ja, ko, zh-Hans or zh-TW, got 'Japanese please'",
    ):
        parse_deck_text(_deck("lang: Japanese please\ntitle: A"), source=tmp_path / "d.deck.yaml")


def test_the_chart_link_refusal_does_not_advise_an_escape_a_chart_would_draw(tmp_path):
    slide = (
        "title: A\nplace:\n  - at: {cols: full}\n    chart:\n      kind: column\n"
        "      data: [{category: '[Q1](https://x.io)', value: 1}]"
    )
    with pytest.raises(SpecError) as caught:
        parse_deck_text(_deck(slide), source=tmp_path / "d.deck.yaml")
    assert "backslash" not in str(caught.value)


def test_a_goto_refusal_numbers_placements_as_the_author_wrote_them(tmp_path):
    slide = (
        "title: A\nplace:\n  - at: {rows: top-half}\n    split:\n"
        "      - card: {heading: One}\n      - card: {heading: Two}\n      - card: {heading: Three}\n"
        "  - at: {cols: full, rows: bottom-half}\n    goto: apendix\n    card: {heading: Go}"
    )
    with pytest.raises(SpecError, match=r"slide 1: placement 2: 'goto: apendix' names no slide"):
        parse_deck_text(_deck(slide), source=tmp_path / "d.deck.yaml")


@pytest.mark.parametrize(
    ("spec", "named"),
    [
        pytest.param(
            "theme: t\ntrue: 1\nzzz: 2\n---\ntitle: T\n",
            "d.deck.yaml: deck config: unknown field true;",
            id="deck-config-bool",
        ),
        pytest.param(
            "theme: t\n2021-01-01: 1\nzzz: 2\n---\ntitle: T\n",
            "d.deck.yaml: deck config: unknown field 2021-01-01;",
            id="deck-config-date",
        ),
        pytest.param(
            "theme: t\n---\ntitle: T\ntrue: 1\nzzz: 2\n",
            "d.deck.yaml: slide 1: unknown field true;",
            id="slide-bool",
        ),
        pytest.param(
            "theme: t\n---\ntitle: T\n2021-01-01: 1\nzzz: 2\n",
            "d.deck.yaml: slide 1: unknown field 2021-01-01;",
            id="slide-date",
        ),
        pytest.param(
            "theme: t\n---\ntitle: T\nplace: [{at: {cols: full}, true: 1}]\n",
            "d.deck.yaml: slide 1: placement 1: unknown field true;",
            id="placement-bool-alone",
        ),
    ],
)
def test_a_key_yaml_read_as_a_boolean_or_a_date_is_a_spec_error(tmp_path, spec, named):
    """Beside a string key it once raised TypeError from `sorted`; alone, from the
    did-you-mean lookup."""
    with pytest.raises(SpecError) as e:
        _parse(spec, tmp_path)
    assert named in str(e.value)
    assert str(e.value).endswith("; quote the key")


@pytest.mark.parametrize("written", ["nan%", "inf%", "1e400%"])
def test_a_box_percent_that_is_not_finite_is_refused(tmp_path, written):
    spec = (
        "theme: t\n---\ntitle: T\nplace:\n"
        f"  - at: {{box: {{x: {written}, y: 0%, w: 10%, h: 10%}}}}\n"
        "    bullets: {items: [a]}\n"
    )
    with pytest.raises(SpecError, match=rf"box.x is a percent of the canvas, got '{written}'"):
        _parse(spec, tmp_path)


_MORPH_CARD = "place:\n  - at: {{cols: full}}\n    morph: {}\n    {}"


def test_a_morph_name_is_read_onto_its_placement(tmp_path):
    deck = _parse(
        _deck("title: One\n" + _MORPH_CARD.format("hero", "card: {heading: H}")), tmp_path
    )
    assert deck.slides[0].place[0].morph == "hero"


def test_a_chart_cannot_morph(tmp_path):
    chart = "chart: {kind: column, data: [{category: a, value: 1}]}"
    with pytest.raises(
        SpecError,
        match=r"slide 1: placement 1: 'morph' on a chart — deckwright pairs no chart across "
        r"slides; morph a card, panel, image or icon",
    ):
        _parse(_deck("title: One\n" + _MORPH_CARD.format("hero", chart)), tmp_path)


def test_one_morph_name_cannot_be_two_placements_on_a_slide(tmp_path):
    twice = (
        "title: One\nplace:\n"
        "  - at: {cols: left-half}\n    morph: hero\n    card: {heading: A}\n"
        "  - at: {cols: right-half}\n    morph: hero\n    card: {heading: B}"
    )
    with pytest.raises(
        SpecError,
        match=r"slide 1: placement 2: 'morph: hero' is already placement 1 — a name pairs one "
        r"placement with its namesake on the next slide",
    ):
        _parse(_deck(twice), tmp_path)


def test_one_morph_name_cannot_be_two_components_on_slides_in_a_row(tmp_path):
    first = "title: One\n" + _MORPH_CARD.format("hero", "card: {heading: H}")
    second = "title: Two\ntransition: morph\n" + _MORPH_CARD.format("hero", "panel: {}")
    with pytest.raises(
        SpecError,
        match=r"slide 2: placement 1: 'morph: hero' is a card on slide 1 and a panel here — "
        r"PowerPoint pairs shapes in the order they were drawn",
    ):
        _parse(_deck(first, second), tmp_path)


def test_one_morph_name_may_be_two_components_on_slides_apart(tmp_path):
    first = "title: One\n" + _MORPH_CARD.format("hero", "card: {heading: H}")
    between = "title: Between"
    third = "title: Three\n" + _MORPH_CARD.format("hero", "panel: {}")
    deck = _parse(_deck(first, between, third), tmp_path)
    assert [s.place[0].morph for s in deck.slides if s.place] == ["hero", "hero"]
