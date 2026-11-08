"""Reading a hand-edited deck back against the build that made it."""

from __future__ import annotations

import json

import pytest
from pptx.oxml.ns import qn
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


def _unhashed(built):
    data = json.loads(built.manifest.read_text())
    del data["deck_hash"]
    built.manifest.write_text(json.dumps(data))


def test_a_manifest_recording_no_deck_hash_reports_what_differs(built):
    """An older manifest has nothing to compare the file against: whether it was edited is
    unknown, not false, and what differs is still read."""
    _unhashed(built)
    _edit(built.deck, lambda s: s.shapes.add_textbox(Inches(1), Inches(6), Inches(2), Inches(0.4)))
    drift = read_back(built.deck)
    assert drift.edited is None
    assert [c.kind for c in drift.changes] == ["added"]


def test_the_report_without_a_deck_hash_says_the_edit_is_unknown(built):
    _unhashed(built)
    _edit(built.deck, lambda s: s.shapes.add_textbox(Inches(1), Inches(6), Inches(2), Inches(0.4)))
    lines = render_drift(read_back(built.deck)).splitlines()
    assert lines[2].startswith("Whether it was edited since its build from `")
    assert lines[2].endswith("d.deck.yaml` is unknown: D.manifest.json records no file hash.")
    assert lines[4] == "## Slide 1"


def test_the_report_without_a_deck_hash_and_no_change_says_no_shape_differs(built):
    _unhashed(built)
    lines = render_drift(read_back(built.deck)).splitlines()
    assert lines[2].startswith("Whether it was edited")
    assert lines[4] == "No shape differs from the build."


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
    with pytest.raises(
        SpecError, match=r"no manifest deckwright can read in .* records build deckwright:[0-9a-f]+"
    ):
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


_MORPHS = (
    "theme: testtheme\nout: out/M.pptx\n---\n"
    "title: One\nplace:\n  - at: {cols: full}\n    bullets: {items: [alpha, beta]}\n---\n"
    "title: Two\nplace:\n  - at: {cols: full}\n    bullets: {items: [gamma, delta]}\n---\n"
    "place:\n  - at: {cols: left-half}\n    morph: fig\n    card: {heading: Left, body: words}\n"
    "---\ntransition: morph\nplace:\n  - at: {cols: right-half}\n    morph: fig\n"
    "    card: {heading: Left, body: words}\n---\ntitle: Five\n"
)
_GONE = "the build made this slide and the deck no longer has it"
_ADDED = "not in the build — added by hand"


@pytest.fixture
def morphs(project):
    """Two titled slides, a titleless morph pair that moves a card from the left half to the
    right, and a titled last slide."""
    from deckwright.compile import build_deck

    (project / "m.deck.yaml").write_text(_MORPHS)
    return build_deck(project / "m.deck.yaml", theme_path=project / "testtheme.yaml")


def _changes(drift):
    return [(c.kind, c.slide, c.shape, c.detail) for c in drift.changes]


def _swap_the_morph_slides(prs):
    ids = prs.slides._sldIdLst
    third = ids[2]
    ids.remove(third)
    ids.insert(3, third)


def _retype_the_left_card(prs, position):
    frame = _named(prs.slides[position], "m.fig.card#2")
    frame.text_frame.paragraphs[0].runs[0].text = "Changed"


def _paste_slide_twos_bullets_onto_slide_one(prs):
    import copy

    source = _named(prs.slides[1], "s2.p1.bullets#1")
    prs.slides[0].shapes._spTree.insert(2, copy.deepcopy(source._element))


def test_a_slide_deleted_ahead_of_morph_slides_is_the_only_change(morphs):
    """The morph slides carry no number: matched by place they would be read against each
    other's records."""
    from deckwright.utils.deck import delete_slide

    drift = _saved_as(morphs, "M cut.pptx", lambda prs: delete_slide(prs, 0))
    assert _changes(drift) == [("slide-gone", 1, "slide 1", _GONE)]


def test_morph_slides_swapped_by_hand_read_as_one_move(morphs):
    drift = _saved_as(morphs, "M swapped.pptx", _swap_the_morph_slides)
    assert _changes(drift) == [("slide-moved", 3, "slide 3", "built at 3 of 5, now at 4")]


def test_a_morph_slide_retyped_in_place_still_reads_as_retyped(morphs):
    """Its shapes no longer match where it sits, but it is the one slide of the build that
    can lie between its neighbours and shares their names."""
    drift = _saved_as(morphs, "M retyped.pptx", lambda prs: _retype_the_left_card(prs, 2))
    assert _changes(drift) == [("retyped", 3, "m.fig.card#2", "'Left words' → 'Changed words'")]


def test_a_shape_pasted_from_another_slide_reads_as_added_where_it_landed(morphs):
    """The pasted shape carries slide 2's number ahead of slide 1's own shapes."""
    drift = _saved_as(morphs, "M pasted.pptx", _paste_slide_twos_bullets_onto_slide_one)
    assert _changes(drift) == [("added", 1, "s2.p1.bullets#1", _pasted(2))]


def test_a_slide_holding_another_slides_shape_keeps_its_own_after_that_slide_goes(morphs):
    """Slide 2 carries two of its own shapes and one of slide 1's."""
    from deckwright.utils.deck import delete_slide

    def paste_then_delete(prs):
        _paste(prs, 0, "s1.chrome.title", 1)
        delete_slide(prs, 0)

    drift = _saved_as(morphs, "M merged.pptx", paste_then_delete)
    assert _changes(drift) == [
        ("slide-gone", 1, "slide 1", _GONE),
        ("added", 2, "s1.chrome.title", _pasted(1)),
    ]


def test_every_shape_grouped_by_hand_keeps_its_slide(morphs):
    def group(prs):
        slide = prs.slides[1]
        slide.shapes.add_group_shape(list(slide.shapes))

    drift = _saved_as(morphs, "M grouped.pptx", group)
    assert drift.changes == ()


_HELD = (
    "theme: testtheme\nout: out/H.pptx\n---\ntitle: One\n---\n"
    "place:\n  - at: {cols: left-half}\n    morph: fig\n    card: {heading: Held, body: words}\n"
    "---\ntransition: morph\nplace:\n  - at: {cols: right-half}\n    morph: fig\n"
    "    card: {heading: Held, body: words}\n"
    "---\ntransition: morph\nplace:\n  - at: {cols: right-half}\n    morph: fig\n"
    "    card: {heading: Held, body: words}\n"
)


def test_one_of_two_held_morph_slides_deleted_is_one_slide_gone(project):
    """Slides 3 and 4 draw the same shapes in the same place: the survivor answers for the
    record where it now sits, and only the last is gone."""
    from deckwright.compile import build_deck
    from deckwright.utils.deck import delete_slide

    (project / "h.deck.yaml").write_text(_HELD)
    held = build_deck(project / "h.deck.yaml", theme_path=project / "testtheme.yaml")
    drift = _saved_as(held, "H cut.pptx", lambda prs: delete_slide(prs, 2))
    assert _changes(drift) == [("slide-gone", 4, "slide 4", _GONE)]


def test_a_morph_slide_moved_and_retyped_is_added_and_gone(morphs):
    """Neither its place nor its shapes say which slide it was, so it is not read against
    another slide's records."""

    def swap_and_retype(prs):
        _swap_the_morph_slides(prs)
        _retype_the_left_card(prs, 3)

    drift = _saved_as(morphs, "M swapped retyped.pptx", swap_and_retype)
    assert _changes(drift) == [
        (
            "slide-added",
            4,
            "slide 4",
            "its morph shapes match no slide of the build — added by hand, or moved and "
            "edited both",
        ),
        ("slide-gone", 3, "slide 3", _GONE),
    ]


def test_a_slide_numbered_past_the_build_is_added(morphs):
    def renumber(prs):
        for shape in prs.slides[4].shapes:
            shape.name = "s9." + shape.name.partition(".")[2]

    drift = _saved_as(morphs, "M renumbered.pptx", renumber)
    assert _changes(drift) == [
        ("slide-added", 5, "slide 5", _ADDED),
        ("slide-gone", 5, "slide 5", _GONE),
    ]


def _grouped(slide, *names):
    return slide.shapes.add_group_shape([_named(slide, name) for name in names])


def _shifted(built, name, dx):
    """The `moved` detail for the record ``name`` drawn ``dx`` inches to the right."""
    records = json.loads(built.manifest.read_text())["slides"][0]["shapes"]
    was = next(r["box"] for r in records if r["name"] == name)
    before = f"{was['x']:g},{was['y']:g} {was['w']:g}×{was['h']:g}in"
    return f"{before} → {was['x'] + dx:g},{was['y']:g} {was['w']:g}×{was['h']:g}in"


def test_shapes_grouped_by_hand_read_back_unchanged(built):
    _edit(built.deck, lambda s: _grouped(s, "s1.p1.bullets#1"))
    drift = read_back(built.deck)
    assert drift.edited is True
    assert drift.changes == ()


