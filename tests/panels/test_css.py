import dataclasses

from deckwright.panels.css import panel_css


def test_every_colour_role_becomes_a_custom_property(theme):
    css = panel_css(theme)
    for role, value in theme.palette.roles.items():
        assert f"--c-{role}: #{value}" in css


def test_every_type_rung_becomes_a_custom_property(theme):
    css = panel_css(theme)
    for role, style in theme.ramp.items():
        assert f"--t-{role}: {style.size}pt" in css


def test_the_faces_are_declared(theme):
    css = panel_css(theme)
    assert f'--font: "{theme.face}"' in css
    assert f'--font-mono: "{theme.mono}"' in css


def test_the_font_stack_ends_in_a_generic_family(theme):
    """A bare face falls back to the browser's default serif the moment it is not installed:
    var()'s own fallback never fires for a defined variable, so the family is baked in."""
    css = panel_css(theme)
    font_line = next(ln for ln in css.splitlines() if ln.strip().startswith("--font:"))
    mono_line = next(ln for ln in css.splitlines() if ln.strip().startswith("--font-mono:"))
    assert font_line.rstrip(";").rstrip().endswith("sans-serif")
    assert mono_line.rstrip(";").rstrip().endswith("monospace")


def test_it_is_a_root_block(theme):
    css = panel_css(theme).strip()
    assert css.startswith(":root {")
    assert css.endswith("}")


def test_output_does_not_depend_on_dict_insertion_order(theme):
    reversed_roles = dict(reversed(list(theme.palette.roles.items())))
    shuffled = dataclasses.replace(
        theme,
        palette=dataclasses.replace(theme.palette, roles=reversed_roles),
        ramp=dict(reversed(list(theme.ramp.items()))),
    )
    assert panel_css(shuffled) == panel_css(theme)


def test_every_declaration_is_terminated(theme):
    body = [ln.strip() for ln in panel_css(theme).splitlines()[1:-1]]
    assert body and all(ln.endswith(";") for ln in body)


def test_output_tracks_theme_values(theme):
    shuffled = dataclasses.replace(
        theme,
        palette=dataclasses.replace(
            theme.palette, roles={**theme.palette.roles, "accent-1": "123456"}
        ),
        face="Georgia",
    )
    css = panel_css(shuffled)
    assert "--c-accent-1: #123456" in css
    assert '--font: "Georgia"' in css
    assert "#27B94C" not in css
