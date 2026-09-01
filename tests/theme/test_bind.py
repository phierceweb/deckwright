import pathlib
import textwrap

import logging

import pytest

from deckwright.errors import ThemeError
from deckwright.theme import load_theme
from deckwright.theme.defaults import DEFAULT_ROLES


def _midtone_template(tmp_path) -> pathlib.Path:
    """A template whose accent1 clears neither its page nor its ink at 4.5:1 — 7272BC reads 4.33:1
    on FFFFFF and 4.34:1 on 101020. That window only exists because the ink is *near*-black, which
    is why the scheme is hand-built rather than stock."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    path = tmp_path / "midtone.pptx"
    prs.save(str(path))
    _edit_scheme(path, {"accent1": "7272BC", "lt1": "FFFFFF", "dk1": "101020"})
    return path


def _edit_scheme(path: pathlib.Path, slots: dict[str, str]) -> None:
    """Rewrite clrScheme slots in the saved package — the loader reads the file."""
    import shutil
    import zipfile

    from lxml import etree

    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    tmp = path.with_suffix(".tmp.pptx")
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w") as dst:
        for item in src.namelist():
            data = src.read(item)
            if item.endswith("theme/theme1.xml"):
                root = etree.fromstring(data)
                for slot, hexval in slots.items():
                    holder = root.find(f".//{{{A}}}{slot}")
                    for child in list(holder):
                        holder.remove(child)
                    etree.SubElement(holder, f"{{{A}}}srgbClr").set("val", hexval)
                data = etree.tostring(root, xml_declaration=True, standalone=True)
            dst.writestr(item, data)
    shutil.move(tmp, path)


BASE = """
    name: testtheme
    template: assets/t.pptx
    bind:
      page: lt1
      ink:  dk1
    type:
      min_pt: 10.5
      ramp:
        title: {pt: 32, bold: true}
        body: {pt: 13.5}
    scale:
      margin: {top: 4%, right: 4.6%, bottom: 6.7%, left: 4.6%}
      columns: 12
      gutter: 1.35%
      body_top: 22.7%
"""


def _write(tmp_path, template, body: str):
    (tmp_path / "assets").mkdir(exist_ok=True)
    (tmp_path / "assets" / "t.pptx").write_bytes(template.read_bytes())
    path = tmp_path / "t.yaml"
    path.write_text(textwrap.dedent(body))
    return path


def test_a_bound_role_takes_the_templates_value(tmp_path, synthetic_template):
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.palette.role("page") == "FFFFFF"  # lt1
    assert theme.palette.role("ink") == "000000"  # dk1


def test_an_unbound_role_keeps_the_system_default(tmp_path, synthetic_template):
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.palette.role("line") == DEFAULT_ROLES["line"]
    assert theme.palette.role("surface") == DEFAULT_ROLES["surface"]


def test_a_theme_that_binds_nothing_at_all_still_loads(tmp_path, synthetic_template):
    body = BASE.replace("    bind:\n      page: lt1\n      ink:  dk1\n", "")
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert theme.palette.roles == DEFAULT_ROLES


def test_an_accent_bound_to_an_unedited_slot_keeps_the_system_default(tmp_path, synthetic_template):
    """The synthetic template's accent1 is stock Office, so the bind says nothing."""
    body = BASE.replace("      ink:  dk1", "      ink:  dk1\n      accent-1: accent1")
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert theme.palette.role("accent-1") == DEFAULT_ROLES["accent-1"]


def test_an_extra_accent_bound_to_an_unedited_slot_never_joins_the_ramp(
    tmp_path, synthetic_template
):
    body = BASE.replace("      ink:  dk1", "      ink:  dk1\n      accent-7: accent3")
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert "accent-7" not in theme.palette.roles
    assert "accent-7" not in theme.palette.accents


def test_an_extra_accent_bound_to_an_edited_slot_joins_the_ramp(tmp_path, synthetic_template):
    """dk2 (1F497D) is not one of Microsoft's accent values, so the bind is real."""
    body = BASE.replace("      ink:  dk1", "      ink:  dk1\n      accent-5: dk2")
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert theme.palette.role("accent-5") == "1F497D"
    assert theme.palette.accents[-1] == "accent-5"


def test_a_bound_accent_gets_whichever_ink_reads_on_it(tmp_path, synthetic_template):
    """Both branches: dark dk2 needs white, near-white lt2 needs ink. A fixed white
    accent-ink would make the second unloadable."""
    body = BASE.replace(
        "      ink:  dk1", "      ink:  dk1\n      accent-5: dk2\n      accent-6: lt2"
    )
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert theme.palette.pair("accent-5").fg == "FFFFFF"  # page on 1F497D, 9.10:1
    assert theme.palette.pair("accent-6").fg == "000000"  # ink on EEECE1, 17.72:1


