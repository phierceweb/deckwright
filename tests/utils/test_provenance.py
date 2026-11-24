"""The manifest reader refuses a field held as a type no build writes."""

from __future__ import annotations

import json
from dataclasses import fields

import pytest

from deckwright.compile.manifest import ManifestRecorder
from deckwright.compile.record import PlacementRecord, Provenance, ShapeRecord, SlideRecord
from deckwright.errors import SpecError
from deckwright.utils.provenance import RECORD_FIELDS, SLIDE_FIELDS, TOP_FIELDS, read_manifest

_SHAPE = {"shape_id": 2, "name": "s1.p1.card", "box": {"x": 1.0, "y": 1, "w": 3.0, "h": 1.0}}


def _manifest(tmp_path, *, top=None, slide=None, **records):
    data = {"slides": [{"index": 1, "shapes": [dict(_SHAPE)], **(slide or {}), **records}]}
    path = tmp_path / "d.manifest.json"
    path.write_text(json.dumps({**data, **(top or {})}))
    return path


def _refusal(path, **kwargs):
    with pytest.raises(SpecError) as caught:
        read_manifest(path, **kwargs)
    return str(caught.value).split("(", 1)[1].split(") — ", 1)[0]


@pytest.mark.parametrize(
    ("spoiled", "why"),
    [
        ({"top": {"deck_hash": 5}}, "deck_hash is 5, not text"),
        ({"top": {"canvas": [13.333, 7.5]}}, "canvas is [13.333, 7.5], not a slide size"),
        ({"top": {"canvas": {"w": True}}}, "canvas is {'w': True}, not a slide size"),
        (
            {"top": {"canvas": {"w": 13.333, "h": "7.5"}}},
            "canvas is {'w': 13.333, 'h': '7.5'}, not a slide size",
        ),
        (
            {"top": {"canvas": {"w": 10**400}}},
            "canvas is {'w': 100000000000000000000000000000000…, not a slide size",
        ),
        ({"slide": {"backdrop": 1}}, "backdrop of slide 1 is 1, not true or false"),
        ({"slide": {"backdrop": "yes"}}, "backdrop of slide 1 is 'yes', not true or false"),
        ({"slide": {"transition": 2}}, "transition of slide 1 is 2, not text"),
        (
            {"shapes": [{**_SHAPE, "font_pt": "x"}]},
            "font_pt of slide 1's shape 's1.p1.card' is 'x', not a number",
        ),
        (
            {"shapes": [_SHAPE, {**_SHAPE, "name": 5}]},
            "name of slide 1's shape record 2 is 5, not text",
        ),
        (
            {"shapes": [{**_SHAPE, "font_pt": 10**400}]},
            "font_pt of slide 1's shape 's1.p1.card' is 100000000000000000000000000000000000000…, "
            "not a number",
        ),
        (
            {"shapes": [{**_SHAPE, "font_pt": "a" * 39}]},
            f"font_pt of slide 1's shape 's1.p1.card' is '{'a' * 38}…, not a number",
        ),
        (
            {"shapes": [{**_SHAPE, "font_pt": "a" * 38}]},
            f"font_pt of slide 1's shape 's1.p1.card' is '{'a' * 38}', not a number",
        ),
        (
            {"shapes": [{**_SHAPE, "name": "", "font_pt": "x"}]},
            "font_pt of slide 1's shape record 1 is 'x', not a number",
        ),
        (
            {"shapes": [{**_SHAPE, "line_pt": [float("nan")]}]},
            "line_pt of slide 1's shape 's1.p1.card' is [nan], not a list of numbers",
        ),
        (
            {"animations": [{"steps": [[5]]}]},
            "steps of slide 1's animation record 1 is [[5]], "
            "not a list of steps, each a list of shape names",
        ),
        (
            {"shapes": [{**_SHAPE, "shape_id": 2.5}]},
            "shape_id of slide 1's shape 's1.p1.card' is 2.5, not a whole number",
        ),
        (
            {"shapes": [{**_SHAPE, "box": {"x": 1.0, "y": 1.0, "w": 3.0}}]},
            "box of slide 1's shape 's1.p1.card' is {'x': 1.0, 'y': 1.0, 'w': 3.0}, "
            "not a box of four numbers",
        ),
        (
            {"shapes": [{**_SHAPE, "line_pt": [12.0, "13"]}]},
            "line_pt of slide 1's shape 's1.p1.card' is [12.0, '13'], not a list of numbers",
        ),
        (
            {"shapes": [{**_SHAPE, "lines": "one line"}]},
            "lines of slide 1's shape 's1.p1.card' is 'one line', not a list of text",
        ),
        (
            {"placements": [{"origin": "s1.p1", "box": {"x": "0", "y": 0, "w": 1, "h": 1}}]},
            "box of slide 1's placement 's1.p1' is {'x': '0', 'y': 0, 'w': 1, 'h': 1}, "
            "not a box of four numbers",
        ),
        (
            {"animations": [{"clicks": 1}, {"clicks": True}]},
            "clicks of slide 1's animation record 2 is True, not a whole number",
        ),
        (
            {"animations": [{"steps": [["s1.p1.card"], "s1.p2.card"]}]},
            "steps of slide 1's animation record 1 is [['s1.p1.card'], 's1.p2.card'], "
            "not a list of steps, each a list of shape names",
        ),
    ],
)
def test_a_field_of_the_wrong_type_is_refused_naming_it(tmp_path, spoiled, why):
    assert _refusal(_manifest(tmp_path, **spoiled)) == why


