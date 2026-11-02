"""`extract` reading the spec a build kept beside its deck, for what the file does not show."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest
import yaml
from pptx import Presentation
from pptx.oxml.ns import qn

from deckwright.compile import build_deck
from deckwright.compile.readback import read_back
from deckwright.spec import parse_deck
from deckwright.spec.draft import draft_spec
from deckwright.spec.extract import harvest
from deckwright.utils.a11y import describe

pytestmark = [pytest.mark.kept_spec, pytest.mark.xdist_group("kept-spec-tour")]

TOUR = Path(__file__).resolve().parents[2] / "examples" / "feature-tour.deck.yaml"
# The tour's placements whose fields its file does not carry.
LOST = (
    "s3.p1.callouts",
    "s4.p1.stats",
    "s6.p1.swatches",
    "s7.p1.grid",
    "s7.p2.callouts",
    "s10.p1.code",
    "s10.p2.callouts",
    "s11.p1.code",
    "s11.p2.callouts",
    "s25.p1.callouts",
    "s26.p1.stats",
    "s27.p1.callouts",
    "s28.p1.stats",
)

STATED = """theme: base
title: Stated
out: out/Stated.pptx
---
title: A plate and a picture
place:
  - at: {cols: left-half, rows: {from: 0, to: 8}}
    card: {pair: accent-1, heading: Blue, body: On accent one, radius: 0.2, icon: mark.png}
  - at: {cols: right-half, rows: {from: 0, to: 8}}
    image:
      src: pale.png
      alt: A pale field
      crop: "16:9"
      scrim: {opacity: 0.6}
      over: [Words on it]
"""


@pytest.fixture(scope="module")
def tour(tmp_path_factory):
    root = tmp_path_factory.mktemp("tour")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DECKWRIGHT_CACHE_DIR", str(root / "cache"))
        return build_deck(TOUR, out=root / "out" / "Tour.pptx")


@pytest.fixture
def own_tour(tour, tmp_path):
    """The tour's build directory copied, for a test that changes what lies beside the deck."""
    shutil.copytree(tour.deck.parent, tmp_path / "out")
    return tmp_path / "out" / tour.deck.name


def _drafted(deck) -> tuple[str, list[dict]]:
    text = draft_spec(harvest(deck), title="Draft", theme="base").text
    return text, [d for d in yaml.safe_load_all(text) if isinstance(d, dict)][1:]


def _from_the_file_alone(deck) -> None:
    """The draft the file alone gives: every lost placement drafted from its words, with what
    the manifest says still read."""
    text, _ = _drafted(deck)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("deckwright.spec._manifest.kept_placements", lambda *a, **k: {})
        assert text == _drafted(deck)[0]
    assert text.count("drafted as bullets") == 13
    config = next(yaml.safe_load_all(text))
    assert config["sections"] == ["Chrome", "Theme", "Spec", "QA"]


def _entry(slide: dict, component: str) -> dict:
    (entry,) = [e for e in slide.get("place", []) if component in e]
    return entry


def _shapes(deck, prefix: str) -> tuple[object, list]:
    prs = Presentation(str(deck))
    slide = int(prefix[1:].split(".")[0])
    return prs, [s for s in prs.slides[slide - 1].shapes if str(s.name).startswith(prefix)]


def test_the_tours_placements_come_back_with_the_fields_their_spec_gave_them(tour):
    text, slides = _drafted(tour.deck)
    spec = parse_deck(TOUR).slides
    for token in LOST:
        slide, _, component = token.split(".")
        index = int(slide[1:])
        (placed,) = [p for p in spec[index - 1].place if p.component == component]
        assert _entry(slides[index - 1], component)[component] == placed.body, token
    named = [
        token
        for line in text.splitlines()
        if line.startswith("# fields the file does not show come from the spec")
        for token in line.split(": ", 1)[1].split(", ")
    ]
    assert sorted(named) == sorted(LOST)
    assert "drafted as bullets" not in text
    assert "image" in slides[8]["place"][0]  # a document's source is a file beside the spec


