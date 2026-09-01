import pytest

from deckwright.errors import SpecError
from deckwright.spec import parse_deck_text

_HEAD = "theme: t\n---\n"


def _slide(body, tmp_path):
    return parse_deck_text(_HEAD + body, source=tmp_path / "d.deck.yaml").slides[0]


def _one(entry, tmp_path):
    return _slide("place:\n  - " + entry + "\n", tmp_path)


def test_a_placement_names_its_component_and_keeps_its_mapping(tmp_path):
    slide = _one("at: {cols: left-half}\n    bullets: {items: [a, b]}", tmp_path)
    assert slide.place[0].component == "bullets"
    assert slide.place[0].body == {"items": ["a", "b"]}


def test_a_named_fraction_is_kept_as_a_name(tmp_path):
    """It resolves against the theme's grid, which the spec layer has not met."""
    at = _one("at: {cols: left-half}\n    bullets: {items: [a]}", tmp_path).place[0].at
    assert at == {"cols": "left-half"}


def test_an_exact_span_is_kept_as_a_pair_of_integers(tmp_path):
    at = _one("at: {cols: {from: 0, to: 7}}\n    bullets: {items: [a]}", tmp_path).place[0].at
    assert at == {"cols": (0, 7)}


def test_a_row_span_is_kept_alongside_the_columns(tmp_path):
    at = (
        _one("at: {cols: left-half, rows: {from: 2, to: 8}}\n    bullets: {items: [a]}", tmp_path)
        .place[0]
        .at
    )
    assert at == {"cols": "left-half", "rows": (2, 8)}


def test_a_box_is_read_as_fractions(tmp_path):
    at = (
        _one("at: {box: {x: 0%, y: 50%, w: 100%, h: 50%}}\n    bullets: {items: [a]}", tmp_path)
        .place[0]
        .at
    )
    assert at == {"box": (0.0, 0.5, 1.0, 0.5)}


def test_a_component_with_no_mapping_gets_an_empty_one(tmp_path):
    assert _one("at: {cols: left-half}\n    bullets:", tmp_path).place[0].body == {}


def test_two_placements_keep_their_order(tmp_path):
    slide = _slide(
        "place:\n"
        "  - at: {cols: left-half}\n    bullets: {items: [a]}\n"
        "  - at: {cols: right-half}\n    stats: {items: [{value: '4', label: x}]}\n",
        tmp_path,
    )
    assert [p.component for p in slide.place] == ["bullets", "stats"]


def test_a_placement_may_be_named_for_a_later_connector(tmp_path):
    assert (
        _one("at: {cols: left-half}\n    id: left\n    bullets: {items: [a]}", tmp_path).place[0].id
        == "left"
    )


def test_a_placement_may_declare_that_it_bleeds(tmp_path):
    assert (
        _one(
            "at: {box: {x: -5%, y: 0%, w: 60%, h: 100%}}\n    bleed: true\n    bullets: {items: [a]}",
            tmp_path,
        )
        .place[0]
        .bleed
        is True
    )


def test_a_non_boolean_bleed_is_rejected(tmp_path):
    with pytest.raises(SpecError, match=r"placement 1: 'bleed' must be true or false, got 'yes'"):
        _one("at: {cols: left-half}\n    bleed: 'yes'\n    bullets: {items: [a]}", tmp_path)


def test_two_placements_may_not_share_an_id(tmp_path):
    with pytest.raises(SpecError, match=r"slide 1: placement 2: duplicate id 'x'"):
        _slide(
            "place:\n"
            "  - at: {cols: left-half}\n    id: x\n    bullets: {items: [a]}\n"
            "  - at: {cols: right-half}\n    id: x\n    bullets: {items: [b]}\n",
            tmp_path,
        )


def test_a_slide_without_place_has_no_placements(tmp_path):
    assert _slide("title: T\n", tmp_path).place == ()


def test_place_must_be_a_list(tmp_path):
    with pytest.raises(SpecError, match=r"slide 1: 'place' must be a list, got dict"):
        _slide("place: {at: {cols: left-half}}\n", tmp_path)


def test_a_placement_must_be_a_mapping(tmp_path):
    with pytest.raises(SpecError, match=r"slide 1: placement 1: expected a mapping, got str"):
        _slide("place:\n  - just a string\n", tmp_path)


def test_a_placement_without_at_names_the_slide_and_the_field(tmp_path):
    with pytest.raises(SpecError, match=r"slide 1: placement 1: missing required field 'at'"):
        _slide("place:\n  - bullets: {items: [a]}\n", tmp_path)


def test_a_placement_with_no_component_lists_the_known_ones(tmp_path):
    with pytest.raises(
        SpecError, match=r"slide 1: placement 1: no component .*known components: .*bullets"
    ):
        _one("at: {cols: left-half}", tmp_path)


