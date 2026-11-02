"""Shared fixtures for compile tests: a synthetic project and its theme."""

from __future__ import annotations

import textwrap

import pytest

_THEME_YAML = """
    name: testtheme
    template: assets/t.pptx
    bind: {page: lt1, ink: dk1, inverse: dk1, line: lt2}
    type:
      min_pt: 10.5
      ramp:
        kicker: {pt: 14, bold: true}
        caption: {pt: 12}
        body: {pt: 13.5}
        lead: {pt: 19}
        head: {pt: 18, bold: true}
        stat: {pt: 30, bold: true}
        subtitle: {pt: 15}
        title: {pt: 32, bold: true}
        display: {pt: 46, bold: true}
        hero: {pt: 52, bold: true}
    scale:
      margin: {top: 4%, right: 4.5751%, bottom: 6.6667%, left: 4.6501%}
      columns: 12
      gutter: 1.35%
      body_top: 22.6667%
"""

_DECK_YAML = """
    theme: testtheme
    title: Demo
    sections: [One, Two]
    out: out/Demo.pptx
    ---
    section: One
    kicker: One
    title: First
    ---
    section: Two
    background: inverse
    title: Two
    subtitle: The second act.
    ---
    section: Two
    title: Second
    subtitle: With a subhead
"""


@pytest.fixture
def theme_yaml() -> str:
    """The dedented ``testtheme.yaml`` text, for tests that lay out their own dirs."""
    return textwrap.dedent(_THEME_YAML)


@pytest.fixture
def project(tmp_path, synthetic_template, theme_yaml):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "t.pptx").write_bytes(synthetic_template.read_bytes())
    (tmp_path / "testtheme.yaml").write_text(theme_yaml)
    (tmp_path / "d.deck.yaml").write_text(textwrap.dedent(_DECK_YAML))
    return tmp_path
