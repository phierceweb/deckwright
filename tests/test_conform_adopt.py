"""What `--adopt` is allowed to write, and what it must refuse to write over. Adoption is the one
thing `conform` does outside `out/`: it writes into the theme directory, beside the template it
binds to, where a file may be somebody's hand-edited theme and nothing would recover it."""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml
from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.util import Inches, Pt
from typer.testing import CliRunner

from deckwright.cli import app
from deckwright.compile.build import build_deck
from deckwright.conform import conform, install, plan
from deckwright.conform.derive import derive
from deckwright.errors import ThemeError
from deckwright.theme import load_theme

runner = CliRunner()

# One any template can draw, and one no placement can hold — 60 columns leave less
# width than the theme's gutter pads a cell by, which is a LayoutError.
FINE = {
    "title": "A slide",
    "place": [{"at": {"cols": "full"}, "bullets": {"items": ["One", "Two"]}}],
}
DOOMED = {
    "title": "Too many columns",
    "place": [{"at": {"cols": "full"}, "table": {"rows": [["c"] * 60]}}],
}


def _template(path, slides: int = 1):
    """A stock Office deck is a usable template: it carries a theme part to derive from.
    ``slides`` gives two templates of the same name different bytes."""
    prs = Presentation()
    for _ in range(slides):
        prs.slides.add_slide(prs.slide_layouts[6])
    prs.save(str(path))
    return path


@pytest.fixture
def themes(tmp_path, monkeypatch):
    """Adoption writes where ``build`` resolves theme names from, so it reads the
    same env var — point both at a scratch directory."""
    root = tmp_path / "themes"
    root.mkdir()
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(root))
    return root


@pytest.fixture
def template(themes):
    """A template is adopted where it lives, so it starts in the theme directory."""
    return _template(themes / "Brand.pptx")


def test_an_adopted_theme_builds_a_deck_that_names_it(themes, template, tmp_path):
    """The end of onboarding: `theme: brand` and nothing else supplied."""
    conform(template, tmp_path / "out", exercises={"fine": FINE}, adopt="brand")

    spec = tmp_path / "d.deck.yaml"
    spec.write_text("theme: brand\nout: d.pptx\n---\ntitle: T\n")
    result = build_deck(spec, out=tmp_path / "d.pptx")

    assert result.deck.is_file()
    assert (themes / "brand.theme.yaml").is_file()
    assert not (themes / "assets").exists(), "adoption must not copy the template"


def test_the_adopted_theme_carries_the_adopted_name(themes, template, tmp_path):
    """The derivation names the theme after the template stem. Adopting renames it,
    so the file, its name and the `theme:` a deck writes are one word."""
    conform(template, tmp_path / "out", exercises={"fine": FINE}, adopt="brand")

    assert yaml.safe_load((themes / "brand.theme.yaml").read_text())["name"] == "brand"


def test_install_repoints_the_theme_at_the_template_beside_it(themes, template, tmp_path):
    """The installed theme names its template as a bare filename resolved beside itself — the
    source path is a fact about where it was derived, not about where it now lives."""
    derived = tmp_path / "derived.theme.yaml"
    derived.write_text(
        yaml.safe_dump({"name": "derived", "template": str(tmp_path / "elsewhere.pptx")})
    )

    installed = install(plan("brand", template), derived)

    assert yaml.safe_load(installed.read_text())["template"] == "Brand.pptx"
    assert installed.parent == template.parent


def test_re_adopting_the_same_template_keeps_the_hand_edits(themes, template, tmp_path):
    """The theme beside the template IS this run's sidecar, so a refresh carries the edits
    through verbatim. Georgia is the tell — no derivation from a stock template makes it."""
    hand_edited = themes / "brand.theme.yaml"
    hand_edited.write_text(
        "name: brand\ntemplate: Brand.pptx\ntype:\n  face: Georgia\n  heading_face: Georgia\n"
    )

    conform(template, tmp_path / "out", exercises={"fine": FINE}, adopt="brand")

    assert yaml.safe_load(hand_edited.read_text())["type"]["face"] == "Georgia"


def test_force_re_derives_and_discards_the_hand_edits(themes, template, tmp_path):
    """`--force` is the only way to throw tuning away: it ignores the sidecar that would
    otherwise restore it."""
    (themes / "brand.theme.yaml").write_text(
        "name: brand\ntemplate: Brand.pptx\ntype:\n  face: Georgia\n"
    )

    conform(template, tmp_path / "out", exercises={"fine": FINE}, adopt="brand", force=True)

    assert (
        yaml.safe_load((themes / "brand.theme.yaml").read_text()).get("type", {}).get("face")
        != "Georgia"
    )