def test_two_components_in_one_placement_name_both(tmp_path):
    with pytest.raises(
        SpecError, match=r"placement 1: more than one component — found 'bullets' and 'chart'"
    ):
        _one(
            "at: {cols: left-half}\n    bullets: {items: [a]}\n    chart: {kind: column}", tmp_path
        )


def test_a_misspelled_component_suggests_the_closest_match(tmp_path):
    with pytest.raises(
        SpecError, match=r"placement 1: unknown field 'bulets'; did you mean 'bullets'\?"
    ):
        _one("at: {cols: left-half}\n    bulets: {items: [a]}", tmp_path)


def test_an_unrecognisable_placement_key_lists_what_is_accepted(tmp_path):
    with pytest.raises(
        SpecError,
        match=r"placement 1: unknown field 'colour'; known fields: "
        r"at, id, bleed, align, anchor, reveals, bullets",
    ):
        _one("at: {cols: left-half}\n    colour: blue", tmp_path)


def test_the_offending_placement_is_numbered(tmp_path):
    with pytest.raises(SpecError, match=r"slide 1: placement 2: missing required field 'at'"):
        _slide(
            "place:\n  - at: {cols: left-half}\n    bullets: {items: [a]}\n  - stats: {}\n",
            tmp_path,
        )


def test_a_non_mapping_component_value_is_rejected(tmp_path):
    with pytest.raises(
        SpecError, match=r"placement 1: component 'bullets' must be a mapping, got str"
    ):
        _one("at: {cols: left-half}\n    bullets: oops", tmp_path)


def test_at_must_be_a_mapping(tmp_path):
    with pytest.raises(SpecError, match=r"placement 1: 'at' must be a mapping, got list"):
        _one("at: [0, 6]\n    bullets: {items: [a]}", tmp_path)


def test_at_needs_cols_or_box(tmp_path):
    with pytest.raises(SpecError, match=r"placement 1: 'at' needs 'cols' or 'box'"):
        _one("at: {rows: top-half}\n    bullets: {items: [a]}", tmp_path)


def test_a_misspelled_at_key_suggests_the_closest_match(tmp_path):
    with pytest.raises(
        SpecError, match=r"placement 1: 'at': unknown field 'col'; did you mean 'cols'\?"
    ):
        _one("at: {col: [0, 6]}\n    bullets: {items: [a]}", tmp_path)


def test_a_box_cannot_be_combined_with_columns(tmp_path):
    with pytest.raises(
        SpecError, match=r"placement 1: 'at.box' cannot be combined with 'cols' or 'rows'"
    ):
        _one(
            "at: {box: {x: 0%, y: 0%, w: 100%, h: 100%}, cols: left-half}\n    bullets: {items: [a]}",
            tmp_path,
        )


def test_a_positional_column_span_names_the_form_that_replaced_it(tmp_path):
    """Every deck written before the cutover hits this exactly once."""
    with pytest.raises(SpecError, match=r"cols is a name or a mapping, not a list"):
        _one("at: {cols: [0, 6]}\n    bullets: {items: [a]}", tmp_path)


def test_a_positional_span_of_two_shows_the_mapping_to_write(tmp_path):
    with pytest.raises(SpecError, match=r"write \{from: 0, to: 7\}"):
        _one("at: {cols: [0, 7]}\n    bullets: {items: [a]}", tmp_path)


def test_a_fractional_column_span_is_rejected(tmp_path):
    with pytest.raises(SpecError, match=r"from and to are whole indices"):
        _one("at: {cols: {from: 0.0, to: 6.5}}\n    bullets: {items: [a]}", tmp_path)


def test_a_column_name_outside_the_vocabulary_lists_what_is_accepted(tmp_path):
    with pytest.raises(SpecError, match=r"cols 'left-quarter' names no fraction"):
        _one("at: {cols: left-quarter}\n    bullets: {items: [a]}", tmp_path)


def test_a_row_name_is_not_a_column_name(tmp_path):
    """The two vocabularies are separate, and the message must offer the right one."""
    with pytest.raises(SpecError, match=r"one of: full, left-half"):
        _one("at: {cols: top-half}\n    bullets: {items: [a]}", tmp_path)


def test_an_empty_column_span_is_rejected(tmp_path):
    with pytest.raises(SpecError, match=r"cols from 6 must be less than to 6"):
        _one("at: {cols: {from: 6, to: 6}}\n    bullets: {items: [a]}", tmp_path)


def test_a_negative_column_span_is_rejected(tmp_path):
    with pytest.raises(SpecError, match=r"cols from -1 must be 0 or more"):
        _one("at: {cols: {from: -1, to: 6}}\n    bullets: {items: [a]}", tmp_path)