def test_a_group_moved_by_hand_moves_each_shape_in_it(built):
    def group_and_move(slide):
        _grouped(slide, "s1.p1.bullets#1").left += Inches(1)

    _edit(built.deck, group_and_move)
    assert _changes(read_back(built.deck)) == [
        ("moved", 1, "s1.p1.bullets#1", _shifted(built, "s1.p1.bullets#1", 1))
    ]


def test_a_shape_added_inside_a_hand_group_is_added(built):
    def group_with_a_stranger(slide):
        group = _grouped(slide, "s1.p1.bullets#1")
        note = group.shapes.add_textbox(Inches(1), Inches(6), Inches(2), Inches(0.4))
        note.name = "Note"
        note.text_frame.text = "a note"

    _edit(built.deck, group_with_a_stranger)
    assert [(c.kind, c.shape) for c in read_back(built.deck).changes] == [("added", "Note")]


def test_a_nested_hand_group_moved_reads_in_slide_space(built):
    def nest_and_move(slide):
        inner = _grouped(slide, "s1.p1.bullets#1")
        slide.shapes.add_group_shape([inner]).left += Inches(1)

    _edit(built.deck, nest_and_move)
    assert _changes(read_back(built.deck)) == [
        ("moved", 1, "s1.p1.bullets#1", _shifted(built, "s1.p1.bullets#1", 1))
    ]


def test_an_equation_inside_a_hand_group_is_read_from_its_fallback(built):
    def wrap_and_group(slide):
        _wrap_in_alternate_content(slide, "s1.chrome.title")
        group = slide.shapes.add_group_shape([])
        mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
        group._element.append(slide.shapes._spTree.find(f"{{{mc}}}AlternateContent"))

    _edit(built.deck, wrap_and_group)
    assert read_back(built.deck).changes == ()


def _add_empty_picture_placeholder(slide):
    """What python-pptx clones onto a new slide from a layout holding one: a `p:sp` with a
    `p:ph`, no words and no picture."""
    from pptx.oxml import parse_xml
    from pptx.oxml.ns import nsdecls

    slide.shapes._spTree.append(
        parse_xml(
            f'<p:sp {nsdecls("p", "a")}><p:nvSpPr><p:cNvPr id="90" name="Picture Placeholder 1"/>'
            '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="pic" idx="10"/>'
            "</p:nvPr></p:nvSpPr><p:spPr/></p:sp>"
        )
    )


def test_an_empty_layout_placeholder_is_not_a_hand_edit(built):
    """The build never records it, and nobody can add a placeholder to a slide by hand."""
    _edit(built.deck, _add_empty_picture_placeholder)
    assert read_back(built.deck).changes == ()


_PLATED = (
    "theme: base\ntitle: T\nout: out/P.pptx\n---\nbackground: inverse\n"
    "kicker: PART 2\ntitle: At noon, sunlight takes a short path through the air\n"
    "subtitle: Straight down through the layer.\nplace:\n"
    "  - {at: {box: {x: 0%, y: 13%, w: 40%, h: 4%}}, bleed: true, panel: {pair: page}}\n"
)


def test_a_chrome_frame_does_not_answer_for_the_plate_beside_it(project):
    """The plate the build lays under a chrome line is a shape of its own,
    `s1.chrome.subtitle.plate`, recorded ahead of the frame's lines. Claimed by the frame
    `s1.chrome` as a dotted child, its box would be read as the frame's."""
    from pptx import Presentation

    from deckwright.compile import build_deck

    (project / "p.deck.yaml").write_text(_PLATED)
    built = build_deck(project / "p.deck.yaml")
    names = [s.name for s in Presentation(str(built.deck)).slides[0].shapes]
    assert {"s1.chrome.subtitle.plate", "s1.chrome"} <= set(names)
    assert read_back(built.deck).changes == ()


def test_a_table_put_in_a_layout_placeholder_by_hand_is_added(built):
    """PowerPoint inserts a table into a content placeholder as a `p:graphicFrame` that keeps
    its `p:ph`: a placeholder, and filled."""

    def tabled(slide):
        frame = slide.shapes.add_table(2, 2, Inches(1), Inches(6), Inches(3), Inches(1))
        frame.name = "Table 9"
        nv = frame._element.find(qn("p:nvGraphicFramePr")).find(qn("p:nvPr"))
        nv.append(nv.makeelement(qn("p:ph"), {"idx": "1"}))

    _edit(built.deck, tabled)
    assert [(c.kind, c.shape) for c in read_back(built.deck).changes] == [("added", "Table 9")]


_MORPH_ADDED = (
    "its morph shapes match no slide of the build — added by hand, or moved and edited both"
)
_HELD_APART = (
    "theme: testtheme\nout: out/A.pptx\n---\ntitle: One\n---\n"
    "place:\n  - at: {cols: left-half}\n    morph: fig\n    card: {heading: Held, body: words}\n"
    "---\ntransition: morph\nplace:\n  - at: {cols: right-half}\n    morph: fig\n"
    "    card: {heading: Held, body: words}\n"
    "---\ntransition: none\nplace:\n  - at: {cols: right-half}\n    morph: fig\n"
    "    card: {heading: Held, body: words}\n---\ntitle: Five\n"
)
_TITLED_MORPH = (
    "theme: testtheme\nout: out/T.pptx\n---\ntitle: One\n---\ntitle: Two\nplace:\n"
    "  - at: {cols: left-half}\n    morph: fig\n    card: {heading: Left, body: words}\n"
    "---\ntransition: morph\nplace:\n  - at: {cols: right-half}\n    morph: fig\n"
    "    card: {heading: Left, body: words}\n---\ntitle: Four\n"
)


def _build(project, name, spec):
    from deckwright.compile import build_deck

    (project / f"{name}.deck.yaml").write_text(spec)
    return build_deck(project / f"{name}.deck.yaml", theme_path=project / "testtheme.yaml")


def _move(prs, source, target):
    """Move the slide at ``source`` (from 0) so it sits at ``target``."""
    ids = prs.slides._sldIdLst
    moved = ids[source]
    ids.remove(moved)
    ids.insert(target, moved)


def _duplicate_to_the_end(prs, index):
    import copy

    source = prs.slides[index]
    clone = prs.slides.add_slide(source.slide_layout)
    for shape in list(clone.shapes):
        shape._element.getparent().remove(shape._element)
    for shape in source.shapes:
        clone.shapes._spTree.append(copy.deepcopy(shape._element))


def test_a_slide_deleted_ahead_of_two_held_morph_slides_is_the_only_change(project):
    """Slides 3 and 4 are drawn alike: matched by place, the survivor at 3 took slide 3's
    records and slide 4's twin read as moved."""
    from deckwright.utils.deck import delete_slide

    held = _build(project, "h", _HELD)
    drift = _saved_as(held, "H first cut.pptx", lambda prs: delete_slide(prs, 0))
    assert _changes(drift) == [("slide-gone", 1, "slide 1", _GONE)]


def test_a_slide_moved_past_two_held_morph_slides_is_the_only_move(project):
    held = _build(project, "h", _HELD)
    drift = _saved_as(held, "H first last.pptx", lambda prs: _move(prs, 0, 3))
    assert _changes(drift) == [("slide-moved", 1, "slide 1", "built at 1 of 4, now at 4")]


def test_of_two_held_slides_on_different_transitions_the_deleted_one_is_gone(project):
    """The deck keeps the transition each slide arrives on, which says which twin is left."""
    from deckwright.utils.deck import delete_slide

    apart = _build(project, "a", _HELD_APART)
    drift = _saved_as(apart, "A cut.pptx", lambda prs: delete_slide(prs, 2))
    assert _changes(drift) == [("slide-gone", 3, "slide 3", _GONE)]


def test_of_two_held_slides_on_different_transitions_the_moved_one_moved(project):
    apart = _build(project, "a", _HELD_APART)
    drift = _saved_as(apart, "A moved.pptx", lambda prs: _move(prs, 3, 1))
    assert _changes(drift) == [("slide-moved", 4, "slide 4", "built at 4 of 5, now at 2")]


def test_a_hand_slide_holding_a_morph_card_does_not_take_the_retyped_slides_records(morphs):
    """Two slides without numbers between the same neighbours: the one carrying all of the
    build slide's morph names is that slide, retyped; the other holds one copied card."""
    import copy

    def compete(prs):
        source = prs.slides[2]
        added = prs.slides.add_slide(source.slide_layout)
        for shape in list(added.shapes):
            shape._element.getparent().remove(shape._element)
        added.shapes._spTree.append(copy.deepcopy(_named(source, "m.fig.card#2")._element))
        _named(added, "m.fig.card#2").left += Inches(1)
        _move(prs, 5, 2)
        _retype_the_left_card(prs, 3)

    drift = _saved_as(morphs, "M compete.pptx", compete)
    assert _changes(drift) == [
        ("slide-added", 3, "slide 3", _MORPH_ADDED),
        ("retyped", 3, "m.fig.card#2", "'Left words' → 'Changed words'"),
    ]


