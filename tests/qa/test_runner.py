import json

import pytest

from tests.conftest import save_blank_deck

from deckwright.compile.scaffold import new_deck
from deckwright.errors import SpecError
from deckwright.qa import runner
from deckwright.qa.model import Severity
from deckwright.qa.runner import run_qa


@pytest.fixture(autouse=True)
def _unasked_font_scan(monkeypatch):
    """Pin the scan to "not asked" — otherwise which faces the developer's machine
    happens to have decides how many findings every render test here sees."""
    monkeypatch.setattr("deckwright.qa.fonts.installed_families", lambda: None)


def _write_manifest(path, theme_path, *, bad_box=False):
    box = [12.0, 1.0, 3.0, 1.0] if bad_box else [1.0, 1.0, 3.0, 1.0]
    path.write_text(
        json.dumps(
            {
                "deck": "d.pptx",
                "theme": "testtheme",
                "theme_path": str(theme_path),
                "slide_w": 13.333,
                "slide_h": 7.5,
                "slides": [
                    {
                        "index": 1,
                        "layout": "content",
                        "animations": [],
                        "shapes": [
                            {
                                "shape_id": 2,
                                "name": "Box",
                                "box": dict(zip("xywh", box, strict=True)),
                                "text": "hello",
                                "lines": ["hello"],
                                "font_pt": 13.5,
                                "fg": "2D0937",
                                "bg": "FFFFFF",
                                "rendered": "native",
                            }
                        ],
                    }
                ],
            }
        )
    )


def test_a_clean_manifest_yields_no_findings(tmp_path, theme_file):
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    _write_manifest(manifest, theme_file)
    report = run_qa(deck, manifest=manifest, render=False, outdir=tmp_path)
    assert report.findings == ()


def test_an_out_of_bounds_shape_is_reported(tmp_path, theme_file):
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    _write_manifest(manifest, theme_file, bad_box=True)
    report = run_qa(deck, manifest=manifest, render=False, outdir=tmp_path)
    assert report.count(Severity.ERROR) == 1
    assert report.findings[0].check == "bounds"


def test_reports_are_written(tmp_path, theme_file):
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    _write_manifest(manifest, theme_file)
    run_qa(deck, manifest=manifest, render=False, outdir=tmp_path)
    assert (tmp_path / "qa.md").is_file()
    assert (tmp_path / "qa.json").is_file()


def test_a_manifest_with_no_slides_key_is_flagged(tmp_path, theme_file):
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "deck": "d.pptx",
                "theme": "testtheme",
                "theme_path": str(theme_file),
                "slide_w": 13.333,
                "slide_h": 7.5,
            }
        )
    )
    report = run_qa(deck, manifest=manifest, render=False, outdir=tmp_path)
    assert len(report.findings) == 1
    assert report.findings[0].check == "empty-manifest"
    assert report.findings[0].severity is Severity.WARN


def test_a_manifest_with_an_empty_slides_list_is_flagged(tmp_path, theme_file):
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "deck": "d.pptx",
                "theme": "testtheme",
                "theme_path": str(theme_file),
                "slide_w": 13.333,
                "slide_h": 7.5,
                "slides": [],
            }
        )
    )
    report = run_qa(deck, manifest=manifest, render=False, outdir=tmp_path)
    assert len(report.findings) == 1
    assert report.findings[0].check == "empty-manifest"


def test_a_manifest_with_slides_is_not_flagged_as_empty(tmp_path, theme_file):
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    _write_manifest(manifest, theme_file)
    report = run_qa(deck, manifest=manifest, render=False, outdir=tmp_path)
    assert not any(f.check == "empty-manifest" for f in report.findings)


def test_a_missing_manifest_is_rejected(tmp_path):
    deck = save_blank_deck(tmp_path / "d.pptx")
    with pytest.raises(SpecError, match="manifest not found"):
        run_qa(deck, render=False, outdir=tmp_path)


def test_the_manifest_defaults_to_the_deck_sibling(tmp_path, theme_file):
    deck = save_blank_deck(tmp_path / "d.pptx")
    _write_manifest(tmp_path / "d.manifest.json", theme_file)
    assert run_qa(deck, render=False, outdir=tmp_path).findings == ()


def test_findings_are_sorted_by_slide(tmp_path, theme_file):
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    _write_manifest(manifest, theme_file, bad_box=True)
    data = json.loads(manifest.read_text())
    second = json.loads(json.dumps(data["slides"][0]))
    second["index"] = 2
    data["slides"].append(second)
    manifest.write_text(json.dumps(data))
    report = run_qa(deck, manifest=manifest, render=False, outdir=tmp_path)
    assert [f.slide for f in report.findings] == [1, 2]


