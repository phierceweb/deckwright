"""Curating, packing and verifying the glyph set, on a checkout small enough to read."""

from __future__ import annotations

import hashlib
import zipfile

import pytest

from deckwright.errors import SpecError
from deckwright.icons import vendor

GOOD = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M2 2h20v20H2z"/></svg>'
)
PLAIN = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M2 2h20v20H2z"/></svg>'
# A square inside a square wound the same way: even-odd punches a hole, nonzero fills it.
RING = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    b'<path d="M0 0h24v24H0z M6 6h12v12H6z"/></svg>'
)


def _checkout(tmp_path):
    root = tmp_path / "material-design-icons"
    for name, data in (("home", GOOD), ("plain", PLAIN), ("ring", RING)):
        path = root / "symbols" / "web" / name / "materialsymbolsrounded" / f"{name}_fill1_24px.svg"
        path.parent.mkdir(parents=True)
        path.write_bytes(data)
    return root


def test_needs_nonzero_is_true_only_where_the_two_rules_disagree():
    assert vendor.needs_nonzero(RING) is True
    assert vendor.needs_nonzero(GOOD) is False
    assert vendor.needs_nonzero(GOOD.replace(b"0 0 24 24", b"0 0")) is False
    assert (
        vendor.needs_nonzero(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"/>')
        is False
    )


def test_curate_keeps_each_glyph_gives_it_a_viewbox_and_drops_what_needs_nonzero(tmp_path):
    kept, dropped = vendor.curate(_checkout(tmp_path))
    assert sorted(kept) == ["home.svg", "plain.svg"]
    assert dropped == ["ring.svg"]
    assert kept["plain.svg"].startswith(b'<svg viewBox="0 0 24 24" xmlns=')
    assert kept["home.svg"] == GOOD


def test_pack_is_byte_identical_for_one_set_and_stores_without_compressing(tmp_path):
    entries = {"b": PLAIN, "a": GOOD}
    one = vendor.pack(entries, tmp_path / "1.zip")
    two = vendor.pack(dict(reversed(entries.items())), tmp_path / "2.zip")
    assert one.read_bytes() == two.read_bytes()
    with zipfile.ZipFile(one) as z:
        assert [i.filename for i in z.infolist()] == ["a", "b"]
        assert {i.compress_type for i in z.infolist()} == {zipfile.ZIP_STORED}
        assert {i.date_time for i in z.infolist()} == {(1980, 1, 1, 0, 0, 0)}


@pytest.fixture
def licensed(tmp_path, monkeypatch):
    (tmp_path / "LICENSE").write_text("Apache-2.0")
    monkeypatch.setattr(vendor, "MATERIAL", tmp_path)
    return tmp_path


def test_a_manifest_round_trips_and_a_bundle_matching_it_verifies_clean(licensed):
    bundle, manifest = licensed / "g.zip", licensed / "g.sum"
    vendor.pack({"a": GOOD}, bundle)
    vendor.write_manifest({"a": GOOD}, ref="0123456789abcdef", dropped=1, path=manifest)
    ref, hashes = vendor.read_manifest(manifest)
    assert ref == "0123456789abcdef"
    assert hashes == {"a": hashlib.sha256(GOOD).hexdigest()}
    assert vendor.verify(bundle, manifest) == []


def test_verify_names_each_way_a_bundle_can_disagree_with_its_manifest(licensed):
    bundle, manifest = licensed / "g.zip", licensed / "g.sum"
    assert vendor.verify(bundle, manifest) == [
        f"no glyph bundle at {bundle} — run 'deckwright glyphs sync'"
    ]
    vendor.pack({"a": GOOD, "extra": GOOD}, bundle)
    vendor.write_manifest(
        {"a": PLAIN, "gone": GOOD}, ref="0123456789abcdef", dropped=0, path=manifest
    )
    assert vendor.verify(bundle, manifest) == [
        "1 glyph(s) in the manifest are not in the bundle: gone",
        "1 glyph(s) in the bundle are not in the manifest: extra",
        "a does not match its manifest hash",
    ]
    (licensed / "LICENSE").unlink()
    assert vendor.verify(bundle, manifest)[-1] == f"the set's licence is missing from {licensed}"


def test_a_manifest_that_is_missing_or_names_no_commit_is_refused(tmp_path):
    with pytest.raises(SpecError, match=r"no glyph manifest at .*absent\.sum"):
        vendor.read_manifest(tmp_path / "absent.sum")
    (tmp_path / "nopin.sum").write_text("abc  a\n")
    with pytest.raises(SpecError, match=r"glyph manifest .*nopin\.sum names no upstream commit"):
        vendor.read_manifest(tmp_path / "nopin.sum")


def test_sync_curates_packs_and_says_what_moved_against_the_manifest_it_replaces(
    licensed, monkeypatch
):
    """The fetch is a network clone, so a checkout on disk stands in for it; everything after
    the fetch is the real thing."""
    bundle, manifest = licensed / "g.zip", licensed / "g.sum"
    vendor.write_manifest(
        {"home.svg": PLAIN, "old.svg": GOOD}, ref="aaaaaaaaaaaa", dropped=0, path=manifest
    )
    monkeypatch.setattr(vendor, "fetch", lambda ref, into: _checkout(into))

    moved = vendor.sync("bbbbbbbbbbbb", bundle=bundle, manifest=manifest)

    assert moved == {
        "ref": "bbbbbbbbbbbb",
        "kept": 2,
        "dropped": 1,
        "added": ["plain.svg"],
        "removed": ["old.svg"],
        "changed": ["home.svg"],
    }
    assert vendor.read_manifest(manifest)[0] == "bbbbbbbbbbbb"
    assert vendor.verify(bundle, manifest) == []