def test_a_duplicated_morph_slide_is_reported_as_a_copy(morphs):
    drift = _saved_as(morphs, "M twice.pptx", lambda prs: _duplicate_to_the_end(prs, 3))
    assert _changes(drift) == [("slide-added", 6, "slide 6", "a copy of slide 4 — added by hand")]


def test_an_empty_slide_after_a_deleted_one_keeps_its_records(project):
    from deckwright.utils.deck import delete_slide

    spec = (
        "theme: testtheme\nout: out/E.pptx\n---\ntitle: One\n---\ntitle: Two\n---\n"
        "transition: none\n---\ntitle: Four\n"
    )
    empty = _build(project, "e", spec)
    drift = _saved_as(empty, "E cut.pptx", lambda prs: delete_slide(prs, 0))
    assert _changes(drift) == [("slide-gone", 1, "slide 1", _GONE)]


def test_two_morph_slides_retyped_in_place_read_as_retyped(morphs):
    def retype_both(prs):
        _retype_the_left_card(prs, 2)
        _retype_the_left_card(prs, 3)

    drift = _saved_as(morphs, "M both.pptx", retype_both)
    assert _changes(drift) == [
        ("retyped", 3, "m.fig.card#2", "'Left words' → 'Changed words'"),
        ("retyped", 4, "m.fig.card#2", "'Left words' → 'Changed words'"),
    ]


def test_a_morph_slide_moved_earlier_and_retyped_is_added_and_gone(morphs):
    def swap_and_retype(prs):
        _swap_the_morph_slides(prs)
        _retype_the_left_card(prs, 2)

    drift = _saved_as(morphs, "M earlier.pptx", swap_and_retype)
    assert _changes(drift) == [
        ("slide-added", 3, "slide 3", _MORPH_ADDED),
        ("slide-gone", 4, "slide 4", _GONE),
    ]


def test_the_last_morph_slide_retyped_in_place_reads_as_retyped(project):
    held = _build(project, "h", _HELD)
    drift = _saved_as(held, "H last.pptx", lambda prs: _retype_the_left_card(prs, 3))
    assert _changes(drift) == [("retyped", 4, "m.fig.card#2", "'Held words' → 'Changed words'")]


def test_a_titled_morph_slide_cut_leaves_the_untitled_one_paired(project):
    """Slide 2 is numbered and carries the morph card too; the untitled slide 3 retyped beside
    the gap is still slide 3."""
    from deckwright.utils.deck import delete_slide

    def cut_and_retype(prs):
        delete_slide(prs, 1)
        _retype_the_left_card(prs, 1)

    titled = _build(project, "t", _TITLED_MORPH)
    drift = _saved_as(titled, "T cut.pptx", cut_and_retype)
    assert _changes(drift) == [
        ("slide-gone", 2, "slide 2", _GONE),
        ("retyped", 3, "m.fig.card#2", "'Left words' → 'Changed words'"),
    ]


def test_a_titled_morph_slide_with_its_title_deleted_is_that_slide(project):
    """Its morph shapes still carry every morph name the build drew there."""

    def untitle(prs):
        slide = prs.slides[1]
        for shape in [s for s in slide.shapes if s.name.startswith("s2.")]:
            shape._element.getparent().remove(shape._element)

    titled = _build(project, "t", _TITLED_MORPH)
    drift = _saved_as(titled, "T untitled.pptx", untitle)
    assert [(c.kind, c.slide) for c in drift.changes] == [("gone", 2)] * len(drift.changes)
    assert ("gone", 2, "s2.chrome.title") in [(c.kind, c.slide, c.shape) for c in drift.changes]


def test_identical_held_slides_cut_leave_the_lowest_number(project):
    from deckwright.utils.deck import delete_slide

    def cut_two(prs):
        delete_slide(prs, 2)
        delete_slide(prs, 1)

    held = _build(project, "h", _HELD)
    drift = _saved_as(held, "H two cut.pptx", cut_two)
    assert _changes(drift) == [
        ("slide-gone", 2, "slide 2", _GONE),
        ("slide-gone", 4, "slide 4", _GONE),
    ]


def test_a_morph_slide_sharing_no_name_with_the_gap_is_added(morphs):
    def rename(prs):
        for shape in prs.slides[2].shapes:
            shape.name = shape.name.replace("m.fig.", "m.other.")

    drift = _saved_as(morphs, "M renamed.pptx", rename)
    assert _changes(drift) == [
        ("slide-added", 3, "slide 3", _MORPH_ADDED),
        ("slide-gone", 3, "slide 3", _GONE),
    ]


def test_a_shape_pasted_from_another_deck_keeps_its_slide(built):
    def stranger(slide):
        box = slide.shapes.add_textbox(Inches(1), Inches(6), Inches(2), Inches(0.4))
        box.name = "s9.p1.text#1"

    _edit(built.deck, stranger)
    assert [(c.kind, c.slide, c.shape) for c in read_back(built.deck).changes] == [
        ("added", 1, "s9.p1.text#1")
    ]


def test_the_later_of_two_slides_swapped_at_the_end_is_named(morphs):
    drift = _saved_as(morphs, "M tail.pptx", lambda prs: _move(prs, 4, 3))
    assert _changes(drift) == [("slide-moved", 4, "slide 4", "built at 4 of 5, now at 5")]


_APART = (
    "theme: testtheme\nout: out/F.pptx\n---\ntitle: One\n---\n"
    "place:\n  - at: {cols: right-half}\n    morph: fig\n    card: {heading: Far, body: words}\n"
    "---\ntitle: Three\n---\n"
    "place:\n  - at: {cols: right-half}\n    morph: fig\n    card: {heading: Far, body: words}\n"
    "---\ntitle: Five\n"
)


def test_of_two_slides_drawn_alike_far_apart_the_deleted_one_is_gone(project):
    """The survivor sits between slides 3 and 5, so it is slide 4, not the lowest match."""
    from deckwright.utils.deck import delete_slide

    far = _build(project, "f", _APART)
    drift = _saved_as(far, "F cut.pptx", lambda prs: delete_slide(prs, 1))
    assert _changes(drift) == [("slide-gone", 2, "slide 2", _GONE)]


def _plated(project):
    from deckwright.compile import build_deck

    (project / "p.deck.yaml").write_text(_PLATED)
    return build_deck(project / "p.deck.yaml")


def test_a_chrome_plate_deleted_by_hand_is_gone_and_its_frame_unmoved(project):
    def unplate(prs):
        plate = _named(prs.slides[0], "s1.chrome.title.plate")
        plate._element.getparent().remove(plate._element)

    drift = _saved_as(_plated(project), "P unplated.pptx", unplate)
    assert _changes(drift) == [
        (
            "gone",
            1,
            "s1.chrome.title.plate",
            "the build drew this and the deck no longer has it",
        )
    ]


def test_a_hand_shape_named_for_a_chrome_line_leaves_the_frame_unchanged(project):
    def namesake(prs):
        box = prs.slides[0].shapes.add_textbox(Inches(1), Inches(6.5), Inches(2), Inches(0.5))
        box.name = "s1.chrome.title"
        box.text_frame.text = "hand"

    drift = _saved_as(_plated(project), "P namesake.pptx", namesake)
    assert {c.shape for c in drift.changes} == {"s1.chrome.title"}


def _add_placeholder(slide, *, words="", paint=""):
    from pptx.oxml import parse_xml
    from pptx.oxml.ns import nsdecls

    body = f"<p:txBody><a:bodyPr/><a:p><a:r><a:t>{words}</a:t></a:r></a:p></p:txBody>"
    slide.shapes._spTree.append(
        parse_xml(
            f'<p:sp {nsdecls("p", "a")}><p:nvSpPr><p:cNvPr id="92" name="Body 9"/><p:cNvSpPr/>'
            '<p:nvPr><p:ph type="body" idx="13"/></p:nvPr></p:nvSpPr><p:spPr>'
            '<a:xfrm><a:off x="914400" y="914400"/><a:ext cx="914400" cy="914400"/></a:xfrm>'
            f"{paint}</p:spPr>{body if words else ''}</p:sp>"
        )
    )


def test_a_placeholder_typed_into_by_hand_is_added(built):
    _edit(built.deck, lambda s: _add_placeholder(s, words="typed by hand"))
    assert [(c.kind, c.shape) for c in read_back(built.deck).changes] == [("added", "Body 9")]


@pytest.mark.parametrize(
    "paint",
    [
        '<a:solidFill><a:srgbClr val="FF0000"/></a:solidFill>',
        '<a:gradFill><a:gsLst><a:gs pos="0"><a:srgbClr val="FF0000"/></a:gs>'
        '<a:gs pos="100000"><a:srgbClr val="0000FF"/></a:gs></a:gsLst></a:gradFill>',
        '<a:pattFill prst="pct5"><a:fgClr><a:srgbClr val="FF0000"/></a:fgClr>'
        '<a:bgClr><a:srgbClr val="FFFFFF"/></a:bgClr></a:pattFill>',
        "<a:blipFill><a:stretch><a:fillRect/></a:stretch></a:blipFill>",
        "<a:grpFill/>",
    ],
    ids=["solid", "gradient", "pattern", "picture", "group"],
)
def test_a_placeholder_given_a_fill_by_hand_is_added(built, paint):
    _edit(built.deck, lambda s: _add_placeholder(s, paint=paint))
    assert [(c.kind, c.shape) for c in read_back(built.deck).changes] == [("added", "Body 9")]