def test_the_draft_rebuilds_into_the_tour_but_for_the_document_held_as_its_picture(tour, tmp_path):
    drafted = draft_spec(harvest(tour.deck), title="Draft", theme="base")
    for name, blob in drafted.media.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(blob)
    spec = tmp_path / "draft.deck.yaml"
    spec.write_text(drafted.text.replace("out: out/draft/Draft v1.pptx", "out: out/Draft.pptx"))
    drift = read_back(build_deck(spec).deck, manifest=tour.manifest)
    assert {c.shape for c in drift.changes} == {"s9.p1.document#1", "s9.p1.image#1"}


def test_a_placement_with_a_word_changed_by_hand_is_drafted_from_the_file_alone(tour):
    prs, shapes = _shapes(tour.deck, "s4.p1.stats#")
    run = next(
        r for s in shapes if s.has_text_frame for p in s.text_frame.paragraphs for r in p.runs
    )
    run.text = f"{run.text} edited"
    edited = tour.deck.with_name("Word changed.pptx")
    prs.save(str(edited))

    text, slides = _drafted(edited)
    assert any("edited" in item for item in _entry(slides[3], "bullets")["bullets"]["items"])
    assert "# s4.p1.stats: drafted as bullets" in text
    assert "stats" in _entry(slides[25], "stats")


def test_a_placement_missing_a_shape_its_build_drew_is_drafted_from_the_file_alone(tour):
    prs, shapes = _shapes(tour.deck, "s3.p1.callouts#")
    gone = shapes[-1]._element
    gone.getparent().remove(gone)
    edited = tour.deck.with_name("Shape deleted.pptx")
    prs.save(str(edited))

    text, slides = _drafted(edited)
    assert "# s3.p1.callouts: drafted as bullets" in text
    assert "callouts" in _entry(slides[24], "callouts")


def test_a_placement_holding_a_shape_its_build_never_drew_is_drafted_from_the_file_alone(tour):
    """A wordless shape added under the placement's name: its words still match the build's."""
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches

    prs, _ = _shapes(tour.deck, "s4.p1.stats#")
    added = prs.slides[3].shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(1), Inches(1))
    added.name = "s4.p1.stats#9"
    edited = tour.deck.with_name("Shape added.pptx")
    prs.save(str(edited))

    text, _ = _drafted(edited)
    assert "# s4.p1.stats: drafted as bullets" in text


def test_a_deck_carrying_another_build_id_is_read_from_the_file_alone(own_tour):
    prs = Presentation(str(own_tour))
    prs.core_properties.identifier = "deckwright:0000000000000000"
    prs.save(str(own_tour))
    _from_the_file_alone(own_tour)


def test_a_deck_whose_kept_spec_is_gone_is_read_from_the_file_alone(own_tour):
    (own_tour.parent / ".build" / f"{own_tour.stem}.deck.yaml").unlink()
    _from_the_file_alone(own_tour)


def test_a_kept_spec_that_is_not_a_file_is_never_read(own_tour):
    """A pipe would hold `extract` until something wrote to it; this one is fed the spec."""
    import os
    import threading

    kept = own_tour.parent / ".build" / f"{own_tour.stem}.deck.yaml"
    raw = kept.read_bytes()
    kept.unlink()
    os.mkfifo(kept)

    def feed() -> None:
        with open(kept, "wb") as pipe:
            pipe.write(raw)

    threading.Thread(target=feed, daemon=True).start()
    _from_the_file_alone(own_tour)


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a directory it may not list")
def test_a_kept_spec_that_cannot_be_read_is_ignored(own_tour):
    build = own_tour.parent / ".build"
    build.chmod(0)
    try:
        _from_the_file_alone(own_tour)
    finally:
        build.chmod(0o755)


def test_a_kept_spec_larger_than_any_build_keeps_is_ignored(own_tour, monkeypatch):
    monkeypatch.setattr("deckwright.spec._snapshot._LARGEST", 10)
    _from_the_file_alone(own_tour)


def test_a_records_lines_are_not_read_for_its_words(own_tour):
    """`text` holds every record's words; `lines` only splits them."""
    before, _ = _drafted(own_tour)
    manifest = own_tour.with_suffix(".manifest.json")
    data = json.loads(manifest.read_text())
    (record,) = [r for r in data["slides"][3]["shapes"] if r["name"] == "s4.p1.stats#1"]
    record["lines"] = [1, 2]
    manifest.write_text(json.dumps(data))
    assert _drafted(own_tour)[0] == before


