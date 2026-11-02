"""Reading a hand-edited deck back against the build that made it."""

from __future__ import annotations

import json

import pytest
from pptx.util import Inches

from deckwright.compile.readback import read_back, render_drift
from deckwright.errors import SpecError


@pytest.fixture
def built(project):
    """A real build: a deck, and the manifest that describes it."""
    from deckwright.compile import build_deck

    (project / "d.deck.yaml").write_text(
        "theme: testtheme\nout: out/D.pptx\n---\ntitle: A title\n"
        "place:\n  - at: {cols: full}\n    bullets: {items: [alpha, beta]}\n"
    )
    return build_deck(project / "d.deck.yaml", theme_path=project / "testtheme.yaml")


def _edit(deck, change):
    from pptx import Presentation

    prs = Presentation(str(deck))
    change(prs.slides[0])
    prs.save(str(deck))


def _named(slide, name):
    return [sh for sh in slide.shapes if sh.name == name][0]


def test_an_untouched_deck_reads_back_as_unedited(built):
    drift = read_back(built.deck)
    assert drift.edited is False
    assert drift.changes == ()


def test_a_moved_shape_is_reported_with_both_rectangles(built):
    _edit(
        built.deck,
        lambda s: setattr(
            _named(s, "s1.chrome.title"), "left", _named(s, "s1.chrome.title").left + Inches(1)
        ),
    )
    drift = read_back(built.deck)
    assert drift.edited is True
    moved = drift.of("moved")
    assert [c.shape for c in moved] == ["s1.chrome.title"]
    assert "→" in moved[0].detail


def test_a_nudge_below_the_tolerance_is_not_a_move(built):
    """The manifest rounds to a thousandth; float dust is not an edit."""
    _edit(
        built.deck,
        lambda s: setattr(
            _named(s, "s1.chrome.title"), "left", _named(s, "s1.chrome.title").left + 900
        ),
    )
    assert read_back(built.deck).of("moved") == []


def test_retyped_text_is_reported_against_what_was_built(built):
    def retype(slide):
        _named(slide, "s1.chrome.title").text_frame.paragraphs[0].runs[0].text = "Other"

    _edit(built.deck, retype)
    retyped = read_back(built.deck).of("retyped")
    assert [c.shape for c in retyped] == ["s1.chrome.title"]
    assert "'A title' → 'Other'" in retyped[0].detail


def test_a_shape_added_by_hand_says_no_placement_made_it(built):
    _edit(built.deck, lambda s: s.shapes.add_textbox(Inches(1), Inches(6), Inches(2), Inches(0.4)))
    added = read_back(built.deck).of("added")
    assert len(added) == 1
    assert "added by hand" in added[0].detail


def test_a_shape_deleted_by_hand_is_reported_gone(built):
    def drop(slide):
        shape = _named(slide, "s1.p1.bullets#1")
        shape._element.getparent().remove(shape._element)

    _edit(built.deck, drop)
    assert [c.shape for c in read_back(built.deck).of("gone")] == ["s1.p1.bullets#1"]


def test_one_frame_answers_for_every_line_it_carries(project):
    """Chrome records one manifest row per line but draws one shape named `sN.chrome`, so
    matching from the manifest side reports every line missing."""
    from deckwright.compile import build_deck

    (project / "c.deck.yaml").write_text(
        "theme: testtheme\nout: out/C.pptx\n---\nkicker: K\ntitle: T\nsubtitle: S\n"
    )
    made = build_deck(project / "c.deck.yaml", theme_path=project / "testtheme.yaml")
    drift = read_back(made.deck)
    assert drift.of("gone") == []
    assert drift.of("added") == []


def test_a_deck_with_no_manifest_says_how_to_get_one(built):
    built.manifest.unlink()
    with pytest.raises(SpecError, match="manifest not found"):
        read_back(built.deck)


