import pytest

from deckwright.charts.model import _BUBBLE_CHART_TYPES, _XY_CHART_TYPES, ChartSpec, Series
from deckwright.errors import LayoutError


def _body(**over):
    body = {
        "kind": "bar",
        "data": [
            {"category": "Q1", "values": {"A": 1}},
            {"category": "Q2", "values": {"A": 2}},
        ],
    }
    body.update(over)
    return body


def _xy_body(**over):
    body = {"kind": "xy-scatter", "data": [{"x": 1.2, "y": 4.5}, {"x": 2.4, "y": 8.1}]}
    body.update(over)
    return body


def _bubble_body(**over):
    body = {
        "kind": "bubble",
        "data": [{"x": 1.2, "y": 4.5, "size": 30}, {"x": 2.4, "y": 8.1, "size": 55}],
    }
    body.update(over)
    return body


def test_a_spec_round_trips_its_fields(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec.from_body(ctx, _body())
    assert spec.type == "bar"
    assert spec.categories == ("Q1", "Q2")
    assert spec.series[0].values == (1.0, 2.0)


def test_a_render_field_is_rejected_as_unknown(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match=r"slide 1 .*'render'"):
        ChartSpec.from_body(ctx, _body(render="native"))


def test_an_unknown_chart_kind_lists_the_known_ones(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match="bar"):
        ChartSpec.from_body(ctx, _body(kind="sunburst"))


def test_a_non_mapping_body_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match=r"slide 1 .*mapping"):
        ChartSpec.from_body(ctx, None)


def test_a_string_body_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match=r"slide 1 .*mapping"):
        ChartSpec.from_body(ctx, "chart")


def test_an_unknown_chart_field_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match=r"slide 1 .*'bogus'"):
        ChartSpec.from_body(ctx, _body(bogus=1))


# --- No backward compatibility: the old shape must fail naming the new one. ---


def test_a_top_level_type_field_points_at_kind(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = {"type": "bar", "categories": ["Q1"], "series": [{"name": "A", "values": [1]}]}
    with pytest.raises(LayoutError, match=r"'type'.*'kind'"):
        ChartSpec.from_body(ctx, body)


def test_a_top_level_categories_field_points_at_data(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match=r"'categories'.*'data'"):
        ChartSpec.from_body(ctx, _body(categories=["Q1", "Q2"]))


def test_a_top_level_series_field_points_at_data(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match=r"'series'.*'data'"):
        ChartSpec.from_body(ctx, _body(series=[{"name": "A", "values": [1, 2]}]))


def test_a_top_level_highlight_field_points_at_per_row_highlight(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match=r"'highlight'.*per-row"):
        ChartSpec.from_body(ctx, _body(highlight=1))


# --- data: missing or empty ---


def test_missing_data_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match=r"'data'"):
        ChartSpec.from_body(ctx, {"kind": "bar"})


def test_empty_data_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match=r"'data'"):
        ChartSpec.from_body(ctx, _body(data=[]))


# --- Series order and the row-oriented shape ---


