"""The XML deckwright reads did not necessarily come from deckwright.

`conform`, `qa`, `inspect` and `diff` all parse a `.pptx` the user was sent. lxml's
default parser expands entities declared in an inline DTD; `deckwright.utils.xml` refuses
them. Delete `resolve_entities=False` there and every test here goes red.
"""

from __future__ import annotations

import pathlib
import re
import zipfile

from deckwright.conform.sample import MARKER, is_sample
from deckwright.utils.xml import fromstring as parse_xml

_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_SRC = pathlib.Path(__file__).resolve().parents[1] / "src/deckwright"


def test_an_inline_entity_is_not_expanded():
    """The default parser returns 'BOOM' here — that is the whole difference."""
    xml = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "BOOM">]><r>&a;</r>'
    assert parse_xml(xml).text is None


def test_entity_amplification_expands_to_nothing():
    xml = (
        b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa">'
        b'<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]><l>&b;</l>'
    )
    assert parse_xml(xml).text is None


def test_a_hostile_package_cannot_forge_the_sample_marker(tmp_path):
    """`is_sample` reads `docProps/core.xml` out of any path it is handed. With entities
    resolved, a file that merely *declares* the marker as an entity is accepted as ours."""
    core = (
        f'<?xml version="1.0"?>\n'
        f'<!DOCTYPE cp:coreProperties [<!ENTITY spoof "{MARKER}">]>\n'
        f'<cp:coreProperties xmlns:cp="{_CP}">'
        f"<cp:category>&spoof;</cp:category></cp:coreProperties>"
    )
    hostile = tmp_path / "hostile.pptx"
    with zipfile.ZipFile(hostile, "w") as z:
        z.writestr("docProps/core.xml", core)

    assert is_sample(hostile) is False

    # Control: the same bytes with the marker written literally ARE recognised, so the
    # assertion above is about entity expansion and not about the reader being broken.
    honest = tmp_path / "honest.pptx"
    with zipfile.ZipFile(honest, "w") as z:
        z.writestr(
            "docProps/core.xml",
            f'<?xml version="1.0"?><cp:coreProperties xmlns:cp="{_CP}">'
            f"<cp:category>{MARKER}</cp:category></cp:coreProperties>",
        )
    assert is_sample(honest) is True


def test_no_module_parses_xml_with_the_default_parser():
    """The gate on the fix. A rule you have to remember has already failed once."""
    offenders = []
    for path in _SRC.rglob("*.py"):
        if path.name == "xml.py" and path.parent.name == "utils":
            continue
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"etree\.(fromstring|XML|parse|fromstringlist)\(", line):
                offenders.append(f"{path.relative_to(_SRC)}:{i}")
    assert offenders == [], (
        "parse untrusted XML through deckwright.utils.xml.fromstring, not lxml directly: "
        + ", ".join(offenders)
    )