def test_a_manifest_recording_no_deck_hash_cannot_call_it_edited(built):
    """An older manifest has nothing to compare, and guessing 'edited' would cry wolf."""
    data = json.loads(built.manifest.read_text())
    del data["deck_hash"]
    built.manifest.write_text(json.dumps(data))
    _edit(built.deck, lambda s: s.shapes.add_textbox(Inches(1), Inches(6), Inches(2), Inches(0.4)))
    assert read_back(built.deck).edited is False


def test_the_report_names_the_spec_to_carry_the_edit_back_into(built):
    _edit(
        built.deck,
        lambda s: setattr(
            _named(s, "s1.chrome.title"), "left", _named(s, "s1.chrome.title").left + Inches(1)
        ),
    )
    report = render_drift(read_back(built.deck))
    assert "d.deck.yaml" in report
    assert "**moved** `s1.chrome.title`" in report


def test_an_unedited_deck_reports_that_there_is_nothing_to_carry_back(built):
    assert "nothing to carry back" in render_drift(read_back(built.deck))


def _wrap_in_alternate_content(slide, name, *, fallback=True):
    """Move ``name`` into an ``mc:AlternateContent``: a Choice holding a copy with other
    words, and the original as the Fallback."""
    import copy

    from lxml import etree

    mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    shape = _named(slide, name)._element
    alternate = etree.Element(f"{{{mc}}}AlternateContent", nsmap={"mc": mc})
    shape.addprevious(alternate)
    choice = etree.SubElement(alternate, f"{{{mc}}}Choice", Requires="a14")
    bare = copy.deepcopy(shape)
    for text in bare.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t"):
        text.text = "only a reader of a14 sees this"
    choice.append(bare)
    if fallback:
        etree.SubElement(alternate, f"{{{mc}}}Fallback").append(shape)
    else:
        shape.getparent().remove(shape)


def test_a_shape_inside_markup_compatibility_is_read_from_its_fallback(built):
    """python-pptx skips `mc:AlternateContent`, which reported every equation or 3D model
    `gone`. The Fallback is what a reader of no extension namespace takes."""
    _edit(built.deck, lambda s: _wrap_in_alternate_content(s, "s1.p1.bullets#1"))
    drift = read_back(built.deck)
    assert drift.edited is True
    assert drift.changes == ()


def test_markup_compatibility_with_no_fallback_is_read_from_its_choice(built):
    _edit(built.deck, lambda s: _wrap_in_alternate_content(s, "s1.p1.bullets#1", fallback=False))
    assert read_back(built.deck).of("gone") == []


@pytest.fixture
def parts(project):
    """A build holding a table and a chart: two frames whose parts are records, not shapes."""
    from deckwright.compile import build_deck

    (project / "p.deck.yaml").write_text(
        "theme: testtheme\nout: out/P.pptx\n---\ntitle: Parts\n"
        "place:\n"
        "  - at: {cols: left-half}\n"
        "    table: {header: [A, B], rows: [[1, 2], [3, 4]]}\n"
        "  - at: {cols: right-half}\n"
        "    chart:\n"
        "      kind: column\n"
        "      data:\n"
        "        - {category: Q1, value: 1}\n"
        "        - {category: Q2, value: 2}\n"
        "        - {category: Q3, value: 3}\n"
        "        - {category: Q4, value: 4}\n"
    )
    return build_deck(project / "p.deck.yaml", theme_path=project / "testtheme.yaml")


def test_a_table_and_a_chart_read_back_clean_from_their_own_build(parts):
    """A frame `…table#1` owns `…table.r1c1`, and `…chart#1` owns `…chart.labels`: neither is
    a shape, so without that claim every cell and chart part is gone from an untouched deck."""
    drift = read_back(parts.deck)
    assert drift.edited is False
    assert drift.changes == ()