@pytest.mark.parametrize(("line", "fill"), [(2, 0), (0, 3)], ids=["line-only", "fill-only"])
def test_a_placeholder_given_a_shape_style_by_hand_is_added(built, line, fill):
    def styled(slide):
        _add_placeholder(slide)
        from pptx.oxml import parse_xml
        from pptx.oxml.ns import nsdecls

        _named(slide, "Body 9")._element.append(
            parse_xml(
                f'<p:style {nsdecls("p", "a")}><a:lnRef idx="{line}"><a:schemeClr val="accent1"/>'
                f'</a:lnRef><a:fillRef idx="{fill}"><a:schemeClr val="accent1"/></a:fillRef>'
                '<a:effectRef idx="0"><a:schemeClr val="accent1"/></a:effectRef>'
                '<a:fontRef idx="minor"><a:schemeClr val="lt1"/></a:fontRef></p:style>'
            )
        )

    _edit(built.deck, styled)
    assert [(c.kind, c.shape) for c in read_back(built.deck).changes] == [("added", "Body 9")]


def test_a_placeholder_whose_outline_is_turned_off_is_still_empty(built):
    hidden = "<a:ln><a:noFill/></a:ln>"
    _edit(built.deck, lambda s: _add_placeholder(s, paint=hidden))
    assert read_back(built.deck).changes == ()


@pytest.mark.parametrize(
    "fill",
    [
        '<a:solidFill><a:srgbClr val="0000FF"/></a:solidFill>',
        '<a:gradFill><a:gsLst><a:gs pos="0"><a:srgbClr val="0000FF"/></a:gs></a:gsLst></a:gradFill>',
        '<a:pattFill prst="pct5"><a:fgClr><a:srgbClr val="0000FF"/></a:fgClr></a:pattFill>',
    ],
    ids=["solid", "gradient", "pattern"],
)
def test_a_placeholder_given_an_outline_by_hand_is_added(built, fill):
    _edit(built.deck, lambda s: _add_placeholder(s, paint=f'<a:ln w="12700">{fill}</a:ln>'))
    assert [(c.kind, c.shape) for c in read_back(built.deck).changes] == [("added", "Body 9")]


def test_a_placeholder_holding_only_a_space_is_still_empty(built):
    _edit(built.deck, lambda s: _add_placeholder(s, words=" "))
    assert read_back(built.deck).changes == ()


def _renamed_with_damaged_shapes(built):
    """A copy under another name, so its manifest is found by build id, beside a manifest whose
    first slide's shape records are not a list."""
    import shutil

    copy = built.deck.with_name("Renamed.pptx")
    shutil.copy(built.deck, copy)
    data = json.loads(built.manifest.read_text())
    data["slides"][0]["shapes"] = "x"
    built.manifest.write_text(json.dumps(data))
    return copy


def test_a_renamed_deck_beside_damaged_records_is_refused_naming_them(built):
    copy = _renamed_with_damaged_shapes(built)
    with pytest.raises(SpecError, match="slide 1's shapes is not a list of records"):
        read_back(copy)


def test_extract_still_reads_the_manifest_of_a_renamed_deck_with_damaged_records(built):
    from pptx import Presentation

    from deckwright.spec._manifest import from_manifest

    copy = _renamed_with_damaged_shapes(built)
    assert from_manifest(copy, Presentation(str(copy))).theme == "testtheme"


def _paste(prs, source, name, onto):
    import copy

    shape = _named(prs.slides[source], name)
    prs.slides[onto].shapes._spTree.append(copy.deepcopy(shape._element))
    return prs.slides[onto].shapes[-1]


def test_a_titled_slides_shape_pasted_onto_a_morph_slide_reads_as_added_there(morphs):
    """The morph slide now carries slide 5's number too; its morph shapes still say it is slide 3,
    and reading it as slide 5 would break the deck's order."""
    drift = _saved_as(morphs, "M title on 3.pptx", lambda prs: _paste(prs, 4, "s5.chrome.title", 2))
    assert [(c.kind, c.slide, c.shape) for c in drift.changes] == [("added", 3, "s5.chrome.title")]


def test_a_shape_pasted_onto_a_morph_slide_from_an_earlier_slide_reads_as_added_there(morphs):
    drift = _saved_as(
        morphs, "M bullets on 3.pptx", lambda prs: _paste(prs, 1, "s2.p1.bullets#1", 2)
    )
    assert [(c.kind, c.slide, c.shape) for c in drift.changes] == [("added", 3, "s2.p1.bullets#1")]


def test_a_shape_from_another_deck_pasted_onto_a_morph_slide_reads_as_added_there(morphs):
    def stranger(prs):
        _paste(prs, 1, "s2.p1.bullets#1", 2).name = "s9.p1.bullets#1"

    drift = _saved_as(morphs, "M stranger on 3.pptx", stranger)
    assert _changes(drift) == [
        ("added", 3, "s9.p1.bullets#1", f"{_ADDED}, so no placement made it")
    ]


def _held_at(x, transition=None):
    lead = f"transition: {transition}\n" if transition else ""
    return (
        f"{lead}place:\n  - at: {{box: {{x: {x}%, y: 20%, w: 30%, h: 30%}}}}\n"
        "    morph: fig\n    card: {heading: Held, body: words}\n"
    )


def _deck(project, name, *slides):
    return _build(
        project, name, f"theme: testtheme\nout: out/{name}.pptx\n---\n" + "---\n".join(slides)
    )


def test_of_three_held_slides_on_none_morph_none_the_first_deleted_is_gone(project):
    from deckwright.utils.deck import delete_slide

    held = _deck(
        project,
        "nmn",
        "title: One\n",
        _held_at(0, "none"),
        _held_at(0, "morph"),
        _held_at(0, "none"),
        "title: Five\n",
    )
    drift = _saved_as(held, "NMN cut.pptx", lambda prs: delete_slide(prs, 1))
    assert _changes(drift) == [("slide-gone", 2, "slide 2", _GONE)]


def test_a_transition_removed_by_hand_on_one_of_three_held_slides_is_that_slides(project):
    """The three draw alike, so their order alone says which one lost its transition."""
    from pptx.oxml.ns import qn as _qn

    def untransition(prs):
        element = prs.slides[2]._element
        mc = "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
        for child in [*element.findall(_qn("p:transition")), *element.findall(mc)]:
            element.remove(child)

    held = _deck(
        project,
        "mmm",
        "title: One\n",
        _held_at(0, "morph"),
        _held_at(0, "morph"),
        _held_at(0, "morph"),
        "title: Five\n",
    )
    drift = _saved_as(held, "MMM bare.pptx", untransition)
    assert _changes(drift) == [("retimed", 3, "slide 3", "transition morph → none")]


# Slides 2, 3 and 5 hold nothing; slide 5 alone arrives by morph, which tells it from the others.
_EMPTIES = (
    "title: One\n",
    "transition: none\n",
    "notes: three\n",
    _held_at(0, "morph"),
    "transition: morph\nnotes: five\n",
    "title: Six\n",
)


def test_an_empty_slide_deleted_among_empty_slides_is_the_only_change(project):
    from deckwright.utils.deck import delete_slide

    empties = _deck(project, "em", *_EMPTIES)
    drift = _saved_as(empties, "EM cut.pptx", lambda prs: delete_slide(prs, 2))
    assert _changes(drift) == [("slide-gone", 3, "slide 3", _GONE)]


def test_an_empty_slide_moved_among_empty_slides_is_one_move(project):
    empties = _deck(project, "em", *_EMPTIES)
    drift = _saved_as(empties, "EM moved.pptx", lambda prs: _move(prs, 4, 1))
    assert _changes(drift) == [("slide-moved", 5, "slide 5", "built at 5 of 6, now at 2")]


def test_text_typed_onto_an_empty_build_slide_is_added_there(project):
    def typed(prs):
        box = prs.slides[2].shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1))
        box.name = "Typed"
        box.text_frame.text = "by hand"

    empties = _deck(project, "em", *_EMPTIES)
    drift = _saved_as(empties, "EM typed.pptx", typed)
    assert [(c.kind, c.slide, c.shape) for c in drift.changes] == [("added", 3, "Typed")]


def test_an_unfilled_placeholder_on_an_empty_build_slide_is_not_a_change(project):
    empties = _deck(project, "em", *_EMPTIES)
    drift = _saved_as(empties, "EM placeholder.pptx", lambda prs: _add_placeholder(prs.slides[2]))
    assert drift.changes == ()


