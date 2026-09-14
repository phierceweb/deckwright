"""Reading a deck deckwright did not build, and the ``extract`` command around it."""

from __future__ import annotations

import copy
import re

import pytest
from pptx import Presentation
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.util import Emu, Inches, Pt
from typer.testing import CliRunner

from deckwright.cli import app
from deckwright.compile import build_deck
from deckwright.errors import SpecError
from deckwright.spec.draft import render_markdown, render_spec
from deckwright.spec.extract import MAX_GROUP_DEPTH, harvest

runner = CliRunner()

_CHROME_TEXT = {
    "kicker": "PART ONE",
    "title": "Revenue is up",
    "subtitle": "And the line beneath it",
}

# A 1x1 PNG, small enough to inline and real enough for python-pptx to measure.
_DOT_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000100ffff0300000600"
    "0557bfabd40000000049454e44ae426082"
)


@pytest.fixture
def foreign_deck(tmp_path):
    """A deck built by python-pptx alone — a stranger's deck, as far as deckwright knows."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Revenue is up"
    body = slide.placeholders[1].text_frame
    body.text = "North America grew 12%"
    body.add_paragraph().text = "EMEA grew 4%"
    slide.notes_slide.notes_text_frame.text = "Lead with the number."

    second = prs.slides.add_slide(prs.slide_layouts[5])
    second.shapes.title.text = "By region"
    table = second.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(6), Inches(1)).table
    table.cell(0, 0).text = "Region"
    table.cell(0, 1).text = "Growth"
    table.cell(1, 0).text = "EMEA"
    table.cell(1, 1).text = "4%"

    path = tmp_path / "foreign.pptx"
    prs.save(path)
    return path


@pytest.fixture
def deck_with_a_picture(tmp_path):
    """One slide carrying something extraction cannot turn into words."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "With art"
    png = tmp_path / "dot.png"
    png.write_bytes(_DOT_PNG)
    slide.shapes.add_picture(str(png), Inches(1), Inches(1))
    path = tmp_path / "art.pptx"
    prs.save(path)
    return path


@pytest.fixture
def deck_of_unlabelled_art(tmp_path):
    """An arrow and a blank band: drawn on purpose, holding no words."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "The process"
    slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(1), Inches(2), Inches(2), Inches(1))
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1), Inches(4), Inches(2), Inches(1))
    path = tmp_path / "process.pptx"
    prs.save(path)
    return path


def test_harvest_reads_the_title_the_body_and_the_notes(foreign_deck):
    first = harvest(foreign_deck)[0]
    assert first.index == 1
    assert first.title == "Revenue is up"
    assert first.blocks == (("North America grew 12%", "EMEA grew 4%"),)
    assert first.notes == "Lead with the number."


def test_harvest_reads_a_table_as_rows_of_cells(foreign_deck):
    second = harvest(foreign_deck)[1]
    assert second.title == "By region"
    assert second.tables == ((("Region", "Growth"), ("EMEA", "4%")),)


def test_harvest_names_what_it_could_not_convert(deck_with_a_picture):
    """A picture is not lost silently — the author is told it was there."""
    dropped = harvest(deck_with_a_picture)[0].dropped
    assert len(dropped) == 1
    assert "picture" in dropped[0].lower()


def test_harvest_reads_blocks_in_reading_order_not_shape_order(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    for text, top in (("lower", 4), ("upper", 1)):
        slide.shapes.add_textbox(
            Inches(1), Inches(top), Inches(4), Inches(1)
        ).text_frame.text = text
    path = tmp_path / "order.pptx"
    prs.save(path)

    assert harvest(path)[0].blocks == (("upper",), ("lower",))


def test_harvest_survives_a_shape_that_reports_no_offset(tmp_path):
    """A shape whose ``a:off`` is absent reads back as ``top is None``."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    placed = slide.shapes.add_textbox(Inches(1), Inches(4), Inches(4), Inches(1))
    placed.text_frame.text = "placed"
    adrift = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    adrift.text_frame.text = "adrift"
    xfrm = adrift._element.spPr.find(qn("a:xfrm"))
    xfrm.remove(xfrm.find(qn("a:off")))
    path = tmp_path / "adrift.pptx"
    prs.save(path)

    assert harvest(path)[0].blocks == (("adrift",), ("placed",))


def test_harvest_rejects_a_file_that_is_not_a_deck(tmp_path):
    not_a_deck = tmp_path / "notes.txt"
    not_a_deck.write_text("hello")
    with pytest.raises(SpecError):
        harvest(not_a_deck)


def test_a_shape_holding_no_words_is_named_rather_than_vanishing(deck_of_unlabelled_art):
    dropped = harvest(deck_of_unlabelled_art)[0].dropped
    assert len(dropped) == 2
    assert [item.split(" ", 1)[0] for item in dropped] == ["auto_shape", "auto_shape"]


def test_an_empty_text_box_is_not_reported_as_a_loss(tmp_path):
    """Nothing was ever placed in it, so there is nothing to tell the author about."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Nothing here"
    slide.shapes.add_textbox(Inches(1), Inches(2), Inches(2), Inches(1))
    path = tmp_path / "empty-box.pptx"
    prs.save(path)

    assert harvest(path)[0].dropped == ()


def test_a_draft_extracted_from_a_deck_builds_again(tmp_path, foreign_deck):
    """Two slides of a stranger's deck, extracted and compiled with no edit in between."""
    draft = tmp_path / "draft.deck.yaml"
    result = runner.invoke(app, ["extract", str(foreign_deck), "-o", str(draft)])
    assert result.exit_code == 0, result.output
    assert "2 slide(s)" in result.output

    built = build_deck(draft)
    assert built.slides == 2
    assert built.deck.is_file()


def test_an_unknown_output_format_is_rejected(foreign_deck):
    result = runner.invoke(app, ["extract", str(foreign_deck), "--as", "pdf"])
    assert result.exit_code != 0
    assert isinstance(result.exception, SpecError)


