import logging
import pathlib
import re
import textwrap

import pytest
from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

from deckwright.errors import ThemeError
from deckwright.theme import DEFAULT_PALETTE, load_theme


def _write(tmp_path, template, body: str):
    (tmp_path / "assets").mkdir(exist_ok=True)
    dest = tmp_path / "assets" / "t.pptx"
    dest.write_bytes(template.read_bytes())
    path = tmp_path / "t.yaml"
    path.write_text(textwrap.dedent(body))
    return path


BASE = """
    name: testtheme
    template: assets/t.pptx
    bind:
      page: lt1
      ink: dk1
    type:
      ramp:
        title: {pt: 32, bold: true}
        body: {pt: 13.5}
      min_pt: 10.5
    scale:
      margin: {top: 4%, right: 4.5751%, bottom: 6.6667%, left: 4.6501%}
      columns: 12
      gutter: 1.35%
      body_top: 22.6667%
"""


def test_fonts_come_from_the_template(tmp_path, synthetic_template):
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.face == "Calibri"  # the stock Office theme's latin typeface
    assert theme.mono == "Courier New"  # default when unset


def test_slide_size_comes_from_the_template(tmp_path, synthetic_template):
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.grid.slide_w == pytest.approx(13.333, abs=1e-3)
    assert theme.grid.slide_h == pytest.approx(7.5, abs=1e-3)


def test_type_ramp_is_parsed_into_styles(tmp_path, synthetic_template):
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.style("title").size == pytest.approx(32)
    assert theme.style("title").bold is True
    assert theme.style("body").bold is False


def test_line_weight_defaults_when_the_type_block_omits_it(tmp_path, synthetic_template):
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.line_weight == pytest.approx(2.25)  # the 0.30 rung at 7.5in


def test_line_weight_is_read_from_the_type_block_in_points(tmp_path, synthetic_template):
    body = BASE.replace("      min_pt: 10.5\n", "      min_pt: 10.5\n      line_weight_pt: 3\n")
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert theme.line_weight == pytest.approx(3.0)