def test_an_empty_slide_swapped_with_its_titled_neighbour_is_one_move(project):
    plain = _deck(project, "pl", "title: One\n", "title: Two\n", "notes: three\n", "title: Four\n")
    drift = _saved_as(plain, "PL swapped.pptx", lambda prs: _move(prs, 2, 1))
    assert _changes(drift) == [("slide-moved", 2, "slide 2", "built at 2 of 4, now at 3")]


_RUN = (
    "title: One\n",
    _held_at(0),
    _held_at(35, "morph"),
    _held_at(70, "morph"),
    "title: Five\n",
)


def _retyped(position):
    return ("retyped", position, "m.fig.card#2", "'Held words' → 'Changed words'")


def test_a_morph_run_retyped_with_a_step_cut_reads_as_retyped_and_one_gone(project):
    from deckwright.utils.deck import delete_slide

    def reword(prs):
        _retype_the_left_card(prs, 1)
        _retype_the_left_card(prs, 3)
        delete_slide(prs, 2)

    run = _deck(project, "run", *_RUN)
    assert _changes(_saved_as(run, "RUN reworded.pptx", reword)) == [
        _retyped(2),
        ("slide-gone", 3, "slide 3", _GONE),
        _retyped(4),
    ]


def test_a_morph_step_cut_and_the_next_retyped_reads_as_retyped(project):
    from deckwright.utils.deck import delete_slide

    def cut_and_reword(prs):
        _retype_the_left_card(prs, 3)
        delete_slide(prs, 2)

    run = _deck(project, "run", *_RUN)
    assert _changes(_saved_as(run, "RUN cut.pptx", cut_and_reword)) == [
        ("slide-gone", 3, "slide 3", _GONE),
        _retyped(4),
    ]


def test_a_morph_step_copied_aside_and_the_next_retyped_is_one_added(project):
    def copy_aside(prs):
        _duplicate_to_the_end(prs, 2)
        _named(prs.slides[5], "m.fig.card#1").left += Inches(1)
        _named(prs.slides[5], "m.fig.card#2").left += Inches(1)
        _move(prs, 5, 3)
        _retype_the_left_card(prs, 4)

    run = _deck(project, "run", *_RUN)
    drift = _saved_as(run, "RUN aside.pptx", copy_aside)
    assert [(c.kind, c.slide) for c in drift.changes] == [("slide-added", 4), ("retyped", 4)]


def test_a_titled_slide_moved_ahead_of_a_retyped_morph_slide(morphs):
    def move_and_retype(prs):
        _move(prs, 4, 2)
        _retype_the_left_card(prs, 3)

    drift = _saved_as(morphs, "M ahead.pptx", move_and_retype)
    assert _changes(drift) == [
        ("slide-moved", 5, "slide 5", "built at 5 of 5, now at 3"),
        ("retyped", 3, "m.fig.card#2", "'Left words' → 'Changed words'"),
    ]


def test_one_held_twin_cut_and_the_other_retyped(project):
    from deckwright.utils.deck import delete_slide

    def cut_and_retype(prs):
        delete_slide(prs, 3)
        _retype_the_left_card(prs, 2)

    held = _build(project, "h", _HELD)
    assert _changes(_saved_as(held, "H cut retyped.pptx", cut_and_retype)) == [
        ("retyped", 3, "m.fig.card#2", "'Held words' → 'Changed words'"),
        ("slide-gone", 4, "slide 4", _GONE),
    ]


def test_an_untouched_deck_opening_on_titleless_slides_reads_clean(project):
    opening = _deck(project, "op", "transition: none\n", _held_at(0), "title: Three\n")
    drift = _saved_as(opening, "OP same.pptx", lambda prs: None)
    assert drift.changes == ()


def test_a_first_morph_slide_retyped_reads_as_retyped(project):
    opening = _deck(project, "op", _held_at(0), "title: Two\n")
    drift = _saved_as(opening, "OP retyped.pptx", lambda prs: _retype_the_left_card(prs, 0))
    assert _changes(drift) == [_retyped(1)]


def test_a_copy_of_a_slide_holding_another_slides_shape_answers_to_neither(morphs):
    def copy_and_paste(prs):
        _duplicate_to_the_end(prs, 0)
        _paste(prs, 1, "s2.p1.bullets#1", 5)

    drift = _saved_as(morphs, "M copy pasted.pptx", copy_and_paste)
    assert _changes(drift) == [
        (
            "slide-added",
            6,
            "slide 6",
            "holds shapes named for slides 1 and 2, so it answers to none of them",
        )
    ]


def test_a_hand_slide_holding_one_shape_of_slide_two_is_its_copy_not_slide_two(morphs):
    """Both carry slide 2's number; the real slide carries more of its shapes."""

    def hand_slide(prs):
        added = prs.slides.add_slide(prs.slides[0].slide_layout)
        for shape in list(added.shapes):
            shape._element.getparent().remove(shape._element)
        _paste(prs, 1, "s2.p1.bullets#1", 5)
        _move(prs, 5, 1)

    drift = _saved_as(morphs, "M hand two.pptx", hand_slide)
    assert _changes(drift) == [("slide-added", 2, "slide 2", "a copy of slide 2 — added by hand")]


def test_a_copy_of_a_held_slide_does_not_stand_in_for_a_deleted_neighbour(project):
    """The copy matches slides 3 and 4 exactly, so it is not read as slide 2 edited."""
    from deckwright.utils.deck import delete_slide

    def cut_and_copy(prs):
        _duplicate_to_the_end(prs, 3)
        delete_slide(prs, 1)

    held = _build(project, "h", _HELD)
    assert _changes(_saved_as(held, "H copy.pptx", cut_and_copy)) == [
        ("slide-added", 4, "slide 4", "a copy of slide 3 — added by hand"),
        ("slide-gone", 2, "slide 2", _GONE),
    ]


def test_a_morph_slide_with_one_card_deleted_is_still_that_slide(morphs):
    def cut_card(prs):
        card = _named(prs.slides[2], "m.fig.card#1")
        card._element.getparent().remove(card._element)

    drift = _saved_as(morphs, "M one card.pptx", cut_card)
    assert [(c.kind, c.slide, c.shape) for c in drift.changes] == [("gone", 3, "m.fig.card#1")]


def test_of_two_held_slides_left_after_a_hand_slide_the_lowest_answers(project):
    from deckwright.utils.deck import delete_slide

    def cut_and_insert(prs):
        added = prs.slides.add_slide(prs.slides[0].slide_layout)
        for shape in list(added.shapes):
            shape._element.getparent().remove(shape._element)
        added.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1)).name = "Hand"
        delete_slide(prs, 2)
        _move(prs, 3, 2)

    held = _build(project, "h", _HELD)
    assert _changes(_saved_as(held, "H hand.pptx", cut_and_insert)) == [
        ("slide-added", 3, "slide 3", _ADDED),
        ("slide-gone", 4, "slide 4", _GONE),
    ]


def test_a_held_slide_moved_ahead_of_everything_answers_to_the_lowest(project):
    from deckwright.utils.deck import delete_slide

    def cut_and_lead(prs):
        delete_slide(prs, 3)
        _move(prs, 2, 0)

    held = _build(project, "h", _HELD)
    assert _changes(_saved_as(held, "H lead.pptx", cut_and_lead)) == [
        ("slide-moved", 3, "slide 3", "built at 3 of 4, now at 1"),
        ("slide-gone", 4, "slide 4", _GONE),
    ]


def test_a_shape_from_another_deck_on_an_empty_slide_is_added_there(project):
    def stranger(prs):
        box = prs.slides[2].shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1))
        box.name = "s9.p1.text#1"

    empties = _deck(project, "em", *_EMPTIES)
    drift = _saved_as(empties, "EM stranger.pptx", stranger)
    assert [(c.kind, c.slide, c.shape) for c in drift.changes] == [("added", 3, "s9.p1.text#1")]


def test_an_empty_slide_moved_with_an_unfilled_placeholder_on_it_is_one_move(project):
    def move_and_reset(prs):
        _move(prs, 4, 1)
        _add_placeholder(prs.slides[1])

    empties = _deck(project, "em", *_EMPTIES)
    drift = _saved_as(empties, "EM moved reset.pptx", move_and_reset)
    assert _changes(drift) == [("slide-moved", 5, "slide 5", "built at 5 of 6, now at 2")]


def test_a_placeholder_whose_shape_style_paints_nothing_is_still_empty(built):
    def unstyled(slide):
        _add_placeholder(slide)
        from pptx.oxml import parse_xml
        from pptx.oxml.ns import nsdecls

        _named(slide, "Body 9")._element.append(
            parse_xml(
                f'<p:style {nsdecls("p", "a")}><a:lnRef idx="0"><a:schemeClr val="accent1"/>'
                '</a:lnRef><a:fillRef idx="0"><a:schemeClr val="accent1"/></a:fillRef>'
                '<a:effectRef idx="0"><a:schemeClr val="accent1"/></a:effectRef>'
                '<a:fontRef idx="minor"><a:schemeClr val="lt1"/></a:fontRef></p:style>'
            )
        )

    _edit(built.deck, unstyled)
    assert read_back(built.deck).changes == ()