def test_run_qa_renders_and_includes_overflow_findings(
    tmp_path, theme_file, monkeypatch, dirty_manifest_deck
):
    calls = {}
    monkeypatch.setattr(
        runner,
        "render_to_images",
        lambda deck, out, **kw: calls.setdefault("rendered", (deck, out)) or [],
    )
    monkeypatch.setattr(runner, "extract_pages", lambda pdf, **kw: ["nothing here"])
    deck, manifest = dirty_manifest_deck
    report = runner.run_qa(deck, manifest=manifest, render=True, outdir=tmp_path)
    assert "rendered" in calls
    assert any(f.check == "overflow" for f in report.findings)


def test_run_qa_without_render_skips_the_renderer_and_overflow(
    tmp_path, theme_file, monkeypatch, dirty_manifest_deck
):
    calls = {}
    monkeypatch.setattr(
        runner, "render_to_images", lambda deck, out, **kw: calls.setdefault("rendered", True) or []
    )
    deck, manifest = dirty_manifest_deck
    report = runner.run_qa(deck, manifest=manifest, render=False, outdir=tmp_path)
    assert "rendered" not in calls
    assert not any(f.check == "overflow" for f in report.findings)


def _slide(index, shapes):
    return {"index": index, "layout": "content", "animations": [], "shapes": shapes}


def _shape(**over):
    if "box" in over:
        over["box"] = dict(zip("xywh", over["box"], strict=True))
    return {
        "shape_id": 2,
        "name": "Box",
        "box": dict(zip("xywh", (1.0, 1.0, 3.0, 1.0), strict=True)),
        "text": "hello",
        "lines": ["hello"],
        "font_pt": 13.5,
        "fg": "2D0937",
        "bg": "FFFFFF",
        "rendered": "native",
        **over,
    }


def test_every_check_is_wired_into_the_run(tmp_path, theme_file):
    """One slide breaking all four rules — a check dropped from the tuple goes silent."""
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "deck": "d.pptx",
                "theme": "testtheme",
                "theme_path": str(theme_file),
                "slide_w": 13.333,
                "slide_h": 7.5,
                "slides": [
                    _slide(
                        1,
                        [
                            _shape(shape_id=2, box=(12.0, 1.0, 3.0, 1.0)),  # out of bounds
                            _shape(shape_id=3, font_pt=6.0),  # under the floor
                            _shape(shape_id=4, fg="CCCCCC", bg="FFFFFF"),  # 1.6:1
                        ],
                    )
                ],
            }
        )
    )
    report = run_qa(deck, manifest=manifest, render=False, outdir=tmp_path)
    assert {f.check for f in report.findings} == {"bounds", "min-font", "contrast"}


def test_the_package_check_runs_on_the_deck_itself(tmp_path, theme_file):
    """It reads the saved file rather than the manifest, so a run that skips it would
    stay green on every manifest-derived assertion above while the deck refuses to open."""
    import zipfile

    deck = save_blank_deck(tmp_path / "d.pptx")
    broken = tmp_path / "broken.pptx"
    with zipfile.ZipFile(deck) as zin, zipfile.ZipFile(broken, "w") as zo:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith("ppt/slides/slide"):
                data = data[:-20]
            zo.writestr(item, data)
    manifest = tmp_path / "broken.manifest.json"
    _write_manifest(manifest, theme_file)
    report = run_qa(broken, manifest=manifest, render=False, outdir=tmp_path)
    assert "package" in {f.check for f in report.findings}


def test_findings_are_ordered_by_slide_then_severity(tmp_path, theme_file):
    """The checks append in their own order, so only the sort can produce this one."""
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "deck": "d.pptx",
                "theme": "testtheme",
                "theme_path": str(theme_file),
                "slide_w": 13.333,
                "slide_h": 7.5,
                "slides": [
                    _slide(1, [_shape(shape_id=2, font_pt=6.0)]),  # slide 1 WARN
                    _slide(2, [_shape(shape_id=3, box=[12.0, 1.0, 3.0, 1.0])]),  # slide 2 ERROR
                ],
            }
        )
    )
    report = run_qa(deck, manifest=manifest, render=False, outdir=tmp_path)
    # check_bounds runs first, so slide 2's ERROR is appended before slide 1's WARN.
    assert [(f.slide, f.check) for f in report.findings] == [(1, "min-font"), (2, "bounds")]


def test_a_manifest_naming_no_theme_is_rejected(tmp_path):
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    manifest.write_text(json.dumps({"deck": "d.pptx", "slides": []}))
    with pytest.raises(SpecError, match="no theme_path recorded"):
        run_qa(deck, manifest=manifest, render=False, outdir=tmp_path)