def test_a_template_outside_the_theme_directory_is_refused(themes, tmp_path):
    """The theme binds its template by bare filename resolved beside itself, so adopting one
    that lives elsewhere would write a theme pointing at nothing. One directory, one copy."""
    stray = _template(tmp_path / "Downloads-Brand.pptx")

    with pytest.raises(ThemeError, match="a template is adopted where it lives"):
        conform(stray, tmp_path / "out", exercises={"fine": FINE}, adopt="brand")

    assert not (themes / "brand.theme.yaml").exists()


def test_a_name_already_bound_to_a_different_template_is_refused(themes, template, tmp_path):
    """Two brands can both want `brand`. The second must not silently repoint the first."""
    other = _template(themes / "Other.pptx", slides=3)
    (themes / "brand.theme.yaml").write_text(
        yaml.safe_dump({"name": "brand", "template": other.name})
    )

    with pytest.raises(ThemeError, match="binds"):
        conform(template, tmp_path / "out", exercises={"fine": FINE}, adopt="brand")

    assert yaml.safe_load((themes / "brand.theme.yaml").read_text())["template"] == "Other.pptx"


def test_the_same_template_adopted_twice_is_not_a_collision(themes, template, tmp_path):
    """Adopting one template under two names is ordinary — a light and a dark theme
    over the same brand deck. Only *differing* bytes are a collision."""
    conform(template, tmp_path / "out", exercises={"fine": FINE}, adopt="brand")
    conform(template, tmp_path / "out2", exercises={"fine": FINE}, adopt="brand-dark")

    assert (themes / "brand-dark.theme.yaml").is_file()


def test_a_name_that_escapes_the_theme_directory_is_refused(themes, template, tmp_path):
    """`themes` is a directory below `tmp_path`, so `../escaped` names a real file
    outside it — the write a bare-name check exists to stop."""
    with pytest.raises(ThemeError, match="bare theme name"):
        conform(template, tmp_path / "out", exercises={"fine": FINE}, adopt="../escaped")

    assert not (tmp_path / "escaped.yaml").exists()


def test_the_name_is_vetted_before_a_single_exercise_is_built(themes, template, tmp_path):
    """A collision found at the end of a two-minute run has already cost the run it
    exists to prevent. Nothing may be written before the target is known good."""
    other = _template(themes / "Other.pptx", slides=3)
    (themes / "brand.theme.yaml").write_text(
        yaml.safe_dump({"name": "brand", "template": other.name})
    )
    out = tmp_path / "out"

    with pytest.raises(ThemeError):
        conform(template, out, exercises={"fine": FINE}, adopt="brand")

    assert not out.exists()


def test_a_failing_exercise_does_not_block_adoption(themes, template, tmp_path):
    """A FAIL says this template cannot carry that shape, and editing the theme is the answer —
    which needs the theme somewhere that survives, not the disposable directory."""
    result = conform(
        template, tmp_path / "out", exercises={"fine": FINE, "doomed": DOOMED}, adopt="brand"
    )

    assert [name for name, _ in result.failed] == ["doomed"]
    assert result.adopted == themes / "brand.theme.yaml"
    assert (themes / "brand.theme.yaml").is_file()


def test_nothing_is_adopted_when_nothing_built(themes, template, tmp_path):
    """Every exercise failing means the theme does not describe the template at all.
    Installing that under a project name would bless an artefact that builds nothing."""
    result = conform(template, tmp_path / "out", exercises={"doomed": DOOMED}, adopt="brand")

    assert not (themes / "brand.theme.yaml").exists()
    assert result.adopted is None
    assert "no exercise built" in result.refused
    assert "not adopted:" in result.report()


def test_a_missing_template_names_itself(themes, tmp_path):
    """python-pptx raises `PackageNotFoundError` for this, which reaches the CLI as a
    traceback rather than as a message with the path in it."""
    with pytest.raises(ThemeError, match="template not found"):
        conform(tmp_path / "absent.pptx", tmp_path / "out", exercises={"fine": FINE})


def test_a_template_that_will_not_open_names_itself(themes, template, tmp_path):
    """Present but unreadable — a truncated download, or a .key someone renamed.
    `notes()` is the first thing a run opens, so it is the site that has to say so."""
    template.write_bytes(b"PK\x03\x04 truncated")

    with pytest.raises(ThemeError, match=r"template .*Brand\.pptx is not a readable \.pptx"):
        conform(template, tmp_path / "out", exercises={"fine": FINE})