def _duplicate_after(prs, index):
    """What Duplicate Slide does: a copy of the slide, its transition included, right after it."""
    import copy

    _duplicate_to_the_end(prs, index)
    source, clone = prs.slides[index]._element, prs.slides[len(prs.slides) - 1]._element
    mc = "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
    for child in source:
        if child.tag in (qn("p:transition"), mc):
            clone.append(copy.deepcopy(child))
    _move(prs, len(prs.slides) - 1, index + 1)


def _pasted(n):
    return f"drawn by the build on slide {n} — pasted here by hand"


def test_a_morph_slides_cards_moved_onto_the_next_steps_spot_are_moved(morphs):
    """Slide 3 now draws exactly what slide 4 draws, but arrives on its own transition, not
    slide 4's morph."""

    def onto_four(prs):
        for name in ("m.fig.card#1", "m.fig.card#2"):
            mine, theirs = _named(prs.slides[2], name), _named(prs.slides[3], name)
            mine.left, mine.top = theirs.left, theirs.top
            mine.width, mine.height = theirs.width, theirs.height

    drift = _saved_as(morphs, "M onto four.pptx", onto_four)
    assert sorted((c.kind, c.slide, c.shape) for c in drift.changes) == [
        ("moved", 3, "m.fig.card#1"),
        ("moved", 3, "m.fig.card#2"),
    ]


_RUN4 = (
    "title: One\n",
    _held_at(0),
    _held_at(20, "morph"),
    _held_at(40, "morph"),
    _held_at(60, "morph"),
    "title: Six\n",
)


def test_a_step_moved_away_and_the_next_drawn_in_its_place_and_retyped(project):
    """Slide 3 still matches exactly, out of order; slide 4 is the edited slide between 2 and 5,
    even though it now sits where slide 3 was drawn."""

    def move_and_redraw(prs):
        _move(prs, 2, 5)
        for name in ("m.fig.card#1", "m.fig.card#2"):
            mine, theirs = _named(prs.slides[2], name), _named(prs.slides[5], name)
            mine.left, mine.top = theirs.left, theirs.top
        _retype_the_left_card(prs, 2)

    run = _deck(project, "run4", *_RUN4)
    drift = _saved_as(run, "RUN4 redrawn.pptx", move_and_redraw)
    kinds = sorted((c.kind, c.slide, c.shape) for c in drift.changes)
    assert kinds == [
        ("moved", 4, "m.fig.card#1"),
        ("moved", 4, "m.fig.card#2"),
        ("retyped", 4, "m.fig.card#2"),
        ("slide-moved", 3, "slide 3"),
    ]


def test_a_shape_pasted_onto_a_morph_slide_whose_source_is_then_deleted(morphs):
    """Slide 3's morph shapes, drawn as built, outweigh the one shape named for slide 2."""
    from deckwright.utils.deck import delete_slide

    def paste_and_cut(prs):
        _paste(prs, 1, "s2.p1.bullets#1", 2)
        delete_slide(prs, 1)

    drift = _saved_as(morphs, "M paste cut.pptx", paste_and_cut)
    assert _changes(drift) == [
        ("slide-gone", 2, "slide 2", _GONE),
        ("added", 3, "s2.p1.bullets#1", _pasted(2)),
    ]


def test_a_title_pasted_onto_a_titled_morph_slide_whose_source_is_then_deleted(project):
    from deckwright.utils.deck import delete_slide

    def paste_and_cut(prs):
        _paste(prs, 0, "s1.chrome.title", 1)
        delete_slide(prs, 0)

    titled = _build(project, "t", _TITLED_MORPH)
    assert _changes(_saved_as(titled, "T paste cut.pptx", paste_and_cut)) == [
        ("slide-gone", 1, "slide 1", _GONE),
        ("added", 2, "s1.chrome.title", _pasted(1)),
    ]


def test_a_later_title_pasted_onto_a_morph_slide_whose_source_is_then_deleted(project):
    from deckwright.utils.deck import delete_slide

    def paste_and_cut(prs):
        _paste(prs, 3, "s4.chrome.title", 2)
        delete_slide(prs, 3)

    titled = _build(project, "t", _TITLED_MORPH)
    assert _changes(_saved_as(titled, "T later cut.pptx", paste_and_cut)) == [
        ("added", 3, "s4.chrome.title", _pasted(4)),
        ("slide-gone", 4, "slide 4", _GONE),
    ]


_NOTED = ("title: One\n", "notes: two\n", "title: Three\n", "title: Four\n")


def _blank(prs):
    added = prs.slides.add_slide(prs.slides[0].slide_layout)
    for shape in list(added.shapes):
        shape._element.getparent().remove(shape._element)
    return added


def test_a_blank_slide_added_does_not_stand_in_for_a_deleted_empty_one(project):
    """The build's slide 2 holds nothing but notes; the blank slide holds no notes."""
    from deckwright.utils.deck import delete_slide

    def blank_and_cut(prs):
        _blank(prs)
        delete_slide(prs, 1)

    noted = _deck(project, "nt", *_NOTED)
    assert _changes(_saved_as(noted, "NT blank.pptx", blank_and_cut)) == [
        ("slide-added", 4, "slide 4", _ADDED),
        ("slide-gone", 2, "slide 2", _GONE),
    ]


def test_a_blank_slide_inserted_ahead_of_an_empty_slide_typed_on(project):
    def blank_and_type(prs):
        _blank(prs)
        _move(prs, 4, 1)
        prs.slides[2].shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1)).name = "Typed"

    noted = _deck(project, "nt", *_NOTED)
    assert [
        (c.kind, c.slide, c.shape)
        for c in _saved_as(noted, "NT typed.pptx", blank_and_type).changes
    ] == [
        ("slide-added", 2, "slide 2"),
        ("added", 2, "Typed"),
    ]


def test_a_hand_slide_ahead_of_its_moved_source_is_the_copy(morphs):
    """Both are out of order; the real slide carries more of slide 2's shapes."""

    def hand_then_move(prs):
        _blank(prs)
        _paste(prs, 1, "s2.p1.bullets#1", 5)
        _move(prs, 1, 5)

    drift = _saved_as(morphs, "M hand ahead.pptx", hand_then_move)
    assert _changes(drift) == [
        ("slide-added", 5, "slide 5", "a copy of slide 2 — added by hand"),
        ("slide-moved", 2, "slide 2", "built at 2 of 5, now at 6"),
    ]


def test_a_moved_slide_carrying_another_slides_title_keeps_its_own(morphs):
    from deckwright.utils.deck import delete_slide

    def paste_cut_move(prs):
        _paste(prs, 0, "s1.chrome.title", 1)
        delete_slide(prs, 0)
        _move(prs, 0, 3)

    drift = _saved_as(morphs, "M carried.pptx", paste_cut_move)
    assert _changes(drift) == [
        ("slide-moved", 2, "slide 2", "built at 2 of 5, now at 4"),
        ("slide-gone", 1, "slide 1", _GONE),
        ("added", 2, "s1.chrome.title", _pasted(1)),
    ]


def test_a_hand_slide_does_not_take_slide_two_when_slide_two_is_retimed(morphs):
    """Shapes carried outrank the transition kept."""

    def hand_and_retime(prs):
        _blank(prs)
        _paste(prs, 1, "s2.p1.bullets#1", 5)
        _move(prs, 5, 1)
        _retime_like(prs, 2, 4)

    drift = _saved_as(morphs, "M hand retimed.pptx", hand_and_retime)
    assert _changes(drift) == [
        ("slide-added", 2, "slide 2", "a copy of slide 2 — added by hand"),
        ("retimed", 2, "slide 2", "transition none → morph"),
    ]


def test_a_retyped_slide_given_a_morph_answers_to_the_slide_drawn_where_it_is(project):
    """Likeness of the drawing outranks the transition kept: slide 2 now arrives on slide 3's
    morph, yet it is drawn where slide 2 was."""
    from deckwright.utils.deck import delete_slide

    def retype_retime_cut(prs):
        _retype_the_left_card(prs, 1)
        _retime_like(prs, 1, 2)
        delete_slide(prs, 2)

    pair = _deck(project, "pr", "title: One\n", _held_at(0), _held_at(35, "morph"), "title: Four\n")
    assert [(c.kind, c.slide) for c in _saved_as(pair, "PR.pptx", retype_retime_cut).changes] == [
        ("retyped", 2),
        ("retimed", 2),
        ("slide-gone", 3),
    ]


def test_a_slide_duplicated_in_place_reads_the_second_as_the_copy(morphs):
    drift = _saved_as(morphs, "M dup.pptx", lambda prs: _duplicate_after(prs, 1))
    assert _changes(drift) == [("slide-added", 3, "slide 3", "a copy of slide 2 — added by hand")]