@pytest.fixture
def three(project):
    from deckwright.compile import build_deck

    (project / "t.deck.yaml").write_text(
        "theme: testtheme\nout: out/T.pptx\n---\ntitle: One\n---\ntitle: Two\n---\ntitle: Three\n"
    )
    return build_deck(project / "t.deck.yaml", theme_path=project / "testtheme.yaml")


def _saved_as(built, name, change):
    """A hand-edited copy beside the build, read back against the build's own manifest."""
    from pptx import Presentation

    prs = Presentation(str(built.deck))
    change(prs)
    copy = built.deck.with_name(name)
    prs.save(str(copy))
    return read_back(copy, manifest=built.manifest)


def test_a_deleted_slide_is_reported_once_and_later_slides_still_match(three):
    """A slide's number is read off its `sN.` names. Matched by position instead, slide 3's
    chrome is gone from slide 2 and added to it."""
    from deckwright.utils.deck import delete_slide

    drift = _saved_as(three, "T cut.pptx", lambda prs: delete_slide(prs, 1))
    assert [(c.kind, c.slide, c.shape) for c in drift.changes] == [("slide-gone", 2, "slide 2")]


def test_a_slide_pasted_in_by_hand_is_reported_added(three):
    """No shape on it carries an `sN.` name, and the foreign name raises nothing."""

    def paste(prs):
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        for shape in list(slide.shapes):
            shape._element.getparent().remove(shape._element)
        slide.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1)).name = "Group 7"

    drift = _saved_as(three, "T plus.pptx", paste)
    assert [(c.kind, c.slide, c.shape) for c in drift.changes] == [("slide-added", 4, "slide 4")]


def test_the_built_deck_names_its_build_in_its_core_properties(three):
    from pptx import Presentation

    build_id = json.loads(three.manifest.read_text())["build_id"]
    assert Presentation(str(three.deck)).core_properties.identifier == f"deckwright:{build_id}"


def test_a_renamed_copy_finds_its_manifest_by_build_id(three):
    """Save As under another name leaves no sibling manifest; the deck's own build id finds it."""
    import shutil

    copy = shutil.copy(three.deck, three.deck.with_name("Sent to client.pptx"))
    drift = read_back(copy)
    assert drift.edited is False
    assert drift.changes == ()


def test_a_copy_with_no_manifest_anywhere_says_which_build_it_wanted(three, tmp_path):
    import shutil

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    copy = shutil.copy(three.deck, elsewhere / "T.pptx")
    with pytest.raises(SpecError, match=r"no manifest in .* records build deckwright:[0-9a-f]+"):
        read_back(copy)


def test_an_older_manifest_without_a_build_id_still_reads_back(three):
    data = json.loads(three.manifest.read_text())
    del data["build_id"]
    three.manifest.write_text(json.dumps(data))
    assert read_back(three.deck).changes == ()


@pytest.fixture
def card(project):
    from deckwright.compile import build_deck

    (project / "c.deck.yaml").write_text(
        "theme: testtheme\nout: out/C.pptx\n---\ntitle: One card\n"
        "place:\n  - at: {cols: left-half, rows: {from: 1, to: 6}}\n    id: q\n"
        "    card: {heading: The question, body: What went wrong}\n"
    )
    return build_deck(project / "c.deck.yaml", theme_path=project / "testtheme.yaml")


def test_a_resized_recoloured_and_relabelled_shape_reads_back(card):
    """Select the box, set a size and a colour, tick nothing else: the three edits a presenter
    makes most, each of which used to be "a change this cannot see"."""
    from pptx.dml.color import RGBColor
    from pptx.util import Pt

    from deckwright.utils.a11y import describe

    def change(prs):
        plate, words = (s for s in prs.slides[0].shapes if s.name.startswith("s1.q.card#"))
        runs = [r for p in words.text_frame.paragraphs for r in p.runs]
        runs[0].font.size = Pt(40)
        for run in runs:
            run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
        describe(plate, alt="A plate")

    drift = _saved_as(card, "C edited.pptx", change)
    got = {(c.kind, c.shape): c.detail for c in drift.changes}
    assert got == {
        ("restyled", "s1.q.card#2"): "size 18/13.5pt → 40/13.5pt; colour 1A1D21 → FF0000",
        ("relabelled", "s1.q.card#1"): "alt none → 'A plate'",
    }


