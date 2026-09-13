"""Every component reports a motion role for each shape it reveals, so the theme's
`motion.roles` decides how each kind of thing enters.

Expectations are literal role names, group by group; ``None`` marks a bare shape id.
"""

from __future__ import annotations

import dataclasses

import pytest
from PIL import Image

import deckwright.components  # noqa: F401 — registers the built-ins
from deckwright.layouts.components import as_body_result, get_component
from deckwright.layouts.motion import apply_reveal

_CASES = {
    "prose": ({"paragraphs": ["One short paragraph."]}, [["text"]]),
    "bullets": ({"items": ["One", "Two"]}, [["text"], ["text"]]),
    "bullets-heading": ({"heading": "Why", "items": ["One"]}, [["text", "text"]]),
    "bullets-columns": ({"columns": 2, "items": ["One", "Two", "Three"]}, [["text"], ["text"]]),
    "card": ({"heading": "Heading", "body": "Body."}, [["surface", "text"]]),
    "card-icon": (
        {"heading": "Heading", "body": "Body.", "icon": "shield"},
        [["surface", "figure", "text"]],
    ),
    "panel": ({}, [["surface"]]),
    "ellipse": ({"label": "7"}, [["surface"]]),
    "icon": ({"name": "shield"}, [["figure"]]),
    "stats": ({"items": [{"value": "12", "label": "units"}]}, [["text"]]),
    "callouts": ({"items": [{"head": "A point"}]}, [["surface", "text"]]),
    "callouts-icon": ({"items": [{"head": "A point", "icon": "bolt"}]}, [["figure", "text"]]),
    "table": ({"rows": [["a", "b"], ["c", "d"]]}, [["text"]]),
    "swatches": ({"roles": ["accent-1"]}, [["surface", "text"]]),
    "versus": (
        {"left": {"value": "1", "label": "Before"}, "right": {"value": "2", "label": "After"}},
        [["surface", "text", "figure"], ["surface", "text"]],
    ),
    "diverge": (
        {"items": [{"label": "North", "value": 3}]},
        [["text", "surface", "text"]],
    ),
    "code": ({"lines": ["print('hi')"]}, [["text"]]),
    "rule": ({}, [["line"]]),
    "fanout": (
        {
            "source": "publish(post)",
            "items": [{"icon": "mail", "text": "Digest"}, {"text": "Cache"}],
        },
        [
            ["surface", "text", "line", "line"],
            ["line", "line", "figure", "text"],
            ["line", "line", "text"],
        ],
    ),
}


def _roles(groups):
    return [[item[1] if isinstance(item, tuple) else None for item in group] for group in groups]


@pytest.mark.parametrize("case", list(_CASES))
def test_a_component_reports_a_role_for_every_shape_it_reveals(ctx_factory, case):
    body, expected = _CASES[case]
    component = case.split("-")[0]
    ctx = ctx_factory({component: body})
    result = as_body_result(get_component(component)(ctx))
    assert _roles(result.groups) == expected


def test_an_image_reports_its_picture_as_a_figure(ctx_factory, tmp_path):
    photo = tmp_path / "p.png"
    Image.new("RGB", (400, 300), (40, 90, 160)).save(photo)
    ctx = ctx_factory({"image": {"src": str(photo)}})
    result = as_body_result(get_component("image")(ctx))
    assert _roles(result.groups) == [["figure"]]


def test_an_image_with_words_over_it_reports_the_words_as_text(ctx_factory, tmp_path):
    photo = tmp_path / "p.png"
    Image.new("RGB", (400, 300), (40, 90, 160)).save(photo)
    ctx = ctx_factory({"image": {"src": str(photo), "over": [{"text": "A caption"}]}})
    result = as_body_result(get_component("image")(ctx))
    assert _roles(result.groups)[0][0] == "figure"
    assert _roles(result.groups)[0][-1] == "text"


def test_a_flow_keeps_the_roles_its_parts_report(ctx_factory):
    ctx = ctx_factory({"flow": {"numbered": True, "items": [{"head": "Read"}, {"head": "Name"}]}})
    result = as_body_result(get_component("flow")(ctx))
    assert _roles(result.groups) == [
        ["surface", "surface", "text"],
        ["line", "surface", "surface", "text"],
    ]


def test_a_chart_reports_itself_as_a_datum(ctx_factory):
    ctx = ctx_factory(
        {
            "chart": {
                "kind": "column",
                "data": [{"category": "A", "value": 1}, {"category": "B", "value": 2}],
            }
        }
    )
    result = as_body_result(get_component("chart")(ctx))
    assert _roles(result.groups) == [["datum"]]


def _entrances(slide):
    """``spid -> (presetID, presetSubtype)`` for every entrance the slide's timing holds."""
    from pptx.oxml.ns import qn

    found = {}
    for ctn in slide._element.iter(qn("p:cTn")):
        if ctn.get("presetClass") != "entr":
            continue
        target = next(ctn.iter(qn("p:spTgt")))
        found[int(target.get("spid"))] = (ctn.get("presetID"), ctn.get("presetSubtype"))
    return found


def test_the_theme_binding_for_a_role_is_the_entrance_the_slide_writes(ctx_factory, theme):
    """`surface: wiperight, text: wipeup` must reach the timing XML as two different presets."""
    motion = dataclasses.replace(
        theme.motion, roles={**theme.motion.roles, "surface": "wiperight", "text": "wipeup"}
    )
    ctx = ctx_factory(
        {"card": {"heading": "Heading", "body": "Body."}},
        theme_override=dataclasses.replace(theme, motion=motion),
        animate="one_at_a_time",
    )
    groups = as_body_result(get_component("card")(ctx)).groups
    apply_reveal(ctx, groups)
    plate, text = (item[0] for item in groups[0])
    assert _entrances(ctx.slide)[plate] == ("22", "2")
    assert _entrances(ctx.slide)[text] == ("22", "1")


def test_a_grid_reports_its_bars_and_caption(ctx_factory):
    result = as_body_result(get_component("grid")(ctx_factory({"grid": {}})))
    roles = _roles(result.groups)
    assert set(roles[0]) == {"surface"}
    assert roles[-1] == ["text"]


def test_a_line_wipes_along_the_axis_it_runs_on(ctx_factory):
    """A vertical join wiping right has no width to wipe across, so it would just appear."""
    ctx = ctx_factory(
        {"flow": {"direction": "vertical", "items": [{"head": "Read"}, {"head": "Name"}]}},
        animate="one_at_a_time",
    )
    groups = as_body_result(get_component("flow")(ctx)).groups
    apply_reveal(ctx, groups)
    [join] = [item[0] for group in groups for item in group if item[1] == "line"]
    assert _entrances(ctx.slide)[join] == ("22", "1")


def test_a_horizontal_line_keeps_the_themes_wipe(ctx_factory):
    ctx = ctx_factory(
        {"flow": {"items": [{"head": "Read"}, {"head": "Name"}]}}, animate="one_at_a_time"
    )
    groups = as_body_result(get_component("flow")(ctx)).groups
    apply_reveal(ctx, groups)
    [join] = [item[0] for group in groups for item in group if item[1] == "line"]
    assert _entrances(ctx.slide)[join] == ("22", "2")
