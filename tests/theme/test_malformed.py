"""A malformed theme is a ThemeError naming the key and the value it holds — never a raw
TypeError, OverflowError, ValueError or RuntimeError, and never a theme that loads into
nonsense."""

from __future__ import annotations

import os

import pytest

from deckwright.errors import ThemeError
from deckwright.panels.css import panel_css
from deckwright.theme import load_theme
from deckwright.theme.resolve import theme_file

_TOO_BIG = "1" + "0" * 400
_TOO_LONG = "x" * 300


def _load(tmp_path, body: str):
    path = tmp_path / "t.theme.yaml"
    path.write_text(f"name: t\n{body}", encoding="utf-8")
    return load_theme(path)


def _refusal(tmp_path, body: str) -> str:
    with pytest.raises(ThemeError) as e:
        _load(tmp_path, body)
    return str(e.value)


@pytest.mark.parametrize(
    ("body", "names"),
    [
        pytest.param(
            "scale: {2021-01-01: x, zzz: y}\n",
            "'scale': unknown key 2021-01-01; known keys: body_top, columns, gutter, margin, "
            "rows — YAML reads 2021-01-01 as a date; quote the key",
            id="scale-date",
        ),
        pytest.param(
            "motion: {on: 1, zzz: 2}\n",
            "unknown motion key true; known keys: stagger_ms, advance, beat_ms, roles, "
            "transition — YAML reads an unquoted yes, on or true as the boolean true",
            id="motion-bool",
        ),
        pytest.param(
            "on: 1\nzzz: 2\n", "has unknown top-level key true; known keys: bind", id="top-bool"
        ),
    ],
)
def test_a_key_yaml_read_as_a_date_or_a_boolean_is_named(tmp_path, body, names):
    assert names in _refusal(tmp_path, body)


@pytest.mark.parametrize(
    ("body", "names"),
    [
        pytest.param(
            "chart: {gap_width: .inf}\n", "chart.gap_width must be an int, got inf", id="int-inf"
        ),
        pytest.param(
            "chart: {shadow_blur_pt: .inf}\n",
            "chart.shadow_blur_pt must be a finite number, got inf",
            id="float-inf",
        ),
        pytest.param(
            "chart: {gradient_angle: .nan}\n",
            "chart.gradient_angle must be a finite number, got nan",
            id="float-nan",
        ),
        pytest.param(
            f"chart: {{shadow_dir_deg: {_TOO_BIG}}}\n",
            f"chart.shadow_dir_deg must be a number, got {_TOO_BIG}",
            id="float-overflow",
        ),
    ],
)
def test_a_chart_number_that_is_not_finite_is_refused_by_name(tmp_path, body, names):
    assert names in _refusal(tmp_path, body)