def test_swatches_read_back_clean_from_their_own_build(project):
    """A chip's label frame holds the role and its hex; recorded as the role alone, every
    chip on an untouched deck read back retyped."""
    from deckwright.compile import build_deck

    (project / "s.deck.yaml").write_text(
        "theme: testtheme\nout: out/S.pptx\n---\ntitle: Swatches\n"
        "place:\n  - at: {cols: full}\n    swatches: {roles: [ink, accent-1]}\n"
    )
    built = build_deck(project / "s.deck.yaml", theme_path=project / "testtheme.yaml")
    assert read_back(built.deck).changes == ()


@pytest.fixture
def revealing(project):
    from deckwright.compile import build_deck

    (project / "r.deck.yaml").write_text(
        "theme: testtheme\nout: out/R.pptx\n---\ntitle: Click the question\n"
        "place:\n"
        "  - at: {cols: left-half, rows: {from: 1, to: 6}}\n    id: q\n"
        "    card: {heading: The question, body: What went wrong}\n"
        "  - at: {cols: right-half, rows: {from: 1, to: 6}}\n    reveals: q\n"
        "    card: {heading: The answer, body: One bug.}\n"
    )
    return build_deck(project / "r.deck.yaml", theme_path=project / "testtheme.yaml")


def test_an_animation_removed_by_hand_reads_back_as_retimed(revealing):
    """The timing tree is read with the readers `qa` uses. A trigger PowerPoint added to the
    confirmation kit's deck 04 read back as "no shape differs" before this."""

    def strip(prs):
        slide = prs.slides[0]._element
        slide.remove(
            slide.find("{http://schemas.openxmlformats.org/presentationml/2006/main}timing")
        )

    drift = _saved_as(revealing, "R still.pptx", strip)
    assert [(c.kind, c.slide, c.shape, c.detail) for c in drift.changes] == [
        (
            "retimed",
            1,
            "slide 1",
            "0 click(s), 2 shape(s) revealed, 1 trigger(s) → 0 click(s), 0 shape(s) revealed, 0 trigger(s)",
        )
    ]


def test_a_picture_ticked_decorative_by_hand_says_so(card):
    """The decorative mark outranks the alt text it clears: PowerPoint's own tick on the kit's
    deck 06 read back as an alt change before the order was fixed."""
    from deckwright.utils.a11y import describe

    def tick(prs):
        plate = next(s for s in prs.slides[0].shapes if s.name == "s1.q.card#1")
        describe(plate, decorative=True)

    drift = _saved_as(card, "C ticked.pptx", tick)
    assert [(c.kind, c.shape, c.detail) for c in drift.changes] == [
        ("relabelled", "s1.q.card#1", "marked decorative")
    ]


@pytest.fixture
def pushed(project, theme_yaml):
    """Three slides on a theme whose show arrives by a slow push."""
    from deckwright.compile import build_deck

    (project / "testtheme.yaml").write_text(
        theme_yaml + "motion:\n  transition: {kind: push, dir: u, speed: slow}\n"
    )
    (project / "t.deck.yaml").write_text(
        "theme: testtheme\nout: out/T.pptx\n---\ntitle: One\n---\ntitle: Two\ntransition: none\n"
        "---\ntitle: Three\n"
    )
    return build_deck(project / "t.deck.yaml", theme_path=project / "testtheme.yaml")


def test_the_manifest_records_the_transition_each_slide_arrives_on(pushed):
    slides = json.loads(pushed.manifest.read_text())["slides"]
    assert [s["transition"] for s in slides] == ["push", "none", "push"]