def test_a_kept_spec_edited_since_the_build_is_ignored(own_tour):
    kept = own_tour.parent / ".build" / f"{own_tour.stem}.deck.yaml"
    kept.write_text(kept.read_text() + "# edited\n")
    _from_the_file_alone(own_tour)


@pytest.mark.parametrize("cut", [1, 0], ids=["cut-short", "missing"])
def test_a_spec_hash_not_the_builds_matches_no_kept_spec(own_tour, cut):
    manifest = own_tour.with_suffix(".manifest.json")
    data = json.loads(manifest.read_text())
    data["spec_hash"] = data["spec_hash"][:cut]
    manifest.write_text(json.dumps(data))
    _from_the_file_alone(own_tour)


def test_extract_writes_the_kept_specs_fields_wherever_the_draft_goes(tour, tmp_path):
    from typer.testing import CliRunner

    from deckwright.cli import app

    draft = tmp_path / "draft.deck.yaml"
    result = CliRunner().invoke(app, ["extract", str(tour.deck), "-o", str(draft)])
    assert result.exit_code == 0, result.output
    assert _entry(list(yaml.safe_load_all(draft.read_text()))[4], "stats")["stats"]["items"]


@pytest.mark.parametrize(
    "spec",
    [
        "theme: base\n---\nplace: 3\n",
        "theme: base\ntitle: [unclosed\n",
        "theme: base\ntitle: " + "[" * 5000 + "]" * 5000 + "\n",
    ],
    ids=["spec", "yaml", "nested-past-the-stack"],
)
def test_a_kept_spec_that_no_longer_parses_is_ignored(own_tour, spec):
    """An older deckwright's spec can stop parsing under a newer one; the draft still comes."""
    kept = own_tour.parent / ".build" / f"{own_tour.stem}.deck.yaml"
    kept.write_text(spec)
    manifest = own_tour.with_suffix(".manifest.json")
    data = json.loads(manifest.read_text())
    data["spec_hash"] = hashlib.sha256(kept.read_bytes()).hexdigest()[: len(data["spec_hash"])]
    manifest.write_text(json.dumps(data))
    _from_the_file_alone(own_tour)


@pytest.mark.parametrize(
    "spoil",
    [
        lambda slide: slide.update(shapes="oops"),
        lambda slide: slide["shapes"].__setitem__(0, "oops"),
        lambda slide: slide.update(shapes=5),
    ],
    ids=["shapes-not-a-list", "record-not-a-mapping", "shapes-not-iterable"],
)
def test_a_manifest_recording_its_shapes_malformed_is_read_from_the_file_alone(own_tour, spoil):
    manifest = own_tour.with_suffix(".manifest.json")
    data = json.loads(manifest.read_text())
    spoil(data["slides"][0])
    manifest.write_text(json.dumps(data))
    _from_the_file_alone(own_tour)


def test_a_kept_spec_naming_an_extension_is_never_parsed(tmp_path, monkeypatch):
    """Parsing would import and run the module, and a deck's folder can come from anyone."""
    (tmp_path / "ext.py").write_text("")
    spec = tmp_path / "extended.deck.yaml"
    spec.write_text(
        "theme: base\ntitle: Extended\nextends: ext.py\nout: out/Extended.pptx\n---\n"
        "title: Stats\nplace:\n  - at: {cols: left-half, rows: {from: 0, to: 8}}\n"
        "    stats: {items: [{value: '12', label: roles}]}\n"
    )
    built = build_deck(spec)
    loaded: list[Path] = []
    monkeypatch.setattr("deckwright.layouts.registry.load_extension", loaded.append)

    text, _ = _drafted(built.deck)
    assert loaded == []
    assert "# s1.p1.stats: drafted as bullets" in text


