"""Alternative text and Office's decorative flag, on a shape's non-visual properties.

``descr`` is ECMA-376's own attribute on ``cNvPr``. The decorative flag is Office's
extension: ``adec:decorative`` from [MS-ODRAWXML] 5.32, inside ``cNvPr``'s ``a:extLst``.
"""

from __future__ import annotations

import re
from typing import Any

from lxml import etree
from pptx.oxml.ns import qn

DECORATIVE_NS = "http://schemas.microsoft.com/office/drawing/2017/decorative"
DECORATIVE_EXT = "{C183D7F6-B498-43B3-948B-1728B52AA6E4}"
_DECORATIVE = f"{{{DECORATIVE_NS}}}decorative"
_TRUE = ("1", "true")
# What python-pptx and several other writers put in `descr` when nobody wrote alt text.
_FILE_NAME = re.compile(r"[^\n]*\.(?:png|jpe?g|gif|bmp|tiff?|svg|emf|wmf|webp|heic)", re.IGNORECASE)


def describe(shape: Any, *, alt: str | None = None, decorative: bool = False) -> None:
    """Write ``alt`` as the shape's alternative text, or mark it decorative.

    Without ``alt`` any existing text is removed: python-pptx writes a picture's file name
    there, which a screen reader reads aloud as if it described the picture.
    """
    c_nv_pr = shape._element._nvXxPr.cNvPr
    if alt:
        c_nv_pr.set("descr", alt)
    else:
        c_nv_pr.attrib.pop("descr", None)
    if not decorative:
        return
    ext_lst = c_nv_pr.find(qn("a:extLst"))
    if ext_lst is None:
        ext_lst = etree.SubElement(c_nv_pr, qn("a:extLst"))
    ext = etree.SubElement(ext_lst, qn("a:ext"), uri=DECORATIVE_EXT)
    etree.SubElement(ext, _DECORATIVE, nsmap={"adec": DECORATIVE_NS}, val="1")


def described(shape: Any) -> tuple[str | None, bool]:
    """:func:`description` for a python-pptx shape proxy; nothing for one with no element."""
    c_nv_pr = getattr(getattr(getattr(shape, "_element", None), "_nvXxPr", None), "cNvPr", None)
    return (None, False) if c_nv_pr is None else description(c_nv_pr)


def description(c_nv_pr: Any) -> tuple[str | None, bool]:
    """A ``cNvPr`` element's alternative text, and whether it is marked decorative.

    A flag carrying no ``val`` counts as set: the element's presence is the mark.
    """
    alt = (c_nv_pr.get("descr") or "").strip() or None
    flags = c_nv_pr.iterfind(f"{qn('a:extLst')}/{qn('a:ext')}/{_DECORATIVE}")
    return alt, any(flag.get("val", "1").lower() in _TRUE for flag in flags)


def is_file_name(text: str) -> bool:
    """True for a description that is only an image's file name, not words about it."""
    return _FILE_NAME.fullmatch(text.strip()) is not None