def test_the_transcript_form_writes_markdown_beside_the_deck(tmp_path, foreign_deck):
    result = runner.invoke(app, ["extract", str(foreign_deck), "--as", "md"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "foreign.md").read_text(encoding="utf-8").startswith("# foreign")


def test_a_missing_output_directory_is_created(tmp_path, foreign_deck):
    dest = tmp_path / "drafts" / "foreign.deck.yaml"
    result = runner.invoke(app, ["extract", str(foreign_deck), "-o", str(dest)])
    assert result.exit_code == 0, result.output
    assert dest.is_file()


def test_the_command_says_how_many_shapes_it_could_not_convert(deck_with_a_picture):
    result = runner.invoke(app, ["extract", str(deck_with_a_picture)])
    assert result.exit_code == 0, result.output
    assert "1 shape(s) could not be converted" in result.output


def test_repeated_losses_collapse_into_one_comment(tmp_path, deck_of_unlabelled_art):
    """The count stays one per shape; the comment naming them does not repeat."""
    draft = tmp_path / "process.deck.yaml"
    result = runner.invoke(app, ["extract", str(deck_of_unlabelled_art), "-o", str(draft)])
    assert result.exit_code == 0, result.output
    assert "2 shape(s) could not be converted" in result.output

    text = draft.read_text(encoding="utf-8")
    assert "# not converted: 2 × auto_shape" in text
    assert text.count("# not converted:") == 1


def test_a_draft_of_a_slide_holding_several_things_builds_too(tmp_path):
    """Blocks and a table on one slide: the case that overlaps unless each is banded."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "By region"
    for text, top in (("North America grew 12%", 2), ("EMEA grew 4%", 3)):
        slide.shapes.add_textbox(
            Inches(1), Inches(top), Inches(4), Inches(0.5)
        ).text_frame.text = text
    table = slide.shapes.add_table(2, 2, Inches(1), Inches(4), Inches(6), Inches(1)).table
    table.cell(0, 0).text = "Region"
    table.cell(0, 1).text = "Growth"
    table.cell(1, 0).text = "EMEA"
    table.cell(1, 1).text = "4%"
    source = tmp_path / "crowded.pptx"
    prs.save(source)

    draft = tmp_path / "crowded.deck.yaml"
    result = runner.invoke(app, ["extract", str(source), "-o", str(draft)])
    assert result.exit_code == 0, result.output
    assert build_deck(draft).deck.is_file()


def _grouped_deck(tmp_path, depth: int):
    """A text box ``depth`` groups deep, and a title beside the stack."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Strengths"
    shapes = slide.shapes
    for _ in range(depth):
        shapes = shapes.add_group_shape().shapes
    shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1)).text_frame.text = "internal"
    path = tmp_path / f"grouped{depth}.pptx"
    prs.save(path)
    return path


def test_words_two_groups_deep_are_read_and_the_group_is_not_a_loss(tmp_path):
    """A group is a container, not a leaf: the SWOT template's text sits inside two."""
    slide = harvest(_grouped_deck(tmp_path, depth=2))[0]
    assert slide.blocks == (("internal",),)
    assert slide.dropped == ()


def test_a_group_nested_past_the_depth_cap_is_named_rather_than_walked(tmp_path):
    slide = harvest(_grouped_deck(tmp_path, depth=MAX_GROUP_DEPTH + 1))[0]
    assert slide.blocks == ()
    assert [item.split(" ", 1)[0] for item in slide.dropped] == ["group"]


