"""``[words](address)`` inside a line of copy: parsing it, measuring what it shows, writing it.

A link keeps the ink its line was given, contrast-checked like the rest, and is underlined
so colour is not the only thing marking it. Office draws a hyperlink in the theme's
``hlink`` slot unless the link carries [MS-ODRAWXML]'s ``hlinkClr val="tx"``, so every
link writes that too. ``\\[`` keeps a bracket as text.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from lxml import etree
from pptx.oxml.ns import qn

LINK = re.compile(
    r"(?<!\\)\[(?P<words>(?:[^\[\]\n]|\[[^\[\]\n]*\])+)\]"
    r"\((?P<address>(?:[^()\s]|\([^()\s]*\))*)\)"
)
WEB_SCHEMES = ("http", "https", "mailto")
HLINK_COLOR_NS = "http://schemas.microsoft.com/office/drawing/2018/hyperlinkcolor"
HLINK_COLOR_EXT = "{A12FA001-AC4F-418D-AE19-62706E023703}"
_ESCAPED = re.compile(r"\\\[")


def spans(text: str) -> list[tuple[str, str | None]]:
    """``text`` as ``(words, address)`` runs in order; ``address`` is None between links."""
    out: list[tuple[str, str | None]] = []
    at = 0
    for match in LINK.finditer(text):
        if match.start() > at:
            out.append((_unescape(text[at : match.start()]), None))
        out.append((_unescape(match["words"]), match["address"]))
        at = match.end()
    if at < len(text) or not out:
        out.append((_unescape(text[at:]), None))
    return out


def plain(text: str) -> str:
    """What ``text`` shows once its links are drawn: the words, without the markup."""
    return "".join(words for words, _ in spans(text)) if "[" in text else text


def addresses(text: str) -> list[str]:
    """Every link address in ``text``, in order."""
    return [match["address"] for match in LINK.finditer(text)]


def web_address_problem(address: str) -> str | None:
    """Why ``address`` is not a web address a click can open, or None when it is."""
    parts = urlsplit(address)
    if parts.scheme.lower() not in WEB_SCHEMES:
        return (
            f"{address!r} is not a web address — a link opens http://, https:// or mailto:, "
            f"and anything else is run or opened as a local file"
        )
    if parts.scheme.lower() == "mailto":
        return None if "@" in parts.path else f"{address!r} names no email address"
    if not parts.netloc or any(c.isspace() for c in address):
        return f"{address!r} is not a whole address — it needs a host, and no spaces"
    return None


def link_run(run: Any, address: str) -> None:
    """Make ``run`` a hyperlink to ``address``, drawn in its own ink and underlined."""
    run.hyperlink.address = address
    run.font.underline = True
    hlink = run._r.rPr.find(qn("a:hlinkClick"))
    ext_lst = etree.SubElement(hlink, qn("a:extLst"))
    ext = etree.SubElement(ext_lst, qn("a:ext"), uri=HLINK_COLOR_EXT)
    etree.SubElement(ext, f"{{{HLINK_COLOR_NS}}}hlinkClr", nsmap={"ahyp": HLINK_COLOR_NS}, val="tx")


def _unescape(text: str) -> str:
    return _ESCAPED.sub("[", text)