def test_the_cli_passes_adopt_and_force_through(themes, template, tmp_path, monkeypatch):
    """The flags are the whole feature. One exercise stands in for the registry the real
    command runs — this is about the two flags, not the corpus."""
    monkeypatch.setattr("deckwright.conform.run.EXERCISE", {"fine": FINE})
    other = _template(themes / "Other.pptx", slides=3)
    (themes / "brand.theme.yaml").write_text(
        yaml.safe_dump({"name": "brand", "template": other.name})
    )

    refused = runner.invoke(
        app, ["conform", str(template), "-o", str(tmp_path / "a"), "--adopt", "brand"]
    )
    assert refused.exit_code != 0
    assert yaml.safe_load((themes / "brand.theme.yaml").read_text())["template"] == "Other.pptx"

    forced = runner.invoke(
        app, ["conform", str(template), "-o", str(tmp_path / "b"), "--adopt", "brand", "--force"]
    )
    assert forced.exit_code == 0, forced.output
    assert "adopted -> " in forced.output
    assert yaml.safe_load((themes / "brand.theme.yaml").read_text())["template"] == "Brand.pptx"


def test_a_name_that_starts_legal_and_then_escapes_is_refused(themes, template, tmp_path):
    """`../escaped` fails on its first character, so it cannot tell `match` from `fullmatch`;
    `brand/../../escaped` is the one that needs the end anchored."""
    with pytest.raises(ThemeError, match="bare theme name"):
        conform(template, tmp_path / "out", exercises={"fine": FINE}, adopt="brand/../../escaped")

    assert not (tmp_path / "escaped.yaml").exists()
    assert not (themes / "brand.theme.yaml").exists(), "a legal prefix was written as a theme"


def test_a_sidecar_theme_beside_the_template_is_installed_instead_of_the_derivation(
    themes, template, tmp_path
):
    """A tuned theme kept beside the binary survives the round trip verbatim. Georgia is the tell
    — no derivation from a stock template produces it."""
    sidecar = template.with_name("brand.theme.yaml")
    sidecar.write_text(
        "name: whatever\ntemplate: old.pptx\ntype:\n  face: Georgia\n  heading_face: Georgia\n"
    )

    result = conform(template, tmp_path / "out", exercises={"fine": FINE}, adopt="brand")

    assert result.adopted is not None
    installed = yaml.safe_load((themes / "brand.theme.yaml").read_text())
    assert installed["type"]["face"] == "Georgia"
    assert installed["name"] == "brand"
    assert installed["template"] == template.name
    assert any("sidecar" in n for n in result.notes), result.notes


def test_without_a_sidecar_the_derivation_is_what_installs(themes, template, tmp_path):
    """The sidecar is an override, not a requirement — a first meeting still derives.

    This template derives no `type:` block, so an assertion reading `type.face` holds
    whatever `install` wrote, however little. Assert what `derive` produced.
    """
    result = conform(template, tmp_path / "out", exercises={"fine": FINE}, adopt="fresh")

    installed = yaml.safe_load((themes / "fresh.theme.yaml").read_text())
    assert installed["name"] == "fresh"
    assert installed["template"] == template.name
    assert installed["bind"], installed  # what `derive` read off the template's own scheme
    assert not any("sidecar" in n for n in result.notes), result.notes


def test_adoption_writes_the_theme_and_nothing_else(themes, template, tmp_path):
    """One directory, one copy. Adoption adds a theme file beside the template and
    changes nothing else about the directory — put a `shutil.copy` back into `install`
    and this reddens on the extra entry."""
    before = {p.name for p in themes.iterdir()}

    conform(template, tmp_path / "out", exercises={"fine": FINE}, adopt="brand")

    added = {p.name for p in themes.iterdir()} - before
    assert added == {"brand.theme.yaml"}, added


def test_no_module_copies_a_template(themes, template, tmp_path):
    """The gate on the whole design. A second copy is a second filename, and a second
    filename drifts from the first.

    `out/` is regenerated per run and may hold whatever it likes; nothing that outlives
    a run may copy a brand binary.
    """
    src = pathlib.Path(__file__).resolve().parents[1] / "src/deckwright"
    offenders = [
        f"{path.relative_to(src)}:{i}"
        for path in src.rglob("*.py")
        for i, line in enumerate(path.read_text().splitlines(), 1)
        if re.search(r"shutil\.copy", line)
    ]
    assert offenders == [], (
        "a template is adopted where it lives and is never copied: " + ", ".join(offenders)
    )


