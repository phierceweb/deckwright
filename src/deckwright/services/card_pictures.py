"""Embed the pictures a card's HTML names from beside its source, as ``data:`` URIs.

A card's content policy refuses ``file:``, and the markdown behind a card is often not the
author's own, so only a picture that ships under the source's directory is read. Raw HTML in
the markdown reaches the browser as written, so each place it can name a picture is read as a
browser reads it: whatever the quoting, with entities and percent-escapes decoded.
"""

from __future__ import annotations

import base64
import html
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote

from pf_core.exceptions import InvalidInputError

# A quoted attribute value may hold a '>'.
_START_TAG = re.compile(r"""<([a-z][\w:-]*)\b(?:[^>"']|"[^"]*"|'[^']*')*>""", re.I)
_ATTR = re.compile(r"""([^\s"'>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?""")
_STYLE_BLOCK = re.compile(
    r"""(<style\b(?:[^>"']|"[^"]*"|'[^']*')*>)(.*?)(</style\s*>)""", re.I | re.S
)
_CSS_URL = re.compile(r"""\burl\(\s*(?:"([^"]*)"|'([^']*)'|([^)"'\s]*))\s*\)""", re.I)
_REMOTE = ("data:", "http:", "https:")
# An HTML parser reads a bare <image> as <img>; inside <svg> it is SVG's own, with href.
_URL_ATTRS = frozenset(
    {
        ("img", "src"),
        ("image", "src"),
        ("image", "href"),
        ("image", "xlink:href"),
        ("video", "poster"),
    }
)
_SRCSET_ELEMENTS = frozenset({"img", "source"})


class UnembeddableImage(InvalidInputError):
    """A picture a card's markdown names that the card will not embed.

    ``reason`` is ``missing``, ``outside`` (the path leaves the source's directory) or
    ``not-image``; ``src`` is the name as the markdown wrote it.
    """

    def __init__(self, src: str, reason: str) -> None:
        super().__init__(f"{reason}: {src}")
        self.src, self.reason = src, reason


def inline_local_images(body_html: str, base: Path) -> str:
    """Embed each picture ``body_html`` names from under ``base`` as a ``data:`` URI.

    Read: an ``<img>``'s ``src``; each ``srcset`` candidate of an ``<img>`` or a
    ``<source>``; an SVG ``<image>``'s ``href`` or ``xlink:href``; a ``<video>``'s
    ``poster``; and each CSS ``url()``
    in a ``style`` attribute or a ``<style>`` block. A ``url()`` naming a local file that is
    not a picture, such as a font, is left to the browser. ``my%20pic.png`` is
    ``my pic.png``.

    Raises:
        UnembeddableImage: the file is missing, leaves ``base``, or is not an image.
    """
    root = base.resolve()
    body_html = _STYLE_BLOCK.sub(lambda m: _style_block(root, m), body_html)
    return _START_TAG.sub(lambda m: _start_tag(root, m), body_html)


def _style_block(root: Path, match: re.Match[str]) -> str:
    css = _css(root, match.group(2))
    return match.group(0) if css is None else match.group(1) + css + match.group(3)


def _start_tag(root: Path, match: re.Match[str]) -> str:
    tag, element = match.group(0), match.group(1).lower()
    pieces: list[str] = []
    done = 0
    for attr in _ATTR.finditer(tag, 1 + len(element)):
        key, value = attr.group(1).lower(), _value(attr)
        if value is None:
            continue
        if (element, key) in _URL_ATTRS:
            embedded = _data_uri(root, value)
        elif key == "srcset" and element in _SRCSET_ELEMENTS:
            embedded = _srcset(root, value)
        elif key == "style":
            embedded = _css(root, value)
        else:
            continue
        if embedded is not None:
            pieces += [tag[done : attr.start()], f'{key}="{html.escape(embedded)}"']
            done = attr.end()
    return "".join(pieces) + tag[done:]


def _value(attr: re.Match[str]) -> str | None:
    """An attribute's value with its entities decoded; None when it has none."""
    raw = next((v for v in attr.group(2, 3, 4) if v is not None), None)
    return None if raw is None else html.unescape(raw)


def _css(root: Path, css: str) -> str | None:
    """``css`` with each ``url()`` naming a local picture embedded; None when it names none."""

    def embed(match: re.Match[str]) -> str:
        written = next(v for v in match.group(1, 2, 3) if v is not None)
        uri = _data_uri(root, written, strict=False)
        return match.group(0) if uri is None else f'url("{uri}")'

    embedded = _CSS_URL.sub(embed, css)
    return None if embedded == css else embedded


def _srcset(root: Path, srcset: str) -> str | None:
    """``srcset`` with each local candidate embedded; None when it names no local file."""
    found = [(_data_uri(root, url), url, size) for url, size in _candidates(srcset)]
    if all(uri is None for uri, _, _ in found):
        return None
    return ", ".join(f"{uri or url} {size}".strip() for uri, url, size in found)


def _candidates(srcset: str) -> list[tuple[str, str]]:
    """``(url, descriptors)`` per candidate, split as a browser splits them: a URL runs to
    whitespace, so a ``data:`` URL keeps its comma."""
    found: list[tuple[str, str]] = []
    at = 0
    while (start := _skip_separators(srcset, at)) < len(srcset):
        end = start
        while end < len(srcset) and not srcset[end].isspace():
            end += 1
        url = srcset[start:end]
        if url.endswith(","):
            found.append((url.rstrip(","), ""))
            at = end
            continue
        comma = srcset.find(",", end)
        stop = len(srcset) if comma < 0 else comma
        found.append((url, srcset[end:stop].strip()))
        at = stop + 1
    return found


def _skip_separators(text: str, at: int) -> int:
    while at < len(text) and (text[at].isspace() or text[at] == ","):
        at += 1
    return at


def _data_uri(root: Path, src: str, *, strict: bool = True) -> str | None:
    """The file ``src`` names under ``root`` as a ``data:`` URI.

    None for a web or ``data:`` address, a ``#fragment`` or an empty one, and, unless
    ``strict``, for a file that is not a picture: each is left to the browser.
    """
    name = unquote(src).strip()
    if not name or name.startswith("#") or name.lower().startswith(_REMOTE):
        return None
    target = (root / name).resolve()
    if not target.is_relative_to(root):
        raise UnembeddableImage(src, "outside")
    mime = mimetypes.guess_type(target.name)[0] or ""
    if not mime.startswith("image/"):
        if not strict:
            return None
        raise UnembeddableImage(src, "not-image")
    try:
        data = target.read_bytes()
    except OSError:
        raise UnembeddableImage(src, "missing") from None
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"