def test_a_brand_midtone_neither_ink_reads_on_still_carries_text(tmp_path):
    """An accent clearing neither the page nor the ink. Rejecting the theme would make a
    real brand file unusable, and refusing the pair made a cover on the brand colour
    unbuildable — so the ranking widens to black."""
    template = _midtone_template(tmp_path)
    body = BASE.replace("      ink:  dk1", "      accent-1: accent1")
    theme = load_theme(_write(tmp_path, template, body))
    assert theme.palette.role("accent-1") == "7272BC"
    # The better declared ink, not an invented one.
    assert theme.palette.pair("accent-1").fg in set(theme.palette.roles.values())


def test_a_bind_to_an_unknown_template_slot_is_rejected(tmp_path, synthetic_template):
    body = BASE.replace("page: lt1", "page: accent99")
    with pytest.raises(ThemeError, match="accent99"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_bind_of_an_unknown_role_is_rejected(tmp_path, synthetic_template):
    body = BASE.replace("      ink:  dk1", "      eyebrow: dk1")
    with pytest.raises(ThemeError, match="unknown role 'eyebrow'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_bind_that_puts_white_text_on_a_white_background_is_reported(
    tmp_path, synthetic_template, caplog
):
    """inverse-ink defaults to white; binding inverse to lt1 makes the pair invisible. The
    theme still loads — a real brand file did exactly this, and refusing cost every slide."""
    body = BASE.replace("      ink:  dk1", "      ink:  dk1\n      inverse: lt1")
    with caplog.at_level(logging.WARNING):
        theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert theme.palette.pair("inverse").fg == theme.palette.pair("inverse").bg
    assert "theme_pair_below_aa" in caplog.text


def test_a_replaced_top_level_key_names_what_replaced_it(tmp_path, synthetic_template):
    body = BASE.replace("    name: testtheme", "    name: testtheme\n    compose_on: Blank")
    with pytest.raises(ThemeError, match="'compose_on' is gone"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_the_deleted_roles_block_names_what_replaced_it(tmp_path, synthetic_template):
    body = BASE.replace("    name: testtheme", "    name: testtheme\n    roles: {bg: lt1}")
    with pytest.raises(ThemeError, match="'roles' was replaced by 'bind'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_an_unrecognised_top_level_key_is_rejected(tmp_path, synthetic_template):
    body = BASE.replace("    name: testtheme", "    name: testtheme\n    colours: {}")
    with pytest.raises(ThemeError, match="unknown top-level key 'colours'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_the_scale_comes_from_the_template(tmp_path, synthetic_template):
    theme = load_theme(_write(tmp_path, synthetic_template, BASE))
    assert theme.scale.slide_h == pytest.approx(7.5, abs=1e-3)
    assert theme.scale.slide_w == pytest.approx(13.333, abs=1e-3)


def test_the_line_weight_default_is_a_rung_of_the_canvas(tmp_path, wide_template):
    """Every other size in the system is canvas-relative; the stroke is too."""
    theme = load_theme(_write(tmp_path, wide_template, BASE))
    assert theme.line_weight == pytest.approx(4.5, abs=1e-6)  # 2.25pt at 7.5in


def test_a_role_can_be_bound_to_a_literal_colour(tmp_path, synthetic_template):
    """A master painting a photograph shows a colour no clrScheme slot names."""
    body = BASE.replace(
        "      page: lt1\n      ink:  dk1",
        "      page: '193A6F'\n      ink: lt1\n      muted: AEBACD",
    )
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert theme.palette.role("page") == "193A6F"
    assert theme.palette.pair("page").fg == "FFFFFF"


def test_a_literal_colour_may_carry_a_leading_hash(tmp_path, synthetic_template):
    body = BASE.replace(
        "      page: lt1\n      ink:  dk1",
        "      page: '#193A6F'\n      ink: lt1\n      muted: AEBACD",
    )
    assert load_theme(_write(tmp_path, synthetic_template, body)).palette.role("page") == "193A6F"


def test_a_value_that_is_neither_a_slot_nor_a_colour_is_rejected(tmp_path, synthetic_template):
    body = BASE.replace("      page: lt1", "      page: navyish")
    with pytest.raises(ThemeError, match="unknown template slot 'navyish'"):
        load_theme(_write(tmp_path, synthetic_template, body))


def test_a_literal_accent_is_kept_even_when_it_equals_a_stock_office_colour(
    tmp_path, synthetic_template
):
    """The stock-accent guard means "the brand edited no slot here". A literal is what
    the author typed, so it survives whatever it happens to equal."""
    body = BASE.replace("      page: lt1", "      page: lt1\n      accent-1: '4472C4'")
    theme = load_theme(_write(tmp_path, synthetic_template, body))
    assert theme.palette.role("accent-1") == "4472C4"
