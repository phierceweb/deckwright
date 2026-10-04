"""Extract the text a rendered deck actually contains, and diff it against intent.

Config (env, read at call time, so ``.env`` changes take effect between runs):

- ``DECKWRIGHT_PDFTOTEXT``           — the pdftotext command (default ``pdftotext``).
- ``DECKWRIGHT_PDFTOTEXT_TIMEOUT_S`` — seconds before it is killed (default 60).
"""

from __future__ import annotations

import re
import subprocess
from functools import cached_property
from html import unescape
from pathlib import Path
from typing import Any

from pf_core.log import get_logger, log_exception
from pf_core.utils.env import resolve_int

from deckwright.errors import RenderError
from deckwright.compile.record import box_of
from deckwright.qa.model import Finding, Severity
from deckwright.utils.env import env_str

logger = get_logger(__name__)

_PDFTOTEXT_DEFAULT = "pdftotext"
_TIMEOUT_S_DEFAULT = 60
_PT_PER_IN = 72.0
# The renderer may set a glyph a hair past the box the shape was measured for.
_BOX_PAD_PT = 4
_WORD = re.compile(
    r'<word xMin="(-?[\d.]+)" yMin="(-?[\d.]+)" xMax="(-?[\d.]+)" yMax="(-?[\d.]+)">(.*?)</word>'
)

Word = tuple[float, float, float, float, str]
"""``(x0, y0, x1, y1, text)``: one word pdftotext found, in points from the page's top left."""


def _run_pdftotext(argv: list[str], pdf_path: Path, timeout_s: int) -> str:
    """pdftotext's stdout, decoded as UTF-8 whatever the platform locale is."""
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            check=True,
            timeout=timeout_s,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise RenderError(f"pdftotext failed on {pdf_path}", cause=e) from e
    return str(result.stdout)