def _morph_pair(tmp_path, *, titled: bool):
    """Two slides whose card shares a morph name and its words, set differently by the spec."""
    title = "title: {}\n" if titled else ""
    spec = tmp_path / "pair.deck.yaml"
    spec.write_text(
        "theme: base\ntitle: Pair\nout: out/Pair.pptx\n---\n"
        + title.format("First")
        + "place:\n  - at: {cols: {from: 0, to: 4}, rows: {from: 0, to: 4}}\n"
        "    id: one\n    morph: ant\n    anchor: middle\n"
        "    card: {heading: Ant, body: Same words, radius: 0.4}\n---\n"
        + title.format("Second")
        + "place:\n  - at: {cols: {from: 6, to: 12}, rows: {from: 4, to: 8}}\n"
        "    id: two\n    morph: ant\n    card: {heading: Ant, body: Same words}\n"
    )
    return build_deck(spec).deck


def _unboxed(slide: dict) -> list[dict]:
    return [{k: v for k, v in entry.items() if k != "at"} for entry in slide["place"]]


_PLAIN = [{"morph": "ant", "card": {"heading": "Ant", "body": "Same words"}}]


def test_a_slide_holding_no_shape_named_for_it_takes_nothing_from_the_spec(tmp_path):
    """Morph names carry no slide, so nothing on these slides shows where the build put them."""
    _, slides = _drafted(_morph_pair(tmp_path, titled=False))
    assert [_unboxed(slide) for slide in slides] == [_PLAIN, _PLAIN]


def test_a_moved_slide_takes_nothing_from_the_spec_though_its_ids_are_renumbered(tmp_path):
    """LibreOffice renumbers slide ids on a save, so only the shapes' names show the move."""
    deck = _morph_pair(tmp_path, titled=True)
    prs = Presentation(str(deck))
    ids = prs.slides._sldIdLst
    first = ids[0]
    ids.remove(first)
    ids.append(first)
    for number, entry in enumerate(ids, start=256):
        entry.set("id", str(number))
    prs.save(str(deck))

    _, slides = _drafted(deck)
    assert [_unboxed(slide) for slide in slides] == [_PLAIN, _PLAIN]


def test_a_slide_holding_a_shape_pasted_from_another_takes_nothing_from_the_spec(tmp_path):
    import copy

    deck = _morph_pair(tmp_path, titled=True)
    prs = Presentation(str(deck))
    (title,) = [s for s in prs.slides[1].shapes if s.name == "s2.chrome.title"]
    prs.slides[0].shapes._spTree.append(copy.deepcopy(title._element))
    prs.save(str(deck))

    _, slides = _drafted(deck)
    assert _unboxed(slides[0]) == _PLAIN
    assert _unboxed(slides[1])[0]["id"] == "two"


def test_what_the_file_states_wins_over_what_the_spec_kept(tmp_path):
    """The spec gives back the crop, the scrim and the radius; the file's own word on the
    picture's alt text and the plate's colour stands, and a file the spec names is left out."""
    from PIL import Image

    Image.new("RGB", (800, 450), (250, 250, 245)).save(tmp_path / "pale.png")
    Image.new("RGB", (64, 64), (20, 20, 20)).save(tmp_path / "mark.png")
    spec = tmp_path / "stated.deck.yaml"
    spec.write_text(STATED)
    built = build_deck(spec)

    prs, shapes = _shapes(built.deck, "s1.p2.image#")
    describe(next(s for s in shapes if s.shape_type == 13), decorative=True)  # a picture
    plate = next(s for s in prs.slides[0].shapes if s.name == "s1.p1.card#1")
    plate.fill.gradient()
    edited = built.deck.with_name("Stated by hand.pptx")
    prs.save(str(edited))

    text, (slide,) = _drafted(edited)
    card, image = _entry(slide, "card")["card"], _entry(slide, "image")["image"]
    assert card == {"heading": "Blue", "body": "On accent one", "radius": 0.2}
    assert "its icon is a file beside that spec, so it is left out" in text
    assert image == {
        "src": "draft.media/slide1-p2.png",
        "decorative": True,
        "crop": "16:9",
        "scrim": {"opacity": 0.6},
        "over": ["Words on it"],
    }