def test_a_morph_slide_duplicated_in_place_reads_the_second_as_the_copy(morphs):
    drift = _saved_as(morphs, "M dup morph.pptx", lambda prs: _duplicate_after(prs, 3))
    assert _changes(drift) == [("slide-added", 5, "slide 5", "a copy of slide 4 — added by hand")]


def test_an_edited_morph_slide_prefers_the_slide_with_its_names_over_one_sharing_some(project):
    """After slide 2 goes, slide 3 sits where 2 and 3 were; slide 2 shared only some names."""
    from deckwright.utils.deck import delete_slide

    two_names = (
        "place:\n  - at: {box: {x: 0%, y: 20%, w: 30%, h: 30%}}\n    morph: fig\n"
        "    card: {heading: Held, body: words}\n"
        "  - at: {box: {x: 50%, y: 20%, w: 30%, h: 30%}}\n    morph: other\n"
        "    card: {heading: Other, body: words}\n"
    )

    def shift_and_cut(prs):
        for name in ("m.fig.card#1", "m.fig.card#2"):
            _named(prs.slides[2], name).left += Inches(1)
        delete_slide(prs, 1)

    deck = _deck(project, "nm", "title: One\n", two_names, _held_at(35), "title: Four\n")
    drift = _saved_as(deck, "NM.pptx", shift_and_cut)
    assert sorted((c.kind, c.slide, c.shape) for c in drift.changes) == [
        ("moved", 3, "m.fig.card#1"),
        ("moved", 3, "m.fig.card#2"),
        ("slide-gone", 2, "slide 2"),
    ]


def test_an_empty_slide_cut_and_a_hand_slide_added_at_the_end_is_added_and_gone(project):
    from deckwright.utils.deck import delete_slide

    def hand_and_cut(prs):
        _blank(prs).shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1)).name = "Hand"
        delete_slide(prs, 2)

    empties = _deck(project, "em", *_EMPTIES)
    assert [
        (c.kind, c.slide) for c in _saved_as(empties, "EM hand.pptx", hand_and_cut).changes
    ] == [
        ("slide-added", 6),
        ("slide-gone", 3),
    ]


def test_a_slide_emptied_in_place_reads_as_every_shape_gone(morphs):
    def clear(prs):
        for shape in list(prs.slides[1].shapes):
            shape._element.getparent().remove(shape._element)

    drift = _saved_as(morphs, "M cleared.pptx", clear)
    assert sorted((c.kind, c.slide, c.shape) for c in drift.changes) == [
        ("gone", 2, "s2.chrome.title"),
        ("gone", 2, "s2.p1.bullets#1"),
    ]


def test_morph_slides_swapped_against_a_manifest_recording_no_transitions_read_as_a_move(morphs):
    """An older manifest records no transition: it cannot disagree with the one a slide has."""
    data = json.loads(morphs.manifest.read_text())
    for slide in data["slides"]:
        slide.pop("transition", None)
    morphs.manifest.write_text(json.dumps(data))
    drift = _saved_as(morphs, "M old swapped.pptx", _swap_the_morph_slides)
    assert _changes(drift) == [("slide-moved", 3, "slide 3", "built at 3 of 5, now at 4")]


def test_of_two_empty_slides_told_apart_by_transition_the_deleted_one_is_gone(project):
    from deckwright.utils.deck import delete_slide

    two = _deck(
        project, "tw", "title: One\n", "transition: none\n", "transition: morph\n", "title: Four\n"
    )
    drift = _saved_as(two, "TW cut.pptx", lambda prs: delete_slide(prs, 1))
    assert _changes(drift) == [("slide-gone", 2, "slide 2", _GONE)]


def test_a_blank_slide_added_does_not_stand_in_for_an_empty_slide_on_another_transition(project):
    """Neither carries notes; only the transition tells the blank slide from the deleted one."""
    from deckwright.utils.deck import delete_slide

    def blank_and_cut(prs):
        _blank(prs)
        delete_slide(prs, 1)

    deck = _deck(
        project, "bt", "title: One\n", "transition: morph\n", "title: Three\n", "title: Four\n"
    )
    assert _changes(_saved_as(deck, "BT blank.pptx", blank_and_cut)) == [
        ("slide-added", 4, "slide 4", _ADDED),
        ("slide-gone", 2, "slide 2", _GONE),
    ]


_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"


def _timing(slide):
    return [c for c in slide._element if c.tag in (qn("p:transition"), _MC)]


def _retime_like(prs, target, source=None):
    """Give slide ``target`` the transition slide ``source`` arrives on, or none at all."""
    import copy

    element = prs.slides[target]._element
    for child in _timing(prs.slides[target]):
        element.remove(child)
    if source is not None:
        after = element.find(qn("p:clrMapOvr"))
        at = list(element).index(after) + 1 if after is not None else len(element)
        for offset, child in enumerate(_timing(prs.slides[source])):
            element.insert(at + offset, copy.deepcopy(child))


_TWINS_APART = (
    "title: One\n",
    _held_at(0),
    _held_at(30, "morph"),
    _held_at(30, "none"),
    "title: Five\n",
)


def test_a_slide_given_its_drawn_twins_transition_is_retimed_not_a_copy(project):
    twins = _deck(project, "ta", *_TWINS_APART)
    drift = _saved_as(twins, "TA morph.pptx", lambda prs: _retime_like(prs, 3, 2))
    assert _changes(drift) == [("retimed", 4, "slide 4", "transition none → morph")]


def test_a_slide_stripped_to_its_drawn_twins_transition_is_retimed_not_a_copy(project):
    twins = _deck(project, "ta", *_TWINS_APART)
    drift = _saved_as(twins, "TA none.pptx", lambda prs: _retime_like(prs, 2))
    assert _changes(drift) == [("retimed", 3, "slide 3", "transition morph → none")]


_NOTES_TWINS = (
    "title: One\n",
    "transition: none\nnotes: two\n",
    "title: Three\n",
    "transition: none\n",
    "title: Five\n",
)


def _set_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def test_an_empty_slides_notes_cleared_is_no_change(project):
    twins = _deck(project, "nw", *_NOTES_TWINS)
    drift = _saved_as(twins, "NW cleared.pptx", lambda prs: _set_notes(prs.slides[1], ""))
    assert drift.changes == ()


def test_an_empty_slide_given_its_twins_notes_is_no_change(project):
    twins = _deck(project, "nw", *_NOTES_TWINS)
    drift = _saved_as(twins, "NW typed.pptx", lambda prs: _set_notes(prs.slides[3], "two"))
    assert drift.changes == ()


def test_a_notes_page_without_its_notes_box_reads_as_no_notes(project):
    from pptx.enum.shapes import PP_PLACEHOLDER

    def unbox(prs):
        for placeholder in list(prs.slides[1].notes_slide.placeholders):
            if placeholder.placeholder_format.type == PP_PLACEHOLDER.BODY:
                placeholder._element.getparent().remove(placeholder._element)

    noted = _deck(project, "nt", *_NOTED)
    assert _saved_as(noted, "NT unboxed.pptx", unbox).changes == ()


def test_an_empty_slides_notes_edited_beside_a_deleted_titled_slide_is_that_empty_slide(project):
    from deckwright.utils.deck import delete_slide

    def cut_and_note(prs):
        delete_slide(prs, 1)
        _set_notes(prs.slides[1], "three, revised")

    plain = _deck(project, "pl", "title: One\n", "title: Two\n", "notes: three\n", "title: Four\n")
    assert _changes(_saved_as(plain, "PL noted.pptx", cut_and_note)) == [
        ("slide-gone", 2, "slide 2", _GONE)
    ]


def test_a_shape_named_for_a_slide_that_never_drew_it_is_not_called_pasted(morphs):
    def stranger(prs):
        box = prs.slides[2].shapes.add_textbox(Inches(1), Inches(1), Inches(1), Inches(1))
        box.name = "s2.p5.card#1"

    drift = _saved_as(morphs, "M unrecorded.pptx", stranger)
    assert _changes(drift) == [("added", 3, "s2.p5.card#1", f"{_ADDED}, so no placement made it")]


def test_a_morph_shape_pasted_onto_another_slide_names_a_slide_the_build_drew_it_on(morphs):
    drift = _saved_as(morphs, "M morph pasted.pptx", lambda prs: _paste(prs, 2, "m.fig.card#1", 0))
    assert _changes(drift) == [("added", 1, "m.fig.card#1", _pasted(3))]


def test_a_hand_shape_named_for_its_own_slide_is_added_not_pasted(morphs):
    def own(prs):
        box = prs.slides[1].shapes.add_textbox(Inches(1), Inches(1), Inches(1), Inches(1))
        box.name = "s2.note"

    drift = _saved_as(morphs, "M own.pptx", own)
    assert _changes(drift) == [("added", 2, "s2.note", f"{_ADDED}, so no placement made it")]