def extract_pages(
    pdf_path: str | Path,
    *,
    layout: bool = False,
    pdftotext: str | None = None,
    timeout: int | None = None,
) -> list[str]:
    """Return the text of each page of ``pdf_path``, in order.

    Both extraction modes are returned because each splits lines the other keeps whole:
    reading order on wide tracking, ``-layout`` on whatever sits beside a wrapped line.

    Raises:
        RenderError: the PDF is missing, or pdftotext failed or timed out.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise RenderError(f"PDF not found: {pdf_path}")
    binary = env_str(pdftotext, "DECKWRIGHT_PDFTOTEXT", default=_PDFTOTEXT_DEFAULT)
    timeout_s = resolve_int(timeout, "DECKWRIGHT_PDFTOTEXT_TIMEOUT_S", default=_TIMEOUT_S_DEFAULT)
    argv = [binary, *(["-layout"] if layout else []), str(pdf_path), "-"]
    pages = _run_pdftotext(argv, pdf_path, timeout_s).split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    logger.info("pdf_text_extracted", pdf=str(pdf_path), pages=len(pages))
    return pages


def page_words(
    pdf_path: str | Path, *, pdftotext: str | None = None, timeout: int | None = None
) -> list[list[Word]]:
    """Every word of ``pdf_path``, page by page and in reading order, from one pdftotext run.

    Raises:
        RenderError: pdftotext failed or timed out.
    """
    binary = env_str(pdftotext, "DECKWRIGHT_PDFTOTEXT", default=_PDFTOTEXT_DEFAULT)
    timeout_s = resolve_int(timeout, "DECKWRIGHT_PDFTOTEXT_TIMEOUT_S", default=_TIMEOUT_S_DEFAULT)
    html = _run_pdftotext([binary, "-bbox", str(pdf_path), "-"], Path(pdf_path), timeout_s)
    return [
        [
            (float(x0), float(y0), float(x1), float(y1), unescape(text))
            for x0, y0, x1, y1, text in _WORD.findall(page)
        ]
        for page in html.split("<page ")[1:]
    ]


def text_within(words: list[Word], box: tuple[float, float, float, float]) -> str:
    """The text of ``words`` inside ``box`` — inches from the slide's top left.

    A glyph counts if any of it is inside, a line if its middle is. pdftotext gives words
    rather than glyphs, so each glyph takes an equal share of its word: exact in a monospace
    listing, close in anything else.
    """
    left, top, width, height = (v * _PT_PER_IN for v in box)
    x0, x1 = left - _BOX_PAD_PT, left + width + _BOX_PAD_PT
    y0, y1 = top - _BOX_PAD_PT, top + height + _BOX_PAD_PT
    kept = []
    for wx0, wy0, wx1, wy1, text in words:
        if not text or not y0 <= (wy0 + wy1) / 2 <= y1:
            continue
        step = (wx1 - wx0) / len(text)
        inside = "".join(
            ch for k, ch in enumerate(text) if wx0 + k * step < x1 and wx0 + (k + 1) * step > x0
        )
        if inside:
            kept.append(inside)
    return " ".join(kept)


def normalise(text: str) -> str:
    """Collapse whitespace and casefold, so layout differences do not read as loss."""
    return " ".join(text.split()).casefold()


def _matchable(text: str) -> str:
    """Fold *text* for containment: normalised, then spacing and hyphens dropped.

    pdftotext rebuilds a line the renderer wrapped at a hyphen two ways — reading
    order deletes the hyphen ("non-text" -> "nontext"), -layout keeps it with the
    row break beside it ("non- text"). Ignoring spacing and hyphens erases both.
    """
    return normalise(text).replace(" ", "").replace("-", "")


class _Boxes:
    """The text inside a shape's box, every page read from one ``pdftotext -bbox`` pass made
    the first time a box is asked for."""

    def __init__(self, pdf_path: str | Path) -> None:
        self._pdf_path = pdf_path

    @cached_property
    def _pages(self) -> list[list[Word]] | None:
        try:
            return page_words(self._pdf_path)
        except RenderError as e:
            log_exception(e, message_prepend="overflow word boxes failed", log_level="warning")
            return None

    def text(self, page: int, box: tuple[float, float, float, float]) -> str | None:
        """The matchable text inside ``box`` on 1-based ``page``, or ``None`` if the words
        could not be read."""
        pages = self._pages
        if pages is None or not 0 < page <= len(pages):
            return None
        return _matchable(text_within(pages[page - 1], box))


def check_overflow(
    manifest: dict[str, Any],
    pages: list[str],
    alt_pages: list[str] | None = None,
    *,
    pdf_path: str | Path | None = None,
) -> list[Finding]:
    """Flag recorded text that did not survive into the rendered page.

    Text is missing only if absent from *both* extractions (see :func:`extract_pages`).
    ``rendered="image"`` records are skipped: a PDF extractor cannot see text in a picture.
    Given *pdf_path*, a line the page does not hold is asked for inside the shape's own box,
    and a line on a ``plate`` inside the plate only; ``docs/qa.md`` has why.
    """
    slides = manifest.get("slides", [])
    if len(slides) != len(pages):
        return [
            Finding(
                slide=0,
                check="page-count",
                severity=Severity.ERROR,
                detail=f"manifest has {len(slides)} slide(s) but the render has {len(pages)} page(s)",
            )
        ]

    alt = alt_pages if alt_pages and len(alt_pages) == len(pages) else [""] * len(pages)
    findings: list[Finding] = []
    boxes = _Boxes(pdf_path) if pdf_path is not None else None
    for page_no, (slide, page, alt_page) in enumerate(zip(slides, pages, alt, strict=True), 1):
        haystack = _matchable(page)
        alt_haystack = _matchable(alt_page)
        for shape in slide.get("shapes", []):
            if shape.get("rendered", "native") != "native":
                continue
            box = box_of(shape)
            plate = boxes.text(page_no, box) if boxes and box and shape.get("plate") else None
            own: str | None = None
            lines = shape.get("lines") or ([shape["text"]] if shape.get("text") else [])
            for line in lines:
                needle = _matchable(str(line))
                if not needle:
                    continue
                if plate is not None:
                    if needle in plate:
                        continue
                elif needle in haystack or needle in alt_haystack:
                    continue
                elif boxes and box:
                    if own is None:
                        own = boxes.text(page_no, box) or ""
                    if needle in own:
                        continue
                where = "inside its plate" if plate is not None else "in the rendered slide"
                findings.append(
                    Finding(
                        slide=slide["index"],
                        check="overflow",
                        severity=Severity.ERROR,
                        detail=f"{str(line)[:70]!r} was not found {where}",
                        box=box,
                        shape=shape.get("name"),
                    )
                )
    return findings