def _brand(tmp_path, monkeypatch):
    """A glyph from a folder `extract` cannot see, alone and on a card."""
    folder = tmp_path / "brand-icons"
    folder.mkdir()
    (folder / "brandmark.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M2 2 L22 2 L12 22 Z"/></svg>'
    )
    monkeypatch.setenv("DECKWRIGHT_ICON_DIR", str(folder))
    spec = tmp_path / "brand.deck.yaml"
    spec.write_text(
        "theme: base\ntitle: Brand\nout: out/Brand.pptx\n---\ntitle: A mark\nplace:\n"
        "  - at: {cols: {from: 0, to: 4}, rows: {from: 0, to: 8}}\n"
        "    icon: {name: brandmark, alt: Our mark}\n"
        "  - at: {cols: {from: 6, to: 12}, rows: {from: 0, to: 8}}\n"
        "    card: {heading: Ours, body: The mark on a card, icon: brandmark}\n"
    )
    built = build_deck(spec)
    monkeypatch.delenv("DECKWRIGHT_ICON_DIR")
    return built


def _marked(built, *, decorative: bool, descr: str | None = None) -> dict:
    """The slide drafted after the glyph is marked by hand."""
    prs, (mark,) = _shapes(built.deck, "s1.p1.icon#")
    describe(mark, decorative=decorative)
    if descr is not None:
        mark._element.find(".//" + qn("p:cNvPr")).set("descr", descr)
    edited = built.deck.with_name("Marked by hand.pptx")
    prs.save(str(edited))
    _, (slide,) = _drafted(edited)
    return slide


def test_a_glyph_the_file_cannot_name_comes_back_by_the_spec_with_the_files_alt_text(
    tmp_path, monkeypatch
):
    """Read without its folder the drawing is nameless; the spec names it, and the mark the
    author set by hand on the shape is the one drafted, not the spec's alt text."""
    slide = _marked(_brand(tmp_path, monkeypatch), decorative=True)
    assert _entry(slide, "icon")["icon"] == {"name": "brandmark", "decorative": True}
    assert _entry(slide, "card")["card"]["icon"] == "brandmark"


@pytest.mark.parametrize(
    ("decorative", "descr", "expected"),
    [(False, "brandmark.svg", {}), (True, "A note", {"decorative": True})],
    ids=["a-file-name-is-no-alt-text", "decorative-wins-over-a-description"],
)
def test_a_glyphs_description_comes_back_only_as_alt_text(
    tmp_path, monkeypatch, decorative, descr, expected
):
    slide = _marked(_brand(tmp_path, monkeypatch), decorative=decorative, descr=descr)
    assert _entry(slide, "icon")["icon"] == {"name": "brandmark", **expected}


NAMED = """theme: base
title: Named
out: out/Named.pptx
---
title: Morph placements a spec names by id
place:
  - at: {cols: {from: 0, to: 4}, rows: {from: 0, to: 4}}
    id: ant
    morph: ant
    card: {heading: ant, body: h = 27}
  - at: {cols: {from: 0, to: 4}, rows: {from: 7, to: 11}}
    id: cat
    morph: cat
    card: {heading: cat, body: h = 43}
  - at: {cols: {from: 0, to: 4}, rows: {from: 4, to: 7}}
    connector: {from: ant, to: cat, arrow: end}
  - at: {cols: {from: 6, to: 12}, rows: {from: 0, to: 4}}
    id: go
    morph: shared
    card: {heading: Go, body: Click}
  - at: {cols: {from: 6, to: 12}, rows: {from: 6, to: 10}}
    id: gone
    reveals: go
    card: {heading: Gone, body: Shown}
  - at: {cols: {from: 6, to: 12}, rows: {from: 10, to: 12}}
    anchor: middle
    align: center
    prose: {paragraphs: [Centred in its box]}
"""