def test_an_unconvertible_shape_inside_a_group_is_named_in_its_own_right(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    group = slide.shapes.add_group_shape()
    arrow = group.shapes.add_shape(
        MSO_SHAPE.RIGHT_ARROW, Inches(1), Inches(1), Inches(2), Inches(1)
    )
    arrow.name = "Step 2 to 3"
    path = tmp_path / "grouped-arrow.pptx"
    prs.save(path)

    assert harvest(path)[0].dropped == ("auto_shape 'Step 2 to 3'",)


def test_a_group_reads_in_its_own_place_and_its_children_among_themselves(tmp_path):
    """A child's offset is in the group's child space, so it may not be sorted against
    a slide-level shape: here the children sit at 0.2in and 0.1in of a group whose own
    top is 5in, and a flat sort would read them before everything else on the slide."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text_frame.text = "first"
    group = slide.shapes.add_group_shape()
    for text, top in (("fourth", 0.2), ("third", 0.1)):
        group.shapes.add_textbox(
            Inches(1), Inches(top), Inches(4), Inches(0.05)
        ).text_frame.text = text
    group.top = Inches(5)
    slide.shapes.add_textbox(Inches(1), Inches(3), Inches(4), Inches(1)).text_frame.text = "second"
    path = tmp_path / "mixed.pptx"
    prs.save(path)

    assert harvest(path)[0].blocks == (("first",), ("second",), ("third",), ("fourth",))


def _named_deck(tmp_path, names: dict[str, str], *, sizes: dict[str, int] | None = None):
    """A deck carrying deckwright's own shape-name convention for chrome."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    for top, (name, text) in enumerate(names.items()):
        box = slide.shapes.add_textbox(Inches(1), Inches(1 + top), Inches(6), Inches(1))
        box.name = name
        box.text_frame.text = text
        if sizes and name in sizes:
            box.text_frame.paragraphs[0].runs[0].font.size = Pt(sizes[name])
    path = tmp_path / "named.pptx"
    prs.save(path)
    return path


def test_deckwright_own_chrome_is_read_off_the_shape_names(tmp_path):
    """A deck deckwright built has no title placeholder — its chrome is named text boxes."""
    path = _named_deck(
        tmp_path,
        {
            "s3.chrome.kicker": "PART ONE",
            "s3.chrome.title": "Revenue is up",
            "s3.chrome.subtitle": "And the line beneath it",
        },
    )
    slide = harvest(path)[0]
    assert (slide.kicker, slide.title, slide.subtitle) == (
        "PART ONE",
        "Revenue is up",
        "And the line beneath it",
    )
    assert slide.blocks == ()


def test_a_stacked_chrome_frame_is_split_by_the_type_it_is_set_in(tmp_path):
    """Three fields sharing one box collapse to ``s3.chrome``; only the type says which
    line is the title."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(3))
    box.name = "s3.chrome"
    frame = box.text_frame
    frame.text = "PART ONE"
    for text in ("Revenue is up", "And the line beneath it"):
        frame.add_paragraph().text = text
    for para, size in zip(frame.paragraphs, (13, 34, 16), strict=True):
        para.runs[0].font.size = Pt(size)
    path = tmp_path / "stacked.pptx"
    prs.save(path)

    slide = harvest(path)[0]
    assert (slide.kicker, slide.title, slide.subtitle) == (
        "PART ONE",
        "Revenue is up",
        "And the line beneath it",
    )


def test_a_real_title_placeholder_outranks_a_shape_named_for_the_same_field(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "The placeholder"
    named = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
    named.name = "s1.chrome.title"
    named.text_frame.text = "The named box"
    path = tmp_path / "both.pptx"
    prs.save(path)

    slide = harvest(path)[0]
    assert slide.title == "The placeholder"
    assert slide.blocks == (("The named box",),)


def test_a_second_claim_on_a_chrome_field_becomes_a_block_rather_than_vanishing(tmp_path):
    """Two title placeholders: one is the title, the other is still the deck's words."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "The first"
    second = copy.deepcopy(slide.shapes.title._element)
    slide.shapes._spTree.append(second)
    slide.shapes[-1].text_frame.text = "The second"
    path = tmp_path / "two-titles.pptx"
    prs.save(path)

    slide = harvest(path)[0]
    assert slide.title == "The first"
    assert slide.blocks == (("The second",),)


def test_a_lone_oversized_line_at_the_top_is_read_as_the_title(tmp_path):
    """Many foreign decks set the headline as an ordinary text box."""
    path = _named_deck(
        tmp_path,
        {"head": "Revenue is up", "body": "North America grew 12%"},
        sizes={"head": 40, "body": 14},
    )
    slide = harvest(path)[0]
    assert slide.title == "Revenue is up"
    assert slide.blocks == (("North America grew 12%",),)


def test_an_ordinary_top_line_is_not_promoted_to_the_title(tmp_path):
    """A wrong title is worse than no title, so a line set like its neighbours stays
    a body line."""
    path = _named_deck(
        tmp_path,
        {"head": "North America grew 12%", "body": "EMEA grew 4%"},
        sizes={"head": 16, "body": 14},
    )
    slide = harvest(path)[0]
    assert slide.title is None
    assert slide.blocks == (("North America grew 12%",), ("EMEA grew 4%",))


def _round_trip(tmp_path, generations: int) -> list[tuple[str, ...]]:
    """Build a deck, harvest it, redraft it, build again — ``generations`` times.

    Returns the body text read back at each generation.
    """
    spec = tmp_path / "g0.deck.yaml"
    spec.write_text(
        "theme: base\n"
        "title: Round Trip\n"
        f"out: {tmp_path / 'g1' / 'Round Trip v1.pptx'}\n"
        "---\n"
        "title: A worked example\n"
        "place:\n"
        "  - at: {cols: full}\n"
        "    bullets:\n"
        "      items: [a body line, another line]\n",
        encoding="utf-8",
    )
    read: list[tuple[str, ...]] = []
    for generation in range(1, generations + 1):
        content = harvest(build_deck(spec).deck)
        read.append(tuple(line for slide in content for block in slide.blocks for line in block))
        spec = tmp_path / f"g{generation}.deck.yaml"
        spec.write_text(
            render_spec(
                content,
                title="Round Trip",
                theme="base",
                out=str(tmp_path / f"g{generation + 1}" / "Round Trip v1.pptx"),
                source="a deck",
            ),
            encoding="utf-8",
        )
    return read


def test_three_generations_of_round_trip_are_a_fixed_point(tmp_path):
    """The bullets component writes its dot as run text, so each pass used to read one
    back and write it again: 'a body line', '•  a body line', '•  •  a body line'."""
    first, second, third = _round_trip(tmp_path, generations=3)
    assert first == ("a body line", "another line")
    assert second == first
    assert third == second


def test_a_leading_dot_a_foreign_deck_typed_is_kept(tmp_path):
    """Only a shape named for the bullets component carries a marker deckwright wrote — a
    stranger's dot, marker and all, is a word the author meant."""
    path = _named_deck(tmp_path, {"Body 2": "\u2022  a hand-typed dot"})
    assert harvest(path)[0].blocks == (("\u2022  a hand-typed dot",),)


def _stacked_deck(tmp_path, lines: dict[str, int]):
    """One chrome frame stacking ``lines``, each paragraph set at its own size."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(3))
    box.name = "s1.chrome"
    frame = box.text_frame
    for index, text in enumerate(lines):
        para = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        para.text = text
    for para, size in zip(frame.paragraphs, lines.values(), strict=True):
        para.runs[0].font.size = Pt(size)
    path = tmp_path / "stacked-chrome.pptx"
    prs.save(path)
    return path


def test_an_element_the_shape_tree_cannot_build_is_named_rather_than_aborting(tmp_path):
    """``p:contentPart`` is what PowerPoint writes for an ink annotation. python-pptx
    lists it as a shape tag but cannot build one, so iterating the tree used to raise."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes._spTree.append(parse_xml(f'<p:contentPart {nsdecls("p", "r")} r:id="rId9"/>'))
    path = tmp_path / "ink.pptx"
    prs.save(path)

    assert harvest(path)[0].dropped == ("p:contentPart — an element python-pptx cannot read",)


def test_an_element_the_shape_tree_never_enumerates_is_named_too(tmp_path):
    """PowerPoint wraps a 3D model or a newer-namespace effect in ``mc:AlternateContent``,
    which is not one of python-pptx's shape tags — so the slide read as empty."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes._spTree.append(
        parse_xml(
            "<mc:AlternateContent"
            ' xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"/>'
        )
    )
    path = tmp_path / "alternate.pptx"
    prs.save(path)

    assert harvest(path)[0].dropped == ("mc:AlternateContent — an element python-pptx cannot read",)


def test_a_group_that_yields_nothing_is_named_rather_than_vanishing(tmp_path):
    """An empty group is descended into and yields no leaf, so nothing else names it."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_group_shape().name = "Ungrouped art"
    path = tmp_path / "empty-group.pptx"
    prs.save(path)

    assert harvest(path)[0].dropped == ("group 'Ungrouped art'",)


def test_shapes_sharing_a_visual_row_read_left_to_right(tmp_path):
    """The SWOT template sets its four letters 1241 EMU — 0.0014in — apart, which an
    exact sort on ``top`` reads as four rows, one per letter, in the wrong order."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    letters = Inches(2)
    captions = Inches(4)
    for text, left, top in (
        ("W", 4, letters),
        ("S", 1, letters + 1241),
        ("T", 7, letters + 480),
        ("O", 5.5, letters + 900),
        ("Weaknesses", 4, captions),
        ("Strengths", 1, captions + 1100),
        ("Threats", 7, captions + 300),
        ("Opportunities", 5.5, captions + 760),
    ):
        box = slide.shapes.add_textbox(Inches(left), top, Inches(1.4), Inches(1))
        box.text_frame.text = text
    path = tmp_path / "swot.pptx"
    prs.save(path)

    assert harvest(path)[0].blocks == (
        ("S",),
        ("W",),
        ("O",),
        ("T",),
        ("Strengths",),
        ("Weaknesses",),
        ("Opportunities",),
        ("Threats",),
    )


def test_a_two_line_chrome_frame_is_named_by_which_side_of_the_larger_line_they_sit(tmp_path):
    """Two lines cannot say which two fields they are, so the larger is the title and
    the other is named for its side: a kicker over a subtitle reads as a kicker over a
    title, and every word is kept."""
    over = harvest(_stacked_deck(tmp_path, {"PART ONE": 13, "And the line beneath it": 16}))[0]
    assert (over.kicker, over.title, over.subtitle) == ("PART ONE", "And the line beneath it", None)
    assert over.blocks == ()

    under = harvest(_stacked_deck(tmp_path, {"Revenue is up": 34, "The line beneath": 16}))[0]
    assert (under.kicker, under.title, under.subtitle) == (
        None,
        "Revenue is up",
        "The line beneath",
    )
    assert under.blocks == ()


def test_a_stacked_kicker_over_a_title_is_still_split(tmp_path):
    """13pt under 34pt: the title is set clear of its kicker, so which is which is not
    in doubt."""
    path = _stacked_deck(tmp_path, {"PROBLEM": 13, "Three things are broken": 34})

    slide = harvest(path)[0]
    assert (slide.kicker, slide.title, slide.subtitle) == (
        "PROBLEM",
        "Three things are broken",
        None,
    )
    assert slide.blocks == ()


def test_a_foreign_shape_whose_name_merely_ends_in_chrome_is_not_chrome(tmp_path):
    """Every name deckwright writes is ``s<n>.chrome`` or ``s<n>.chrome.<field>``; a
    stranger's 'Diagram v1.chrome' used to take the slide's title with it."""
    path = _named_deck(
        tmp_path,
        {"Diagram v1.chrome": "Pipeline", "body": "and the words"},
        sizes={"Diagram v1.chrome": 14, "body": 32},
    )
    slide = harvest(path)[0]
    assert slide.title is None
    assert slide.blocks == (("Pipeline",), ("and the words",))


def _chrome_deck(tmp_path, fields: tuple[str, ...], *, rung: str | None = None):
    """A deck deckwright built carrying exactly ``fields`` as its chrome."""
    spec = tmp_path / "chrome.deck.yaml"
    lines = "".join(f"{name}: {_CHROME_TEXT[name]}\n" for name in fields)
    spec.write_text(
        f"theme: base\ntitle: Chrome\nout: {tmp_path / 'built' / 'Chrome v1.pptx'}\n---\n"
        + lines
        + (f"chrome: {{title: {{rung: {rung}}}}}\n" if rung else ""),
        encoding="utf-8",
    )
    return build_deck(spec).deck


def _chrome_sizes(deck) -> list[float]:
    """The point size of each paragraph in the slide's shared chrome frame."""
    shape = next(s for s in Presentation(str(deck)).slides[0].shapes if s.name == "s1.chrome")
    return [
        max(r.font.size.pt for r in p.runs if r.font.size is not None)
        for p in shape.text_frame.paragraphs
        if p.text.strip()
    ]


@pytest.mark.parametrize(
    "fields",
    [
        ("kicker",),
        ("title",),
        ("subtitle",),
        ("kicker", "title"),
        ("title", "subtitle"),
        ("kicker", "title", "subtitle"),
    ],
)
def test_a_chrome_field_deckwright_wrote_comes_back_as_itself(tmp_path, fields):
    slide = harvest(_chrome_deck(tmp_path, fields))[0]
    assert {name: getattr(slide, name) for name in _CHROME_TEXT if getattr(slide, name)} == {
        name: _CHROME_TEXT[name] for name in fields
    }
    assert slide.blocks == ()


def test_a_kicker_over_a_subtitle_keeps_both_lines_and_reads_the_lower_as_the_title(tmp_path):
    """The one combination two paragraphs cannot express: 13pt over 18pt is a kicker
    over a subtitle and a kicker over a small title alike."""
    deck = _chrome_deck(tmp_path, ("kicker", "subtitle"))
    assert _chrome_sizes(deck) == [13.0, 18.0]

    slide = harvest(deck)[0]
    assert (slide.kicker, slide.title, slide.subtitle) == (
        _CHROME_TEXT["kicker"],
        _CHROME_TEXT["subtitle"],
        None,
    )


def test_the_head_rung_keeps_all_three_fields_though_the_title_is_barely_larger(tmp_path):
    """``chrome: {title: {rung: head}}`` sets 13/22/18pt — a documented treatment whose
    title clears its kicker by a fifth, not by half."""
    deck = _chrome_deck(tmp_path, ("kicker", "title", "subtitle"), rung="head")
    assert _chrome_sizes(deck) == [13.0, 22.0, 18.0]

    slide = harvest(deck)[0]
    assert (slide.kicker, slide.title, slide.subtitle) == (
        _CHROME_TEXT["kicker"],
        _CHROME_TEXT["title"],
        _CHROME_TEXT["subtitle"],
    )


def _boxes(tmp_path, boxes: tuple[tuple[str, int, int, int], ...], name: str):
    """A slide of text boxes placed at exact EMU: text, left, top, height."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    for text, left, top, height in boxes:
        box = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(1600000), Emu(height))
        box.text_frame.text = text
    path = tmp_path / name
    prs.save(path)
    return path


def test_a_band_of_shapes_set_at_different_heights_reads_left_to_right(tmp_path):
    """One row of the industry 4.0 template's slide 8, at its own geometry: four boxes
    0.29in to 0.57in tall whose tops span 0.03in. Banding on the gap between tops reads
    the rightmost first, because it is the tallest and starts highest."""
    path = _boxes(
        tmp_path,
        (
            ("$ 64,090", 8921354, 4191327, 523220),
            ("Your Text Here", 4408344, 4211493, 276998),
            ("Easy to change colors", 6454778, 4211493, 482889),
            ("LOREM IPSUM DOLOR SIT AMET", 1121430, 4222105, 461665),
        ),
        "industry.pptx",
    )

    assert harvest(path)[0].blocks == (
        ("LOREM IPSUM DOLOR SIT AMET",),
        ("Your Text Here",),
        ("Easy to change colors",),
        ("$ 64,090",),
    )


def test_two_rows_that_barely_graze_each_other_stay_two_rows(tmp_path):
    """The opposite failure: too generous a band reads one row across both, which puts
    the lower-left line before the upper-right one."""
    path = _boxes(
        tmp_path,
        (
            ("upper right", 5000000, 1000000, 900000),
            ("lower left", 1000000, 1630000, 900000),
        ),
        "two-rows.pptx",
    )

    assert harvest(path)[0].blocks == (("upper right",), ("lower left",))


def _group_holding(tmp_path, xml: str, name: str):
    """A group of two text boxes with ``xml`` appended as a third child."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    group = slide.shapes.add_group_shape()
    for text, top in (("before", 1), ("after", 2)):
        group.shapes.add_textbox(
            Inches(1), Inches(top), Inches(4), Inches(0.4)
        ).text_frame.text = text
    group.shapes._element.append(parse_xml(xml))
    path = tmp_path / name
    prs.save(path)
    return path


def test_an_unreadable_element_inside_a_group_is_named_and_its_siblings_still_convert(tmp_path):
    """A group builds its children through a factory that inspects nothing, so an ink
    annotation comes back as a shape with no geometry to sort on."""
    path = _group_holding(
        tmp_path, f'<p:contentPart {nsdecls("p", "r")} r:id="rId9"/>', "grouped-ink.pptx"
    )

    slide = harvest(path)[0]
    assert slide.dropped == ("p:contentPart — an element python-pptx cannot read",)
    assert slide.blocks == (("before",), ("after",))


def test_an_alternate_content_wrapper_inside_a_group_is_named_too(tmp_path):
    """The wrapper PowerPoint writes for a 3D model or a newer-namespace effect."""
    path = _group_holding(
        tmp_path,
        "<mc:AlternateContent"
        ' xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"/>',
        "grouped-alternate.pptx",
    )

    slide = harvest(path)[0]
    assert slide.dropped == ("mc:AlternateContent — an element python-pptx cannot read",)
    assert slide.blocks == (("before",), ("after",))


def _solid(shape, rgb: str):
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(rgb)


def _rect(shapes, left, top, width, height, *, rgb: str = "12161B"):
    shape = shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    _solid(shape, rgb)
    return shape


def _canvas(prs, slide, *, rgb: str = "12161B"):
    return _rect(slide.shapes, Emu(0), Emu(0), prs.slide_width, prs.slide_height, rgb=rgb)


def _tinted(prs, slide, rgb: str, modifier: str):
    """A full-bleed solid whose RGB carries a colour transform, as PowerPoint writes
    a transparency or a 'darker 50%' swatch."""
    shape = _canvas(prs, slide, rgb=rgb)
    colour = shape._element.spPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
    colour.append(parse_xml(f'<a:{modifier} {nsdecls("a")} val="50000"/>'))


def _deck_painted(tmp_path, paint, *, words: bool = True):
    """A deck whose first slide ``paint(prs, slide)`` draws on, with one text box the
    author wrote beside whatever it drew."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    paint(prs, slide)
    if words:
        body = slide.shapes.add_textbox(Inches(1), Inches(3), Inches(6), Inches(1)).text_frame
        body.text = "A line the author wrote"
    path = tmp_path / "painted.pptx"
    prs.save(path)
    return path


@pytest.mark.parametrize(
    "paint",
    [
        pytest.param(_canvas, id="at the origin at canvas size"),
        pytest.param(
            lambda prs, s: _rect(
                s.shapes,
                -Inches(0.1),
                -Inches(0.1),
                prs.slide_width + Inches(0.2),
                prs.slide_height + Inches(0.2),
            ),
            id="bleeding past every edge",
        ),
        pytest.param(
            lambda prs, s: setattr(_canvas(prs, s), "rotation", 180.0), id="turned a half turn"
        ),
        pytest.param(
            lambda prs, s: _rect(
                s.shapes, Emu(0), Emu(0), prs.slide_width - Pt(0.5), prs.slide_height - Pt(0.5)
            ),
            id="half a point short, inside the slack",
        ),
    ],
)
def test_a_shape_covering_the_canvas_is_read_as_the_slides_background(tmp_path, paint):
    slide = harvest(_deck_painted(tmp_path, paint))[0]
    assert slide.background_rgb == "12161B"
    assert slide.dropped == (), "the background is converted, so it is not a loss"
    assert slide.blocks == (("A line the author wrote",),)


@pytest.mark.parametrize(
    "paint",
    [
        pytest.param(
            lambda prs, s: _rect(
                s.shapes, Emu(0), Emu(0), prs.slide_width - Inches(1), prs.slide_height - Inches(1)
            ),
            id="at the origin, short of both edges",
        ),
        pytest.param(
            lambda prs, s: _rect(
                s.shapes, Emu(0), Emu(0), prs.slide_width - Inches(1), prs.slide_height
            ),
            id="short in width only",
        ),
        pytest.param(
            lambda prs, s: _rect(
                s.shapes, Emu(0), Emu(0), prs.slide_width, prs.slide_height - Inches(1)
            ),
            id="short in height only",
        ),
        pytest.param(
            lambda prs, s: _rect(
                s.shapes, Emu(0), Emu(0), prs.slide_width - Pt(2), prs.slide_height
            ),
            id="two points short in width",
        ),
        pytest.param(
            lambda prs, s: _rect(
                s.shapes, Emu(0), Emu(0), prs.slide_width, prs.slide_height - Pt(2)
            ),
            id="two points short in height",
        ),
        pytest.param(
            lambda prs, s: _rect(s.shapes, Inches(2), Inches(2), prs.slide_width, prs.slide_height),
            id="canvas-sized but inset from the origin",
        ),
        pytest.param(
            lambda prs, s: setattr(_canvas(prs, s), "rotation", 45.0), id="turned a quarter"
        ),
        pytest.param(lambda prs, s: _canvas(prs, s).fill.gradient(), id="a gradient"),
        pytest.param(
            lambda prs, s: setattr(
                _canvas(prs, s).fill.fore_color, "theme_color", MSO_THEME_COLOR.ACCENT_1
            ),
            id="a scheme colour",
        ),
        pytest.param(lambda prs, s: _tinted(prs, s, "000000", "alpha"), id="a translucent solid"),
        pytest.param(lambda prs, s: _tinted(prs, s, "FFFFFF", "lumMod"), id="white darkened 50%"),
    ],
)
def test_a_shape_that_does_not_paint_the_whole_canvas_in_one_colour_is_art(tmp_path, paint):
    slide = harvest(_deck_painted(tmp_path, paint))[0]
    assert slide.background_rgb is None
    assert len(slide.dropped) == 1, "it is art the author has to put back"
    assert slide.blocks == (("A line the author wrote",),)


def test_words_typed_into_the_full_bleed_panel_are_harvested_with_its_colour(tmp_path):
    """A section divider with its headline typed into the painted panel itself."""

    def paint(prs, slide):
        shape = _canvas(prs, slide, rgb="1E3A5F")
        shape.text_frame.text = "Section Two: the words live on the painted panel"

    slide = harvest(_deck_painted(tmp_path, paint, words=False))[0]
    assert slide.background_rgb == "1E3A5F"
    assert slide.blocks == (("Section Two: the words live on the painted panel",),)
    assert slide.dropped == ()


def test_of_two_full_bleed_solids_the_one_on_top_is_the_background(tmp_path):
    """Document order is z order, so the later shape is the one the slide shows; the
    one beneath it is covered, not lost."""

    def paint(prs, slide):
        _canvas(prs, slide, rgb="12161B")
        _canvas(prs, slide, rgb="1F5FA8")

    slide = harvest(_deck_painted(tmp_path, paint))[0]
    assert slide.background_rgb == "1F5FA8"
    assert slide.dropped == ()


def test_a_group_child_filling_its_own_child_space_is_not_the_slides_background(tmp_path):
    """A child's offsets are in the group's space: this one reports the canvas but is
    drawn two inches square."""

    def paint(prs, slide):
        group = slide.shapes.add_group_shape()
        _rect(group.shapes, Emu(0), Emu(0), prs.slide_width, prs.slide_height, rgb="A8431C")
        xfrm = group._element.grpSpPr.get_or_add_xfrm()
        xfrm.get_or_add_off().x, xfrm.get_or_add_off().y = Inches(4), Inches(3)
        xfrm.get_or_add_ext().cx, xfrm.get_or_add_ext().cy = Inches(2), Inches(2)
        xfrm.get_or_add_chOff().x = xfrm.get_or_add_chOff().y = 0
        xfrm.get_or_add_chExt().cx, xfrm.get_or_add_chExt().cy = prs.slide_width, prs.slide_height

    slide = harvest(_deck_painted(tmp_path, paint))[0]
    assert slide.background_rgb is None
    assert len(slide.dropped) == 1


def test_a_slides_own_background_fill_is_read(tmp_path):
    """Real decks paint a slide through ``p:bg``, not a shape."""

    def paint(prs, slide):
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor.from_string("FFB55A")

    slide = harvest(_deck_painted(tmp_path, paint))[0]
    assert slide.background_rgb == "FFB55A"
    assert slide.dropped == ()


def test_a_slide_background_in_a_scheme_colour_is_not_read(tmp_path):
    def paint(prs, slide):
        slide.background.fill.solid()
        slide.background.fill.fore_color.theme_color = MSO_THEME_COLOR.ACCENT_1

    assert harvest(_deck_painted(tmp_path, paint))[0].background_rgb is None


def test_a_full_bleed_shape_paints_over_the_slides_own_background(tmp_path):
    def paint(prs, slide):
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor.from_string("FFB55A")
        _canvas(prs, slide, rgb="12161B")

    assert harvest(_deck_painted(tmp_path, paint))[0].background_rgb == "12161B"


def test_a_full_bleed_picture_is_art_rather_than_a_background(tmp_path):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    png = tmp_path / "dot.png"
    png.write_bytes(_DOT_PNG)
    s.shapes.add_picture(str(png), Emu(0), Emu(0), prs.slide_width, prs.slide_height)
    path = tmp_path / "photo.pptx"
    prs.save(path)
    slide = harvest(path)[0]
    assert slide.background_rgb is None
    assert len(slide.dropped) == 1


def test_the_backgrounds_a_deckwright_deck_declares_come_back_by_name(tmp_path):
    spec = tmp_path / "d.deck.yaml"
    spec.write_text(
        "theme: base\ntitle: Painted\nout: d.pptx\n"
        "---\nbackground: inverse\ntitle: A dark cover\n"
        "---\ntitle: An ordinary page\n"
        "---\nbackground: accent-1\ntitle: An opener\n",
        encoding="utf-8",
    )
    build_deck(spec)
    text = render_spec(harvest(tmp_path / "d.pptx"), title="Painted", theme="base")
    assert re.findall(r"^background: (.+)$", text, re.M) == ["inverse", "accent-1"]


def test_a_named_title_frame_outranks_a_stacked_frames_positional_guess(tmp_path):
    """``chrome: {title: {at: {box: …}}}`` boxes the title alone and stacks the other
    two, so the stack's lower line is the subtitle, not a small title."""
    spec = tmp_path / "boxed.deck.yaml"
    spec.write_text(
        f"theme: base\ntitle: Boxed\nout: {tmp_path / 'boxed.pptx'}\n---\n"
        "kicker: PART ONE\ntitle: Revenue is up\nsubtitle: And the line beneath it\n"
        "chrome: {title: {at: {box: {x: '5%', y: '60%', w: '90%', h: '20%'}}}}\n",
        encoding="utf-8",
    )
    slide = harvest(build_deck(spec).deck)[0]
    assert (slide.kicker, slide.title, slide.subtitle) == (
        "PART ONE",
        "Revenue is up",
        "And the line beneath it",
    )
    assert slide.blocks == ()


def test_a_named_title_frame_outranks_a_one_line_stack_read_above_it(tmp_path):
    """A lone stacked line can only be guessed as the title; the frame named for the
    title is not a guess, wherever it sits on the slide."""
    path = _named_deck(tmp_path, {"s1.chrome": "PART ONE", "s1.chrome.title": "Revenue is up"})
    slide = harvest(path)[0]
    assert slide.title == "Revenue is up"
    assert slide.blocks == (("PART ONE",),)


def test_two_stacked_lines_set_at_one_size_are_a_kicker_over_its_title(tmp_path):
    """``chrome: {kicker: {rung: title}}`` with no subtitle: a tie is the documented
    kicker treatment, not a title over a subtitle at the title's own size."""
    slide = harvest(_stacked_deck(tmp_path, {"KICK": 34, "The Title": 34}))[0]
    assert (slide.kicker, slide.title, slide.subtitle) == ("KICK", "The Title", None)


def test_an_empty_paragraph_between_stacked_lines_does_not_shift_their_sizes(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(3))
    box.name = "s1.chrome"
    frame = box.text_frame
    frame.text = "PART ONE"
    frame.paragraphs[0].runs[0].font.size = Pt(13)
    frame.add_paragraph()
    title = frame.add_paragraph()
    title.text = "Revenue is up"
    title.runs[0].font.size = Pt(34)
    path = tmp_path / "gapped.pptx"
    prs.save(path)

    slide = harvest(path)[0]
    assert (slide.kicker, slide.title, slide.subtitle) == ("PART ONE", "Revenue is up", None)


def test_a_stacked_frame_of_four_lines_keeps_every_line_past_the_title_as_subtitle(tmp_path):
    lines = {"PART ONE": 13, "Revenue is up": 34, "line three": 16, "line four": 16}
    slide = harvest(_stacked_deck(tmp_path, lines))[0]
    assert slide.subtitle == "line three line four"


def _sized_boxes(tmp_path, boxes: tuple[tuple[tuple[str, ...], float, int], ...]):
    """Text boxes of ``(paragraphs, top in inches, point size)``, one below another."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    for paragraphs, top, size in boxes:
        frame = slide.shapes.add_textbox(Inches(1), Inches(top), Inches(6), Inches(0.6)).text_frame
        frame.text = paragraphs[0]
        for text in paragraphs[1:]:
            frame.add_paragraph().text = text
        for para in frame.paragraphs:
            para.runs[0].font.size = Pt(size)
    path = tmp_path / "sized.pptx"
    prs.save(path)
    return path


def test_a_multi_line_top_block_is_never_promoted_to_the_title(tmp_path):
    """Promoting it would keep its first line and lose the rest."""
    path = _sized_boxes(
        tmp_path,
        (
            (("Revenue is up", "and margins too"), 1, 40),
            (("point 0",), 3, 14),
            (("point 1",), 4, 14),
            (("point 2",), 5, 14),
        ),
    )
    slide = harvest(path)[0]
    assert slide.title is None
    assert slide.blocks == (
        ("Revenue is up", "and margins too"),
        ("point 0",),
        ("point 1",),
        ("point 2",),
    )


def test_a_later_line_as_large_as_the_head_keeps_the_head_a_body_line(tmp_path):
    """A closing 'Questions?' set like the opener says neither is the title."""
    path = _sized_boxes(
        tmp_path,
        (
            (("Revenue is up",), 1, 40),
            (("point 0",), 2.2, 12),
            (("point 1",), 3.4, 12),
            (("point 2",), 4.6, 12),
            (("Questions?",), 5.8, 40),
        ),
    )
    slide = harvest(path)[0]
    assert slide.title is None
    assert slide.blocks[0] == ("Revenue is up",)
    assert slide.blocks[-1] == ("Questions?",)


def test_a_wordless_shape_in_the_band_does_not_decide_which_row_a_label_reads_in(tmp_path):
    """One card of the social-media template's slide 26: a tall picture placeholder
    beside a short label and a percentage. Banded on the placeholder, the label falls
    to the next row and the far-right percentage reads before it."""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.96), Inches(1), Inches(1.1))
    for text, left, top, height in (
        ("75%", 11.61, 1.98, 0.57),
        ("Add Text Here", 3.23, 2.1, 0.34),
    ):
        box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(1.5), Inches(height))
        box.text_frame.text = text
    path = tmp_path / "card.pptx"
    prs.save(path)

    slide = harvest(path)[0]
    assert slide.blocks == (("Add Text Here",), ("75%",))
    assert len(slide.dropped) == 1


def test_a_connector_across_a_row_of_groups_does_not_split_the_row(tmp_path):
    """A real template's geometry, in pixels: three text groups on one band, and a low
    arrow that starts level with the middle one."""
    px = 9525
    prs = Presentation()
    prs.slide_width, prs.slide_height = 1280 * px, 720 * px
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    for text, left, top, width, height in (
        ("Add Text", 544, 442, 190, 122),
        ("Content Here", 58, 477, 184, 117),
        ("Easy to change colors", 1040, 480, 184, 117),
    ):
        group = slide.shapes.add_group_shape()
        box = group.shapes.add_textbox(left * px, top * px, width * px, height * px)
        box.text_frame.text = text
    slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, 640 * px, 442 * px, 1033 * px, 509 * px)
    path = tmp_path / "connector-row.pptx"
    prs.save(path)

    slide = harvest(path)[0]
    assert slide.blocks == (("Content Here",), ("Add Text",), ("Easy to change colors",))


def test_a_caption_starting_beside_a_tall_panel_does_not_join_its_row(tmp_path):
    """The overlap covers the caption's height but a tenth of the panel's."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    for text, left, top, height in (("panel", 4, 1.0, 4.0), ("caption", 1, 1.2, 0.4)):
        box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(2), Inches(height))
        box.text_frame.text = text
    path = tmp_path / "panel.pptx"
    prs.save(path)

    assert harvest(path)[0].blocks == (("panel",), ("caption",))