def test_a_positional_box_names_the_keyed_form(tmp_path):
    with pytest.raises(SpecError, match=r"box is keyed, not a list"):
        _one("at: {box: [0, 0, 1, 1]}\n    bullets: {items: [a]}", tmp_path)


def test_a_box_value_that_is_not_a_percent_is_rejected(tmp_path):
    """0.5 and 0.5in look alike on the page and only one is meant."""
    with pytest.raises(SpecError, match=r"box.x is a percent of the canvas"):
        _one("at: {box: {x: 0.5, y: 0%, w: 50%, h: 10%}}\n    bullets: {items: [a]}", tmp_path)


def test_a_zero_width_box_is_rejected(tmp_path):
    with pytest.raises(SpecError, match=r"box needs a positive width and height"):
        _one("at: {box: {x: 0%, y: 0%, w: 0%, h: 100%}}\n    bullets: {items: [a]}", tmp_path)


def test_a_box_may_start_off_the_canvas(tmp_path):
    at = (
        _one("at: {box: {x: -5%, y: 0%, w: 110%, h: 40%}}\n    bullets: {items: [a]}", tmp_path)
        .place[0]
        .at
    )
    assert at == {"box": (-0.05, 0.0, 1.1, 0.4)}


def test_a_component_from_the_extends_module_is_accepted(tmp_path):
    (tmp_path / "ext.py").write_text(
        "from deckwright.layouts.components import component\n"
        "\n"
        "@component('t-ext-component')\n"
        "def _c(ctx):\n"
        "    return []\n"
    )
    text = "theme: t\nextends: ext.py\n---\nplace:\n  - at: {cols: full}\n    t-ext-component: {}\n"
    slide = parse_deck_text(text, source=tmp_path / "d.deck.yaml").slides[0]
    assert slide.place[0].component == "t-ext-component"


def test_a_placement_defaults_to_left_aligned_from_the_top(tmp_path):
    placement = _one("at: {cols: left-half}\n    bullets: {items: [a]}", tmp_path).place[0]
    assert (placement.align, placement.anchor) == ("left", "top")


def test_a_placement_keeps_the_align_and_anchor_it_declares(tmp_path):
    placement = _one(
        "at: {cols: left-half}\n    align: right\n    anchor: middle\n    bullets: {items: [a]}",
        tmp_path,
    ).place[0]
    assert (placement.align, placement.anchor) == ("right", "middle")


def test_an_align_outside_the_vocabulary_lists_what_is_accepted(tmp_path):
    with pytest.raises(SpecError, match="'align' must be one of left, center, right"):
        _one("at: {cols: left-half}\n    align: justify\n    bullets: {items: [a]}", tmp_path)


def test_an_anchor_outside_the_vocabulary_lists_what_is_accepted(tmp_path):
    with pytest.raises(SpecError, match="'anchor' must be one of top, middle, bottom"):
        _one("at: {cols: left-half}\n    anchor: baseline\n    bullets: {items: [a]}", tmp_path)


# --- slide chrome overrides ------------------------------------------------


def test_a_slide_chrome_override_reaches_the_spec(tmp_path):
    slide = _slide(
        "title: T\nchrome:\n  title: {at: {box: {x: 10%, y: 60%, w: 50%, h: 10%}}, "
        "align: center, rung: hero, pair: accent-1}\n",
        tmp_path,
    )
    field = slide.chrome["title"]
    # Written in percents, kept as canvas fractions: a chrome override is normalised
    # on the way in, like a placement's own box.
    assert field.at == {"box": pytest.approx((0.1, 0.6, 0.5, 0.1))}
    assert (field.align, field.rung, field.pair) == ("center", "hero", "accent-1")


def test_a_slide_declaring_no_chrome_block_overrides_nothing(tmp_path):
    assert _slide("title: T\n", tmp_path).chrome == {}


def test_chrome_for_a_field_the_slide_has_no_text_for_is_rejected(tmp_path):
    with pytest.raises(SpecError, match="'chrome' sets 'subtitle' but the slide has no"):
        _slide("title: T\nchrome:\n  subtitle: {align: center}\n", tmp_path)


def test_an_unknown_chrome_field_is_rejected_naming_the_vocabulary(tmp_path):
    with pytest.raises(SpecError, match="unknown chrome field 'eyebrow'"):
        _slide("title: T\nchrome:\n  eyebrow: {align: center}\n", tmp_path)


def test_a_chrome_box_given_in_inches_is_rejected_as_leaving_the_canvas(tmp_path):
    with pytest.raises(SpecError, match=r"box .* leaves the canvas"):
        _slide(
            "title: T\nchrome:\n  title: {at: {box: {x: 62%, y: 60%, w: 1130%, h: 125%}}}\n",
            tmp_path,
        )


