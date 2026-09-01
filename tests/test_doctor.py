"""What `deckwright doctor` attests, and the statuses it must not confuse: a missing external tool is a
fact about this machine, a broken install is something to fix — and a check that FAILs on an absent
LibreOffice would make `bin/setup` fail on a machine that never needed it."""

from __future__ import annotations

import re

import pytest

from deckwright import doctor


@pytest.fixture(autouse=True)
def _unasked_font_scan(monkeypatch):
    """Pin the scan to "did not look" — otherwise any check here that reaches
    `check_fonts` shells out to the real fc-list."""
    monkeypatch.setattr("deckwright.doctor.installed_families", lambda: None)


def test_a_missing_external_tool_warns_and_never_fails(monkeypatch):
    """`bin/setup` runs doctor. If absence were FAIL, setup would refuse to finish on
    a perfectly good machine that only ever builds decks."""
    monkeypatch.setattr(doctor.shutil, "which", lambda _: None)
    monkeypatch.setenv("DECKWRIGHT_SOFFICE", "/nope/soffice")
    monkeypatch.setenv("DECKWRIGHT_PDFTOPPM", "/nope/pdftoppm")
    monkeypatch.setenv("DECKWRIGHT_PDFTOTEXT", "/nope/pdftotext")
    monkeypatch.setenv("DECKWRIGHT_FC_LIST", "/nope/fc-list")
    monkeypatch.setenv("DECKWRIGHT_CHROME", "")
    monkeypatch.setattr("deckwright.services.htmlshot.os.path.exists", lambda _: False)

    results = doctor.check_tools()
    assert {r.name for r in results} == {"soffice", "pdftoppm", "pdftotext", "fc-list", "chrome"}
    assert {r.status for r in results} == {"WARN"}


def test_every_missing_tool_names_a_command_that_installs_it(monkeypatch):
    """A warning nobody can act on gets scrolled past."""
    monkeypatch.setattr(doctor.shutil, "which", lambda _: None)
    monkeypatch.setattr("deckwright.services.htmlshot.os.path.exists", lambda _: False)
    monkeypatch.setenv("DECKWRIGHT_CHROME", "")
    for result in doctor.check_tools():
        assert "brew " in result.detail or "apt-get " in result.detail, result.detail


def test_a_chrome_path_that_is_not_there_warns_rather_than_passing(monkeypatch):
    """DECKWRIGHT_CHROME short-circuits the probe, so the path it names is the one nothing
    else looks at before a build reaches for it."""
    monkeypatch.setattr(doctor.shutil, "which", lambda _: None)
    monkeypatch.setenv("DECKWRIGHT_CHROME", "/nonexistent/chrome")
    chrome = next(r for r in doctor.check_tools() if r.name == "chrome")
    assert chrome.status == "WARN"
    assert "not found (/nonexistent/chrome)" in chrome.detail


def test_the_table_reports_the_version_that_answered():
    """A bug report starts with which deckwright built the deck."""
    rows = {(r.group, r.name): r for r in doctor.run_checks()}
    version = rows[("deckwright", "version")]
    assert version.status == "PASS"
    assert re.match(r"\d+\.\d+", version.detail)


def test_a_broken_glyph_bundle_fails_rather_than_warns(monkeypatch):
    """This one *is* the install being wrong, and it is the check bin/setup acts on."""
    monkeypatch.setattr(
        "deckwright.icons.vendor.verify", lambda *a, **k: ["3 glyph(s) do not match"]
    )
    result = doctor.check_glyphs()
    assert result.status == "FAIL"
    assert "glyphs sync" in result.detail


def test_an_intact_bundle_reports_the_upstream_it_is_pinned_to():
    result = doctor.check_glyphs()
    assert result.status == "PASS"
    assert "glyphs @" in result.detail


def _as_checkout(path):
    """Make `path` look like deckwright's own source tree, not just any Python project."""
    (path / "pyproject.toml").write_text('[project]\nname = "deckwright"\n', encoding="utf-8")