def test_what_a_placement_is_named_and_set_by_comes_back_from_the_spec(tmp_path):
    """A morph placement's shapes carry its morph name, not its id, so the id a connector or a
    reveal names it by is the spec's, as are `align:` and `anchor:`; the draft rebuilds into
    the deck it was read from."""
    spec = tmp_path / "named.deck.yaml"
    spec.write_text(NAMED)
    built = build_deck(spec)

    text, (slide,) = _drafted(built.deck)
    ant, cat, line, go, gone, centred = slide["place"]
    assert (ant["id"], cat["id"], go["id"]) == ("ant", "cat", "go")
    assert line["connector"] == {"from": "ant", "to": "cat", "arrow": "end"}
    assert gone["reveals"] == "go"
    assert (centred["align"], centred["anchor"]) == ("center", "middle")
    (noted,) = [row for row in text.splitlines() if "from the spec" in row]
    assert noted.split(": ", 1)[1].split(", ") == [
        "m.ant.card",
        "m.cat.card",
        "s1.p3.connector",
        "m.shared.card",
        "s1.p6.prose",
    ]

    again = tmp_path / "draft.deck.yaml"
    again.write_text(text.replace("out: out/draft/Draft v1.pptx", "out: out/Draft.pptx"))
    assert read_back(build_deck(again).deck, manifest=built.manifest).changes == ()


TABLED = """theme: base
title: Tabled
out: out/Tabled.pptx
---
title: A table with a spanned header and a total
place:
  - at: {cols: {from: 0, to: 10}, rows: top-two-thirds}
    table:
      header: [Workstream, {text: Effort, across: 2, align: center}, Owner]
      rows:
        - [Spec and schema, '12', '8', Compiler]
        - [Placement engine, '21', '14', Layout]
      total: [{text: Total, emphasis: true}, '33', '22', '']
"""


def test_a_tables_words_come_back_as_the_spec_wrote_them_until_a_cell_is_edited(tmp_path):
    """The file reads a spanned cell as two and a total as a row; while every cell holds what
    the build wrote, the spec's header, rows and total stand, and the draft rebuilds as built."""
    spec = tmp_path / "tabled.deck.yaml"
    spec.write_text(TABLED)
    built = build_deck(spec)

    text, (slide,) = _drafted(built.deck)
    (placed,) = parse_deck(spec).slides[0].place
    table = _entry(slide, "table")["table"]
    assert {k: table[k] for k in ("header", "rows", "total")} == {
        k: placed.body[k] for k in ("header", "rows", "total")
    }
    again = tmp_path / "draft.deck.yaml"
    again.write_text(text.replace("out: out/draft/Draft v1.pptx", "out: out/Draft.pptx"))
    assert read_back(build_deck(again).deck, manifest=built.manifest).changes == ()

    prs, (frame,) = _shapes(built.deck, "s1.p1.table#")
    frame.table.cell(1, 1).text_frame.paragraphs[0].runs[0].text = "13"
    edited = built.deck.with_name("Cell edited.pptx")
    prs.save(str(edited))
    _, (slide,) = _drafted(edited)
    assert "total" not in _entry(slide, "table")["table"]


BLED = """theme: base
title: Bled
out: out/Bled.pptx
---
title: A panel under its words
place:
  - at: {box: {x: 60%, y: 0%, w: 40%, h: 100%}}
    bleed: true
    panel: {pair: inverse}
  - at: {box: {x: 64%, y: 30%, w: 30%, h: 30%}}
    prose: {paragraphs: [On the panel]}
"""


def test_a_bleed_the_manifest_does_not_record_comes_back_from_the_spec(tmp_path):
    """A panel drafted without its bleed overlaps the words laid on it, which the build
    refuses."""
    spec = tmp_path / "bled.deck.yaml"
    spec.write_text(BLED)
    built = build_deck(spec)
    text, (slide,) = _drafted(built.deck)
    assert _entry(slide, "panel")["bleed"] is True  # the manifest's, so nothing is named
    assert "from the spec it was built from" not in text

    data = json.loads(Path(built.manifest).read_text())
    for slide in data["slides"]:
        for placement in slide["placements"]:
            placement.pop("bleed", None)
    Path(built.manifest).write_text(json.dumps(data))

    text, (slide,) = _drafted(built.deck)
    assert _entry(slide, "panel")["bleed"] is True
    assert "from the spec it was built from: s1.p1.panel" in text
    again = tmp_path / "draft.deck.yaml"
    again.write_text(text.replace("out: out/draft/Draft v1.pptx", "out: out/Draft.pptx"))
    assert build_deck(again).deck.is_file()