def test_missing_template_is_rejected(tmp_path, synthetic_template):
    body = BASE.replace("template: assets/t.pptx", "template: assets/nope.pptx")
    with pytest.raises(ThemeError, match="template not found"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_template_that_is_not_a_readable_pptx_is_a_theme_error(tmp_path, synthetic_template):
    """Otherwise it reaches the CLI as a python-pptx traceback, naming neither the template nor
    the theme that points at it."""
    path = _write(tmp_path, synthetic_template, BASE)
    (tmp_path / "assets" / "t.pptx").write_bytes(b"PK\x03\x04 truncated")

    with pytest.raises(ThemeError, match=r"template .*t\.pptx is not a readable \.pptx"):
        load_theme(path)


def test_missing_theme_file_is_rejected(tmp_path):
    with pytest.raises(ThemeError, match="theme file not found"):
        load_theme(tmp_path / "absent.yaml")


def test_a_reserve_poly_is_read_as_canvas_fractions(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    reserve:
      - name: logo-wedge
        poly: [{x: 100%, y: 72.27%}, {x: 100%, y: 100%}, {x: 82.5%, y: 100%}]
"""
    )
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert len(theme.reserve) == 1
    assert theme.reserve[0].poly == ((1.0, 0.7227), (1.0, 1.0), (0.825, 1.0))


def test_a_reserve_poly_scales_onto_the_canvas_it_was_loaded_against(tmp_path, synthetic_template):
    """Fractions, not inches: the wedge covers the bottom-right corner at any size."""
    body = (
        BASE
        + """
    reserve:
      - name: logo-wedge
        poly: [{x: 100%, y: 72.27%}, {x: 100%, y: 100%}, {x: 82.5%, y: 100%}]
"""
    )
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    box = theme.reserve[0].rect(theme.scale)
    assert box.right == pytest.approx(theme.scale.slide_w)
    assert box.bottom == pytest.approx(theme.scale.slide_h)


def test_a_reserve_entry_without_a_poly_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    reserve:
      - name: bad
"""
    )
    with pytest.raises(ThemeError, match="needs a 'poly'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_reserve_entry_that_is_not_a_mapping_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    reserve: [logo-wedge]
"""
    )
    with pytest.raises(ThemeError, match=r"each 'reserve' entry is a mapping"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_reserve_block_that_is_not_a_list_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    reserve: logo-wedge
"""
    )
    with pytest.raises(ThemeError, match=r"'reserve' is a list of regions"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_poly_point_missing_its_second_number_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    reserve:
      - name: wedge
        poly: [{x: 100%, y: 72.27%}, {x: 100%}]
"""
    )
    with pytest.raises(
        ThemeError,
        match=r"reserved region 'wedge': every 'poly' point is an \{x, y\} "
        r"mapping in percents of the canvas, got \{'x': '100%'\}",
    ):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_flat_list_of_numbers_is_not_a_poly(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    reserve:
      - name: wedge
        poly: [[100%, 72.27%], [82.5%, 100%]]
"""
    )
    with pytest.raises(ThemeError, match=r"a 'poly' point is keyed — write \{x: 78%, y: 0%\}"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_non_numeric_poly_point_is_rejected(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    reserve:
      - name: wedge
        poly: [{x: left, y: top}, {x: right, y: bottom}]
"""
    )
    with pytest.raises(ThemeError, match=r"poly.x is a percent of the canvas, got 'left'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_the_old_safe_zones_key_is_rejected_by_name(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    safe_zones:
      - name: wedge
        poly: [{x: 1333.3%, y: 542%}, {x: 1333.3%, y: 750%}, {x: 1100%, y: 750%}]
"""
    )
    with pytest.raises(ThemeError, match="'safe_zones' is gone — use 'reserve'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_theme_hash_is_stable_and_content_sensitive(tmp_path, synthetic_template):
    a = load_theme(_write(tmp_path, synthetic_template, BASE))
    b = load_theme(_write(tmp_path, synthetic_template, BASE))
    c = load_theme(_write(tmp_path, synthetic_template, BASE.replace("pt: 32", "pt: 37.5")))
    assert a.hash == b.hash
    assert a.hash != c.hash


def test_malformed_yaml_is_rejected_as_a_theme_error(tmp_path, synthetic_template):
    with pytest.raises(ThemeError, match="invalid YAML"):
        load_theme(_write(tmp_path, synthetic_template, "name: t\ntemplate: [unclosed\n"))


def test_non_mapping_theme_file_is_rejected(tmp_path, synthetic_template):
    with pytest.raises(ThemeError, match="mapping at its top level"):
        load_theme(_write(tmp_path, synthetic_template, "- just\n- a list\n"))


def test_an_applies_to_on_a_reserved_region_names_its_replacement(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    reserve:
      - name: wedge
        poly: [{x: 100%, y: 72.27%}, {x: 100%, y: 100%}, {x: 82.5%, y: 100%}]
        applies_to: [content]
"""
    )
    with pytest.raises(
        ThemeError,
        match=r"reserved region 'wedge': 'applies_to' is gone — a slide has "
        r"no layout to scope a region to; every region applies to "
        r"every slide",
    ):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_an_unknown_reserve_key_lists_what_is_accepted(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    reserve:
      - name: wedge
        poly: [{x: 100%, y: 72.27%}, {x: 100%, y: 100%}, {x: 82.5%, y: 100%}]
        colour: orange
"""
    )
    with pytest.raises(
        ThemeError,
        match=r"reserved region 'wedge': unknown key 'colour'; "
        r"known keys: name, poly",
    ):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_theme_hash_changes_when_the_template_changes(tmp_path, synthetic_template):
    from pptx import Presentation

    path = _write(tmp_path, synthetic_template, BASE)
    before = load_theme(path).hash
    prs = Presentation(str(tmp_path / "assets" / "t.pptx"))
    prs.slides.add_slide(prs.slide_layouts[6])
    prs.save(str(tmp_path / "assets" / "t.pptx"))
    assert load_theme(path).hash != before


FACES = BASE.replace(
    "      min_pt: 10.5",
    "      face: Aptos\n      heading_face: Aptos Display\n      min_pt: 10.5",
).replace(
    "        title: {pt: 32, bold: true}",
    "        title: {pt: 32, bold: true, face: heading}\n"
    "        kicker: {pt: 12, face: Courier New}",
)


def test_a_declared_face_beats_the_templates_font_scheme(tmp_path, synthetic_template):
    """A template's fontScheme routinely lags its real typeface, so an explicit face wins."""
    theme = load_theme(_write(tmp_path, synthetic_template, FACES))
    assert theme.face == "Aptos"  # not the template's Calibri
    assert theme.heading_face == "Aptos Display"


def test_a_ramp_rung_renders_in_the_face_it_asks_for(tmp_path, synthetic_template):
    theme = load_theme(_write(tmp_path, synthetic_template, FACES))
    assert theme.font_for(theme.style("title")) == "Aptos Display"  # face: heading
    assert theme.font_for(theme.style("body")) == "Aptos"  # names none -> body face
    assert theme.font_for(theme.style("kicker")) == "Courier New"  # a literal typeface


def test_a_rung_asking_for_mono_gets_the_themes_mono_face(tmp_path):
    """`face: mono` is the only way a rung reaches `type: mono` without repeating the
    string, which then drifts from it with nothing catching the drift."""
    path = tmp_path / "t.yaml"
    path.write_text(
        'name: t\ntype:\n  mono: "IBM Plex Mono"\n  ramp:\n    stat: {pt: 34, face: mono}\n'
    )
    theme = load_theme(path)
    assert theme.style("stat").face == "IBM Plex Mono"


def test_the_faces_fall_back_to_the_template_when_undeclared(tmp_path, synthetic_template):
    """major is the display face, minor the body face — both Calibri in stock Office."""
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.face == "Calibri"
    assert theme.heading_face == "Calibri"
    assert theme.font_for(theme.style("title")) == "Calibri"


def test_a_theme_may_omit_its_template_entirely(tmp_path):
    """The design system stands alone: a theme file needs no brand asset to load."""
    path = tmp_path / "bare.yaml"
    path.write_text("name: bare\n")
    theme = load_theme(path)
    assert theme.template is None
    assert theme.palette.accents  # the built-in ramp, not an empty one
    assert theme.style("body").size > 0


def test_a_templateless_theme_still_gets_the_whole_type_ramp(tmp_path):
    """A theme restates only what it moves, so an omitted ramp is the built-in one."""
    path = tmp_path / "bare.yaml"
    path.write_text("name: bare\n")
    ramp = load_theme(path).ramp
    assert {
        "kicker",
        "caption",
        "body",
        "lead",
        "head",
        "stat",
        "subtitle",
        "title",
        "display",
        "hero",
    } <= set(ramp)


def test_a_declared_rung_overrides_only_itself(tmp_path):
    path = tmp_path / "bare.yaml"
    path.write_text("name: bare\ntype:\n  ramp:\n    body: {pt: 22.5}\n")
    theme = load_theme(path)
    assert theme.style("body").size == pytest.approx(3.0 * theme.grid.slide_h)
    assert "title" in theme.ramp  # the rest of the ramp survives


def test_a_literal_colour_binds_without_any_template(tmp_path):
    """An author with a story and no brand file still gets their own palette."""
    path = tmp_path / "bare.yaml"
    path.write_text("name: bare\nbind:\n  page: '10212A'\n  accent-1: E4572E\n")
    palette = load_theme(path).palette
    assert palette.role("page") == "10212A"
    assert palette.role("accent-1") == "E4572E"


def test_binding_a_slot_name_without_a_template_is_rejected(tmp_path):
    """A slot name needs a clrScheme to resolve against; a literal does not."""
    path = tmp_path / "bare.yaml"
    path.write_text("name: bare\nbind:\n  accent-1: accent1\n")
    with pytest.raises(ThemeError, match="reads as a template slot name"):
        load_theme(path)


def test_a_templateless_theme_that_binds_nothing_keeps_every_default(tmp_path):
    """Binding nothing must reproduce DEFAULT_PALETTE exactly."""
    path = tmp_path / "bare.yaml"
    path.write_text("name: bare\n")
    assert load_theme(path).palette == DEFAULT_PALETTE


def test_marks_without_a_template_are_rejected(tmp_path):
    """Mark media resolves beside the template or out of it, so a themeless theme has
    nowhere to look — say so at load, not with an AttributeError mid-build."""
    path = tmp_path / "bare.yaml"
    path.write_text("name: bare\nmarks:\n  inverse: {media: art.jpg}\n")
    with pytest.raises(ThemeError, match="declares 'marks:' but no 'template:'"):
        load_theme(path)


def test_a_mark_named_after_a_painted_backdrop_is_kept(tmp_path, synthetic_template):
    body = BASE + "    marks:\n      inverse: {media: art.jpg}\n"
    assert load_theme(_write(tmp_path, synthetic_template, body)).marks == {
        "inverse": {"media": "art.jpg"}
    }


def test_a_mark_naming_no_painted_backdrop_is_rejected(tmp_path, synthetic_template):
    """A mark nothing lays down is the silent drop this loader exists to reject."""
    body = BASE + "    marks:\n      wordmark: {media: logo.png, left: 10.55, top: 6.35}\n"
    with pytest.raises(ThemeError, match=r"mark 'wordmark' names no painted backdrop"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_chrome_treatment_declared_in_inches_is_rejected(tmp_path, synthetic_template):
    """Inch values written where the loader expects canvas percents leave the canvas."""
    body = (
        BASE
        + """
    chrome:
      title: {at: {box: {x: 62%, y: 60%, w: 1130%, h: 125%}}}
"""
    )
    with pytest.raises(ThemeError, match=r"box .* leaves the canvas"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_chrome_treatment_reaches_the_theme(tmp_path, synthetic_template):
    body = (
        BASE
        + """
    chrome:
      title: {at: {box: {x: 0%, y: 5%, w: 100%, h: 14%}}, align: center, anchor: bottom}
"""
    )
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert theme.chrome["title"].align == "center"
    assert theme.chrome["title"].anchoring == "bottom"
    assert theme.chrome["title"].at == {"box": pytest.approx((0.0, 0.05, 1.0, 0.14))}


def test_a_theme_declaring_no_chrome_leaves_every_field_at_its_default(
    tmp_path, synthetic_template
):
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.chrome == {}


def test_a_chrome_field_the_vocabulary_does_not_name_is_rejected(tmp_path, synthetic_template):
    body = BASE + "    chrome:\n      eyebrow: {align: center}\n"
    with pytest.raises(ThemeError, match="unknown chrome field 'eyebrow'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_chrome_align_outside_the_vocabulary_is_rejected(tmp_path, synthetic_template):
    body = BASE + "    chrome:\n      title: {align: justify}\n"
    with pytest.raises(ThemeError, match="align must be one of left, center, right"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_mark_whose_value_is_not_a_mapping_is_rejected_at_load(tmp_path, synthetic_template):
    """Caught at load, not mid-build from the compositor on whichever slide reaches it first."""
    body = BASE + "    marks:\n      inverse: art.jpg\n"
    with pytest.raises(ThemeError, match=r"mark 'inverse' needs a mapping with a 'media:'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_mark_without_media_is_rejected_at_load(tmp_path, synthetic_template):
    body = BASE + "    marks:\n      inverse: {opacity: 0.5}\n"
    with pytest.raises(ThemeError, match=r"mark 'inverse' needs a mapping with a 'media:'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_ramp_entry_naming_only_a_size_keeps_its_rungs_weight_and_face(tmp_path):
    """`title: {pt: 34}` resizes the title; it must not quietly un-bold it or strip the
    heading face."""
    path = tmp_path / "t.yaml"
    path.write_text("name: t\ntype:\n  ramp:\n    title: {pt: 34}\n    body: {pt: 14}\n")
    theme = load_theme(path)
    assert theme.style("title").bold is True
    assert theme.style("title").face == theme.heading_face
    assert theme.style("body").bold is False


def test_an_explicit_bold_false_still_wins(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text("name: t\ntype:\n  ramp:\n    title: {pt: 34, bold: false}\n")
    theme = load_theme(path)
    assert theme.style("title").bold is False


def test_a_bare_theme_name_loads_the_packaged_builtin(tmp_path, monkeypatch):
    """`deckwright.load_theme("base")` is the advertised way in."""
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path / "no-such-dir"))
    assert load_theme("base").name == "base"


def test_a_bare_name_prefers_the_theme_directory_over_the_packaged_builtin(tmp_path, monkeypatch):
    (tmp_path / "base.theme.yaml").write_text("name: local-override\n")
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path))
    assert load_theme("base").name == "local-override"


def test_an_unknown_name_names_the_directory_it_searched_and_the_remedy(tmp_path, monkeypatch):
    """Not a bare 'theme file not found: acme', which names no directory, env var or way out."""
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path))
    with pytest.raises(ThemeError) as excinfo:
        load_theme("acme")
    message = str(excinfo.value)
    assert "unknown theme 'acme'" in message
    assert str(tmp_path) in message
    assert "DECKWRIGHT_THEME_DIR" in message
    assert "deckwright conform <brand>.pptx --adopt acme" in message
    assert "packaged: base" in message


def test_a_path_shaped_reference_is_reported_as_a_path_not_an_unknown_name(tmp_path):
    """A mistyped path must not be answered with 'onboard a brand template'."""
    with pytest.raises(ThemeError) as excinfo:
        load_theme(tmp_path / "absent.yaml")
    message = str(excinfo.value)
    assert "theme file not found" in message
    assert "unknown theme" not in message


# --- a fontScheme reference left in a theme file -----------------------------

PITCHDECK = (
    pathlib.Path(__file__).resolve().parents[2]
    / "templates"
    / "free pitch deck template powerpoint.pptx"
)

REF = """
    name: brand
    template: assets/t.pptx
    bind:
      page: lt1
      ink: dk1
    type:
      {key}: {value}
"""


def _brand_theme(tmp_path, key: str, value: str):
    """A theme on the corpus template, whose fontScheme names Montserrat-Bold major and
    Open Sans minor. Stock Office sets both to Calibri, so on a synthetic template a
    per-key fallback is invisible."""
    if not PITCHDECK.is_file():
        pytest.skip(f"{PITCHDECK.name} not present — templates/ is gitignored")
    return _write(tmp_path, PITCHDECK, REF.format(key=key, value=value))


def _events(caplog) -> list[dict]:
    return [r.msg for r in caplog.records if isinstance(r.msg, dict)]


@pytest.mark.parametrize(
    ("key", "expected"),
    [("face", "Open Sans"), ("heading_face", "Montserrat-Bold"), ("mono", "Courier New")],
)
def test_a_fontscheme_reference_in_a_face_falls_back_to_a_real_one(tmp_path, caplog, key, expected):
    """`+mj-lt` is OOXML's reference to a template's major latin font, not a typeface.
    Kept, it is measured against nothing and rendered as whatever the reader falls back
    to; dropped, the key takes the face it would have had with no `type:` entry at all."""
    with caplog.at_level(logging.WARNING):
        theme = load_theme(_brand_theme(tmp_path, key, "+mj-lt"))

    assert getattr(theme, key) == expected


def test_the_reference_warning_names_the_theme_the_key_the_token_and_the_remedy(tmp_path, caplog):
    """Nothing else tells a reader that a theme on disk carries one, or that the fix is
    an adoption rather than an edit."""
    with caplog.at_level(logging.WARNING):
        load_theme(_brand_theme(tmp_path, "face", "+mn-cs"))

    warned = [e for e in _events(caplog) if e["event"] == "theme_face_scheme_reference"]
    assert len(warned) == 1
    assert warned[0]["theme"] == "brand"
    assert warned[0]["key"] == "type.face"
    assert warned[0]["token"] == "+mn-cs"
    assert "--adopt brand" in warned[0]["fix"]


def test_an_uninstalled_face_is_not_reported_as_a_fontscheme_reference(tmp_path, caplog):
    """The two warnings take different fixes — re-adopt the template, against name a
    measured face or accept the slack — so a real face must never raise the first."""
    with caplog.at_level(logging.WARNING):
        load_theme(_brand_theme(tmp_path, "face", "Brandish Grotesk"))

    events = {e["event"] for e in _events(caplog)}
    assert "theme_face_unmeasured" in events
    assert "theme_face_scheme_reference" not in events


def test_a_scheme_reference_is_recognised_whatever_its_case(tmp_path, caplog, synthetic_template):
    """A theme file is hand-edited, so the token arrives in whatever case was typed. Match
    it case-sensitively and `+MJ-LT` sails through as a typeface named "+MJ-LT"."""
    body = BASE.replace("      min_pt: 10.5", '      face: "+MJ-LT"\n      min_pt: 10.5')
    with caplog.at_level(logging.WARNING):
        theme = load_theme(_write(tmp_path, synthetic_template, body))

    assert theme.face == "Calibri"
    warned = [e for e in _events(caplog) if e["event"] == "theme_face_scheme_reference"]
    assert [w["token"] for w in warned] == ["+MJ-LT"]


def test_a_rung_face_matching_an_alias_only_in_case_stays_literal_and_warns(tmp_path, caplog):
    """`face: Mono` is a typeface named "Mono", which no machine has; nothing else says so
    until qa renders and fontconfig answers."""
    path = tmp_path / "t.yaml"
    path.write_text(
        'name: t\ntype:\n  mono: "IBM Plex Mono"\n  ramp:\n    stat: {pt: 34, face: Mono}\n'
    )
    with caplog.at_level(logging.WARNING):
        theme = load_theme(path)

    assert theme.style("stat").face == "Mono"
    warned = [e for e in _events(caplog) if e["event"] == "theme_ramp_face_alias_case"]
    assert [(w["rung"], w["face"]) for w in warned] == [("stat", "Mono")]


# --- a template whose fontScheme names no latin face --------------------------


def _blank_major_face(pptx: pathlib.Path) -> None:
    """Rewrite the template so its fontScheme's major latin entry names no face — a real
    template shape, and one `conform` derives from without complaint."""
    prs = Presentation(str(pptx))
    part = prs.slide_masters[0].part.part_related_by(RT.THEME)
    xml, n = re.subn(
        r'(<a:majorFont>\s*<a:latin typeface=")[^"]*(")', r"\1\2", part.blob.decode("utf8")
    )
    assert n == 1
    part._blob = xml.encode("utf8")
    prs.save(str(pptx))


def test_a_template_with_no_major_latin_face_loads_with_the_builtin_faces(
    tmp_path, caplog, synthetic_template
):
    """`conform` skips such a scheme and writes the face it counted off the slides, so
    the theme it adopts must load past the same scheme; a theme naming no face gets the
    design system's, and the warning says which scheme entry was unusable."""
    path = _write(tmp_path, synthetic_template, BASE)
    _blank_major_face(tmp_path / "assets" / "t.pptx")

    with caplog.at_level(logging.WARNING):
        theme = load_theme(path)

    assert (theme.face, theme.heading_face) == ("Helvetica", "Helvetica")
    warned = [e for e in _events(caplog) if e["event"] == "theme_font_scheme_unusable"]
    assert len(warned) == 1
    assert warned[0]["theme"] == "testtheme"
    assert "no major latin typeface" in warned[0]["reason"]


# --- numbers that cast but cannot be weighed ----------------------------------

_TOO_BIG = "1" + "0" * 320  # an integer past the range of the float `isfinite` weighs


@pytest.mark.parametrize(
    ("block", "names"),
    [
        pytest.param(f"scale: {{rows: {_TOO_BIG}}}", "rows is a whole number", id="rows"),
        pytest.param(f"scale: {{columns: {_TOO_BIG}}}", "columns is a whole number", id="columns"),
        pytest.param(f"motion: {{beat_ms: {_TOO_BIG}}}", "beat_ms is a whole number", id="beat"),
        pytest.param(
            f"motion: {{stagger_ms: {_TOO_BIG}}}", "stagger_ms is a whole number", id="stagger"
        ),
    ],
)
def test_an_integer_too_large_to_weigh_is_refused_by_name(tmp_path, block, names):
    """These reach the finite check as ints past a float's range — `int()` takes an integer
    of any size, where a float that large fails the cast. Weigh one outside `number`'s try
    and the loader raises a bare OverflowError instead of naming the key."""
    path = tmp_path / "t.yaml"
    path.write_text(f"name: t\n{block}\n", encoding="utf-8")

    with pytest.raises(ThemeError, match=names):
        load_theme(path)


@pytest.mark.parametrize(
    "block,message",
    [
        ("scale:\n  gutterr: 2%\n", "'scale': unknown key 'gutterr'"),
        ("scale:\n  margin:\n    topp: 5%\n", "'scale.margin': unknown key 'topp'"),
        ("type:\n  wibble: 42\n", "'type': unknown key 'wibble'"),
    ],
)
def test_a_typo_in_a_nested_theme_block_is_refused(tmp_path, block, message):
    """Dropped, the value leaves the default standing and the theme reads as if honoured."""
    path = tmp_path / "probe.theme.yaml"
    path.write_text(f"name: probe\n{block}", encoding="utf-8")
    with pytest.raises(ThemeError) as e:
        load_theme(path)
    assert message in str(e.value)


@pytest.mark.parametrize(
    "block",
    [
        "scale:\n  margin: {top: 5%}\n  columns: 12\n  gutter: 1.5%\n  body_top: 22%\n",
        "type:\n  face: Helvetica\n  ramp:\n    body: {pt: 14}\n",
    ],
)
def test_every_key_a_nested_block_really_reads_is_accepted(tmp_path, block):
    """The guard on the guard: a check that refuses real keys is worse than none."""
    path = tmp_path / "probe.theme.yaml"
    path.write_text(f"name: probe\n{block}", encoding="utf-8")
    assert load_theme(path).name == "probe"


def _routed(ref) -> str:
    with pytest.raises(ThemeError) as e:
        load_theme(ref)
    return str(e.value)


def _command(message: str) -> list[str]:
    """The backticked command, split the way a shell would read it."""
    import shlex

    return shlex.split(message.split("`")[1])


def test_a_template_in_the_theme_dir_is_sent_to_conform_in_a_command_that_pastes(
    tmp_path, monkeypatch
):
    """Most real template names carry spaces or brackets, which a shell splits or globs."""
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path))
    brand = tmp_path / "Free Doodle [Dark].pptx"
    Presentation().save(str(brand))
    message = _routed("Free Doodle [Dark].pptx")
    assert "is a template, not a theme" in message
    assert _command(message) == ["deckwright", "conform", str(brand), "--adopt", "free-doodle-dark"]
    assert message.endswith("then build with 'theme: free-doodle-dark'")


def test_a_template_already_adopted_names_the_theme_to_build_with(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path))
    Presentation().save(str(tmp_path / "Brand.pptx"))
    (tmp_path / "house.theme.yaml").write_text("name: house\ntemplate: Brand.pptx\n")
    (tmp_path / "other.theme.yaml").write_text("name: other\ntemplate: Else.pptx\n")
    assert _routed(tmp_path / "Brand.pptx").endswith(
        "it is already adopted — build with 'theme: house'"
    )


def test_a_template_outside_the_theme_dir_is_moved_in_before_conform(tmp_path, monkeypatch):
    """`conform --adopt` refuses a template that does not live in the theme dir."""
    root = tmp_path / "themes"
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(root))
    brand = tmp_path / "My Brand.pptx"
    Presentation().save(str(brand))
    words = _command(_routed(brand))
    assert words[:3] == ["mkdir", "-p", str(root)]
    assert words[4:7] == ["mv", str(brand), f"{root}/"]
    assert words[8:] == [
        "deckwright",
        "conform",
        str(root / "My Brand.pptx"),
        "--adopt",
        "my-brand",
    ]