def test_an_empty_corpus_skips_and_says_what_that_costs(tmp_path, monkeypatch):
    """A green suite without the corpus proves almost nothing, and doctor is where
    that becomes visible before the tests run rather than after."""
    monkeypatch.chdir(tmp_path)
    _as_checkout(tmp_path)
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path / "templates"))
    (tmp_path / "templates").mkdir()
    result = doctor.check_corpus()
    assert result.status == "SKIP"
    assert "unit tests only" in result.detail


def test_outside_a_checkout_the_corpus_check_names_something_the_reader_has(tmp_path, monkeypatch):
    """A wheel carries neither tests/test_templates.py nor templates/README.md."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path / "templates"))
    result = doctor.check_corpus()
    assert result.status == "SKIP"
    assert "deckwright conform" in result.detail
    assert "tests/" not in result.detail
    assert "README" not in result.detail


def test_a_populated_corpus_passes(tmp_path, monkeypatch, synthetic_template):
    # Its own directory: `synthetic_template` writes into tmp_path too, and a corpus
    # of "however many files the fixtures happened to leave" measures nothing.
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(corpus))
    (corpus / "brand.pptx").write_bytes(synthetic_template.read_bytes())
    result = doctor.check_corpus()
    assert result.status == "PASS"
    assert "1 template" in result.detail


def test_the_builtin_theme_resolves_with_no_theme_directory(tmp_path, monkeypatch):
    """The packaged fallback is what makes an install with no theme dir able to build."""
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path / "nothing-here"))
    result = doctor.check_theme()
    assert result.status == "PASS"
    assert "packaged" in result.detail


def test_the_fonts_row_warns_and_names_the_face_this_machine_lacks(monkeypatch):
    """A render set in a substituted face reports clean, so the row has to name the face
    rather than say the count is wrong."""
    monkeypatch.setattr("deckwright.doctor.installed_families", lambda: frozenset({"courier new"}))
    result = doctor.check_fonts()
    assert result.status == "WARN"
    assert "Helvetica" in result.detail


@pytest.mark.parametrize(
    ("theme_yaml", "names"),
    [
        pytest.param("name: base\npalette: [oops\n", "invalid YAML", id="unparseable"),
        pytest.param("name: base\nscale: {rows: twelve}\n", "'twelve'", id="grid-rows"),
        pytest.param("name: base\nscale: {rows: .inf}\n", "inf", id="grid-rows-infinite"),
        pytest.param("name: base\nscale: {columns: .inf}\n", "inf", id="grid-columns-infinite"),
        pytest.param("name: base\nscale: 12\n", "scale is a mapping", id="scale-not-a-mapping"),
        pytest.param("name: base\ntype: 5\n", "type is a mapping", id="type-not-a-mapping"),
        pytest.param("name: base\ntype: {ramp: [a]}\n", "type.ramp is a mapping", id="ramp-list"),
        pytest.param("name: base\ntype: {ramp: {title: {pt: huge}}}\n", "'huge'", id="ramp-pt"),
        pytest.param(
            "name: base\ntype: {reference_height: tall}\n",
            "type.reference_height is a canvas height in inches",
            id="reference-height-not-a-number",
        ),
        pytest.param(
            "name: base\ntype: {reference_height: .inf}\n",
            "type.reference_height is a canvas height in inches, got inf",
            id="reference-height-infinite",
        ),
        pytest.param(
            "name: base\ntype: {min_pt: .nan}\n",
            "type.min_pt is a point size, got nan",
            id="min-pt-nan",
        ),
        pytest.param(
            "name: base\ntype: {reference_height: 0, ramp: {title: {pt: 34}}}\n",
            "reference_height",
            id="ramp-reference-height",
        ),
        pytest.param(
            "name: base\ntype: {reference_height: 0, min_pt: 10}\n",
            "reference_height",
            id="reference-height-zero-with-no-ramp",
        ),
        pytest.param(
            "name: base\ntype: {min_pt: small}\n", "type.min_pt", id="min-pt-not-a-number"
        ),
        pytest.param(
            "name: base\ntype: {line_weight_pt: thick}\n",
            "type.line_weight_pt",
            id="line-weight-not-a-number",
        ),
        pytest.param(
            "name: base\nmotion: {stagger_ms: soon}\n",
            "motion stagger_ms is a whole number of milliseconds",
            id="stagger-not-a-number",
        ),
        pytest.param(
            "name: base\nmotion: {beat_ms: soon}\n",
            "motion beat_ms is a whole number of milliseconds",
            id="beat-not-a-number",
        ),
        pytest.param("name: base\nmotion: 5\n", "motion is a mapping", id="motion-not-a-mapping"),
        pytest.param("name: base\nchart: 5\n", "chart is a mapping", id="chart-not-a-mapping"),
    ],
)
def test_a_base_theme_that_will_not_load_still_prints_a_table(
    tmp_path, monkeypatch, capsys, theme_yaml, names
):
    """Every row after the theme check still prints, and the theme row says what is wrong."""
    monkeypatch.setattr("deckwright.doctor.installed_families", lambda: frozenset({"helvetica"}))
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path))
    (tmp_path / "base.theme.yaml").write_text(theme_yaml, encoding="utf-8")

    results = doctor.run_checks()
    rows = {(r.group, r.name): r for r in results}
    assert rows[("theme", "builtin")].status == "WARN"
    assert names in rows[("theme", "builtin")].detail
    assert rows[("fonts", "base")].status == "SKIP"
    assert "theme row" in rows[("fonts", "base")].detail
    assert doctor.report(results) == 0
    printed = capsys.readouterr().out
    assert "glyphs.bundle" in printed
    assert "tools.soffice" in printed


def test_a_check_that_raises_still_leaves_a_full_table(monkeypatch, capsys):
    """The loader is guarded key by key, and this is the net under that: a defect nobody
    foresaw costs its own row, not the attestation the reader ran doctor for."""

    def check_glyphs():
        raise RuntimeError("no idea")

    monkeypatch.setattr(doctor, "check_glyphs", check_glyphs)
    results = doctor.run_checks()
    rows = {(r.group, r.name): r for r in results}
    assert rows[("glyphs", "check")].status == "FAIL"
    assert "raised RuntimeError: no idea" in rows[("glyphs", "check")].detail
    assert {"deckwright", "theme", "fonts", "sample", "templates", "tools"} <= {
        r.group for r in results
    }
    assert doctor.report(results) == 1
    assert "tools.soffice" in capsys.readouterr().out


def test_the_fonts_row_skips_rather_than_warns_without_fontconfig(monkeypatch):
    """A WARN would fire on every machine that never installed fontconfig, about faces
    it may well have."""
    monkeypatch.setattr("deckwright.doctor.installed_families", lambda: None)
    assert doctor.check_fonts().status == "SKIP"


def test_a_foreign_file_at_the_sample_path_is_left_alone(tmp_path, monkeypatch, synthetic_template):
    """Setup never overwrites it, so doctor's job is to say it is not ours."""
    monkeypatch.chdir(tmp_path)
    _as_checkout(tmp_path)
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path / "templates"))
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "sample.pptx").write_bytes(synthetic_template.read_bytes())
    result = doctor.check_sample()
    assert result.status == "WARN"
    assert "not the generated sample" in result.detail


def test_outside_a_checkout_the_sample_check_skips(tmp_path, monkeypatch):
    """A pip user has no templates/ and should not be told they are missing one."""
    monkeypatch.chdir(tmp_path)
    result = doctor.check_sample()
    assert result.status == "SKIP"


@pytest.mark.parametrize("status", ["PASS", "WARN", "SKIP"])
def test_only_a_fail_sets_a_non_zero_exit(status):
    """setup runs `doctor || true`, but CI will not — so the code has to mean this."""
    from pf_core.doctor import CheckResult

    assert doctor.report([CheckResult("g", "n", status, "d")]) == 0
    assert doctor.report([CheckResult("g", "n", "FAIL", "d")]) == 1