def test_a_transition_changed_by_hand_reads_back(pushed):
    from lxml import etree

    ns = "http://schemas.openxmlformats.org/presentationml/2006/main"

    def fade(prs):
        node = prs.slides[2]._element.find(f"{{{ns}}}transition")
        for child in list(node):
            node.remove(child)
        etree.SubElement(node, f"{{{ns}}}fade")

    drift = _saved_as(pushed, "T faded.pptx", fade)
    assert [(c.kind, c.slide, c.shape, c.detail) for c in drift.changes] == [
        ("retimed", 3, "slide 3", "transition push → fade")
    ]


def test_a_manifest_that_records_no_transition_is_not_a_change(pushed):
    """A manifest written before the key existed: unrecorded is unknown, never `none`."""
    data = json.loads(pushed.manifest.read_text())
    for slide in data["slides"]:
        del slide["transition"]
    pushed.manifest.write_text(json.dumps(data))
    assert read_back(pushed.deck).changes == ()


@pytest.fixture
def staged(project):
    """Three bullets, one per click."""
    from deckwright.compile import build_deck

    (project / "b.deck.yaml").write_text(
        "theme: testtheme\nout: out/B.pptx\n---\ntitle: Staged\nanimate: one_at_a_time\n"
        "place:\n  - at: {cols: full}\n    bullets: {items: [alpha, beta, gamma]}\n"
    )
    return build_deck(project / "b.deck.yaml", theme_path=project / "testtheme.yaml")


def test_a_staged_build_reads_back_clean_from_its_own_deck(staged):
    assert json.loads(staged.manifest.read_text())["slides"][0]["animations"][0]["clicks"] == 3
    assert read_back(staged.deck).changes == ()


def test_a_click_removed_from_a_staged_build_reads_back_as_retimed(staged):
    ns = "http://schemas.openxmlformats.org/presentationml/2006/main"

    def drop_the_last_click(prs):
        timing = prs.slides[0]._element.find(f"{{{ns}}}timing")
        main = next(c for c in timing.iter(f"{{{ns}}}cTn") if c.get("nodeType") == "mainSeq")
        groups = main.find(f"{{{ns}}}childTnLst")
        groups.remove(groups[-1])

    drift = _saved_as(staged, "B short.pptx", drop_the_last_click)
    assert [(c.kind, c.detail) for c in drift.changes] == [
        (
            "retimed",
            "3 click(s), 1 shape(s) revealed, 0 trigger(s) → 2 click(s), 1 shape(s) revealed, 0 trigger(s)",
        )
    ]


def test_a_slide_duplicated_by_hand_is_reported_as_a_copy(three):
    """The copy carries its original's names, so it carries its number too. Matched by number
    alone, one of the two would answer for the slide and the other would vanish."""
    import copy

    def duplicate(prs):
        source = prs.slides[1]
        clone = prs.slides.add_slide(source.slide_layout)
        for shape in list(clone.shapes):
            shape._element.getparent().remove(shape._element)
        for shape in source.shapes:
            clone.shapes._spTree.append(copy.deepcopy(shape._element))

    drift = _saved_as(three, "T twice.pptx", duplicate)
    assert [(c.kind, c.slide, c.shape, c.detail) for c in drift.changes] == [
        ("slide-added", 4, "slide 4", "a copy of slide 2 — added by hand")
    ]


def test_a_slide_moved_by_hand_is_reported_and_still_read_against_its_own_records(three):
    def move_the_last_to_the_front(prs):
        ids = prs.slides._sldIdLst
        last = ids[-1]
        ids.remove(last)
        ids.insert(0, last)

    drift = _saved_as(three, "T moved.pptx", move_the_last_to_the_front)
    assert [(c.kind, c.slide, c.shape, c.detail) for c in drift.changes] == [
        ("slide-moved", 3, "slide 3", "built at 3 of 3, now at 1")
    ]