def test_overflow_consults_the_layout_extraction_too(tmp_path, theme_file, monkeypatch):
    """Reading order splits a widely-tracked line; -layout splits a wrapped line by whatever sits
    beside it. Text missing from one but present in the other did survive, so both are read."""
    calls = []

    def fake_extract(pdf, *, layout=False, **kw):
        calls.append(layout)
        return ["nothing recognisable"] if not layout else ["hello"]

    monkeypatch.setattr(runner, "extract_pages", fake_extract)
    monkeypatch.setattr(runner, "render_to_images", lambda deck, out: [out / "s1.png"])
    monkeypatch.setattr(runner, "check_render_contrast", lambda data, images: [])

    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    _write_manifest(manifest, theme_file)
    report = run_qa(deck, manifest=manifest, render=True, outdir=tmp_path)

    assert calls == [False, True]
    assert [f.check for f in report.findings] == []


def test_an_unmappable_canvas_reaches_the_report_from_the_render_check(
    tmp_path, theme_file, monkeypatch
):
    """The geometry checks size themselves off the theme, so only check_render_contrast
    ever notices the manifest's canvas — and only if the run collects what it returns."""
    monkeypatch.setattr(runner, "extract_pages", lambda pdf, **kw: ["hello"])
    monkeypatch.setattr(runner, "render_to_images", lambda deck, out: [out / "s1.png"])

    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    _write_manifest(manifest, theme_file)
    data = json.loads(manifest.read_text())
    data["slide_w"] = 0
    manifest.write_text(json.dumps(data))
    report = run_qa(deck, manifest=manifest, render=True, outdir=tmp_path)

    assert [f.check for f in report.findings] == ["canvas-size"]
    assert report.findings[0].severity is Severity.WARN


def _digest_of(path):
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def test_a_deck_edited_after_the_build_is_reported_as_stale(tmp_path, theme_file):
    """Every other check reads the manifest and believes it, so a deck hand-edited in PowerPoint
    was checked against a description of a file that no longer existed."""
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    _write_manifest(manifest, theme_file)
    data = json.loads(manifest.read_text())
    data["deck_hash"] = _digest_of(deck)
    manifest.write_text(json.dumps(data))
    assert run_qa(deck, manifest=manifest, render=False, outdir=tmp_path).findings == ()

    deck.write_bytes(deck.read_bytes() + b"\0")  # the hand-edit
    findings = run_qa(deck, manifest=manifest, render=False, outdir=tmp_path).findings
    stale = [f for f in findings if f.check == "stale-manifest"]
    assert len(stale) == 1
    assert stale[0].severity is Severity.WARN
    assert _digest_of(deck) in stale[0].detail


def test_a_manifest_recording_no_deck_hash_is_not_reported_stale(tmp_path, theme_file):
    """Older manifests predate the field; absence is not a mismatch."""
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    _write_manifest(manifest, theme_file)
    assert [
        f
        for f in run_qa(deck, manifest=manifest, render=False, outdir=tmp_path).findings
        if f.check == "stale-manifest"
    ] == []


def test_a_relative_theme_path_resolves_against_the_manifest(tmp_path, theme_file):
    """Paths are recorded relative so a delivered manifest carries no home directory; resolving
    against the working directory would break every `qa` run launched from elsewhere."""
    import os

    (tmp_path / "sub").mkdir()
    deck = save_blank_deck(tmp_path / "sub" / "d.pptx")
    manifest = tmp_path / "sub" / "d.manifest.json"
    _write_manifest(manifest, os.path.relpath(theme_file, manifest.parent))
    assert run_qa(deck, manifest=manifest, render=False, outdir=tmp_path).findings == ()


def test_a_scaffold_deck_is_reported_as_placeholder_copy(tmp_path):
    built = new_deck("Scaffold Probe", root=tmp_path / "authoring").built
    report = run_qa(built.deck, manifest=built.manifest, render=False, outdir=tmp_path)
    placeholder = [f for f in report.findings if f.check == "placeholder"]
    assert {(f.slide, f.detail) for f in placeholder} == {
        (1, "'A KICKER' reads like copy nobody meant to ship"),
        (1, "'Three lines and a chrome block make a cover' reads like copy nobody meant to ship"),
        (3, "'Three things are broken' reads like copy nobody meant to ship"),
        (6, "'questions@example.com' reads like copy nobody meant to ship"),
    }
    assert all(f.severity is Severity.WARN for f in placeholder)


