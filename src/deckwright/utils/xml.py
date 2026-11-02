"""XML parsing for bytes that came from somewhere else.

A `.pptx` is a zip of XML, and `conform`, `qa`, `inspect` and `diff` all read one
the user was sent rather than one deckwright wrote. `lxml`'s default parser expands
entities declared in an inline DTD, which is both an entity-amplification lever and,
on older libxml2, a local-file read.
"""

from __future__ import annotations

from typing import Any

from lxml import etree


def _parser() -> etree.XMLParser:
    # Fresh per call: an lxml parser carries error state and is not safe to share.
    return etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


def fromstring(data: bytes) -> Any:
    """Parse ``data`` with entity expansion and network access refused."""
    return etree.fromstring(data, parser=_parser())