def test_a_template_whose_name_is_taken_in_the_theme_dir_is_never_moved_over_it(
    tmp_path, monkeypatch
):
    """`mv` into the theme dir would replace the adopted binary, then re-adopt over its theme."""
    root = tmp_path / "themes"
    root.mkdir()
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(root))
    Presentation().save(str(root / "Brand.pptx"))
    (root / "house.theme.yaml").write_text("name: house\ntemplate: Brand.pptx\n")
    newer = Presentation()
    newer.slides.add_slide(newer.slide_layouts[0])
    newer.save(str(tmp_path / "Brand.pptx"))

    message = _routed(tmp_path / "Brand.pptx")

    assert "mv " not in message
    assert f"{root}/ already holds a different Brand.pptx, adopted as 'house'," in message


def test_a_copy_of_a_template_already_in_the_theme_dir_routes_to_that_one(tmp_path, monkeypatch):
    import shutil

    root = tmp_path / "themes"
    root.mkdir()
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(root))
    Presentation().save(str(root / "Brand.pptx"))
    (root / "house.theme.yaml").write_text("name: house\ntemplate: Brand.pptx\n")
    shutil.copy(root / "Brand.pptx", tmp_path / "Brand.pptx")

    assert _routed(tmp_path / "Brand.pptx").endswith(
        "it is already adopted — build with 'theme: house'"
    )


def test_a_template_symlinked_into_the_theme_dir_is_routed_as_living_there(tmp_path, monkeypatch):
    """Resolving the link itself compares the file with itself, forever."""
    root = tmp_path / "themes"
    root.mkdir()
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(root))
    Presentation().save(str(tmp_path / "Brand.pptx"))
    (root / "Brand.pptx").symlink_to(tmp_path / "Brand.pptx")

    assert _command(_routed(root / "Brand.pptx")) == [
        "deckwright",
        "conform",
        str(root / "Brand.pptx"),
        "--adopt",
        "brand",
    ]


def test_a_template_that_is_nowhere_still_routes_to_conform(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path))
    message = _routed("Brand.pptx")
    assert f"there is no file at Brand.pptx or in {tmp_path}/" in message
    assert _command(message) == [
        "deckwright",
        "conform",
        str(tmp_path / "Brand.pptx"),
        "--adopt",
        "brand",
    ]


def test_a_theme_file_that_is_not_text_is_a_theme_error(tmp_path):
    binary = tmp_path / "noise.yaml"
    binary.write_bytes(b"\x8b\xff\x00\x91 not utf-8")
    with pytest.raises(ThemeError, match=r"noise\.yaml is not a text theme file"):
        load_theme(binary)