_FONT_SCHEME = (
    '<a:fontScheme name="t">'
    '<a:majorFont><a:latin typeface="{major}"/><a:ea typeface="{ea}"/><a:cs typeface=""/>'
    "</a:majorFont>"
    '<a:minorFont><a:latin typeface="{minor}"/><a:ea typeface="{ea}"/><a:cs typeface=""/>'
    "</a:minorFont>"
    "</a:fontScheme>"
)


def _referencing_template(path, runs, *, major="Georgia", minor="Verdana", ea="", scheme=True):
    """A template whose slide text names OOXML font *references* rather than faces.

    Stock Office sets major and minor to the same face, so the theme part is rewritten:
    without that, mapping ``+mn-lt`` onto the major font is invisible.
    """
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    para = slide.shapes.add_textbox(
        Inches(1), Inches(1), Inches(5), Inches(2)
    ).text_frame.paragraphs[0]
    for text, face in runs:
        run = para.add_run()
        run.text = text
        run.font.name = face
        run.font.size = Pt(24)
    part = prs.slide_masters[0].part.part_related_by(RT.THEME)
    part._blob = re.sub(
        r"<a:fontScheme.*?</a:fontScheme>",
        _FONT_SCHEME.format(major=major, minor=minor, ea=ea) if scheme else "",
        part.blob.decode("utf8"),
        flags=re.S,
    ).encode("utf8")
    prs.save(str(path))
    return path


def _derived_face(template):
    return (derive(template).get("type") or {}).get("face")


@pytest.mark.parametrize("token", ["+mj-lt", "+MJ-LT"])
def test_a_major_font_reference_is_resolved_to_the_face_it_names(tmp_path, token):
    """`+mj-lt` is not a typeface, it is "the theme's major latin font". python-pptx
    hands the attribute back verbatim, so counting it writes a string no renderer resolves.
    The upper-case spelling is the same reference: matched case-sensitively it is counted
    as a face named "+MJ-LT"."""
    template = _referencing_template(tmp_path / "Ref.pptx", [("x" * 40, token)])

    assert _derived_face(template) == "Georgia"


def test_a_template_with_no_major_latin_face_adopts_a_theme_that_loads(themes, tmp_path):
    """Derivation reads the face off the slides and shrugs at a fontScheme with an empty
    major entry — so the theme it adopts must open against that same scheme, with the
    face it wrote winning."""
    template = _referencing_template(themes / "Brand.pptx", [("x" * 40, "Courier New")], major="")

    result = conform(template, tmp_path / "out", exercises={"fine": FINE}, adopt="brand")

    assert result.adopted == themes / "brand.theme.yaml"
    assert load_theme("brand").face == "Courier New"


def test_a_minor_font_reference_resolves_to_the_minor_face(tmp_path):
    """The two references name different entries of the same scheme. Point `+mn-lt` at
    the major font and this reads Georgia."""
    template = _referencing_template(tmp_path / "Ref.pptx", [("x" * 40, "+mn-lt")])

    assert _derived_face(template) == "Verdana"


def test_an_unresolvable_reference_is_skipped_rather_than_counted(tmp_path):
    """No fontScheme to resolve against: the reference is dropped and the runs set in a
    real face carry the vote. Counting it instead would beat Courier New 40 characters to 10."""
    template = _referencing_template(
        tmp_path / "Ref.pptx",
        [("x" * 40, "+mj-lt"), ("y" * 10, "Courier New")],
        scheme=False,
    )

    assert _derived_face(template) == "Courier New"


@pytest.mark.parametrize("token", ["+mj-ea", "+mj-cs", "+mn-ea", "+mn-cs"])
def test_a_script_reference_is_skipped_rather_than_read_as_the_latin_face(tmp_path, token):
    """`+mj-ea` names the fontScheme's own `<a:ea>` element and `+mj-cs` its `<a:cs>`,
    neither of which is the latin face. Answering one with the latin face sets CJK or
    complex-script text in a face that cannot carry it."""
    template = _referencing_template(
        tmp_path / "Ref.pptx",
        [("x" * 40, token), ("y" * 10, "Courier New")],
        ea="Yu Gothic",
    )

    assert _derived_face(template) == "Courier New"


def test_the_pitchdeck_template_derives_a_real_face():
    """The corpus template that exhibited this: 201 characters of `+mj-lt` against 8 of
    Open Sans, so the reference won the count and `+mj-lt` was written into the theme."""
    template = (
        pathlib.Path(__file__).resolve().parents[1]
        / "templates"
        / "free pitch deck template powerpoint.pptx"
    )
    if not template.is_file():
        pytest.skip(f"{template.name} not present — templates/ is gitignored")

    assert _derived_face(template) == "Montserrat-Bold"