def test_the_font_check_runs_only_once_something_has_been_rendered(
    tmp_path, theme_file, monkeypatch
):
    """A machine with nothing installed still substituted nothing when nothing rendered."""
    monkeypatch.setattr("deckwright.qa.fonts.installed_families", lambda: frozenset())
    deck = save_blank_deck(tmp_path / "d.pptx")
    manifest = tmp_path / "d.manifest.json"
    _write_manifest(manifest, theme_file)

    dry = run_qa(deck, manifest=manifest, render=False, outdir=tmp_path)
    assert [f for f in dry.findings if f.check == "font-substituted"] == []

    monkeypatch.setattr(runner, "render_to_images", lambda deck, out: [out / "s1.png"])
    monkeypatch.setattr(runner, "extract_pages", lambda pdf, **kw: ["hello"])
    monkeypatch.setattr(runner, "check_render_contrast", lambda data, images: [])
    wet = run_qa(deck, manifest=manifest, render=True, outdir=tmp_path)
    assert [f for f in wet.findings if f.check == "font-substituted"] != []


def test_a_recorded_theme_path_that_still_exists_wins(tmp_path):
    theme = tmp_path / "brand.theme.yaml"
    theme.write_text("name: brand\n", encoding="utf-8")
    got = runner._theme_file(None, str(theme), tmp_path / "d.manifest.json", "brand")
    assert got == theme


def test_a_missing_recorded_path_falls_back_to_the_recorded_name(tmp_path):
    """A deck handed over without its theme file still names the theme, and `base` is
    inside the package the recipient already has."""
    got = runner._theme_file(None, "/gone/base.yaml", tmp_path / "d.manifest.json", "base")
    assert got == "base"


def test_without_a_name_a_missing_recorded_path_is_still_reported_as_that_path(tmp_path):
    got = runner._theme_file(None, "/gone/base.yaml", tmp_path / "d.manifest.json", None)
    assert str(got) == "/gone/base.yaml"


def test_an_explicit_theme_always_wins_over_the_manifest(tmp_path):
    got = runner._theme_file("/asked/for.yaml", "/gone/base.yaml", tmp_path / "m.json", "base")
    assert str(got) == "/asked/for.yaml"


def test_qa_runs_on_a_deck_handed_over_without_its_theme_file(tmp_path, monkeypatch):
    """The handover journey docs/qa.md is written for: send the deck and its manifest."""
    built = new_deck("Handover", root=tmp_path / "authoring").built
    data = json.loads(built.manifest.read_text(encoding="utf-8"))
    assert data["theme"] == "base"
    data["theme_path"] = "/gone/base.yaml"
    built.manifest.write_text(json.dumps(data), encoding="utf-8")

    report = run_qa(built.deck, manifest=built.manifest, render=False, outdir=tmp_path)
    assert not [f for f in report.findings if f.severity is Severity.ERROR]


def test_a_theme_resolved_by_name_that_hashes_differently_is_reported(tmp_path, monkeypatch):
    """The name resolves against the reader's own theme dir, so a handed-over deck can
    pick up a different theme of that name and every finding is measured against it."""
    away = tmp_path / "away"
    away.mkdir()
    (away / "brand.theme.yaml").write_text("name: brand\n", encoding="utf-8")
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(away))
    built = new_deck("Substituted", root=tmp_path / "authoring", theme="brand").built

    other = tmp_path / "other"
    other.mkdir()
    (other / "brand.theme.yaml").write_text("name: brand\ntype:\n  min_pt: 3.0\n", encoding="utf-8")
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(other))
    data = json.loads(built.manifest.read_text(encoding="utf-8"))
    data["theme_path"] = "/gone/brand.theme.yaml"
    built.manifest.write_text(json.dumps(data), encoding="utf-8")

    report = run_qa(built.deck, manifest=built.manifest, render=False, outdir=tmp_path)
    swapped = [f for f in report.findings if f.check == "theme-substituted"]
    assert len(swapped) == 1
    assert swapped[0].severity is Severity.WARN


def test_the_packaged_theme_resolved_by_name_is_not_reported_as_substituted(tmp_path):
    """The handover the fallback exists for: same theme, same hash, no noise."""
    built = new_deck("Quiet Handover", root=tmp_path / "authoring").built
    data = json.loads(built.manifest.read_text(encoding="utf-8"))
    data["theme_path"] = "/gone/base.yaml"
    built.manifest.write_text(json.dumps(data), encoding="utf-8")

    report = run_qa(built.deck, manifest=built.manifest, render=False, outdir=tmp_path)
    assert [f for f in report.findings if f.check == "theme-substituted"] == []