def test_a_long_value_is_cut_short_in_the_refusal(tmp_path):
    path = _manifest(tmp_path, top={"spec": list(range(40))})
    assert _refusal(path) == "spec is [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, …, not text"


@pytest.mark.parametrize(
    "held",
    [
        {"top": {"deck_hash": None, "canvas": {}}},
        {"top": {"canvas": {"w": 13.333, "h": None, "unit": "in"}}},
        {"slide": {"notes": None, "section": None}},
        {"shapes": [{**_SHAPE, "font_pt": 12, "line_pt": [], "text": None, "box": {}}]},
        {"shapes": [{"name": "s1.p1.card", "box": [1.0, 1.0, 3.0, 1.0]}]},
        {"shapes": [{**_SHAPE, "written_by_a_later_build": object.__name__}]},
        {"animations": [{"kind": "click_sequence", "clicks": 0, "steps": [[]]}]},
        {"shapes": [{**_SHAPE, "shape_id": 2.0}], "animations": [{"clicks": 1.0}]},
        {"shapes": [{**_SHAPE, "shape_id": 10**400}]},
    ],
    ids=[
        "nulls-at-the-top",
        "a-canvas-missing-a-side",
        "nulls-on-a-slide",
        "nulls-and-an-empty-box",
        "a-positional-box",
        "a-field-this-version-does-not-know",
        "an-empty-step",
        "a-whole-number-written-as-a-float",
        "a-whole-number-no-float-holds",
    ],
)
def test_a_missing_null_or_unknown_field_is_read(tmp_path, held):
    assert read_manifest(_manifest(tmp_path, **held))["slides"][0]["index"] == 1


def test_extract_reads_past_a_field_of_the_wrong_type(tmp_path):
    path = _manifest(tmp_path, top={"deck_hash": 5}, shapes=[{**_SHAPE, "font_pt": "x"}])
    assert read_manifest(path, records=False)["deck_hash"] == 5


_WRITTEN_AS = {
    "str": "text",
    "str | None": "text",
    "Rendered": "text",
    "int": "whole",
    "float | None": "number",
    "bool": "flag",
    "list[str]": "texts",
    "list[float]": "numbers",
    "Box": "box",
}


@pytest.mark.parametrize(
    ("record", "table", "elsewhere"),
    [
        (Provenance, TOP_FIELDS, set()),
        (SlideRecord, SLIDE_FIELDS, {"index", *RECORD_FIELDS}),
        (ShapeRecord, RECORD_FIELDS["shapes"][2], set()),
        (PlacementRecord, RECORD_FIELDS["placements"][2], set()),
    ],
    ids=["provenance", "slide", "shape", "placement"],
)
def test_every_field_a_build_records_is_checked_as_the_type_it_is_written(record, table, elsewhere):
    written = {f.name: _WRITTEN_AS[str(f.type)] for f in fields(record) if f.name not in elsewhere}
    assert {name: table.get(name) for name in written} == written


def test_a_long_record_name_is_cut_short_in_the_refusal(tmp_path):
    path = _manifest(tmp_path, shapes=[{**_SHAPE, "name": "n" * 300, "font_pt": "x"}])
    assert _refusal(path) == f"font_pt of slide 1's shape '{'n' * 38}… is 'x', not a number"


def test_every_top_level_key_a_build_writes_is_checked():
    written = set(ManifestRecorder(deck="d.pptx", theme="t").to_dict()) - {"slides"}
    assert written == set(TOP_FIELDS)


def test_every_key_an_animation_records_is_checked():
    recorder = ManifestRecorder(deck="d.pptx", theme="t")
    recorder.begin_slide(1, background="page")
    recorder.record_animation("click_sequence", [[2]], clicks=1, trigger=3)
    assert set(recorder.slides[-1].animations[0]) == set(RECORD_FIELDS["animations"][2])
