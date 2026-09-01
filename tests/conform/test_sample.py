"""The generated onboarding template: what it must carry, and what it must not become."""

from __future__ import annotations

import hashlib
import zipfile

import pytest
from lxml import etree

from deckwright.conform.derive import derive
from deckwright.conform.sample import FACE, MARKER, PALETTE, is_sample, write_sample
from deckwright.theme.stock import is_stock_accent
from deckwright.utils.text import measured

A = "http://schemas.openxmlformats.org/drawingml/2006/main"


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    return write_sample(tmp_path_factory.mktemp("sample") / "sample.pptx")


def _theme_xml(path) -> bytes:
    with zipfile.ZipFile(path) as package:
        return package.read("ppt/theme/theme1.xml")


def test_no_accent_is_one_microsoft_ships(sample):
    """A stock accent is discarded by `derive`, so a sample built from the shipped
    scheme would bind no brand colour and conform would report on our own defaults."""
    scheme = etree.fromstring(_theme_xml(sample)).find(f"{{{A}}}themeElements/{{{A}}}clrScheme")
    accents = {
        etree.QName(c).localname: c.find(f"{{{A}}}srgbClr").get("val")
        for c in scheme
        if etree.QName(c).localname.startswith("accent")
    }
    assert len(accents) == 6
    assert [s for s, v in sorted(accents.items()) if is_stock_accent(v)] == []


def test_the_derived_theme_binds_every_accent_and_a_hued_inverse(sample):
    """What the template is *for*: a conform run that exercises the real binding path."""
    theme = derive(sample)
    bind = theme["bind"]
    assert [k for k in bind if k.startswith("accent-")] == [f"accent-{i}" for i in range(1, 7)]
    assert bind["inverse"] == "dk2", "the hued dark, not the near-black ink"
    assert bind["page"] == "lt1" and bind["ink"] == "dk1"


def test_the_face_it_teaches_is_one_deckwright_can_measure(sample):
    """`derive` writes the dominant run face into the adopted theme, so an unmeasured face
    reaches every deck and lays it out against the widest-glyph ceiling."""
    assert measured(FACE), f"{FACE} has no advance table"
    assert derive(sample)["type"]["face"] == FACE
    fonts = etree.fromstring(_theme_xml(sample)).find(f"{{{A}}}themeElements/{{{A}}}fontScheme")
    for kind in ("major", "minor"):
        declared = fonts.find(f"{{{A}}}{kind}Font/{{{A}}}latin").get("typeface")
        assert measured(declared), f"fontScheme {kind} is {declared}, which is unmeasured"


def test_it_is_stamped_so_the_corpus_guard_can_refuse_it(sample):
    """The mark is the firewall. Drop the stamp and the sample silently becomes
    brand-variance evidence it cannot be — see tests/test_templates.py's collection."""
    assert is_sample(sample)
    with zipfile.ZipFile(sample) as package:
        assert MARKER.encode() in package.read("docProps/core.xml")


def test_a_real_template_is_not_mistaken_for_the_sample(tmp_path):
    """`is_sample` gates the corpus, so a false positive would drop a real template."""
    from pptx import Presentation

    plain = tmp_path / "plain.pptx"
    Presentation().save(str(plain))
    assert not is_sample(plain)
    assert not is_sample(tmp_path / "does-not-exist.pptx")


def test_two_writes_are_the_same_file(tmp_path):
    """python-pptx stamps entries with the local clock; the canonicalize pass exists
    so setup rewriting the sample is not a spurious change."""
    first = write_sample(tmp_path / "a.pptx").read_bytes()
    second = write_sample(tmp_path / "b.pptx").read_bytes()
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()


def test_the_palette_it_declares_is_the_one_it_writes(sample):
    """The constant is the documented surface; the file is what conform reads."""
    scheme = etree.fromstring(_theme_xml(sample)).find(f"{{{A}}}themeElements/{{{A}}}clrScheme")
    written = {etree.QName(c).localname: c.find(f"{{{A}}}srgbClr").get("val") for c in scheme}
    assert {k: written[k] for k in PALETTE} == PALETTE