@pytest.mark.parametrize("key", ["id", "reveals"])
def test_a_control_character_in_a_name_is_a_spec_error(tmp_path, key):
    """Both end up as shape names, where lxml rejects them with a bare `ValueError` — which escapes
    as a traceback, and inside `conform` takes the whole run down instead of one exercise."""
    with pytest.raises(SpecError, match=r"contains the control character"):
        _one(f'at: {{cols: left-half}}\n    {key}: "a\\vb"\n    bullets: {{items: [a]}}', tmp_path)


def test_xml_metacharacters_in_an_id_are_still_accepted(tmp_path):
    """python-pptx escapes them; refusing them would be a false positive."""
    slide = _one("at: {cols: left-half}\n    id: 'a&b<c>'\n    bullets: {items: [a]}", tmp_path)
    assert slide.place[0].id == "a&b<c>"


# --- split ------------------------------------------------------------------


def test_a_split_becomes_one_placement_per_child(tmp_path):
    slide = _slide(
        "place:\n  - split:\n"
        "    - card: {heading: One}\n"
        "    - card: {heading: Two}\n"
        "    - card: {heading: Three}\n",
        tmp_path,
    )
    assert [p.component for p in slide.place] == ["card"] * 3
    assert [p.body["heading"] for p in slide.place] == ["One", "Two", "Three"]


def test_each_child_takes_one_share_of_the_band_in_order(tmp_path):
    slide = _slide(
        "place:\n  - split:\n    - card: {heading: One}\n    - card: {heading: Two}\n", tmp_path
    )
    assert [p.at["cols"].index for p in slide.place] == [0, 1]
    assert {p.at["cols"].total for p in slide.place} == {2}


def test_a_child_may_take_more_than_one_share(tmp_path):
    slide = _slide(
        "place:\n  - split:\n"
        "    - card: {heading: One}\n"
        "    - span: 2\n      card: {heading: Two}\n"
        "    - card: {heading: Three}\n",
        tmp_path,
    )
    assert [(p.at["cols"].index, p.at["cols"].span) for p in slide.place] == [
        (0, 1),
        (1, 2),
        (3, 1),
    ]
    assert {p.at["cols"].total for p in slide.place} == {4}


def test_a_split_defaults_to_the_whole_width_and_keeps_the_rows_it_was_given(tmp_path):
    slide = _slide(
        "place:\n  - at: {rows: {from: 1, to: 7}}\n    split:\n    - card: {heading: One}\n",
        tmp_path,
    )
    assert slide.place[0].at["cols"].band == "full"
    assert slide.place[0].at["rows"] == (1, 7)


def test_a_split_may_narrow_the_band_it_divides(tmp_path):
    slide = _slide(
        "place:\n  - at: {cols: right-half}\n    split:\n"
        "    - card: {heading: One}\n    - card: {heading: Two}\n",
        tmp_path,
    )
    assert {p.at["cols"].band for p in slide.place} == {"right-half"}


def test_a_split_child_keeps_its_own_id(tmp_path):
    slide = _slide(
        "place:\n  - split:\n"
        "    - id: left\n      card: {heading: One}\n"
        "    - card: {heading: Two}\n",
        tmp_path,
    )
    assert [p.id for p in slide.place] == ["left", None]


def test_a_split_child_may_not_place_itself(tmp_path):
    with pytest.raises(SpecError, match="a split child has no 'at'"):
        _slide("place:\n  - split:\n    - at: {cols: full}\n      card: {heading: One}\n", tmp_path)


def test_a_split_takes_no_component_of_its_own(tmp_path):
    with pytest.raises(SpecError, match="takes only 'at' and 'split'"):
        _slide(
            "place:\n  - split:\n    - card: {heading: One}\n    bullets: {items: [a]}\n", tmp_path
        )


def test_an_empty_split_is_rejected(tmp_path):
    with pytest.raises(SpecError, match="'split' is a non-empty list"):
        _slide("place:\n  - split: []\n", tmp_path)


def test_a_split_cannot_divide_a_box(tmp_path):
    with pytest.raises(SpecError, match="'split' divides a column band"):
        _slide(
            "place:\n  - at: {box: {x: 0%, y: 0%, w: 100%, h: 100%}}\n    split:\n"
            "    - card: {heading: One}\n",
            tmp_path,
        )


def test_a_span_that_is_not_a_count_is_rejected(tmp_path):
    with pytest.raises(SpecError, match="'span' is a whole number of shares"):
        _slide("place:\n  - split:\n    - span: 0\n      card: {heading: One}\n", tmp_path)