def _deck_with_soft_breaks(tmp_path):
    """A text box, a table cell and the notes, each carrying an ``<a:br/>``."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1)).text_frame
    box.text = "altered version."
    box.paragraphs[0].add_line_break()
    box.paragraphs[0].add_run().text = "Promulgate it."
    cell = slide.shapes.add_table(1, 1, Inches(1), Inches(3), Inches(4), Inches(1)).table.cell(0, 0)
    cell.text = "first half"
    cell.text_frame.paragraphs[0].add_line_break()
    cell.text_frame.paragraphs[0].add_run().text = "second half"
    notes = slide.notes_slide.notes_text_frame
    notes.text = "line one"
    notes.paragraphs[0].add_line_break()
    notes.paragraphs[0].add_run().text = "line two"
    path = tmp_path / "breaks.pptx"
    prs.save(path)
    return path


def test_a_soft_line_break_is_a_space_never_a_control_character(tmp_path):
    """python-pptx returns ``<a:br/>`` as U+000B and writes it back out as literal
    ``_x000B_`` on the slide, so the draft may carry it nowhere."""
    path = _deck_with_soft_breaks(tmp_path)
    slides = harvest(path)
    assert slides[0].blocks == (("altered version. Promulgate it.",),)
    assert slides[0].tables == ((("first half second half",),),)
    assert slides[0].notes == "line one\nline two"

    draft = tmp_path / "breaks.deck.yaml"
    draft.write_text(render_spec(slides, title="Breaks", out="b.pptx"))
    build_deck(draft)
    xml = "".join(
        p.text_frame.text
        for s in Presentation(tmp_path / "b.pptx").slides
        for p in s.shapes
        if p.has_text_frame
    )
    assert "_x000B_" not in xml and "\x0b" not in xml


def test_harvest_carries_a_figures_alt_text_and_skips_a_file_name(tmp_path):
    from deckwright.utils.a11y import describe

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    png = tmp_path / "dot.png"
    png.write_bytes(_DOT_PNG)
    described = slide.shapes.add_picture(str(png), Inches(1), Inches(1))
    describe(described, alt="The team,\n  at the summit")
    described.name = "Summit"
    slide.shapes.add_picture(str(png), Inches(3), Inches(1)).name = "Unnamed"
    path = tmp_path / "alt.pptx"
    prs.save(path)

    content = harvest(path)[0]

    assert content.alt == ("picture 'Summit': The team, at the summit",)
    assert "# alt text on picture 'Summit': The team, at the summit" in render_spec(
        [content], title="Deck"
    )
    assert "*alt text on picture 'Summit': The team, at the summit*" in render_markdown(
        [content], title="Deck"
    )


def test_harvest_writes_a_hyperlinked_run_back_as_link_markup(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    frame = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1)).text_frame
    paragraph = frame.paragraphs[0]
    for text, address in (
        ("Read ", None),
        ("the guide", "https://example.com/g"),
        (" [1](x)", None),
    ):
        run = paragraph.add_run()
        run.text = text
        if address:
            run.hyperlink.address = address
    path = tmp_path / "linked.pptx"
    prs.save(path)

    assert harvest(path)[0].blocks == (("Read [the guide](https://example.com/g) \\[1](x)",),)


def test_stacked_chrome_keeps_its_links_through_extract(tmp_path):
    from deckwright.compile import build_deck

    spec = tmp_path / "c.deck.yaml"
    spec.write_text(
        "theme: base\nout: c.pptx\n---\nkicker: KICK\n"
        "title: 'A [linked](https://t.example.com) title'\n"
        "subtitle: 'The [subtitle](https://s.example.com)'\n"
    )
    build_deck(spec)
    slide = harvest(tmp_path / "c.pptx")[0]
    assert slide.title == "A [linked](https://t.example.com) title"
    assert slide.subtitle == "The [subtitle](https://s.example.com)"


def test_copy_that_reads_as_a_link_without_being_one_is_escaped_in_the_draft(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    frame = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1)).text_frame
    frame.text = "print('[x](https://code.example.com)')"
    path = tmp_path / "literal.pptx"
    prs.save(path)
    assert harvest(path)[0].blocks == ((r"print('\[x](https://code.example.com)')",),)


def test_harvest_carries_a_drawn_shapes_alt_text_too(tmp_path):
    """A glyph icon is a freeform with an empty text frame, not a picture."""
    from deckwright.compile import build_deck

    spec = tmp_path / "i.deck.yaml"
    spec.write_text(
        "theme: base\nout: i.pptx\n---\ntitle: T\nplace:\n  - at: {cols: full}\n"
        "    icon: {name: target, alt: Hit the quarterly target}\n"
    )
    build_deck(spec)
    assert harvest(tmp_path / "i.pptx")[0].alt == (
        "freeform 's1.p1.icon#1': Hit the quarterly target",
    )
