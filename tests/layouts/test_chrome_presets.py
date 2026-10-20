"""`chrome: side` and `chrome: statement`: one word for a whole chrome treatment."""

from __future__ import annotations

import json

import pytest

from deckwright.compile import build_deck
from deckwright.errors import LayoutError, SpecError

_HEAD = "theme: base\ntitle: T\nout: out/P.pptx\n---\n"


def _shapes(tmp_path, slide):
    spec = tmp_path / "p.deck.yaml"
    spec.write_text(_HEAD + slide)
    data = json.loads(build_deck(spec).manifest.read_text())["slides"][0]
    return {s["name"]: s["box"] for s in data["shapes"]}, data["placements"]


def test_side_stacks_the_chrome_in_the_left_third_and_gives_the_body_the_rest(tmp_path):
    shapes, placements = _shapes(
        tmp_path,
        "kicker: K\ntitle: A title in its own column\nchrome: side\n"
        "place:\n  - {at: {cols: full}, card: {heading: Body}}\n",
    )
    title, body = shapes["s1.chrome.title"], placements[0]["box"]
    # base: a 0.8in margin and 11.733in of content; its left third is 3.75in wide.
    assert title["x"] == pytest.approx(0.8, abs=0.01)
    assert title["w"] == pytest.approx(3.75, abs=0.05)
    assert title["y"] > 1.2  # starts where the body starts, not in the header
    # Two of base's 0.2in gutters past the rail's 4.578in right edge, so the gap reads as an edge.
    assert body["x"] == pytest.approx(4.978, abs=0.01)
    assert body["x"] + body["w"] == pytest.approx(0.8 + 11.733, abs=0.01)


def test_side_reads_a_placements_columns_as_fractions_of_the_band_beside_it(tmp_path):
    _, placements = _shapes(
        tmp_path,
        "title: T\nchrome: side\nplace:\n"
        "  - {at: {cols: left-half}, card: {heading: A}}\n"
        "  - {at: {cols: right-half}, card: {heading: B}}\n",
    )
    left, right = (p["box"] for p in placements)
    assert left["w"] == pytest.approx(right["w"], abs=0.01)
    assert right["x"] + right["w"] == pytest.approx(0.8 + 11.733, abs=0.01)


def test_statement_sets_its_lines_centred_and_the_title_at_the_display_rung(tmp_path):
    from pptx import Presentation
    from pptx.oxml.ns import qn

    spec = tmp_path / "p.deck.yaml"
    spec.write_text(
        _HEAD + "kicker: K\ntitle: Keep this one line\nsubtitle: S\nchrome: statement\n"
    )
    built = build_deck(spec)
    data = json.loads(built.manifest.read_text())["slides"][0]
    (title,) = [s for s in data["shapes"] if s["name"] == "s1.chrome.title"]
    assert title["font_pt"] == 46.0  # base's display rung
    # The boxes are symmetric about the slide's middle, so only the paragraphs show centring.
    lines = {
        s.name: {p.get("algn") for p in s._element.iter(qn("a:pPr"))}
        for s in Presentation(str(built.deck)).slides[0].shapes
        if s.name.startswith("s1.chrome.")
    }
    assert lines == {f"s1.chrome.{n}": {"ctr"} for n in ("kicker", "title", "subtitle")}


@pytest.mark.parametrize(
    ("slide", "error", "match"),
    [
        ("title: T\nchrome: sideways\n", SpecError, "or one of side, statement"),
        (
            "chrome: side\nplace:\n  - {at: {cols: full}, card: {heading: H}}\n",
            SpecError,
            "has none of them",
        ),
        (
            "title: " + " ".join(["A very long title that keeps going"] * 8) + "\nchrome: side\n",
            LayoutError,
            "past the",
        ),
        (
            "title: "
            + " ".join(["A very long title that keeps going"] * 8)
            + "\nchrome: statement\n",
            LayoutError,
            r"its box is only .* shorten it, or drop 'chrome: statement'",
        ),
    ],
)
def test_a_preset_that_cannot_be_placed_is_refused_by_name(tmp_path, slide, error, match):
    spec = tmp_path / "p.deck.yaml"
    spec.write_text(_HEAD + slide)
    with pytest.raises(error, match=match):
        build_deck(spec)