@pytest.mark.parametrize("key", ["template", "icons"])
@pytest.mark.parametrize(
    ("value", "why"),
    [
        pytest.param('"a\\0b"', "'a\\x00b' holds a NUL character", id="nul"),
        pytest.param(
            _TOO_LONG, f"'{_TOO_LONG}' has a name longer than the filesystem allows", id="long"
        ),
        pytest.param("loop/child", "'loop/child' runs into a symlink loop", id="loop"),
    ],
)
def test_a_path_the_filesystem_cannot_follow_is_refused_by_name(tmp_path, key, value, why):
    (tmp_path / "loop").symlink_to(tmp_path / "loop")
    message = _refusal(tmp_path, f"{key}: {value}\n")
    assert f"t.theme.yaml: {key} {why}; it names a path beside the theme" in message


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads through a mode-000 directory")
def test_a_path_through_a_directory_nobody_may_search_is_refused_by_name(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        message = _refusal(tmp_path, "template: locked/brand.pptx\n")
    finally:
        locked.chmod(0o755)
    assert "template 'locked/brand.pptx' cannot be looked up: Permission denied" in message


def test_a_theme_name_too_long_to_look_up_is_a_theme_error():
    with pytest.raises(ThemeError, match=r"^theme 'x+' cannot be looked up: File name too long$"):
        theme_file(_TOO_LONG)


def test_an_unusable_template_path_in_another_theme_does_not_stop_the_routing(
    tmp_path, monkeypatch, synthetic_template
):
    """Routing a `.pptx` reads every adopted theme's `template:`; one of them holding a NUL
    is that theme's problem, not this template's."""
    monkeypatch.setenv("DECKWRIGHT_THEME_DIR", str(tmp_path))
    (tmp_path / "Brand.pptx").write_bytes(synthetic_template.read_bytes())
    (tmp_path / "broken.theme.yaml").write_text('name: broken\ntemplate: "a\\0b"\n')
    with pytest.raises(ThemeError, match=r"Brand\.pptx is a template, not a theme — onboard"):
        theme_file(tmp_path / "Brand.pptx")


@pytest.mark.parametrize(
    ("body", "names"),
    [
        pytest.param(
            "type: {min_pt: -10.0}\n", "type.min_pt is a point size above zero, got -10.0", id="min"
        ),
        pytest.param(
            "type: {min_pt: 0}\n", "type.min_pt is a point size above zero, got 0.0", id="min-0"
        ),
        pytest.param(
            "type: {line_weight_pt: -1}\n",
            "type.line_weight_pt is a point size above zero, got -1.0",
            id="line-weight",
        ),
        pytest.param(
            "type: {ramp: {title: {pt: -4}}}\n",
            "type ramp entry 'title': pt is a point size above zero, got -4.0",
            id="ramp",
        ),
    ],
)
def test_a_point_size_at_or_below_zero_is_refused_by_name(tmp_path, body, names):
    assert names in _refusal(tmp_path, body)


@pytest.mark.parametrize(
    ("body", "names"),
    [
        pytest.param(
            "type: {reference_height: 5.0e-324}\n",
            "type.reference_height is 5e-324, too small to divide by — 1pt over it is past any "
            "finite point size",
            id="alone",
        ),
        pytest.param(
            "type: {reference_height: 1.0e-307, ramp: {title: {pt: 34}}}\n",
            "type ramp entry 'title': pt 34.0 over type.reference_height 1e-307 is past any "
            "finite point size",
            id="ramp",
        ),
        pytest.param(
            "type: {reference_height: 1.0e-307, min_pt: 10}\n",
            "type.min_pt 10.0 over type.reference_height 1e-307 is past any finite point size",
            id="min-pt",
        ),
    ],
)
def test_a_reference_height_too_small_to_divide_by_is_refused_by_name(tmp_path, body, names):
    assert names in _refusal(tmp_path, body)


@pytest.mark.parametrize(
    ("body", "names"),
    [
        pytest.param(
            "type: {face: [a]}\n", "type.face is one typeface name, like 'Helvetica', got ['a']"
        ),
        pytest.param(
            "type: {heading_face: 12}\n",
            "type.heading_face is one typeface name, like 'Helvetica', got 12",
        ),
        pytest.param(
            "type: {mono: yes}\n", "type.mono is one typeface name, like 'Helvetica', got True"
        ),
        pytest.param(
            "type: {ramp: {title: {pt: 34, face: [a]}}}\n",
            "type ramp entry 'title': face is one typeface name, like 'Helvetica', got ['a']",
        ),
    ],
)
def test_a_face_that_is_not_one_name_is_refused_by_name(tmp_path, body, names):
    assert names in _refusal(tmp_path, body)


@pytest.mark.parametrize(
    ("body", "names"),
    [
        pytest.param(
            "scale: {margin: {top: nan%}}\n", "top is a percent of the canvas, got 'nan%'"
        ),
        pytest.param("scale: {gutter: inf%}\n", "gutter is a percent of the canvas, got 'inf%'"),
        pytest.param(
            "scale: {body_top: 1e400%}\n", "body_top is a percent of the canvas, got '1e400%'"
        ),
        pytest.param(
            "reserve: [{name: r, poly: [{x: nan%, y: 0%}]}]\n",
            "reserved region 'r': poly.x is a percent of the canvas, got 'nan%'",
        ),
    ],
)
def test_a_percent_that_is_not_finite_is_refused_by_name(tmp_path, body, names):
    assert names in _refusal(tmp_path, body)


def test_a_rung_named_by_a_yaml_boolean_still_loads_into_a_ramp_that_sorts(tmp_path):
    """`on:` as a rung name loads as True. Kept as that key, it breaks every later sort of the
    ramp — the panel stylesheet is one — with a TypeError at build time."""
    theme = _load(tmp_path, "type: {ramp: {on: {pt: 12}}}\n")
    assert "--t-True: 12.0pt;" in panel_css(theme)