def test_a_morph_step_moved_and_retimed_reads_as_moved_and_retimed(project):
    def move_and_retime(prs):
        _move(prs, 3, 7)
        _retime_like(prs, 7)

    run = _deck(
        project,
        "mr",
        "title: One\n",
        "title: Two\n",
        _held_at(0),
        _held_at(30, "morph"),
        _held_at(60, "morph"),
        "title: Six\n",
        "title: Seven\n",
        "title: Eight\n",
    )
    assert _changes(_saved_as(run, "MR.pptx", move_and_retime)) == [
        ("slide-moved", 4, "slide 4", "built at 4 of 8, now at 8"),
        ("retimed", 4, "slide 4", "transition morph → none"),
    ]


def test_a_slide_holding_one_own_and_one_pasted_shape_keeps_its_own(project):
    """The pasted title lands on top: of two numbers carried equally, the one drawn first is
    the slide's own."""
    from deckwright.utils.deck import delete_slide

    def paste_and_cut(prs):
        _paste(prs, 0, "s1.chrome.title", 1)
        delete_slide(prs, 0)

    three = _deck(project, "th", "title: One\n", "title: Two\n", "title: Three\n")
    assert _changes(_saved_as(three, "TH.pptx", paste_and_cut)) == [
        ("slide-gone", 1, "slide 1", _GONE),
        ("added", 2, "s1.chrome.title", _pasted(1)),
    ]


def test_a_step_moved_into_a_deleted_steps_place_reads_as_moved_not_edited(project):
    from deckwright.utils.deck import delete_slide

    def cut_and_move(prs):
        delete_slide(prs, 2)
        _move(prs, 3, 2)

    run = _deck(project, "run4", *_RUN4)
    drift = _saved_as(run, "RUN4 shifted.pptx", cut_and_move)
    assert [c.slide for c in drift.of("slide-gone")] == [3]
    assert {c.kind for c in drift.changes} == {"slide-gone", "slide-moved"}


def test_a_copy_where_an_empty_slide_was_is_a_copy_not_that_slide(project):
    from deckwright.utils.deck import delete_slide

    def copy_in(prs):
        _duplicate_to_the_end(prs, 0)
        delete_slide(prs, 1)
        _move(prs, 3, 1)

    noted = _deck(project, "nt", *_NOTED)
    assert _changes(_saved_as(noted, "NT copy.pptx", copy_in)) == [
        ("slide-added", 2, "slide 2", "a copy of slide 1 — added by hand"),
        ("slide-gone", 2, "slide 2", _GONE),
    ]


def test_a_retyped_morph_step_answers_to_the_step_on_its_own_transition(project):
    from deckwright.utils.deck import delete_slide

    def retype_and_cut(prs):
        _retype_the_left_card(prs, 2)
        delete_slide(prs, 1)

    deck = _deck(
        project,
        "kt",
        "title: One\n",
        _held_at(0, "none"),
        _held_at(0, "morph"),
        _held_at(0, "none"),
        "title: Five\n",
    )
    assert [(c.kind, c.slide) for c in _saved_as(deck, "KT.pptx", retype_and_cut).changes] == [
        ("slide-gone", 2),
        ("retyped", 3),
    ]


def test_a_blank_slide_added_does_not_stand_in_for_a_deleted_titled_slide(morphs):
    from deckwright.utils.deck import delete_slide

    def blank_and_cut(prs):
        _blank(prs)
        delete_slide(prs, 1)

    assert _changes(_saved_as(morphs, "M blank cut.pptx", blank_and_cut)) == [
        ("slide-added", 5, "slide 5", _ADDED),
        ("slide-gone", 2, "slide 2", _GONE),
    ]


def test_a_renamed_morph_slide_does_not_answer_to_an_empty_build_slide(project):
    from deckwright.utils.deck import delete_slide

    def cut_and_rename(prs):
        delete_slide(prs, 1)
        for shape in prs.slides[1].shapes:
            shape.name = shape.name.replace("m.fig.", "m.new.")

    deck = _deck(project, "rn", "title: One\n", "transition: none\n", _held_at(0), "title: Four\n")
    drift = _saved_as(deck, "RN.pptx", cut_and_rename)
    assert [(c.kind, c.slide) for c in drift.changes if c.kind.startswith("slide")] == [
        ("slide-added", 2),
        ("slide-gone", 2),
        ("slide-gone", 3),
    ]


def test_of_two_out_of_order_slides_the_one_carrying_more_takes_it_back(morphs):
    """The real slide 2 carries two of its shapes and lost its transition; the hand slide
    carries one and kept it. Shapes carried decide."""

    def hand_then_move(prs):
        _blank(prs)
        _paste(prs, 1, "s2.p1.bullets#1", 5)
        _move(prs, 1, 5)
        _retime_like(prs, 5, 2)

    drift = _saved_as(morphs, "M hand retimed ahead.pptx", hand_then_move)
    assert [(c.kind, c.slide) for c in drift.changes] == [
        ("slide-added", 5),
        ("slide-moved", 2),
        ("retimed", 2),
    ]


def test_the_last_step_edited_after_its_neighbour_moved_away_takes_the_last_slide(project):
    def move_and_redraw(prs):
        _move(prs, 3, 0)
        for name in ("m.fig.card#1", "m.fig.card#2"):
            mine, theirs = _named(prs.slides[4], name), _named(prs.slides[0], name)
            mine.left, mine.top = theirs.left, theirs.top
        _retype_the_left_card(prs, 4)

    run = _deck(
        project,
        "lt",
        "title: One\n",
        _held_at(0),
        _held_at(20, "morph"),
        _held_at(40, "morph"),
        _held_at(60, "morph"),
    )
    drift = _saved_as(run, "LT.pptx", move_and_redraw)
    assert sorted((c.kind, c.slide, c.shape) for c in drift.changes) == [
        ("moved", 5, "m.fig.card#1"),
        ("moved", 5, "m.fig.card#2"),
        ("retyped", 5, "m.fig.card#2"),
        ("slide-moved", 4, "slide 4"),
    ]


def test_notes_over_several_lines_tell_an_empty_slide_apart(project):
    deck = _deck(
        project,
        "ml",
        "title: One\n",
        "transition: none\nnotes: |\n  line one\n  line two\n",
        "transition: none\n",
        "title: Four\n",
    )
    assert _saved_as(deck, "ML same.pptx", lambda prs: None).changes == ()
    drift = _saved_as(deck, "ML moved.pptx", lambda prs: _move(prs, 1, 2))
    assert [c.kind for c in drift.changes] == ["slide-moved"]


def test_a_slide_redrawn_onto_its_twins_spot_and_transition_keeps_its_own_slot(project):
    """Slide 4 now draws exactly what slide 3 draws, on slide 3's morph; slide 3 still holds
    that, so slide 4 answers to its own slot by its morph names."""

    def onto_three(prs):
        for name in ("m.fig.card#1", "m.fig.card#2"):
            mine, theirs = _named(prs.slides[3], name), _named(prs.slides[2], name)
            mine.left, mine.top = theirs.left, theirs.top
        _retime_like(prs, 3, 2)

    deck = _deck(
        project,
        "ot",
        "title: One\n",
        _held_at(0),
        _held_at(30, "morph"),
        _held_at(60, "none"),
        "title: Five\n",
    )
    drift = _saved_as(deck, "OT.pptx", onto_three)
    assert sorted((c.kind, c.slide, c.shape) for c in drift.changes) == [
        ("moved", 4, "m.fig.card#1"),
        ("moved", 4, "m.fig.card#2"),
        ("retimed", 4, "slide 4"),
    ]


def test_an_empty_slide_retimed_beside_a_deleted_one_answers_to_the_one_with_its_notes(project):
    from deckwright.utils.deck import delete_slide

    def cut_and_retime(prs):
        _retime_like(prs, 2, 3)
        delete_slide(prs, 1)

    deck = _deck(
        project,
        "en",
        "title: One\n",
        "transition: none\nnotes: first\n",
        "transition: none\nnotes: second\n",
        _held_at(0, "morph"),
        "title: Five\n",
    )
    assert [(c.kind, c.slide) for c in _saved_as(deck, "EN.pptx", cut_and_retime).changes] == [
        ("slide-gone", 2),
        ("retimed", 3),
    ]


def test_an_empty_slide_with_its_notes_prefers_an_empty_build_slide_to_a_deleted_titled_one(
    project,
):
    """Both build slides carry its notes; of an empty slide and a titled one it would have to
    have emptied, the empty one is nearer."""
    from deckwright.utils.deck import delete_slide

    def cut_and_retime(prs):
        _retime_like(prs, 2, 3)
        delete_slide(prs, 1)

    deck = _deck(
        project,
        "ep",
        "title: One\n",
        "title: Two\nnotes: same\n",
        "transition: none\nnotes: same\n",
        _held_at(0, "morph"),
        "title: Five\n",
    )
    assert [(c.kind, c.slide) for c in _saved_as(deck, "EP.pptx", cut_and_retime).changes] == [
        ("slide-gone", 2),
        ("retimed", 3),
    ]
