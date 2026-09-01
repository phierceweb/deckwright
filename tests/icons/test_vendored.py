"""The vendored Material Symbols set: how a name reaches it, and what may be in it. Read
through the loader's bundle API — the set travels as one archive — and measured with
:mod:`deckwright.icons.vendor`, so the suite and `deckwright glyphs sync` agree on what ships."""

from __future__ import annotations

import math

import pytest
from lxml import etree

from deckwright.errors import SpecError
from deckwright.icons.aliases import ALIASES, OVERRIDES
from deckwright.icons.load import BUNDLE, VENDORED, Glyph, _find, available, builtin_bytes, load
from deckwright.icons.vendor import NOISE, winding_disagreement

from tests.conftest import LEGACY_GLYPHS

SVG = "{http://www.w3.org/2000/svg}"


def _paths_in(svg: bytes) -> tuple[str, ...]:
    """The `d` attributes straight out of the bytes, without going through the loader."""
    root = etree.fromstring(svg)
    return tuple(str(el.get("d")) for el in root.iter(f"{SVG}path") if el.get("d"))


def _view_of(svg: bytes) -> tuple[float, ...]:
    return tuple(float(v) for v in str(etree.fromstring(svg).get("viewBox")).split())


def _shipped(name: str) -> bytes:
    """The bundle's bytes for ``name``, failing loudly rather than returning None."""
    data = builtin_bytes(name)
    assert data is not None, f"{name} is not in the shipped bundle"
    return data


def test_the_vendored_set_shipped():
    """Every test below is vacuous if the bundle is empty."""
    assert BUNDLE.is_file()
    assert len(available()) > 3000
    assert (VENDORED / "LICENSE").is_file()


def test_the_bundle_matches_the_manifest_it_ships_with():
    """The manifest is the review surface for a re-vendor, so it has to be the truth
    about the bundle beside it — otherwise `git diff` describes a set nobody has."""
    from deckwright.icons import vendor

    assert vendor.verify() == []


@pytest.mark.parametrize("name", LEGACY_GLYPHS)
def test_every_legacy_name_still_resolves(name):
    """The compatibility promise: no deck already written may stop building."""
    assert load(name).subpaths


@pytest.mark.parametrize("name,target", sorted(OVERRIDES.items()))
def test_an_override_replaces_a_glyph_the_set_would_have_supplied(name, target):
    """An override exists to beat the set's own same-named glyph. One that does not
    change the answer belongs in ALIASES, where it cannot shadow anything."""
    found = _find(name, None)
    assert found is not None, "resolves on its own — this is an alias"
    assert load(name).subpaths == _paths_in(_shipped(target))
    assert load(name).subpaths != _paths_in(found.read())


def test_a_theme_glyph_outranks_an_override(tmp_path, monkeypatch):
    """A brand replacing `pin.svg` must get its own pin, not the one we prefer."""
    monkeypatch.setenv("DECKWRIGHT_ICON_DIR", str(tmp_path))
    own = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M 3 3 H 21 V 21 H 3 Z"/></svg>'
    )
    (tmp_path / "pin.svg").write_text(own)
    assert load("pin").subpaths == ("M 3 3 H 21 V 21 H 3 Z",)


def test_a_vendored_name_is_found_under_either_spelling():
    """The set writes `rocket_launch`; deckwright's own names are hyphenated."""
    real = _paths_in(_shipped("rocket_launch"))
    assert load("rocket_launch").subpaths == real
    assert load("rocket-launch").subpaths == real


def test_an_alias_resolves_to_the_glyph_it_names():
    assert load("deploy").subpaths == _paths_in(_shipped("rocket_launch"))
    assert load("team").subpaths == _paths_in(_shipped("groups"))


@pytest.mark.parametrize("alias", sorted(ALIASES))
def test_no_alias_shadows_a_name_that_already_resolves(alias):
    """An alias is consulted only after a miss, so a key that resolves on its own is
    dead weight that reads as if it were doing something."""
    assert _find(alias, None) is None


@pytest.mark.parametrize("alias,target", sorted(ALIASES.items()) + sorted(OVERRIDES.items()))
def test_every_alias_points_at_a_glyph_that_exists(alias, target):
    assert _find(target, None) is not None


def test_an_unknown_name_names_the_closest_real_glyph():
    """Thousands of names make listing them useless; the near miss is the whole help."""
    with pytest.raises(SpecError, match="Did you mean .*rocket_launch"):
        load("rokcet_launch")


def test_a_name_close_to_nothing_says_so_rather_than_guessing():
    with pytest.raises(SpecError, match="Nothing close among the [\\d,]+ names"):
        load("qzxwvu")


@pytest.mark.parametrize("name", ["Check", "check.svg", "../check", "", "a b", "a/b_c"])
def test_a_name_that_is_not_a_slug_is_still_rejected(name):
    """Underscores were let in for the vendored spelling; a path separator was not."""
    with pytest.raises(SpecError, match="must be lowercase letters"):
        load(name)


def test_a_missing_bundle_says_what_to_run_rather_than_guessing_a_near_miss(monkeypatch):
    """Absent glyphs are an install problem, and 'Did you mean…?' over an empty
    vocabulary would send the reader hunting for a typo they did not make."""
    from deckwright.icons import load as load_mod

    monkeypatch.setattr(load_mod, "_bundle", lambda: None)
    with pytest.raises(SpecError, match="glyph bundle is missing.*glyphs sync"):
        load("rocket_launch")


# --- the even-odd guarantee -------------------------------------------------------


def test_the_disagreement_measure_sees_a_hole_that_only_nonzero_would_fill(tmp_path, monkeypatch):
    """Two concentric circles wound the same way: a ring even-odd, a disc nonzero — without
    this the guarantee below could pass by measuring nothing at all."""
    monkeypatch.setenv("DECKWRIGHT_ICON_DIR", str(tmp_path))
    circles = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d='
        '"M 12 2 A 10 10 0 1 0 12 22 A 10 10 0 1 0 12 2 Z '
        '{inner}"/></svg>'
    )
    (tmp_path / "same.svg").write_text(
        circles.format(inner="M 12 6 A 6 6 0 1 0 12 18 A 6 6 0 1 0 12 6 Z")
    )
    (tmp_path / "opposed.svg").write_text(
        circles.format(inner="M 12 6 A 6 6 0 1 1 12 18 A 6 6 0 1 1 12 6 Z")
    )

    same, opposed = load("same"), load("opposed")
    assert winding_disagreement(same.view, same.subpaths) == pytest.approx(math.pi * 36, rel=0.02)
    assert winding_disagreement(opposed.view, opposed.subpaths) == 0.0


def test_no_vendored_glyph_needs_nonzero_winding():
    """deckwright puts every subpath in one `a:path`, which fills even-odd; Material Symbols
    declare no `fill-rule`, so upstream means nonzero. The two part company on the `*_off`
    variants, which is what `deckwright glyphs sync --ref` must keep leaving out."""
    broken = []
    for name in available():
        svg = _shipped(name)
        view = _view_of(svg)
        if winding_disagreement(view, _paths_in(svg)) > NOISE * view[2] * view[3]:
            broken.append(name)
    assert broken == []


def test_the_shipped_glyph_is_a_drawing_the_loader_can_read():
    """`Glyph` is constructed from the bundle in the same shape the loader builds it,
    so a member that parses here but not there would be a difference worth knowing."""
    svg = _shipped("groups")
    direct = Glyph(name="groups", view=_view_of(svg), subpaths=_paths_in(svg))
    assert load("groups") == direct