def test_series_order_follows_the_first_rows_key_order(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(
        data=[
            {"category": "Q1", "values": {"Organic": 1, "Ads": 2}},
            {"category": "Q2", "values": {"Ads": 3, "Organic": 4}},
        ]
    )
    spec = ChartSpec.from_body(ctx, body)
    assert [s.name for s in spec.series] == ["Organic", "Ads"]


def test_a_four_row_two_series_chart_matches_the_old_shape(ctx_factory):
    """The brief's own worked example — this equivalence is what lets native.py
    and components/chart.py stay untouched."""
    ctx = ctx_factory({"title": "T"})
    body = {
        "kind": "column-stacked",
        "data": [
            {"category": "Q1", "values": {"Ads": 20, "Organic": 15}},
            {"category": "Q2", "values": {"Ads": 28, "Organic": 22}},
            {"category": "Q3", "values": {"Ads": 35, "Organic": 30}},
            {"category": "Q4", "values": {"Ads": 42, "Organic": 41}, "highlight": True},
        ],
    }
    spec = ChartSpec.from_body(ctx, body)
    assert spec.categories == ("Q1", "Q2", "Q3", "Q4")
    assert spec.series == (
        Series(name="Ads", values=(20.0, 28.0, 35.0, 42.0)),
        Series(name="Organic", values=(15.0, 22.0, 30.0, 41.0)),
    )
    assert spec.highlight == 3


def test_the_single_value_shorthand_round_trips(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(
        data=[
            {"category": "Q1", "value": 12},
            {"category": "Q4", "value": 91, "highlight": True},
        ]
    )
    spec = ChartSpec.from_body(ctx, body)
    assert spec.categories == ("Q1", "Q4")
    assert spec.series == (Series(name="", values=(12.0, 91.0)),)
    assert spec.highlight == 1


# --- Row errors: missing/extra series ---


def test_a_row_missing_a_series_another_row_has_names_the_row_and_series(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(
        data=[
            {"category": "Q1", "values": {"Ads": 1, "Organic": 2}},
            {"category": "Q2", "values": {"Ads": 3}},
        ]
    )
    with pytest.raises(LayoutError, match=r"row 2 \(category 'Q2'\).*missing series 'Organic'"):
        ChartSpec.from_body(ctx, body)


def test_a_row_with_a_series_no_other_row_has_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(
        data=[
            {"category": "Q1", "values": {"Ads": 1}},
            {"category": "Q2", "values": {"Ads": 2, "Bogus": 9}},
        ]
    )
    with pytest.raises(LayoutError, match=r"row 2 \(category 'Q2'\).*series 'Bogus'.*no other row"):
        ChartSpec.from_body(ctx, body)


# --- value / values mixed ---


def test_mixing_value_and_values_across_rows_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(
        data=[
            {"category": "Q1", "value": 1},
            {"category": "Q2", "values": {"Ads": 2}},
        ]
    )
    with pytest.raises(
        LayoutError, match=r"row 2 \(category 'Q2'\).*'values'.*row 1 \(category 'Q1'\).*'value'"
    ):
        ChartSpec.from_body(ctx, body)


def test_a_single_row_carrying_both_value_and_values_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(data=[{"category": "Q1", "value": 1, "values": {"Ads": 2}}])
    with pytest.raises(LayoutError, match=r"row 1 \(category 'Q1'\).*both 'value' and 'values'"):
        ChartSpec.from_body(ctx, body)


# --- category vs x/y shape mismatches ---


def test_a_category_on_an_xy_row_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _xy_body(data=[{"x": 1, "y": 2, "category": "Q1"}])
    with pytest.raises(LayoutError, match=r"row 1.*'category'.*'xy-scatter'"):
        ChartSpec.from_body(ctx, body)


def test_x_y_on_a_category_row_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(data=[{"x": 1, "y": 2}])
    with pytest.raises(LayoutError, match=r"row 1.*'x'/'y'.*'bar'.*category-shaped"):
        ChartSpec.from_body(ctx, body)


# --- bubble row missing size ---


def test_a_bubble_row_missing_size_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _bubble_body(data=[{"x": 1.2, "y": 4.5}])
    with pytest.raises(LayoutError, match=r"row 1.*'size'.*'bubble'"):
        ChartSpec.from_body(ctx, body)


# --- non-numeric values ---


def test_a_non_numeric_value_in_a_multi_series_row_names_the_row_and_series(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(data=[{"category": "Q1", "values": {"A": "many"}}])
    with pytest.raises(LayoutError, match=r"row 1 \(category 'Q1'\).*series 'A'.*non-numeric"):
        ChartSpec.from_body(ctx, body)


def test_a_non_numeric_value_in_the_single_value_shorthand_names_the_row(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(data=[{"category": "Q1", "value": "many"}])
    with pytest.raises(LayoutError, match=r"row 1 \(category 'Q1'\).*non-numeric"):
        ChartSpec.from_body(ctx, body)


def test_a_non_numeric_x_on_an_xy_row_names_the_row(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _xy_body(data=[{"x": "many", "y": 1}])
    with pytest.raises(LayoutError, match=r"row 1.*non-numeric 'x'"):
        ChartSpec.from_body(ctx, body)


# --- highlight: true on more than one row ---


def test_highlight_true_on_more_than_one_row_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(
        data=[
            {"category": "Q1", "values": {"A": 1}, "highlight": True},
            {"category": "Q2", "values": {"A": 2}, "highlight": True},
        ]
    )
    with pytest.raises(LayoutError, match=r"only one row.*'Q1'.*'Q2'"):
        ChartSpec.from_body(ctx, body)


def test_a_non_bool_highlight_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(data=[{"category": "Q1", "values": {"A": 1}, "highlight": "yes"}])
    with pytest.raises(LayoutError, match=r"row 1.*'highlight'.*true or false"):
        ChartSpec.from_body(ctx, body)


# --- unknown key inside a row ---


def test_an_unknown_key_inside_a_row_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(data=[{"category": "Q1", "value": 1, "bogus": True}])
    with pytest.raises(LayoutError, match=r"row 1.*unknown field 'bogus'"):
        ChartSpec.from_body(ctx, body)


def test_an_unknown_key_inside_an_xy_row_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _xy_body(data=[{"x": 1, "y": 2, "bogus": True}])
    with pytest.raises(LayoutError, match=r"row 1.*unknown field 'bogus'"):
        ChartSpec.from_body(ctx, body)


def test_a_row_missing_its_category_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(data=[{"value": 1}])
    with pytest.raises(LayoutError, match=r"row 1.*needs a 'category'"):
        ChartSpec.from_body(ctx, body)


def test_a_row_missing_value_or_values_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(data=[{"category": "Q1"}])
    with pytest.raises(LayoutError, match=r"row 1 \(category 'Q1'\).*needs a 'value' or 'values'"):
        ChartSpec.from_body(ctx, body)


def test_a_non_mapping_row_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _body(data=["Q1"])
    with pytest.raises(LayoutError, match=r"row 1 must be a mapping"):
        ChartSpec.from_body(ctx, body)


# --- xy / bubble round trips ---


def test_an_xy_spec_round_trips_its_points(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec.from_body(ctx, _xy_body())
    assert spec.categories == ()
    assert spec.series[0].points == ((1.2, 4.5), (2.4, 8.1))
    assert spec.series[0].values is None


def test_a_bubble_spec_round_trips_its_points(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec.from_body(ctx, _bubble_body())
    assert spec.series[0].points == ((1.2, 4.5, 30.0), (2.4, 8.1, 55.0))


def test_a_bubble_row_can_be_highlighted(ctx_factory):
    """A bubble's point is a filled circle, so recolouring it is visible."""
    ctx = ctx_factory({"title": "T"})
    body = {
        "kind": "bubble",
        "data": [
            {"x": 1.2, "y": 4.5, "size": 20},
            {"x": 2.4, "y": 8.1, "size": 40, "highlight": True},
        ],
    }
    assert ChartSpec.from_body(ctx, body).highlight == 1


def test_highlight_is_rejected_where_it_would_do_nothing(ctx_factory):
    """A scatter marker takes its fill from the series, so a per-point highlight
    validates and then changes nothing on screen — confirmed by rendering."""
    ctx = ctx_factory({"title": "T"})
    body = _xy_body(data=[{"x": 1.2, "y": 4.5}, {"x": 2.4, "y": 8.1, "highlight": True}])
    with pytest.raises(LayoutError, match="cannot show 'highlight'"):
        ChartSpec.from_body(ctx, body)


def test_a_bubble_point_with_a_non_positive_size_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = _bubble_body(data=[{"x": 1.2, "y": 4.5, "size": 0}])
    with pytest.raises(LayoutError, match=r"row 1.*non-positive bubble size"):
        ChartSpec.from_body(ctx, body)


@pytest.mark.parametrize(
    "chart_type",
    (
        "column-stacked",
        "column-stacked-100",
        "area",
        "doughnut",
        "line-markers",
        "bar-stacked",
        "bar-stacked-100",
        "area-stacked",
        "radar",
        "pie-exploded",
        "area-stacked-100",
        "doughnut-exploded",
        "line-stacked",
        "line-stacked-100",
        "line-markers-stacked",
        "line-markers-stacked-100",
        "radar-filled",
        "radar-markers",
        "xy-scatter",
        "xy-scatter-lines",
        "xy-scatter-lines-no-markers",
        "xy-scatter-smooth",
        "xy-scatter-smooth-no-markers",
        "bubble",
        "bubble-3d",
    ),
)
def test_a_new_chart_type_round_trips_via_from_body(ctx_factory, chart_type):
    ctx = ctx_factory({"title": "T"})
    if chart_type in _XY_CHART_TYPES:
        body = _xy_body(kind=chart_type)
    elif chart_type in _BUBBLE_CHART_TYPES:
        body = _bubble_body(kind=chart_type)
    else:
        body = _body(kind=chart_type)
    spec = ChartSpec.from_body(ctx, body)
    assert spec.type == chart_type


def test_an_annotate_block_is_refused_as_removed(ctx_factory):
    """It shipped validated-but-undrawn, so a deck may still carry one; the message
    has to say it is gone rather than read as a typo."""
    ctx = ctx_factory({"title": "T"})
    body = _body(annotate={"at": 1, "title": "+33 pts", "detail": "after rollout"})
    with pytest.raises(LayoutError, match="'annotate' is gone"):
        ChartSpec.from_body(ctx, body)


def test_y_min_and_y_max_round_trip(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec.from_body(ctx, _body(y_min=0, y_max=100))
    assert (spec.y_min, spec.y_max) == (0.0, 100.0)


def test_a_non_numeric_y_max_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match="y_max"):
        ChartSpec.from_body(ctx, _body(y_max="high"))


def test_constructing_a_spec_directly_with_mismatched_lengths_is_rejected():
    with pytest.raises(LayoutError, match="categor"):
        ChartSpec(type="bar", categories=("Q1", "Q2"), series=(Series(name="A", values=(1.0,)),))


def test_constructing_a_spec_directly_with_an_out_of_range_highlight_is_rejected():
    with pytest.raises(LayoutError, match="highlight"):
        ChartSpec(
            type="bar",
            categories=("Q1", "Q2"),
            series=(Series(name="A", values=(1.0, 2.0)),),
            highlight=9,
        )


def test_constructing_an_xy_spec_directly_with_an_out_of_range_highlight_is_rejected():
    with pytest.raises(LayoutError, match="highlight"):
        ChartSpec(
            type="xy-scatter",
            categories=(),
            series=(Series(name="", points=((1.0, 2.0), (3.0, 4.0))),),
            highlight=9,
        )


def test_constructing_a_spec_directly_with_empty_series_is_rejected():
    with pytest.raises(LayoutError, match="series"):
        ChartSpec(type="bar", categories=("Q1", "Q2"), series=())


def test_constructing_a_spec_directly_with_empty_categories_is_rejected():
    with pytest.raises(LayoutError, match="categor"):
        ChartSpec(type="bar", categories=(), series=(Series(name="A", values=()),))


def test_constructing_a_spec_directly_with_an_invalid_type_is_rejected():
    with pytest.raises(LayoutError, match="bar"):
        ChartSpec(
            type="scatter", categories=("Q1", "Q2"), series=(Series(name="A", values=(1.0, 2.0)),)
        )


def test_a_spec_is_hashable():
    spec = ChartSpec(
        type="bar", categories=("Q1", "Q2"), series=(Series(name="A", values=(1.0, 2.0)),)
    )
    assert isinstance(hash(spec), int)


def test_a_category_series_with_points_is_rejected_naming_the_series_and_type(ctx_factory):
    with pytest.raises(LayoutError, match=r"'A'.*'bar'"):
        ChartSpec(
            type="bar", categories=("Q1", "Q2"), series=(Series(name="A", points=((1.0, 2.0),)),)
        )


def test_an_xy_series_with_values_is_rejected_naming_the_series_and_type(ctx_factory):
    with pytest.raises(LayoutError, match=r"'Spend vs revenue'.*'xy-scatter'"):
        ChartSpec(
            type="xy-scatter",
            categories=(),
            series=(Series(name="Spend vs revenue", values=(1.0, 2.0)),),
        )


def test_constructing_an_xy_spec_directly_with_categories_is_rejected():
    with pytest.raises(LayoutError, match="categor"):
        ChartSpec(
            type="xy-scatter",
            categories=("Q1", "Q2"),
            series=(Series(name="A", points=((1.0, 2.0),)),),
        )


def test_constructing_a_category_spec_directly_with_points_is_rejected():
    with pytest.raises(LayoutError, match=r"'A'.*'bar'"):
        ChartSpec(
            type="bar", categories=("Q1", "Q2"), series=(Series(name="A", points=((1.0, 2.0),)),)
        )


def test_constructing_a_bubble_spec_directly_with_a_short_point_is_rejected():
    with pytest.raises(LayoutError, match="point 0"):
        ChartSpec(type="bubble", categories=(), series=(Series(name="A", points=((1.0, 2.0),)),))


def test_constructing_a_bubble_spec_directly_with_a_non_positive_size_is_rejected():
    with pytest.raises(LayoutError, match="point 0"):
        ChartSpec(
            type="bubble", categories=(), series=(Series(name="A", points=((1.0, 2.0, 0.0),)),)
        )


@pytest.mark.parametrize("bad", [1.5, "two", True, -1, 99])
def test_a_decimals_that_is_not_a_place_count_is_rejected(ctx_factory, bad):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match="'decimals'"):
        ChartSpec.from_body(ctx, _body(decimals=bad))


def test_decimals_reaches_the_spec(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    assert ChartSpec.from_body(ctx, _body(decimals=3)).decimals == 3


_TWO_SERIES = [
    {"category": "Q1", "values": {"Ours": 1, "Platform average": 7}},
    {"category": "Q2", "values": {"Ours": 2, "Platform average": 7}},
]


def test_labels_false_turns_one_series_off_and_leaves_the_others_alone(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec.from_body(ctx, _body(data=_TWO_SERIES, labels={"Platform average": False}))
    assert [(s.name, s.labels) for s in spec.series] == [
        ("Ours", True),
        ("Platform average", False),
    ]


def test_labels_true_is_the_default_written_out(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    spec = ChartSpec.from_body(ctx, _body(data=_TWO_SERIES, labels={"Ours": True}))
    assert [s.labels for s in spec.series] == [True, True]


def test_a_chart_with_no_labels_key_prints_every_series(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    assert [s.labels for s in ChartSpec.from_body(ctx, _body(data=_TWO_SERIES)).series] == [
        True,
        True,
    ]


@pytest.mark.parametrize("bad", [False, True, "Ours", ["Ours"], {}])
def test_a_labels_that_is_not_a_mapping_of_series_names_is_rejected(ctx_factory, bad):
    """`labels: false` is a different ask; the theme's `label_position` covers it."""
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match="mapping of series name"):
        ChartSpec.from_body(ctx, _body(data=_TWO_SERIES, labels=bad))


def test_labels_naming_a_series_no_row_defines_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match="which no data row defines"):
        ChartSpec.from_body(ctx, _body(data=_TWO_SERIES, labels={"Platfrom average": False}))


def test_a_labels_entry_that_is_not_a_flag_is_rejected(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    with pytest.raises(LayoutError, match="must be true or false"):
        ChartSpec.from_body(ctx, _body(data=_TWO_SERIES, labels={"Ours": 3}))


def test_labels_is_refused_where_the_series_have_no_names(ctx_factory):
    """`value:` rows and the xy/bubble kinds both fold into one unnamed series, and
    python-pptx gives an XySeries no `data_labels` to write."""
    ctx = ctx_factory({"title": "T"})
    single = _body(data=[{"category": "Q1", "value": 1}], labels={"Anything": False})
    with pytest.raises(LayoutError, match="series need names"):
        ChartSpec.from_body(ctx, single)
    with pytest.raises(LayoutError, match="series need names"):
        ChartSpec.from_body(ctx, _xy_body(labels={"Anything": False}))


def test_a_pie_takes_one_series(ctx_factory):
    """python-pptx keeps only the first series for a pie, so a second reached a
    `zip(..., strict=True)` and came out as a bare ValueError traceback."""
    ctx = ctx_factory({"title": "T"})
    body = {
        "kind": "pie",
        "data": [
            {"category": "A", "values": {"Ours": 3, "Theirs": 5}},
            {"category": "B", "values": {"Ours": 4, "Theirs": 2}},
        ],
    }
    with pytest.raises(LayoutError) as e:
        ChartSpec.from_body(ctx, body)
    # The slide prefix pins the `from_body` refusal rather than the `__post_init__`
    # backstop, which cannot name where the deck went wrong.
    assert str(e.value).startswith("slide 1 (component 'chart'):")
    assert "takes one series" in str(e.value)
    assert "'Ours', 'Theirs'" in str(e.value)


def test_a_pie_with_one_series_is_accepted(ctx_factory):
    ctx = ctx_factory({"title": "T"})
    body = {"kind": "pie", "data": [{"category": "A", "values": {"Ours": 3}}]}
    assert len(ChartSpec.from_body(ctx, body).series) == 1
